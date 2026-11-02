#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic", "pyyaml"]
# ///
"""The dataset of changes that unsmell made in eval runs, and their labels.

See evals/README.md for the dataset layout and the review loop.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import ClassVar, Literal, NamedTuple, NotRequired, Required, Self, TypedDict, cast, get_args

import yaml
from pydantic import BaseModel, Field, ValidationError
from run import CACHE, SKILL_MD, Fixture, Report, RunDir, changed_lines, claude, git, positive_int

EVALS = Path(__file__).resolve().parent
CHANGES = EVALS / "changes"
FIXTURES = EVALS / "fixtures"
ROUNDS = EVALS / "rounds"
REVIEW = CACHE / "review"
# The repo that select puts the current change in, and that show prints.
REVIEW_REPO = REVIEW / "repo"
# The id of the change in the review repo, which show and label use when given none.
CURRENT = REVIEW / "current"
# The least similarity at which prior offers a labelled change as a precedent.
MIN_SIMILARITY = 1 / 3
# ANSI SGR codes for show's output; NO_COLOR or a pipe turns them off.
COLORS = {"FIX": "32", "ASK": "33", "PLAN": "36", "KEEP": "35", "SKIP": "90", "DISCARD": "90"}
TTY = sys.stdout.isatty() and "NO_COLOR" not in os.environ


class Label(StrEnum):
    color: str  # the ANSI SGR code that show paints the label in

    GOOD = "good", "32"
    BAD = "bad", "31"
    NEUTRAL = "neutral", "33"
    UNSURE = "unsure", "90"  # looked at, but cannot judge it

    def __new__(cls, value: str, color: str) -> Self:
        member = str.__new__(cls, value)
        member._value_, member.color = value, color
        return member


# The labels that the judge is told the meaning of, and so the ones it may answer and learn from.
JudgeLabel = Literal[Label.GOOD, Label.BAD, Label.NEUTRAL]
JUDGE_LABELS: tuple[Label, ...] = get_args(JudgeLabel)


class CheckStatus(StrEnum):
    OK = "ok"
    FAIL = "fail"
    NO_APPLY = "no-apply"


class Triage(TypedDict):
    """A decision entry in a skill run's decisions.yaml. Only the fields that changes.py reads are listed."""

    id: str
    decision: str
    score: NotRequired[int]
    reason: NotRequired[str]
    change: NotRequired[str]
    task: NotRequired[str]  # what older runs wrote for `change`
    after: NotRequired[str | list[str]]  # the ids of the changes it is stacked on, as "c1, c2" or a list


class RawFinding(TypedDict, total=False):
    """A finding in a skill run's findings/*.yaml. Only the fields that changes.py reads are listed."""

    id: Required[str]
    at: list[str]
    row: str
    claim: str
    fix: str


class Finding(RawFinding):
    """A finding joined with its decision entry."""

    triage: Triage


class FindingsFile(TypedDict, total=False):
    """A findings/*.yaml of a skill run."""

    findings: list[RawFinding] | None


class SeenRow(TypedDict):
    """A sighting as stored in change.yaml."""

    run: str
    round: int
    change: str


class LabelRow(TypedDict):
    """A label entry as stored in change.yaml."""

    label: str
    finding: NotRequired[str]
    note: NotRequired[str]
    by: NotRequired[str]
    date: str


class ChangeFile(TypedDict):
    """A change.yaml as stored."""

    id: str
    fixture: str
    seen: list[SeenRow]
    judge: dict[str, object] | None  # Judgement's fields, which it validates
    labels: list[LabelRow]
    findings: list[Finding]
    after: NotRequired[list[str]]
    check: NotRequired[str]


def paint(text: object, code: str | None) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if TTY and code else str(text)


def paint_label(text: str | None) -> str:
    """Returns a label or a verdict in the label's color.

    A verdict that joins several labels stays plain.
    """
    return paint(text, Label(text).color if text in Label else None)


def load(path: Path) -> object:
    return yaml.safe_load(path.read_text())


def dump(path: Path, data: object) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100))


