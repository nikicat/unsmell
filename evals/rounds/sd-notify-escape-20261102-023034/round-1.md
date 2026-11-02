I ran the run in patches-only mode, so nothing was merged. Your working tree still has only your two modified files, and every task has a patch in the run directory. Each patch was build-checked in its own worktree. The full check and the re-check pass did not run, because they come after a merge.

**The patch to look at first: `t1`, the only one that would have been applied.** Your escaping fix wraps about a dozen interpolation sites by hand with `esc := html.EscapeString`. Nothing forces the next new site to escape. `t1` moves the escaping into a small type, `bodyMarkup` in the new file `markup.go`. Its `text`, `bold`, `italic` and `processChain` methods escape what they are given, so raw `<b>`/`<i>` tags appear only inside it. The editor compared the output before and after over 4,032 input combinations, and it was identical.

`t1` also does three smaller things:
- **Duplicate subject text:** the subject (one item label, "N items", the search attributes, or "all") was written twice, once in bold and once in italics. It is now one `requestSubject` function.
- **Comments:** the 6-line `esc` comment and the two closure comments that opened with their own names are gone.
- **Test:** the regression test is now a table of 8 cases covering every branch you escaped, not only the GPG one. Its doc no longer cites "Vuln 7", which nothing in the repo defines.

**A real bug your change doesn't cover:** `formatSlowUpstreamBody` in `internal/notification/slow_upstream.go` writes item labels, paths and process names into the same kind of markup body without escaping them. Its own comment says it matches `desktop.go`. Patch `t2` (stacked on `t1`) fixes it and adds a test that failed before the fix. Output for safe input is unchanged. I didn't treat it as a straight fix because that file isn't in your changeset, so it's your call.

**What each patch does:**

| Patch | Decision | What it does |
| -- | -- | -- |
| `t1` | Fix | escaping type, one subject function, wider test (above) |
| `t2` | Your call, stacked on `t1` | escapes the slow-upstream body (bug fix) |
| `t3` | Plan, stacked on `t1` | splits `formatBody` into one function per body kind; adds 11 whole-body tests |
| `t4` | Plan | deletes the test helpers `contains`/`stringContains` in favour of `strings.Contains` |
| `t5` | Plan | the reconnect-and-retry-once block, written three times, becomes one `withReconnect` method |
| `t6` | Plan | typed constants for the action keys (`"approve"`, `"deny"`, …) |
| `t7` | Plan | one constant, `approval.AttrSSHDestination`, for the `"destination"` key; touches three packages |
| `t8` | Plan | `notificationMeta` never used its receiver; it becomes a free function of the request type |
| `t9` | Plan | rewrites about 27 doc comments in `desktop.go`/`desktop_test.go` that open with their own name |
| `t10` | Plan | a `Message{Summary, Body, Icon}` struct for the `Notifier` interface; changes that interface |
| `plan.patch` | — | adds these Plan entries to `TODO.md` under "Unsmell run 20261102-023043"; I didn't edit `TODO.md` |

All patches except `t2` and `t3` apply cleanly to your current working tree. `t2` and `t3` need `t1` applied first.

**Docs I rewrote** after the editors finished:
- `t1`, `processChain`: "Appends the process names on a new line, joined by arrows. When showPIDs is set, each name is followed by its PID in brackets."
- `t1`, `requestSubject`: "Returns the plain text that names what req asks for. For a get, delete or write request it is the item label, or "N items" unless there is exactly one item. For a search it is the attributes as "k=v, k=v", or "all" when there are none. Reports false for every other request type."
- `t6`, the action-key type: "The identifier of a notification button. It is sent in the actions list and comes back in the ActionInvoked signal."
- `t7`, `AttrSSHDestination`: "The ItemInfo.Attributes key that holds the host an ssh_sign request connects to."
- `t10`, `Message`: "The text and icon of one desktop notification."

**How the run went:**
- **Survey:** 2 files read whole, 19 declarations, 5 locks (none oversized), 2 shared parameters (one is summary/body/icon travelling together), 3 misplaced rules, 14 inputs from outside (2 used raw), 9 repeated literals, 6 repeated expressions, 3 facts stated twice. 4 changed functions checked by role; only `formatBody` mixed roles, and there were no pure pass-throughs.
- **Findings:** 15, all with a decision (6 fix, 1 your call, 8 plan; none kept, skipped or discarded). Nothing is left open. The changeset was one batch, so the cross-file pass had nothing to compare.
- **Checks:** every patch passed its build and test-compile check, and the notification tests passed for each. Linters and the full test suite were not run.

Everything is in `.git/unsmell/20261102-023043/`: the findings, the decisions in `decisions.yaml`, and the patches under `fixes/`.