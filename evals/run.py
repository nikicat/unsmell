#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic"]
# ///
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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Annotated, NamedTuple, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    DirectoryPath,
    Discriminator,
    Field,
    Tag,
    ValidationError,
    computed_field,
)

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


class Commit(BaseModel, frozen=True):
    """A fixture origin that is a commit in another repo. The commit is the head, and its parent is the base."""

    source: Annotated[Path, AfterValidator(Path.expanduser)]
    rev: str = Field(alias="commit")


class Trees(BaseModel, frozen=True):
    """A fixture origin that the fixture directory holds in head/ and, unless the base is empty, in base/."""

    base: DirectoryPath | None
    head: DirectoryPath


def origin_kind(spec: object) -> str:
    """Returns "commit" when the fixture.toml data names a commit, and "trees" otherwise."""
    return "commit" if isinstance(spec, dict) and "commit" in spec else "trees"


class Fixture(BaseModel, frozen=True):
    """A changeset that the eval reviews, read from a fixture directory."""

    name: str
    check: str  # a shell command that must pass after every round
    origin: Annotated[Annotated[Commit, Tag("commit")] | Annotated[Trees, Tag("trees")], Discriminator(origin_kind)]

    @classmethod
    def load(cls, path: Path) -> Self:
        """Reads the fixture stored in the directory at path.

        Errors when fixture.toml has no check, names a commit without a source, or names no commit while there
        is no head/.
        """
        spec = tomllib.loads((path / "fixture.toml").read_text())
        trees = {"head": path / "head", "base": base if (base := path / "base").is_dir() else None}
        try:
            return cls.model_validate({**spec, "name": path.name, "origin": spec | trees})
        except ValidationError as e:
            raise ValueError(f"{path}: fixture.toml is invalid: {e}") from None

    def run_check(self, repo: Path) -> subprocess.CompletedProcess[str]:
        """Runs the fixture's check in repo and returns the finished process, with its output as text."""
        return subprocess.run(self.check, shell=True, cwd=repo, capture_output=True, text=True, errors="replace")

    def materialize(self, repo: Path) -> None:
        """Creates a git repo at repo whose HEAD is the fixture's base and whose working tree is its head."""
        repo.mkdir(parents=True)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "eval@unsmell")
        git(repo, "config", "user.name", "unsmell eval")
        # The round commits are scratch state, so they must not trigger the user's signing setup.
        git(repo, "config", "commit.gpgsign", "false")
        match self.origin:
            case Commit(source=source, rev=rev):
                copy_tree(source, f"{rev}^", repo)
                commit_base(repo)
                copy_tree(source, rev, repo)
            case Trees(base=base, head=head):
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

    def round(self, n: int) -> "RunRound":
        """Returns round n of the run, counting the fixture's head as round 0."""
        return RunRound(self, n)

    def stamp_skill_hash(self) -> None:
        """Records which skill text the rounds ran, so that their changes can be traced to it."""
        (self.path / "skill.sha256").write_text(hashlib.sha256(SKILL_MD.read_bytes()).hexdigest())

    def skill_hash(self) -> str:
        """Returns the hash of the skill text the rounds ran, or "unknown" for a run that did not record it."""
        stamp = self.path / "skill.sha256"
        return stamp.read_text().strip() if stamp.exists() else "unknown"


@dataclass(frozen=True)
class RunRound:
    """One round of an eval run: what run.py keeps of it in the run directory, and its tree in the run's repo."""

    run: RunDir
    n: int

    @property
    def log(self) -> Path:
        """The path of the round's claude output."""
        return self.run.path / f"round-{self.n}.json"

    def reply(self) -> "Reply":
        """Returns the round's claude reply.

        Errors with ValidationError when its output is not claude's JSON reply.
        """
        return Reply.model_validate_json(self.log.read_text())

    @property
    def record(self) -> Path:
        """The path that holds the round's skill run directories (§3.0 of SKILL.md)."""
        return self.run.path / f"round-{self.n}"

    def keep_record(self) -> None:
        """Moves the skill's record of the round, if it left one, out of the repo to record."""
        record = self.run.repo / ".git" / "unsmell"
        if record.exists():
            shutil.move(record, self.record)
            git(self.run.repo, "worktree", "prune")  # editors' worktrees the skill left behind

    def tag(self, tree: str) -> None:
        """Keeps tree as the round's result, at refs/rounds/n in the repo."""
        commit = git(self.run.repo, "commit-tree", tree, "-m", f"round {self.n}").strip()
        git(self.run.repo, "update-ref", f"refs/rounds/{self.n}", commit)

    def patch(self) -> str:
        """Returns the binary diff of what the round changed."""
        return git(self.run.repo, "diff", "--binary", f"refs/rounds/{self.n - 1}", f"refs/rounds/{self.n}")


