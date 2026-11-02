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
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import (
    Annotated,
    ClassVar,
    Literal,
    NamedTuple,
    NotRequired,
    Required,
    Self,
    TypedDict,
    TypeVar,
    cast,
    get_args,
)

import yaml
from pydantic import BaseModel, Field, SkipValidation, ValidationError
from run import CACHE, SKILL_MD, Fixture, Report, RunDir, RunRound, changed_lines, claude, git, positive_int

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
BOLD = "1"
DIM = "2"
TTY = sys.stdout.isatty() and "NO_COLOR" not in os.environ


class Painted(StrEnum):
    """A vocabulary that show paints, each member in its own color."""

    color: str  # the ANSI SGR code that show paints the member in

    def __new__(cls, value: str, color: str) -> Self:
        member = str.__new__(cls, value)
        member._value_, member.color = value, color
        return member


class Label(Painted):
    GOOD = "good", "32"
    BAD = "bad", "31"
    NEUTRAL = "neutral", "33"
    UNSURE = "unsure", "90"  # looked at, but cannot judge it


class Decision(Painted):
    """The bucket that the skill's triage puts a finding in."""

    FIX = "FIX", "32"
    ASK = "ASK", "33"
    KEEP = "KEEP", "35"
    PLAN = "PLAN", "36"
    SKIP = "SKIP", "90"
    DISCARD = "DISCARD", "90"


# The labels that the judge is told the meaning of, and so the ones it may answer and learn from.
JudgeLabel = Literal[Label.GOOD, Label.BAD, Label.NEUTRAL]
JUDGE_LABELS: frozenset[Label] = frozenset(get_args(JudgeLabel))


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


T = TypeVar("T")
# A field of change.yaml that is left out when it is empty.
Omittable = Annotated[T, Field(exclude_if=lambda v: not v)]
# Findings kept as read: validating them as Finding would drop and reorder the keys it does not list.
StoredFindings = Annotated[list[Finding], SkipValidation]


def paint(text: object, code: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if TTY else str(text)


def paint_term(term: Painted) -> str:
    """Returns a label or a decision in its color."""
    return paint(term, term.color)


def verdict_text(verdict: frozenset[Label]) -> str:
    """Returns a verdict as its labels joined by a plus, as in bad+good, or an empty string when it has none."""
    return "+".join(sorted(verdict))


def paint_verdict(verdict: frozenset[Label]) -> str:
    """Returns a verdict in its label's color.

    A verdict of several labels stays plain.
    """
    return paint_term(min(verdict)) if len(verdict) == 1 else verdict_text(verdict)


def load(path: Path) -> object:
    return yaml.safe_load(path.read_text())


def dump(path: Path, data: object) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100))


def read_patch(path: Path) -> str | None:
    """Returns the diff in a patch file.

    Returns None when the file is missing or blank, which means the editor made no patch.
    """
    text = path.read_text() if path.exists() else ""
    return text if text.strip() else None


def change_id(patch: str) -> str:
    """Returns the id of a patch.

    Two patches that change the same lines of the same files get the same id, whatever their whitespace.
    """
    lines: list[str] = []
    for diff in re.split(r"(?m)^(?=diff )", patch):
        lines += [h for h in diff.partition("\n@@")[0].splitlines() if h.startswith(("--- ", "+++ "))]
        lines += [sign + " ".join(line.text.split()) for sign, line in changed_lines(diff)]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:10]


class LocalChange(NamedTuple):
    """One change of a skill run, as its findings/*.yaml and decisions.yaml give it."""

    findings: list[Finding]  # each carries its decision entry under `triage`
    after: list[str]  # the ids that the skill run gave the changes it is stacked on


