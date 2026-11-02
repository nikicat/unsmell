I cleaned up the prompter-bridge change. The main fix is removing state that your change left dead. Tests pass, and nothing is staged or committed.

**Coverage.** I surveyed 2 files: `prompter.go` and its test, read whole as one batch. I skipped the separate cross-file agent because there was only one batch. There were two re-checks. The second one's findings were comment fixes, which I applied without running a third re-check.

**Fixed**
- **Dead state** (`prompter.go`): the `active` and `closed` fields, the guard in `activate`, its mutex lock and `b.closed = true` in `close()` existed only for the goroutine you removed. Now `activate` has one caller, which runs before the bridge is published, so I deleted all of it. The re-check confirmed there is no race: `mu` still guards `callbacks`, and `-race` passes.
- **Docs that were wrong or narrated history:**
  - The `newPrompterBridge` doc said "unconditionally". That is false: if another process already holds the name, the bridge gives up and is still returned.
  - The same doc said the fallback "draws a GTK dialog". The type doc says the opposite. I took that claim out of the new docs and put a "check which is true" entry in `TODO.md`.
  - The `activate` doc still described the removed "idempotent, no-op after close()" behaviour.
  - Two other comments mentioned the removed re-arming.
- **Stale test text:** a comment at line 75 and an assert message at line 97 still mentioned the old front-prompter check. A comment at line 167 just repeated its assert message. The doc on the new test opened with its own name and ran 8 lines.
- **Stale claim outside the diff:** a comment in `e2e/gnome/vm/demo-driver-install.sh` said the bridge "re-establishes after the relogin". Your change made that untrue.

**Rewrote**
- `prompter.go` `newPrompterBridge`: "Returns a bridge for a backend bus that has no prompter of its own. It calls activate at once, even before gnome-shell's prompter is up. Returns (nil, nil) when the backend bus already has a prompter."
- `prompter.go` `activate`: "Claims org.gnome.keyring.SystemPrompter on the backend bus and exports the bridge there, so unlock prompts reach gnome-shell. If a gcr-prompter or any other process already holds the name, the bridge leaves it and serves nothing."
- `prompter.go` new comment at the `toShell` line in the constructor: "Addressing gnome-shell by name lets each prompt reach the gnome-shell that is running at that moment, even one started after a relogin."
- `prompter_test.go` doc on the new test: "Covers the relogin race, in which the proxy starts before gnome-shell registers its prompter. The bridge must own the backend SystemPrompter name from startup, and forward to gnome-shell once its prompter appears."

**Choices made for you** (because of "fix everything")
- I removed the lock from `activate` rather than keeping it as a guard against a caller that no longer exists.
- I dropped "Errors when the claim or export fails" from the docs, because those are just bus failures. The other option was to keep it.

**Behaviour:** none changed.

**Planned** (new heading "Unsmell run 2026-11-01" in `TODO.md`), all on lines your change didn't touch:
- Settle whether the gcr-prompter fallback hangs or draws a dialog, then fix the type doc.
- The constructor can return a bridge that serves nothing. Either return `(nil, nil)` in that case or return an error.
- The two tests build the same setup inline. Extract shared helpers.
- `unexportCallback` and `close` repeat the same unexport call.
- `systemPrompterPath` is an untyped string. Type it as `dbus.ObjectPath`.
- `proxy.go:163–166` repeats the constructor's contract.
- 13 doc comments open with their own name.

**Discarded:** two step comments in the new test (lines 165 and 179) look like they repeat the test's doc. They mark steps in the test body, so they stay.

**Survey numbers:**
- 2 files read whole, 29 declarations, 1 lock (partly oversized, now fixed).
- 0 shared parameters or misplaced rules, 4 inputs from outside (0 unparsed).
- 8 repeated literals, 4 repeated expressions, 4 facts stated twice.
- 4 changed functions split by role, 2 mixing roles, 0 pass-throughs.
- 31 doc comments checked: 2 missing an exit or stating a false one, 5 describing mechanism or history.

**Verification:** `go vet` and `go test -race ./internal/proxy/` pass, and `go build ./...` succeeds. `staticcheck` couldn't run because the installed binary is too old for this Go version.