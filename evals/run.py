#!/usr/bin/env python3
"""Runs unsmell on fixtures in a loop and reports whether it reaches a fixed point.

See evals/README.md for the fixture format and how a run is isolated.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, NotRequired, Self, TypedDict, cast

SKILL_REPO = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_REPO / "skills" / "unsmell" / "SKILL.md"
CACHE = Path.home() / ".cache" / "unsmell-eval"
CONFIG = CACHE / "config"
ALLOWED = [
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Agent",
    "TodoWrite",
    *(
        f"Bash({cmd}:*)"
        for cmd in [
            "git",
            "grep",
            "rg",
            "sed",
            "awk",
            "cat",
            "head",
            "tail",
            "wc",
            "ls",
            "find",
            "sort",
            "diff",
            "python",
            "python3",
            "uv",
        ]
    ),
]


def git(repo: Path, *args: str, env: Mapping[str, str] | None = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True, env=env).stdout


def snapshot(repo: Path) -> str:
    """Returns the git tree of the working directory, leaving the index and HEAD alone."""
    env = os.environ | {"GIT_INDEX_FILE": str(repo / ".git" / "eval-index")}
    git(repo, "add", "-A", env=env)
    return git(repo, "write-tree", env=env).strip()


class Line(NamedTuple):
    """A line of a diff and the path of its file."""

    path: str
    text: str


def changed_lines(patch: str) -> Iterator[tuple[str, Line]]:
    """Yields the sign ("+" or "-") and the Line of each line a git diff adds or removes.

    The lines of a deleted file carry its old path.
    """
    path, in_hunk = "", False  # git writes a file's ---/+++ header before its first hunk
    for line in patch.splitlines():
        if line.startswith("diff "):
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line.startswith(("+", "-")):
            yield line[0], Line(path, line[1:])
        elif line.startswith(("--- a/", "+++ b/")):
            path = line[6:]


@dataclass
class Delta:
    """The lines one round added and removed, each with its file."""

    added: set[Line] = field(default_factory=set[Line])
    removed: set[Line] = field(default_factory=set[Line])

    @classmethod
    def between(cls, repo: Path, old: str, new: str) -> Self:
        delta = cls()
        for sign, line in changed_lines(git(repo, "diff", "-U0", old, new)):
            text = line.text.strip()
            # ponytail: line-level heuristic; a moved line that changes nothing else counts too
            if len(text) > 3:
                (delta.added if sign == "+" else delta.removed).add(Line(line.path, text))
        return delta

    def empty(self) -> bool:
        return not (self.added or self.removed)

    def reversals(self, earlier: list["Delta"]) -> int:
        """Counts lines this round brings back after an earlier round removed them."""
        return len(self.added & set[Line]().union(*(d.removed for d in earlier)))

    def rework(self, earlier: list["Delta"]) -> int:
        """Counts lines this round removes after an earlier round added them."""
        return len(self.removed & set[Line]().union(*(d.added for d in earlier)))


def copy_tree(source: Path, rev: str, repo: Path) -> None:
    """Writes the files of source at rev into repo, without any of source's history."""
    archive = subprocess.run(["git", "-C", str(source), "archive", rev], check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(repo)], input=archive, check=True)


def commit_base(repo: Path) -> None:
    """Commits the working tree as the base, then empties it for the head."""
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    for item in repo.iterdir():
        if item.name != ".git":
            shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()


@dataclass(frozen=True)
class Commit:
    """A fixture origin that is a commit in another repo. The commit is the head, and its parent is the base."""

    source: Path
    rev: str


@dataclass(frozen=True)
class Trees:
    """A fixture origin that the fixture directory holds in head/ and, unless the base is empty, in base/."""

    base: Path | None
    head: Path


@dataclass(frozen=True)
class Fixture:
    """A changeset that the eval reviews, read from a fixture directory."""

    name: str
    check: str  # a shell command that must pass after every round
    origin: Commit | Trees

    @classmethod
    def load(cls, path: Path) -> Self:
        """Reads the fixture stored in the directory at path.

        Errors when fixture.toml has no check, names a commit without a source, or names neither a commit
        nor a head/ tree.
        """
        spec = tomllib.loads((path / "fixture.toml").read_text())
        if "check" not in spec:
            raise ValueError(f"{path}: fixture.toml has no check")
        match spec:
            case {"commit": rev, "source": source}:
                origin = Commit(Path(source).expanduser(), rev)
            case {"commit": _}:
                raise ValueError(f"{path}: fixture.toml names a commit but no source")
            case _ if (path / "head").is_dir():
                origin = Trees(path / "base" if (path / "base").is_dir() else None, path / "head")
            case _:
                raise ValueError(f"{path}: fixture.toml names no commit, and there is no head/")
        return cls(path.name, spec["check"], origin)

    def run_check(self, repo: Path, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Runs the fixture's check in repo and returns the finished process, with its output as text."""
        return subprocess.run(
            self.check, shell=True, cwd=repo, env=env, capture_output=True, text=True, errors="replace"
        )

    def materialize(self, repo: Path) -> None:
        """Creates a git repo at repo whose HEAD is the fixture's base and whose working tree is its head."""
        repo.mkdir(parents=True)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "eval@unsmell")
        git(repo, "config", "user.name", "unsmell eval")
        # The round commits are scratch state, so they must not trigger the user's signing setup.
        git(repo, "config", "commit.gpgsign", "false")
        match self.origin:
            case Commit(source, rev):
                copy_tree(source, f"{rev}^", repo)
                commit_base(repo)
                copy_tree(source, rev, repo)
            case Trees(base, head):
                if base:
                    shutil.copytree(base, repo, dirs_exist_ok=True)
                commit_base(repo)
                shutil.copytree(head, repo, dirs_exist_ok=True)