def changes(skill_run: Path) -> dict[str, LocalChange]:
    """Returns the changes of one skill run directory, keyed by the id that the skill run gave each."""
    findings = {
        f["id"]: f
        for p in sorted((skill_run / "findings").glob("*.yaml"))
        for f in (cast(FindingsFile | None, load(p)) or {}).get("findings") or []
    }
    by_change: dict[str, list[Finding]] = {}
    for d in cast(list[Triage] | None, load(skill_run / "decisions.yaml")) or []:
        if local_id := d.get("change") or d.get("task"):  # older runs wrote `task`
            by_change.setdefault(local_id, []).append({**findings.get(d["id"], {"id": d["id"]}), "triage": d})
    return {local_id: LocalChange(members, stacked_on(members)) for local_id, members in by_change.items()}


def stacked_on(members: list[Finding]) -> list[str]:
    """Returns the ids that the first `after` among a change's decisions names.

    `after` is a string such as "c1, c2" or a list of such strings.
    """
    after = next((a for f in members if (a := f["triage"].get("after"))), list[str]())
    return [i for value in ([after] if isinstance(after, str) else after) for i in re.findall(r"\w+", value)]


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

    def round(self, n: int) -> "StoredRound":
        """Returns the stored copy of round n of the run."""
        return StoredRound(self, n)


@dataclass(frozen=True)
class StoredRound:
    """The copy of one round of an eval run, which save_round writes and the review of its changes reads."""

    run: StoredRun
    n: int

    @property
    def patch(self) -> Path:
        """The path of the diff that the round made."""
        return self.run.path / f"round-{self.n}.patch"

    @property
    def report(self) -> Path:
        """The path of the skill's report on the round."""
        return self.run.path / f"round-{self.n}.md"

    @property
    def record(self) -> Path:
        """The path that holds the round's skill run directories (§3.0 of SKILL.md)."""
        return self.run.path / f"round-{self.n}"


class Seen(BaseModel):
    """A sighting of a change: the eval run and round in which the skill made it, and the id the skill run gave it."""

    run: str
    round: int
    change: str


class LabelEntry(BaseModel):
    """A label that the user gave to a change, or to one of its findings."""

    label: Label
    finding: Omittable[str | None] = None
    note: Omittable[str] = ""
    by: Omittable[str | None] = None  # written by older versions of label, and kept so that their files round-trip
    date: date


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


class Change(BaseModel):
    """A change that unsmell made in an eval run, stored in its own directory under CHANGES.

    It is the one way to read and write a change.yaml.
    """

    FILE: ClassVar[str] = "change.yaml"

    id: str
    fixture_name: str = Field(alias="fixture")
    seen: list[Seen]
    judge: Judgement | None = None
    labels: list[LabelEntry] = Field(default_factory=list[LabelEntry])
    findings: StoredFindings  # the findings and decisions of the first sighting, which the patch was made for
    after: Omittable[list[str]] = Field(default_factory=list[str])  # the ids of the changes it is stacked on
    check: Omittable[CheckStatus | None] = None

    @classmethod
    def load(cls, id: str) -> Self:
        """Returns the stored change with the given id.

        Errors when the change has no change.yaml, and with ValidationError when the file does not fit Change.
        """
        return cls.model_validate(load(CHANGES / id / cls.FILE))

    @classmethod
    def all(cls) -> list[Self]:
        """Returns every stored change, ordered by id."""
        return sorted((cls.load(p.parent.name) for p in CHANGES.glob(f"*/{cls.FILE}")), key=lambda c: c.id)

    def save(self) -> None:
        # The findings go in as read, so that the YAML anchors they share survive.
        dump(self.file, self.model_dump(mode="json", by_alias=True) | {"findings": self.findings})

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
    def patch(self) -> str | None:
        """The diff of the change, as read_patch reads it."""
        return read_patch(self.patch_file)

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
        return StoredRun.named(self.first.run).round(self.first.round).report

    @cached_property
    def fixture(self) -> Fixture:
        """The fixture the change was made on, read from FIXTURES."""
        return Fixture.load(FIXTURES / self.fixture_name)

    @property
    def decisions(self) -> str:
        """The decisions of the findings, joined as in FIX/ASK."""
        return "/".join(sorted({Decision(f["triage"]["decision"]) for f in self.findings}))

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
    def verdict(self) -> frozenset[Label]:
        """The labels that count, one per finding and one for the whole change. Empty when the change has none."""
        return frozenset(entry.label for entry in self.newest_labels)

    @property
    def notes(self) -> str:
        """The notes of the labels that make up the verdict, joined by semicolons."""
        return "; ".join(entry.note for entry in self.newest_labels if entry.note)

    @cached_property
    def tokens(self) -> set[str]:
        """The words of the changed lines and of the findings' claims."""
        texts = [line.text for _, line in changed_lines(patch)] if (patch := self.patch) is not None else []
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
        """Returns the k labelled changes most similar to this one, leaving this one out."""
        return [m.change for m in self.ranked([c for c in labelled if c.id != self.id])[:k]]

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
    return [
        cid for r in report.rounds for cid in save_round(run.round(r.round), out.round(r.round), report.fixture_name)
    ]