def change_id(patch: str) -> str:
    """Returns the id of a patch.

    Two patches that change the same lines of the same files get the same id, whatever their whitespace.
    """
    lines: list[str] = []
    for diff in re.split(r"(?m)^(?=diff )", patch):
        lines += [h for h in diff.partition("\n@@")[0].splitlines() if h.startswith(("--- ", "+++ "))]
        lines += [sign + " ".join(line.text.split()) for sign, line in changed_lines(diff)]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:10]


def changes(skill_run: Path) -> dict[str, list[Finding]]:
    """Returns the findings of one skill run directory, keyed by the id that the skill run gave each change.

    Each finding carries its decision entry under `triage`.
    """
    findings = {
        f["id"]: f
        for p in sorted((skill_run / "findings").glob("*.yaml"))
        for f in (cast(FindingsFile | None, load(p)) or {}).get("findings") or []
    }
    by_change: dict[str, list[Finding]] = {}
    for d in cast(list[Triage] | None, load(skill_run / "decisions.yaml")) or []:
        if local_id := d.get("change") or d.get("task"):  # older runs wrote `task`
            by_change.setdefault(local_id, []).append({**findings.get(d["id"], {"id": d["id"]}), "triage": d})
    return by_change


def parse_after(value: str | list[str] | None) -> list[str]:
    """Returns the ids that a decision's `after` names, as the skill run gave them.

    `after` is a string such as "c1, c2" or a list.
    """
    return re.findall(r"\w+", value) if isinstance(value, str) else value or []


@dataclass(frozen=True)
class StoredRun:
    """The copy of one eval run under ROUNDS, which extract writes and the review of its changes reads."""

    path: Path

    @classmethod
    def named(cls, name: str) -> Self:
        """Returns the stored copy of the run with the given name."""
        return cls(ROUNDS / name)

    @property
    def meta(self) -> Path:
        return self.path / "meta.yaml"

    def patch(self, n: int) -> Path:
        """Returns the path of the diff that round n made."""
        return self.path / f"round-{n}.patch"

    def report(self, n: int) -> Path:
        """Returns the path of the skill's report on round n."""
        return self.path / f"round-{n}.md"

    def record(self, n: int) -> Path:
        """Returns the path that holds round n's skill run directories (§3.0 of SKILL.md)."""
        return self.path / f"round-{n}"


@dataclass
class Seen:
    """A sighting of a change: the eval run and round in which the skill made it, and the id the skill run gave it."""

    run: str
    round: int
    change: str


@dataclass(kw_only=True)
class LabelEntry:
    """A label that the user gave to a change, or to one of its findings."""

    label: Label
    finding: str | None = None
    note: str = ""
    by: str | None = None  # written by older versions of label, and kept so that their files round-trip
    date: str

    def to_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in vars(self).items() if v}


class JudgeReply(BaseModel, frozen=True):
    """The reply that the judge model must give."""

    label: JudgeLabel
    confidence: float = Field(ge=0, le=1)
    reason: str


class Judgement(JudgeReply, frozen=True):
    """The label that the judge model proposed for a change. A user's label on the change takes precedence over it."""

    model: str


class Match(NamedTuple):
    """A change, and the share of words it has in common with the change it was compared with."""

    change: "Change"
    share: float