@dataclass(frozen=True)
class RunDir:
    """The directory of one eval run, which run.py fills and `changes.py extract` reads."""

    path: Path

    @classmethod
    def for_fixture(cls, fixture_name: str) -> Self:
        """Returns the directory for a new run of the named fixture."""
        return cls(CACHE / "runs" / f"{fixture_name}-{datetime.now():%Y%m%d-%H%M%S}")

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def repo(self) -> Path:
        return self.path / "repo"

    @property
    def report(self) -> Path:
        return self.path / "report.json"

    def log(self, n: int) -> Path:
        """Returns the path of round n's claude output."""
        return self.path / f"round-{n}.json"

    def reply(self, n: int) -> "Reply":
        """Returns round n's claude reply.

        Errors when its output is not JSON.
        """
        return Reply.parse(self.log(n).read_text())

    def record(self, n: int) -> Path:
        """Returns the path that holds round n's skill run directories (§3.0 of SKILL.md)."""
        return self.path / f"round-{n}"

    def keep_record(self, n: int) -> None:
        """Moves the skill's record of round n, if it left one, out of the repo to record(n)."""
        record = self.repo / ".git" / "unsmell"
        if record.exists():
            shutil.move(record, self.record(n))
            git(self.repo, "worktree", "prune")  # editors' worktrees the skill left behind

    def stamp_skill_hash(self) -> None:
        """Records which skill text the rounds ran, so that their changes can be traced to it."""
        (self.path / "skill.sha256").write_text(hashlib.sha256(SKILL_MD.read_bytes()).hexdigest())

    def skill_hash(self) -> str:
        """Returns the hash of the skill text the rounds ran, or "unknown" for a run that did not record it."""
        stamp = self.path / "skill.sha256"
        return stamp.read_text().strip() if stamp.exists() else "unknown"

    def tag_round(self, n: int, tree: str) -> None:
        """Keeps tree as round n's result, at refs/rounds/n in the repo."""
        commit = git(self.repo, "commit-tree", tree, "-m", f"round {n}").strip()
        git(self.repo, "update-ref", f"refs/rounds/{n}", commit)

    def round_patch(self, n: int) -> str:
        """Returns the binary diff of what round n changed."""
        return git(self.repo, "diff", "--binary", f"refs/rounds/{n - 1}", f"refs/rounds/{n}")


@dataclass
class Round:
    """One round's row in report.json. Reports from early runs lack some fields, which load as zero."""

    round: int
    cost_usd: float = 0.0
    added: int = 0
    removed: int = 0
    reversals: int = 0
    rework: int = 0
    check: bool = False
    tree: str = ""

    def __str__(self) -> str:
        return (
            f"round {self.round}: +{self.added} -{self.removed} reversals={self.reversals} "
            f"rework={self.rework} check={'ok' if self.check else 'FAIL'} ${self.cost_usd:.2f}"
        )


class RoundRow(TypedDict):
    """A round as stored in report.json. Rows from early runs lack the fields after round."""

    round: int
    cost_usd: NotRequired[float]
    added: NotRequired[int]
    removed: NotRequired[int]
    reversals: NotRequired[int]
    rework: NotRequired[int]
    check: NotRequired[bool]
    tree: NotRequired[str]


class ReportFile(TypedDict):
    """A report.json as stored. Reports from older runs also hold `workdir`, which is ignored."""

    fixture: str
    rounds: list[RoundRow]


@dataclass
class Report:
    """The outcome of one eval run, kept as report.json in its run directory."""

    run: RunDir  # where the report lives; not stored in it
    fixture_name: str
    rounds: list[Round] = field(default_factory=list[Round])

    @property
    def converged(self) -> bool:
        return self.rounds[-1].added == self.rounds[-1].removed == 0

    @property
    def oscillated(self) -> bool:
        return any(r.reversals for r in self.rounds)

    @classmethod
    def load(cls, run: RunDir) -> Self:
        """Reads the run's report.json."""
        data = cast(ReportFile, json.loads(run.report.read_text()))
        return cls(run, data["fixture"], [Round(**r) for r in data["rounds"]])

    def save(self) -> None:
        data = {
            "fixture": self.fixture_name,
            "rounds": [asdict(r) for r in self.rounds],
            "converged": self.converged,
            "oscillated": self.oscillated,
        }
        self.run.report.write_text(json.dumps(data, indent=2))

    def __str__(self) -> str:
        return (
            f"{self.fixture_name}: {'converged' if self.converged else 'did not converge'} in "
            f"{len(self.rounds)} rounds, {'oscillated' if self.oscillated else 'no reversals'}. {self.run.path}"
        )