def save_round(rnd: RunRound, out: StoredRound, fixture_name: str) -> list[str]:
    """Stores the round in out, with each of its changes in CHANGES, and returns the changes' ids."""
    out.patch.write_text(rnd.patch())
    out.report.write_text(rnd.reply().result)
    ids: list[str] = []
    for skill_run in sorted(p.parent for p in rnd.record.glob("*/decisions.yaml")):
        shutil.copytree(
            skill_run,
            out.record / skill_run.name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("index", "worktrees", "target"),
        )
        found = changes(skill_run)
        saved = {
            local_id: save_change(
                skill_run, fixture_name, Seen(run=rnd.run.name, round=rnd.n, change=local_id), local.findings
            )
            for local_id, local in found.items()
        }
        link_stacked(saved, found)
        ids += [c.id for c in saved.values()]
    return ids


def save_change(skill_run: Path, fixture_name: str, seen: Seen, members: list[Finding]) -> Change:
    """Stores one change of a skill run directory in CHANGES, adding seen to its sightings, and returns it."""
    patch = read_patch(skill_run / "fixes" / f"{seen.change}.patch")
    cid = change_id(patch) if patch is not None else f"{seen.run}-{seen.round}-{seen.change}"
    try:
        change = Change.load(cid)
    except FileNotFoundError:
        change = Change(id=cid, fixture=fixture_name, seen=[], findings=members)
    if seen not in change.seen:
        change.seen.append(seen)
    change.dir.mkdir(parents=True, exist_ok=True)
    if not change.patch_file.exists():
        change.patch_file.write_text("" if patch is None else patch)
    change.save()
    return change


def link_stacked(saved: dict[str, Change], found: dict[str, LocalChange]) -> None:
    """Records on each stacked change of one skill run (SKILL.md §3.0, step 4) the changes it is reviewed on top of.

    saved and found map the id that the skill run gave each change to its stored Change and to its LocalChange.
    """
    for local_id, change in saved.items():
        if parents := [saved[p].id for p in found[local_id].after if p in saved]:
            change.after = parents
            change.save()


def judge_prompt(change: Change, examples: list[Change], skill: str) -> str:
    """Returns the prompt that asks the judge to label the change, showing it the labelled examples."""
    shown = "\n\n".join(
        f"### Example {o.id}: labelled {verdict_text(o.verdict)}\nNote: {o.notes}\n```diff\n{o.patch or ''}```"
        for o in examples
    )
    return (
        "You label one change that a refactoring skill made, as good (worth making), bad (should not "
        "have been made, or made worse code) or neutral. Judge the code, not the skill's own report. "
        "The skill's rules are below for reference; a change can follow them and still be bad.\n\n"
        f"## Labelled examples, most similar first\n\n{shown or '(none yet)'}\n\n"
        f"## The round's own report\n\n{change.report.read_text()[:6000]}\n\n"
        "## The findings and decisions the change was made for\n\n"
        f"{yaml.safe_dump(change.findings, allow_unicode=True)}\n\n"
        f"## The change to label\n\n```diff\n{change.patch or ''}```\n\n"
        f"## The skill\n\n{skill}"
    )