@dataclass
class Change:
    """A change that unsmell made in an eval run, stored in its own directory under CHANGES.

    It is the one way to read and write a change.yaml.
    """

    FILE: ClassVar[str] = "change.yaml"

    id: str
    fixture_name: str
    seen: list[Seen]
    findings: list[Finding]  # the findings and decisions of the first sighting, which the patch was made for
    labels: list[LabelEntry] = field(default_factory=list[LabelEntry])
    judge: Judgement | None = None
    after: list[str] = field(default_factory=list[str])  # the ids of the changes it is stacked on
    check: CheckStatus | None = None

    @classmethod
    def load(cls, id: str) -> Self:
        """Returns the stored change with the given id.

        Errors when the change has no change.yaml.
        """
        d = cast(ChangeFile, load(CHANGES / id / cls.FILE))
        return cls(
            id=d["id"],
            fixture_name=d["fixture"],
            seen=[Seen(**s) for s in d["seen"]],
            findings=d["findings"],
            labels=[
                LabelEntry(
                    label=Label(row["label"]),
                    finding=row.get("finding"),
                    note=row.get("note", ""),
                    by=row.get("by"),
                    date=row["date"],
                )
                for row in d["labels"]
            ],
            judge=Judgement.model_validate(d["judge"]) if d["judge"] else None,
            after=d.get("after", []),
            check=CheckStatus(d["check"]) if "check" in d else None,
        )

    @classmethod
    def all(cls) -> list[Self]:
        """Returns every stored change, ordered by id."""
        return sorted((cls.load(p.parent.name) for p in CHANGES.glob(f"*/{cls.FILE}")), key=lambda c: c.id)

    def save(self) -> None:
        data: dict[str, object] = {
            "id": self.id,
            "fixture": self.fixture_name,
            "seen": [asdict(s) for s in self.seen],
            "judge": self.judge and self.judge.model_dump(mode="json"),
            "labels": [entry.to_dict() for entry in self.labels],
            "findings": self.findings,
        }
        if self.after:
            data["after"] = self.after
        if self.check:
            data["check"] = str(self.check)
        dump(self.file, data)

    @property
    def dir(self) -> Path:
        return CHANGES / self.id

    @property
    def file(self) -> Path:
        return self.dir / self.FILE

    @property
    def patch_file(self) -> Path:
        return self.dir / "change.patch"

    @property
    def patch(self) -> str:
        """The diff of the change, empty when the editor made none."""
        return self.patch_file.read_text()

    @property
    def log_file(self) -> Path:
        """The path of the fixture check's output, kept when the check failed."""
        return self.dir / "check.log"

    @property
    def first(self) -> Seen:
        """The first sighting, which the patch was made for."""
        return self.seen[0]

    @property
    def runs(self) -> set[str]:
        return {s.run for s in self.seen}

    @property
    def report(self) -> Path:
        """The path of the skill's report on the round of the first sighting."""
        return StoredRun.named(self.first.run).report(self.first.round)

    @cached_property
    def fixture(self) -> Fixture:
        """The fixture the change was made on, read from FIXTURES."""
        return Fixture.load(FIXTURES / self.fixture_name)

    @property
    def decisions(self) -> str:
        """The decisions of the findings, joined as in FIX/ASK."""
        return "/".join(sorted({f["triage"]["decision"] for f in self.findings}))

    @property
    def claim(self) -> str:
        """The claim of the first finding."""
        return self.findings[0].get("claim", "")

    @property
    def summary(self) -> str:
        return f"{self.decisions}: {self.claim[:100]}"

    @property
    def newest_labels(self) -> list[LabelEntry]:
        """The newest label entry of each finding and of the whole change."""
        return list({entry.finding: entry for entry in self.labels}.values())

    @property
    def verdict(self) -> str | None:
        """The label that counts, or None when the change has none.

        Each finding's newest label counts, and so does the newest label on the whole change. When these labels
        differ, the result joins them, as in good+bad.
        """
        return "+".join(sorted({entry.label for entry in self.newest_labels})) or None

    @property
    def notes(self) -> str:
        """The notes of the labels that make up the verdict, joined by semicolons."""
        return "; ".join(entry.note for entry in self.newest_labels if entry.note)

    @cached_property
    def tokens(self) -> set[str]:
        """The words of the changed lines and of the findings' claims."""
        texts = [line.text for _, line in changed_lines(self.patch)]
        texts += [f.get("claim", "") for f in self.findings]
        return set(re.findall(r"\w+", "\n".join(texts)))

    def similarity(self, other: "Change") -> float:
        """Returns the share of the words in either change that both have."""
        return len(self.tokens & other.tokens) / (len(self.tokens | other.tokens) or 1)

    def ranked(self, others: Iterable["Change"]) -> list[Match]:
        """Returns a Match for each of the others, the most similar first."""
        return sorted((Match(c, self.similarity(c)) for c in others), key=lambda m: m.share, reverse=True)

    def prior(self) -> Match | None:
        """Returns the Match of the most similar user-labelled change of the same fixture from another run.

        Returns None when no change reaches MIN_SIMILARITY.
        """
        others = [
            c
            for c in Change.all()
            if c.fixture_name == self.fixture_name and c.id != self.id and not self.runs & c.runs and c.verdict
        ]
        return next((m for m in self.ranked(others)[:1] if m.share >= MIN_SIMILARITY), None)

    def neighbours(self, labelled: list["Change"], k: int = 5) -> list["Change"]:
        """Returns the k labelled changes most similar to this one."""
        return [m.change for m in self.ranked(labelled)[:k]]

    def ancestors(self) -> list[str]:
        """Returns the ids of the changes that this one is stacked on, directly or not, each before its dependents."""
        order: list[str] = []
        for parent in self.after:
            for cid in [*Change.load(parent).ancestors(), parent]:
                if cid not in order:
                    order.append(cid)
        return order


