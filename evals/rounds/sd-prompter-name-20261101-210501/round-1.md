I've made six patches and left your working tree alone, as you asked ("patches only"). Nothing was applied, no re-check ran, and I asked no questions. All six worktrees are removed.

**Survey:** 2 files read whole · 33 declarations inventoried · 13 lock lines, 1 oversized (the `active`/`closed` guard and the lock in `activate`, which only served the watch goroutine you removed) · 13 parameter-table rows, 0 shared context columns · 7 placement lines, 0 misplaced rules · 0 request-scoped values threaded · 6 inputs at the edge, 1 unparsed · 9 literal lines, 7 expression lines, 2 facts stated several times · 14 functions split by role · about 20 doc items checked, 2 with an exit or outcome missing. One survey batch, plus one cross-file pass that added 1 finding.

**Patches** (in `fixes/`, all made from the same snapshot of your working tree):

| Task | Decision | What it does | Checks |
|---|---|---|---|
| `t1` | FIX | Deletes the dead `active`/`closed` fields, their guard and the lock in `activate`. Fixes the fallback docs that contradicted each other. Each repeated fact now has one owner. Rewrites the docs below and renames the test to `TestPrompterBridgeClaimsNameBeforeFrontPrompter`. Touches `prompter.go`, `prompter_test.go`, `forward.go` and `proxy.go`. | gofmt, vet and tests pass |
| `t3` | FIX | Fixes two lines in `TestPrompterBridge` that described the front-bus guard you removed and were no longer true. | gofmt, vet pass |
| `t2` | ASK | The alternative to t1's code part: folds `activate` into `newPrompterBridge`, which returns nil when it loses the claim, and removes `owned` as well. | gofmt, vet and tests pass |
| `t4` | ASK | `BeginPrompting` now unexports its callback proxy when forwarding fails, with a new test that pins this. | gofmt, vet and tests pass |
| `t5` | preview (PLAN/SKIP) | Deletes the unused `prompterCallback.logger`, adds an `unexportLocked` helper, types `systemPrompterPath` as `dbus.ObjectPath`, and stops older docs from opening with their own names. | gofmt, vet, build and tests pass |
| `t6` | preview (PLAN) | Adds shared test fixture helpers and a generic `recvWithin[T]`. One timeout message changes wording. | gofmt, vet and tests pass |

Things to know before applying them:
- **t1 and t2 are alternatives.** Both rework `activate` and `close`, so apply one of them.
- **t6 will conflict with t1**, because t6 still uses the old test name. It needs redoing by hand after t1.
- **t1 overrules the survey on one point.** The old docs said the gcr-prompter fallback is display-less and hangs. Your new text says it draws its own GTK dialog. I took your new text as the true one and fixed the old copies, including the ones in `forward.go` and `proxy.go`.
- **t4's claim only partly held.** An unowned front name gets D-Bus-activated to the real `gcr-prompter` wherever gcr is installed, so prompts don't always fail outside GNOME. Two consequences:
  - The patch's doc line "Errors when no front prompter owns …" overstates this. It should read "Errors when the front prompter cannot be reached or rejects the call".
  - The current tests can start the host's real gcr-prompter when they forward before a mock prompter exists.

  Still open for you: should the bridge give the name back, or not claim it outside GNOME?

**Rewrote** (in t1):
- `prompterBridge`, second paragraph: "…There the only SystemPrompter is the gcr-prompter fallback, which the bus D-Bus-activates and which draws its own GTK dialog. The bridge owns org.gnome.keyring.SystemPrompter on the backend bus, so the bus does not activate the fallback. It forwards the prompter conversation to gnome-shell's prompter on the front (session) bus, so the user sees the normal GNOME unlock dialog. The exchange payload carries the DH-encrypted password and is forwarded verbatim between gnome-keyring and gnome-shell. The dispatcher never sees the plaintext."
- `toShell`: "The forwarder of Prompter calls to gnome-shell. It resolves the front prompter by name on each call, so a late or restarted gnome-shell is followed."
- `newPrompterBridge`: "Returns a bridge that owns org.gnome.keyring.SystemPrompter on the backend bus and forwards its prompts to the session prompter on the front bus. Returns nil when the backend bus already has a prompter, as in remote or same-bus mode. If another process claims the name first, the bridge forwards nothing. Errors when the name request or the export on the backend bus fails."
- `activate`: "Claims org.gnome.keyring.SystemPrompter on the backend bus and exports the bridge there. If another process already owns the name, it leaves that owner in place and returns nil. Errors when the name request or the export fails."
- `TestPrompterBridgeClaimsNameBeforeFrontPrompter`: "Checks that the bridge owns the backend SystemPrompter name as soon as the proxy connects, before gnome-shell's prompter exists on the front bus. It also checks that prompts reach that prompter once it appears. This covers relogin, where the proxy often starts before gnome-shell."
- `nameHasOwner`: "Checks whether name currently has an owner on conn. A name that is activatable but not running reports false. See prompterBridge for why that matters."

**Findings** (18 in total, each with an entry in `decisions.yaml`):
- **Fixed** (patches made but not applied): b1-1, b1-3, b1-4, b1-5, b1-6, b1-8, b1-9, b1-10 and cross-1 in t1; b1-7 in t3.
- **Asked** (no answers yet): b1-2 in t2; b1-11 in t4.
- **Planned:** b1-12 (shared test fixture), b1-13 (`recvWithin` helper across packages) and b1-14 (unused logger). Their entries are not in `TODO.md` yet, because "patches only" writes nothing to the working tree. t5 and t6 show what these fixes would cost.
- **Skipped:** b1-15 (score 3), b1-16 (score 3) and b1-17 (score 2), all under the threshold of 5.
- **Kept / Discarded:** none.

To save agents, I grouped the PLAN/SKIP previews into two patches (t5, t6) instead of one per task.

Verification: each patch passed gofmt and go vet in its own worktree, and every patch except t3 also passed the prompter tests. Nothing was run on your working tree.

Run directory: `.git/unsmell/20261101-210519/`