class ReplyFile(TypedDict, total=False):
    """The fields of claude's JSON stdout that Reply reads."""

    result: str
    structured_output: dict[str, object]
    total_cost_usd: float
    is_error: bool


@dataclass(frozen=True)
class Reply:
    """The JSON reply of one headless claude call."""

    result: str
    structured: dict[str, object] | None  # the reply under --json-schema
    cost_usd: float
    is_error: bool = False

    @classmethod
    def parse(cls, text: str) -> Self:
        """Reads a reply from claude's JSON stdout.

        Errors when text is not JSON.
        """
        data = cast(ReplyFile, json.loads(text))
        return cls(
            data.get("result", ""),
            data.get("structured_output"),
            data.get("total_cost_usd", 0.0),
            data.get("is_error", False),
        )


def claude(*args: str, prompt: str | None = None, cwd: Path | None = None, log: Path | None = None) -> Reply:
    """Runs headless claude under the eval config and returns its reply.

    Args:
        args: Flags and the prompt argument, after `-p --output-format json`.
        prompt: Text to send on stdin. Without it, stdin is closed.
        log: File that gets stdout. Stderr goes beside it as .stderr when there is any.

    Errors when claude exits non-zero, its stdout is not JSON, or the reply has is_error.
    """
    out = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--no-session-persistence", *args],
        input=prompt,
        stdin=None if prompt else subprocess.DEVNULL,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=os.environ | {"CLAUDE_CONFIG_DIR": str(CONFIG)},
    )
    if log:
        log.write_text(out.stdout)
        if out.stderr:
            log.with_suffix(".stderr").write_text(out.stderr)
    try:
        reply = Reply.parse(out.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"claude exited {out.returncode} without JSON: {(out.stderr.strip() or out.stdout)[:200]}"
        ) from None
    if out.returncode or reply.is_error:
        raise RuntimeError(f"claude exited {out.returncode}: {(reply.result or out.stderr.strip())[:200]}")
    return reply


def run_skill(run: RunDir, n: int, args: str) -> float:
    """Runs round n of the skill on the run's repo and returns its cost in USD.

    Errors as claude does.
    """
    return claude(
        f"/unsmell:unsmell {args}".strip(),
        "--plugin-dir",
        str(SKILL_REPO),
        "--permission-mode",
        "auto",
        "--permission-prompts",
        "none",
        # No --max-budget-usd: the agent sees the cap and skips the survey agents to stay under it.
        "--allowedTools",
        *ALLOWED,
        cwd=run.repo,
        log=run.log(n),
    ).cost_usd


def evaluate(fixture: Fixture, rounds: int, args: str) -> Report:
    run = RunDir.for_fixture(fixture.name)
    fixture.materialize(run.repo)
    run.stamp_skill_hash()
    trees, report = [snapshot(run.repo)], Report(run, fixture.name)
    deltas: list[Delta] = []
    run.tag_round(0, trees[0])
    for n in range(1, rounds + 1):
        cost = run_skill(run, n, args)
        run.keep_record(n)
        trees.append(snapshot(run.repo))
        delta = Delta.between(run.repo, trees[-2], trees[-1])
        report.rounds.append(
            Round(
                round=n,
                cost_usd=cost,
                added=len(delta.added),
                removed=len(delta.removed),
                reversals=delta.reversals(deltas),
                rework=delta.rework(deltas),
                check=fixture.run_check(run.repo).returncode == 0,
                tree=trees[-1],
            )
        )
        run.tag_round(n, trees[-1])
        print(f"{fixture.name} {report.rounds[-1]}", flush=True)
        if delta.empty():
            break
        deltas.append(delta)
    report.save()
    return report


def positive_int(text: str) -> int:
    if (n := int(text)) < 1:
        raise argparse.ArgumentTypeError(f"{text} is below 1")
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fixtures", nargs="+", type=Path)
    parser.add_argument("--rounds", type=positive_int, default=4, help="most rounds per fixture")
    parser.add_argument("--args", default="fix everything", help="the arguments each round passes to the skill")
    parser.add_argument("--jobs", type=positive_int, default=4, help="fixtures run at once")
    args = parser.parse_args()
    if not (CONFIG / ".credentials.json").exists():
        sys.exit(f"{CONFIG} has no .credentials.json. Link it to your Claude login first, see evals/README.md.")
    fixtures = [Fixture.load(f.resolve()) for f in args.fixtures]
    with ThreadPoolExecutor(args.jobs) as pool:
        runs = [(f, pool.submit(evaluate, f, args.rounds, args.args)) for f in fixtures]
    for fixture, run in runs:
        print(f"{fixture.name}: failed: {e}" if (e := run.exception()) else run.result())
    sys.exit(any(run.exception() for _, run in runs))


if __name__ == "__main__":
    main()