def extract(run: RunDir) -> list[str]:
    """Stores the rounds of one run and returns the ids of the changes in them."""
    report = Report.load(run)
    out = StoredRun.named(run.name)
    out.path.mkdir(parents=True, exist_ok=True)
    dump(out.meta, {"fixture": report.fixture_name, "skill": run.skill_hash(), "rounds": len(report.rounds)})
    return [cid for r in report.rounds for cid in save_round(run, r.round, report.fixture_name, out)]


def save_round(run: RunDir, n: int, fixture_name: str, out: StoredRun) -> list[str]:
    """Stores round n of run in out, with each of its changes in CHANGES, and returns the changes' ids."""
    out.patch(n).write_text(run.round_patch(n))
    out.report(n).write_text(run.reply(n).result)
    ids: list[str] = []
    for skill_run in sorted(p.parent for p in run.record(n).glob("*/decisions.yaml")):
        shutil.copytree(
            skill_run,
            out.record(n) / skill_run.name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("index", "worktrees", "target"),
        )
        found = changes(skill_run)
        saved = {
            local_id: save_change(skill_run, fixture_name, Seen(run.name, n, local_id), members)
            for local_id, members in found.items()
        }
        link_stacked(saved, found)
        ids += [c.id for c in saved.values()]
    return ids


def save_change(skill_run: Path, fixture_name: str, seen: Seen, members: list[Finding]) -> Change:
    """Stores one change of a skill run directory in CHANGES, adding seen to its sightings, and returns it."""
    patch_file = skill_run / "fixes" / f"{seen.change}.patch"
    patch = patch_file.read_text() if patch_file.exists() else ""
    cid = change_id(patch) if patch.strip() else f"{seen.run}-{seen.round}-{seen.change}"
    try:
        change = Change.load(cid)
    except FileNotFoundError:
        change = Change(cid, fixture_name, seen=[], findings=members)
    if seen not in change.seen:
        change.seen.append(seen)
    change.dir.mkdir(parents=True, exist_ok=True)
    if not change.patch_file.exists():
        change.patch_file.write_text(patch)
    change.save()
    return change


def link_stacked(saved: dict[str, Change], found: dict[str, list[Finding]]) -> None:
    """Records on each stacked change of one skill run (SKILL.md §3.0, step 4) the changes it is reviewed on top of.

    saved and found map the id that the skill run gave each change to its stored Change and to its findings.
    """
    for local_id, change in saved.items():
        after = next((after for f in found[local_id] if (after := f["triage"].get("after"))), None)
        if parents := [saved[p].id for p in parse_after(after) if p in saved]:
            change.after = parents
            change.save()


