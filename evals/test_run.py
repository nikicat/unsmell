#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic"]
# ///
"""Checks the round diffing of run.py on a scratch repo. Run: evals/test_run.py"""

import tempfile
from pathlib import Path

from run import CACHE, Delta, git, snapshot


def new_repo(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-q")
    return path


def test_reversal(root: Path) -> None:
    repo = new_repo(root / "edit")
    f = repo / "a.py"
    f.write_text("x = compute_once()\n")
    t0 = snapshot(repo)
    f.write_text("x = compute_twice()\n")
    t1 = snapshot(repo)
    f.write_text("x = compute_once()\n")
    t2 = snapshot(repo)
    first, second = Delta.between(repo, t0, t1), Delta.between(repo, t1, t2)
    assert first.reversals([]) == 0
    assert second.reversals([first]) == 1, second
    assert second.rework([first]) == 1, second
    assert Delta.between(repo, t2, snapshot(repo)).empty()
    assert git(repo, "status", "--porcelain") == "?? a.py\n", "snapshot must not stage"


def test_delete_then_restore(root: Path) -> None:
    repo = new_repo(root / "delete")
    f = repo / "a.py"
    f.write_text("x = compute_once()\n")
    t0 = snapshot(repo)
    f.unlink()
    t1 = snapshot(repo)
    f.write_text("x = compute_once()\n")
    t2 = snapshot(repo)
    first, second = Delta.between(repo, t0, t1), Delta.between(repo, t1, t2)
    assert second.reversals([first]) == 1, second


if __name__ == "__main__":
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=CACHE) as root:
        test_reversal(Path(root))
        test_delete_then_restore(Path(root))
    print("ok")
