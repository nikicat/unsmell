I've made a patch for every task. Nothing was merged into your working tree, as `patches only` asks: `git status` still shows only `?? evals/`, and your index is unchanged. Each patch was build-checked (`py_compile`). As a spot check, `evals/test_run.py` passes on the stacked result, but the full checks and the re-check pass were not run.

**How to apply them:** the tasks touch overlapping code, so most patches stack. Only t1, t2, t3 and t8 apply to your current tree.
- t4 applies on t3. t5 applies on t3 and t4. t6 applies on t5.
- t1 conflicts with t3–t5, so `t1-on-t5.patch` is t1 rebased onto them. I resolved the import conflicts by hand.
- t7 applies on t1–t5. t9 applies on t1 and t3–t8. t10 applies on t9.
- `all-fix.patch` is every FIX task combined against your current tree (1,154 changed lines), and test_run.py passes on it.

Patches are in `fixes/` in the run directory.

## Bugs fixed (in the patches)

- **A failed `claude` call counted as converged** (b1-3, t3). The eval runner ignored the exit status and `is_error`, so an expired login gave an empty round and a "converged" fixture. Now the round's error goes into `report.json` and the fixture is not converged.
- **Diff parser** (b1-8, t1):
  - Every deleted file was recorded under the path "ev/null", so deleting and then restoring a file never counted as a reversal.
  - Content lines starting with `++` or `--` were taken for file headers.
  - Paths shifted if you have `diff.noprefix` set.
  - test_run.py has new tests for all three.
- **`tokens` glued all the changed lines together** with no separator (b2-6, t1). This skewed the similarity scores.
- **`judge ID` showed the change its own label** as the first example in the prompt (b2-7, t7).
- **False docs:**
  - The README said a change is "one hunk" and mentioned a "category" field that doesn't exist (b1-11, t8).
  - The README said the earlier rounds in the review repo are commits, but they are staged (cross-7, t6).
  - `tasks()` claimed to yield 3-tuples (b2-12, t5).
  - The `worktree()` doc said it always uses the same directory (b2-16, t6).

## Patches

| Patch | Findings | What it does |
| -- | -- | -- |
| t1 | b1-8, b1-9, b1-10, b1-24, b2-6, b2-23, cross-5 | Diff reader in `run.py` that tracks file headers; `Line` NamedTuple; one `changed_lines` shared with changes.py. `change_id` gives identical ids on all 249 stored patches. |
| t2 | b1-16 | `clear()` unlinks a symlink to a directory instead of crashing in `rmtree`. |
| t3 | b1-3, b1-4, b2-19, cross-2 | One `claude()` function returning a `Reply`; errors on failure; a `SKILL` constant. |
| t4 | b1-1, b1-13, b1-14, b2-10, cross-1 | `Fixture.load`, `materialize` and `run_check`. A malformed fixture now errors up front instead of silently copying from the current directory. |
| t5 | b1-2, b1-5, b1-6, b1-7, b1-22, b1-23, b2-8, b2-9, b2-11–14, cross-3, cross-4 | `Round`/`Report`/`RunDir`/`Eval` in run.py; `Rounds`/`Task` in changes.py; `extract` split into named steps. `report.json` keeps its keys, and a round-trip test is added. |
| t6 | b2-15, b2-16, b2-17, cross-7 | `review_repo()` with three named steps; `show(rebuild)` split into `select` and `show`. |
| t7 | b2-5, b2-7, b2-20, b2-27 | Cached tokens and one `similarity`; a `Match` result; a `Judge` dataclass. |
| t8 | b1-11, b1-15, b2-29, cross-6 | README owns the dataset layout; changes.py's module doc says what the tool is for and points to it. |
| t9 | b2-2–4, b2-18, b2-21, b2-22, b2-24–26, b2-28, b2-30 | `Label`/`Decision`/`CheckStatus` enums; a shared `pending` selection; commands dispatched with `set_defaults(func=…)`; the hand-written Usage block is gone. |
| t10 | b2-1 (**ASK**) | A `Change` dataclass for `change.yaml`. The patch is the proposal. |

**Behaviour changes worth checking:**
- **t9:** the judge can no longer answer `unsure`, because that label means a person looked and couldn't judge.
- **t9:** `show` now raises an error on a decision or label string it doesn't know, where it used to print it uncoloured.
- **t10:** a load-and-save is byte-identical on 119 of the 120 `change.yaml` files. `1f4303c719` would get its `after` and `check` keys swapped once, into the order the other files use.

## Your decisions

- **b2-1 / t10:** do you want the `Change` dataclass? It rewrites most of changes.py.
- **e-1:** `Delta.between` should pass `--no-color --no-ext-diff`, or a `color.diff=always` setting corrupts the parse. I triaged this as PLAN, but the repo has no TODO.md or other plan file, so it's only recorded in `decisions.yaml`. Where should plans go?

**Skipped** (scored under the threshold of 5, each with a patch): b1-12, b1-17, b1-18, b1-19, b1-20, b1-21, b2-31, b2-32 and e-2. The b1-12 patch breaks changes.py on its own: eight `git(built, …)` calls there would need to become `built.git(…)`.

## Run notes

- The 65 findings and the 65 entries in `decisions.yaml` match one for one: 63 from the surveys and 2 that the t1 editor reported. None was discarded or kept.
- One editor made all eight SKIP patches, rather than one editor per task.
- Your untracked `evals/__pycache__/*.pyc` files ended up in the snapshot base. I removed them from every patch.

```
Survey   4 files read whole · 85 declarations inventoried · 0 locks inventoried, 0 oversized · 3 parameter tables, 3 shared context columns · 21 misplaced rules · 3 request-scoped values threaded · 35 inputs at the edge, 15 unparsed · 41 repeated literals, 24 repeated expressions, 7 facts stated twice · 36 functions split by role, 15 mixing roles, 0 pass-throughs · 38 doc items checked, 7 with an effect or exit missing, 4 leaking mechanism
```

Everything is in `/home/nb/src/unsmell/.git/unsmell/20261102-150632/`: the findings, `decisions.yaml` and `fixes/`.