def judge_prompt(change: Change, examples: list[Change], skill: str) -> str:
    """Returns the prompt that asks the judge to label the change, showing it the labelled examples."""
    shown = "\n\n".join(
        f"### Example {o.id}: labelled {o.verdict}\nNote: {o.notes}\n```diff\n{o.patch}```" for o in examples
    )
    return (
        "You label one change that a refactoring skill made, as good (worth making), bad (should not "
        "have been made, or made worse code) or neutral. Judge the code, not the skill's own report. "
        "The skill's rules are below for reference; a change can follow them and still be bad.\n\n"
        f"## Labelled examples, most similar first\n\n{shown or '(none yet)'}\n\n"
        f"## The round's own report\n\n{change.report.read_text()[:6000]}\n\n"
        "## The findings and decisions the change was made for\n\n"
        f"{yaml.safe_dump(change.findings, allow_unicode=True)}\n\n"
        f"## The change to label\n\n```diff\n{change.patch}```\n\n"
        f"## The skill\n\n{skill}"
    )


def judge(ids: list[str], model: str, jobs: int) -> None:
    skill = SKILL_MD.read_text()
    stored = Change.all()
    labelled = [c for c in stored if c.verdict in JUDGE_LABELS]
    todo = [c for c in stored if (c.id in ids if ids else not c.judge and not c.verdict)]

    def one(change: Change) -> float:
        prompt = judge_prompt(change, change.neighbours(labelled), skill)
        try:
            reply = claude(
                "--json-schema",
                json.dumps(JudgeReply.model_json_schema()),
                "--tools",
                "",
                "--model",
                model,
                prompt=prompt,
            )
            judged = (
                JudgeReply.model_validate(reply.structured)
                if reply.structured
                else JudgeReply.model_validate_json(reply.result)
            )
        except (RuntimeError, ValidationError) as e:
            print(f"{change.id}: judge failed: {e}", file=sys.stderr)
            return 0.0
        change.judge = Judgement(**dict(judged), model=model)
        change.save()
        print(f"{change.id} {change.judge.label:7} {change.judge.confidence:.2f} {change.summary}", flush=True)
        return reply.cost_usd

    with ThreadPoolExecutor(jobs) as pool:
        cost = sum(pool.map(one, todo))
    print(f"judged {len(todo)} changes for ${cost:.2f}")


def build_rounds(fixture: Fixture, stored: StoredRun, upto: int, build: Path) -> Path:
    """Builds the fixture and the stored run's rounds before upto as commits in a new repo at build, and returns it.

    The tag base marks the fixture's base, and the tag round-0 marks the fixture's head.
    """
    if build.exists():
        shutil.rmtree(build)
    fixture.materialize(build)
    git(build, "tag", "base")  # HEAD is the fixture's base: round-0 minus the changeset under review
    git(build, "add", "-A")
    git(build, "commit", "-q", "-m", "fixture head (round 0)")
    git(build, "tag", "round-0")
    for n in range(1, upto):
        git(build, "apply", "--binary", str(stored.patch(n)))
        git(build, "add", "-A")
        git(build, "commit", "-q", "-m", f"round {n}")
    return build


def review_repo(change: Change, repo: Path = REVIEW_REPO) -> Path:
    """Puts the change in repo as the skill saw it, and returns repo.

    HEAD is the fixture's base. The index holds the changeset under review, any earlier rounds, and the changes
    this one is stacked on. The working tree adds the change. The repo is reset on each call, never recreated, so
    an editor can keep it open across changes.
    """
    build = build_rounds(change.fixture, StoredRun.named(change.first.run), change.first.round, repo.parent / "build")
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True)
        git(repo, "init", "-q")
    git(
        repo,
        "fetch",
        "-q",
        "--force",
        str(build),
        "HEAD",
        "+refs/tags/base:refs/tags/base",
        "+refs/tags/round-0:refs/tags/round-0",
    )
    git(repo, "reset", "-q", "--hard")
    # Build output stays: an editor's language server may be writing into it, and it is its cache.
    git(repo, "clean", "-q", "-fdx", "-e", "target/", "-e", "node_modules/", "-e", ".venv/")
    git(repo, "checkout", "-q", "-f", "--detach", "FETCH_HEAD")
    git(repo, "reset", "-q", "--soft", "base")
    shutil.rmtree(build)
    for parent in change.ancestors():  # staged with the changeset, so that git diff shows only what this change adds
        git(repo, "apply", "--index", str(Change.load(parent).patch_file))
    if change.patch.strip():
        git(repo, "apply", "--intent-to-add", str(change.patch_file))  # new files show up in git diff too
    return repo