def judge(changes: list[Change], model: str, jobs: int) -> None:
    skill = SKILL_MD.read_text()
    stored = Change.all()
    labelled = [c for c in stored if len(c.verdict) == 1 and c.verdict <= JUDGE_LABELS]
    todo = changes or [c for c in stored if not c.judge and not c.verdict]

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
        git(build, "apply", "--binary", str(stored.round(n).patch))
        git(build, "add", "-A")
        git(build, "commit", "-q", "-m", f"round {n}")
    return build


class PatchDoesNotApply(Exception):
    """A change's patch, or the patch of a change it is stacked on, no longer applies."""


def review_repo(change: Change, repo: Path = REVIEW_REPO) -> Path:
    """Puts the change in repo as the skill saw it, and returns repo.

    HEAD is the fixture's base. The index holds the changeset under review, any earlier rounds, and the changes
    this one is stacked on. The working tree adds the change. The repo is reset on each call, never recreated, so
    an editor can keep it open across changes.

    Errors with PatchDoesNotApply when the change or a change it is stacked on no longer applies.
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
    try:
        for parent in change.ancestors():  # staged with the changeset, so git diff shows only what this change adds
            git(repo, "apply", "--index", str(Change.load(parent).patch_file))
        if change.patch is not None:
            git(repo, "apply", "--intent-to-add", str(change.patch_file))  # new files show up in git diff too
    except subprocess.CalledProcessError as e:
        raise PatchDoesNotApply(f"{e.cmd}\n{e.stderr}") from e
    return repo


def current() -> Change:
    """Returns the change in the review repo.

    Exits when no change is selected yet.
    """
    if not CURRENT.exists():
        sys.exit("no change selected yet: run next, or show ID")
    return Change.load(CURRENT.read_text().strip())


def select(change: Change) -> None:
    """Puts the change in the review repo and records it as the current one."""
    review_repo(change)
    CURRENT.write_text(change.id)


def show(change: Change) -> None:
    """Prints the change in the review repo."""
    print(
        paint(f"change {change.id}", BOLD) + f": {change.fixture_name} round {change.first.round}"
        f" (seen {len(change.seen)}x)"
    )
    if change.after:
        print(f"  stacked on {', '.join(change.after)}, staged with the changeset")
    for f in change.findings:
        t = f["triage"]
        decision = Decision(t["decision"])
        print(
            f"\n  {paint(f['id'], BOLD)}  {paint(f'{decision} {t.get("score")}', decision.color)}  {f.get('row', '')}"
            f"  {paint(', '.join(f.get('at', [])), DIM)}"
            f"\n    {paint('claim:', DIM)}  {f.get('claim', '').strip()}"
            f"\n    {paint('fix:', DIM)}    {f.get('fix', '').strip()}"
            f"\n    {paint('triage:', DIM)} {t.get('reason', '').strip()}"
        )
    if change.patch is None:
        print("\n  (no patch: the editor could not make this fix, see the triage reasons)")
    if match := change.prior():
        other = match.change
        print(
            f"\n  closest labelled change from an earlier run: {other.id}, {match.share:.0%} of words shared,"
            f" labelled {paint_verdict(other.verdict)}{': ' + other.notes if other.notes else ''}"
        )
    if change.judge:
        j = change.judge
        print(f"judge: {paint_term(j.label)} ({j.confidence:.2f}): {j.reason}")
    for entry in change.labels:
        about = f" on {entry.finding}" if entry.finding else ""
        print(f"label: {paint_term(entry.label)}{about}: {entry.note}")
    color = "--color=always" if TTY else "--color=never"
    print("\n" + git(REVIEW_REPO, "diff", color, "--stat").rstrip())
    staged = git(REVIEW_REPO, "diff", color, "--cached", "--stat").rstrip()
    print(f"\nStaged, the changeset under review (git diff --cached):\n{staged}")
    print(paint(f"\n  cd {REVIEW_REPO} && git diff        # the change", DIM))
    print(paint("  git diff --cached            # the changeset under review", DIM))
    print(paint(f"  report: {change.report}", DIM))
    print(paint(f"  labels: {change.file}", DIM))


def check(changes: list[Change]) -> None:
    """Runs the fixture check on the given changes, or on every unchecked one.

    Records ok, fail or no-apply in each change's change.yaml, with check.log on failure.
    """
    root = CACHE / "check"
    for change in changes or [c for c in Change.all() if c.check is None]:
        try:
            repo = review_repo(change, root / "repo")
        except PatchDoesNotApply as e:
            change.check, log = CheckStatus.NO_APPLY, str(e)
        else:
            out = change.fixture.run_check(repo)
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
        signs = [sign for sign, _ in changed_lines(patch)] if (patch := change.patch) is not None else []
        added, removed = signs.count("+"), signs.count("-")
        print(
            f"{change.id}  {verdict_text(change.verdict) or '-':7}  {change.fixture_name} r{change.first.round}"
            f"  {change.decisions:9}"
            f"  {f'+{added} -{removed}':>9}  {change.check or '-':4}  {' '.join(change.claim.split())[:80]}"
        )


def score(runs: list[RunDir]) -> None:
    for run in runs:
        counts = Counter(
            verdict_text(change.verdict) or (f"judge:{change.judge.label}" if change.judge else "unlabelled")
            for change in Change.all()
            if run.name in change.runs
        )
        print(run.name, " ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def next_change() -> None:
    """Selects and prints the unlabelled change whose judgement is least certain."""
    # A change without a patch (an editor that made none), or one that no longer applies, has nothing to review.
    todo = [c for c in Change.all() if not c.verdict and c.patch is not None and c.check != CheckStatus.NO_APPLY]
    if not todo:
        sys.exit("every change has a user label")
    # The least certain judgements first: they are where a label teaches the judge most.
    change = min(todo, key=lambda c: c.judge.confidence if c.judge else -1)
    select(change)
    show(change)
    print(paint(f"\n{len(todo)} unlabelled, this one included", BOLD))


def show_change(change: Change | None) -> None:
    """Prints the current change, selecting the given one first when there is one."""
    if change:
        select(change)
    show(current())


def label(change: Change, label: Label, finding: str | None, note: str) -> None:
    """Appends a label to a change's change.yaml."""
    if finding and finding not in {f["id"] for f in change.findings}:
        sys.exit(f"{change.id} has no finding {finding}")
    change.labels.append(LabelEntry(label=label, finding=finding, note=note, date=date.today()))
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

    def stored(id: str) -> Change:
        try:
            return Change.load(id)
        except FileNotFoundError:
            raise argparse.ArgumentTypeError(f"no change {id}") from None

    x = command("extract", "split each round of a run into changes", lambda a: extract_runs(a.runs))
    x.add_argument("runs", nargs="+", type=run_dir)
    j = command("judge", "propose a label for changes with none", lambda a: judge(a.changes, a.model, a.jobs))
    j.add_argument("changes", nargs="*", type=stored, metavar="ID")
    j.add_argument("--model", default="opus")
    j.add_argument("--jobs", type=positive_int, default=6)
    c = command(
        "check", "run the fixture's check on each change (a failure leaves check.log)", lambda a: check(a.changes)
    )
    c.add_argument("changes", nargs="*", type=stored, metavar="ID", help="default: every change not checked yet")
    command("list", "list every change with its label, unlabelled ones marked", lambda a: list_changes())
    command("next", "open the next change no human has labelled", lambda a: next_change())
    s = command(
        "show", "open a change in the review repo; no ID: print the current one", lambda a: show_change(a.change)
    )
    s.add_argument("change", nargs="?", type=stored, metavar="ID", help="default: the change in the review repo")
    lab = command("label", "label a change", lambda a: label(a.change or current(), a.label, a.finding, a.note))
    lab.add_argument("change", nargs="?", type=stored, metavar="ID", help="default: the change in the review repo")
    lab.add_argument("label", type=Label, choices=Label)
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