class Round(BaseModel):
    """One round's row in report.json. Rows from early runs lack the fields after round, which load as zero."""

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


class Report(BaseModel):
    """The outcome of one eval run, kept as report.json in its run directory.

    Reports from older runs also hold `workdir`, which is ignored.
    """

    run: RunDir = Field(exclude=True)  # where the report lives; not stored in it
    fixture_name: str = Field(alias="fixture")
    rounds: list[Round] = Field(default_factory=list[Round])
    # The exception that stopped the run, or None when no round raised.
    error: str | None = None

    @computed_field
    @property
    def converged(self) -> bool:
        return self.error is None and bool(self.rounds) and self.rounds[-1].added == self.rounds[-1].removed == 0

    @computed_field
    @property
    def oscillated(self) -> bool:
        return any(r.reversals for r in self.rounds)

    @classmethod
    def load(cls, run: RunDir) -> Self:
        """Reads the run's report.json.

        Errors with ValidationError when it does not hold a report.
        """
        return cls.model_validate(json.loads(run.report.read_text()) | {"run": run})

    def save(self) -> None:
        self.run.report.write_text(self.model_dump_json(by_alias=True, indent=2, exclude_none=True))

    def __str__(self) -> str:
        return (
            f"{self.fixture_name}: {'converged' if self.converged else 'did not converge'} in "
            f"{len(self.rounds)} rounds, {'oscillated' if self.oscillated else 'no reversals'}. {self.run.path}"
        )


class Reply(BaseModel, frozen=True):
    """The JSON reply of one headless claude call."""

    result: str = ""
    structured: dict[str, object] | None = Field(None, alias="structured_output")  # the reply under --json-schema
    cost_usd: float = Field(0.0, alias="total_cost_usd")
    is_error: bool = False


def claude(*args: str, prompt: str | None = None, cwd: Path | None = None, log: Path | None = None) -> Reply:
    """Runs headless claude under the eval config and returns its reply.

    Args:
        args: Flags and the prompt argument, after `-p --output-format json`.
        prompt: Text to send on stdin. Without it, stdin is closed.
        log: File that gets stdout. Stderr goes beside it as .stderr when there is any.

    Errors when claude exits non-zero, its stdout is not a JSON reply, or the reply has is_error.
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
        reply = Reply.model_validate_json(out.stdout)
    except ValidationError:
        raise RuntimeError(
            f"claude exited {out.returncode} without a JSON reply: {(out.stderr.strip() or out.stdout)[:200]}"
        ) from None
    if out.returncode or reply.is_error:
        raise RuntimeError(f"claude exited {out.returncode}: {(reply.result or out.stderr.strip())[:200]}")
    return reply


def run_skill(rnd: RunRound, args: str) -> float:
    """Runs the skill on the run's repo as the given round and returns its cost in USD.

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
        cwd=rnd.run.repo,
        log=rnd.log,
    ).cost_usd


def evaluate(fixture: Fixture, rounds: int, args: str) -> Report:
    """Runs the skill on the fixture for at most `rounds` rounds and returns the report.

    Errors with the exception of a round that fails. The report is saved first, with the error in it.
    """
    run = RunDir.for_fixture(fixture.name)
    fixture.materialize(run.repo)
    run.stamp_skill_hash()
    trees, report = [snapshot(run.repo)], Report(run=run, fixture=fixture.name)
    deltas: list[Delta] = []
    run.round(0).tag(trees[0])
    try:
        for n in range(1, rounds + 1):
            rnd = run.round(n)
            cost = run_skill(rnd, args)
            rnd.keep_record()
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
            rnd.tag(trees[-1])
            print(f"{fixture.name} {report.rounds[-1]}", flush=True)
            if delta.empty():
                break
            deltas.append(delta)
    except Exception as e:
        report.error = f"{type(e).__name__}: {e}"
        raise
    finally:
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
