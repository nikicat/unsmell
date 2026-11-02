# Editor brief (unsmell run 20261102-150632)

You are an editor agent for one task of an /unsmell run on the repo /home/nb/src/unsmell.
Read §5 and §6 of /home/nb/src/unsmell/skills/unsmell/SKILL.md, and the §4 catalog.

- Work ONLY inside your worktree (path given in your prompt). Never touch /home/nb/src/unsmell itself,
  its index, or other worktrees. Do not commit; leave changes in the working tree.
- Your task's findings are in the run directory: findings/b1.yaml, findings/b2.yaml, findings/cross.yaml;
  their final decisions and task ids are in decisions.yaml. Where a decision's reason differs from the
  finding's own, the decision wins.
- Scope of the run: evals/run.py, evals/changes.py, evals/test_run.py, evals/README.md. These are
  untracked in the real repo, so every line counts as changed. Edit other files only if a finding says so.
- Make each fix in the final shape the findings name. No residue (no alias locals, no half of the old shape).
  Behaviour-preserving unless the finding is a bug; say what behaviour changed.
- Style ground truth: no repo style docs or linter config. Python 3.12 idioms (dataclass, NamedTuple,
  StrEnum, match, pathlib). Docs: plain English, short sentences, verb first for functions, noun phrase
  for types and fields, never open with the item's own name, "Errors when …" for the error contract,
  no colon or semicolon joining two ideas, no narration of the body.
- Persisted formats must not change: change.yaml / meta.yaml / report.json keys stay the same, and
  change_id must return the same id for the same patch (ids key the stored dataset in evals/changes/).
- Build check, the only check you run: `python3 -m py_compile evals/run.py evals/changes.py evals/test_run.py`
  in your worktree. Do not run the test suite, linters or the evals.
- Before you finish, read your own `git diff` against the §4 catalog and fix any smell your change added.
- Reply with: what you changed per finding id, any behaviour change, any finding you could not do as
  described and why, and the build check result.