def current() -> str:
    if not CURRENT.exists():
        sys.exit("no change selected yet: run next, or show ID")
    return CURRENT.read_text().strip()


def select(change: Change) -> None:
    """Puts the change in the review repo and records it as the current one."""
    review_repo(change)
    CURRENT.write_text(change.id)


def show(change: Change) -> None:
    """Prints the change in the review repo."""
    print(
        paint(f"change {change.id}", "1") + f": {change.fixture_name} round {change.first.round}"
        f" (seen {len(change.seen)}x)"
    )
    if change.after:
        print(f"  stacked on {', '.join(change.after)}, staged with the changeset")
    for f in change.findings:
        t = f["triage"]
        decision = paint(f"{t['decision']} {t.get('score')}", COLORS.get(t["decision"]))
        print(
            f"\n  {paint(f['id'], '1')}  {decision}  {f.get('row', '')}  {paint(', '.join(f.get('at', [])), '2')}"
            f"\n    {paint('claim:', '2')}  {f.get('claim', '').strip()}"
            f"\n    {paint('fix:', '2')}    {f.get('fix', '').strip()}"
            f"\n    {paint('triage:', '2')} {t.get('reason', '').strip()}"
        )
    if not change.patch.strip():
        print("\n  (no patch: the editor could not make this fix, see the triage reasons)")
    if match := change.prior():
        other = match.change
        print(
            f"\n  closest labelled change from an earlier run: {other.id}, {match.share:.0%} of words shared,"
            f" labelled {paint_label(other.verdict)}{': ' + other.notes if other.notes else ''}"
        )
    if change.judge:
        j = change.judge
        print(f"judge: {paint_label(j.label)} ({j.confidence:.2f}): {j.reason}")
    for entry in change.labels:
        about = f" on {entry.finding}" if entry.finding else ""
        print(f"label: {paint_label(entry.label)}{about}: {entry.note}")
    color = "--color=always" if TTY else "--color=never"
    print("\n" + git(REVIEW_REPO, "diff", color, "--stat").rstrip())
    staged = git(REVIEW_REPO, "diff", color, "--cached", "--stat").rstrip()
    print(f"\nStaged, the changeset under review (git diff --cached):\n{staged}")
    print(paint(f"\n  cd {REVIEW_REPO} && git diff        # the change", "2"))
    print(paint("  git diff --cached            # the changeset under review", "2"))
    print(paint(f"  report: {change.report}", "2"))
    print(paint(f"  labels: {change.file}", "2"))


def check(ids: list[str]) -> None:
    """Runs the fixture check on the given changes, or on every unchecked one.

    Records ok, fail or no-apply in each change's change.yaml, with check.log on failure.
    """
    root = CACHE / "check"
    env = os.environ | {"CARGO_TARGET_DIR": str(root / "target")}
    todo = [c for c in Change.all() if (c.id in ids if ids else c.check is None)]
    for change in todo:
        try:
            repo = review_repo(change, root / "repo")
        except subprocess.CalledProcessError as e:
            change.check, log = CheckStatus.NO_APPLY, f"{e.cmd}\n{e.stderr}"
        else:
            out = change.fixture.run_check(repo, env)
            change.check, log = (
                (CheckStatus.FAIL, out.stdout + out.stderr) if out.returncode else (CheckStatus.OK, None)
            )
        change.save()
        print(f"{change.id} {change.check}", flush=True)
        if log is None:
            change.log_file.unlink(missing_ok=True)
        else:
            change.log_file.write_text(log)


