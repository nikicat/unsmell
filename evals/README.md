# Evals

These evals check that unsmell reaches a fixed point on its own. Running it
again on its own output must change nothing, and no round may undo an earlier
round. A skill that finds nothing would pass that test trivially, so the
fixtures also measure whether real smells get fixed.

## Running

```sh
evals/run.py evals/fixtures/*          # the tuning set
evals/run.py ~/src/unsmell-holdout/*   # the held-out set, to verify only
```

Each fixture runs in a throwaway git repo under `~/.cache/unsmell-eval/runs/`.
Every round invokes `/unsmell:unsmell fix everything` headless, with the skill
loaded from this checkout. The round trees are kept as `refs/rounds/N` in that
repo, so `git diff refs/rounds/1 refs/rounds/2` shows what round 2 changed.

The runs use their own Claude config in `~/.cache/unsmell-eval/config`. It has
no CLAUDE.md, hooks or plugins, so that only the skill steers the result. Link
your login into it once:

```sh
mkdir -p ~/.cache/unsmell-eval/config
ln -s ~/.claude/.credentials.json ~/.cache/unsmell-eval/config/
echo '{}' > ~/.cache/unsmell-eval/config/settings.json
```

## What passes

| Measure | Passes when |
| -- | -- |
| Convergence | a round changes nothing, within the round limit |
| Reversals | no round brings back a line that an earlier round removed |
| Check | the fixture's `check` command passes after every round |
| Stability | the above holds over repeated runs, since runs vary |

## Fixtures

A fixture is a directory with a `fixture.toml`. It always holds `check`, a shell
command that must pass after each round. The code under review comes from one of
two places:

- A real commit. `source` names a local repo and `commit` a commit in it. The
  run's HEAD is the commit's parent and its working tree is the commit, so the
  commit is the changeset. Only the two trees are copied, so the skill cannot
  read the later history that shows how the author went on.
- Trees in the fixture itself. `head/` is the working tree under review, and
  `base/` is the committed tree that it changes. Leave `base/` out when every
  file is new.

Two sets keep the tuning honest. The fixtures in this directory are the tuning
set: change the skill until they pass. The held-out set lives in a separate
private repo, and nobody reads it while changing the skill. A rule that only
helps the tuning set shows up as a held-out failure.

When a user rules on a conflict between two rules, the case becomes a tuning
fixture, so that the ruling stays settled.

## Changes and labels

Convergence alone does not say whether a change was worth making, so every
change that a run makes goes into a labelled dataset:

- `changes/<id>/change.patch` is the patch of one change. A dataset change is a
  skill change seen in one or more runs, keyed by its patch. `change.yaml`
  beside it records where the change was seen, the findings with their
  decisions, what the judge proposed, and the labels. A label is `good`, `bad`,
  `neutral` or `unsure`. It carries a note, and optionally the finding it is
  about. The id hashes the changed lines, whatever their whitespace, so a later
  run that makes the same change lands in the same directory and keeps its
  labels.
- `rounds/<run>/` holds each round's full patch and report, so that the tree a
  change was made on can be rebuilt from its fixture.

The loop:

```sh
evals/run.py --jobs 5 evals/fixtures/*          # 1. run the skill
evals/changes.py extract ~/.cache/unsmell-eval/runs/<run>...   # 2. split into changes
evals/changes.py check                          # 3. run each new change's fixture check
evals/changes.py judge                          # 4. propose labels for new changes
evals/changes.py next                           # 5. review one in the review repo, least certain first
evals/changes.py label ID bad -f b1-4 -n "says how, not what"
evals/changes.py score ~/.cache/unsmell-eval/runs/<run>...     # 6. count by label
```

`next` and `show ID` rebuild the fixture in the review repo. Its HEAD is the
fixture's base. The changeset under review, the earlier rounds and any changes
this one is stacked on are staged. The change itself is left unstaged, so
`git diff` in the printed directory shows exactly the change in its context. A
label from a person always wins over the judge's. A run that brings back a
change labelled `bad` is a regression, whatever its convergence; a `good` change
on the original code that a run no longer makes is a loss of recall.