def list_changes() -> None:
    """Prints one line per change, grouped by fixture.

    Each line shows the change's verdict, its decisions, its size, its check status and its first claim.
    """
    for change in sorted(Change.all(), key=lambda c: (c.fixture_name, c.first.round, c.first.change)):
        signs = [sign for sign, _ in changed_lines(change.patch)]
        added, removed = signs.count("+"), signs.count("-")
        print(
            f"{change.id}  {change.verdict or '-':7}  {change.fixture_name} r{change.first.round}  {change.decisions:9}"
            f"  {f'+{added} -{removed}':>9}  {change.check or '-':4}  {' '.join(change.claim.split())[:80]}"
        )


def score(runs: list[RunDir]) -> None:
    for run in runs:
        counts = Counter(
            change.verdict or (f"judge:{change.judge.label}" if change.judge else "unlabelled")
            for change in Change.all()
            if run.name in change.runs
        )
        print(run.name, " ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def next_change() -> None:
    """Selects and prints the unlabelled change whose judgement is least certain."""
    # A change without a patch (an editor that made none), or one that no longer applies, has nothing to review.
    todo = [c for c in Change.all() if not c.verdict and c.patch.strip() and c.check != CheckStatus.NO_APPLY]
    if not todo:
        sys.exit("every change has a user label")
    # The least certain judgements first: they are where a label teaches the judge most.
    change = min(todo, key=lambda c: c.judge.confidence if c.judge else -1)
    select(change)
    show(change)
    print(paint(f"\n{len(todo)} unlabelled, this one included", "1"))


def show_change(id: str | None) -> None:
    """Prints the current change, selecting the one with the given ID first when there is one."""
    if id:
        select(Change.load(id))
    show(Change.load(current()))


def label(id: str, label: Label, finding: str | None, note: str) -> None:
    """Appends a label to a change's change.yaml."""
    change = Change.load(id)
    if finding and finding not in {f["id"] for f in change.findings}:
        sys.exit(f"{change.id} has no finding {finding}")
    change.labels.append(LabelEntry(label=label, finding=finding, note=note, date=date.today().isoformat()))
    change.save()
    print(f"{change.id}: {label}")


def extract_runs(runs: list[RunDir]) -> None:
    """Extracts the changes of each run and prints how many each has."""
    for run in runs:
        print(f"{run.name}: {len(set(extract(run)))} changes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def command(name: str, help: str, run: Callable[[argparse.Namespace], None]) -> argparse.ArgumentParser:
        parser = sub.add_parser(name, help=help)
        parser.set_defaults(run=run)
        return parser

    def run_dir(path: str) -> RunDir:
        return RunDir(Path(path).resolve())

    x = command("extract", "split each round of a run into changes", lambda a: extract_runs(a.runs))
    x.add_argument("runs", nargs="+", type=run_dir)
    j = command("judge", "propose a label for changes with none", lambda a: judge(a.ids, a.model, a.jobs))
    j.add_argument("ids", nargs="*")
    j.add_argument("--model", default="opus")
    j.add_argument("--jobs", type=positive_int, default=6)
    c = command("check", "run the fixture's check on each change (a failure leaves check.log)", lambda a: check(a.ids))
    c.add_argument("ids", nargs="*", help="default: every change not checked yet")
    command("list", "list every change with its label, unlabelled ones marked", lambda a: list_changes())
    command("next", "open the next change no human has labelled", lambda a: next_change())
    s = command("show", "open a change in the review repo; no ID: print the current one", lambda a: show_change(a.id))
    s.add_argument("id", nargs="?", help="default: the change in the review repo")
    lab = command("label", "label a change", lambda a: label(a.id or current(), Label(a.label), a.finding, a.note))
    lab.add_argument("id", nargs="?", help="default: the change in the review repo")
    lab.add_argument("label", choices=Label)
    lab.add_argument(
        "-f", "--finding", help="the finding of the change that the label is about; the whole change when left out"
    )
    lab.add_argument("-n", "--note", default="", help="why: what is good or wrong about it")
    r = command("score", "count a run's changes by label", lambda a: score(a.runs))
    r.add_argument("runs", nargs="+", type=run_dir)
    a = p.parse_args()
    a.run(a)


if __name__ == "__main__":
    main()
