I fixed every finding on the changed lines. All of them were doc comments or script comments, so no code changed. Every finding off the changed lines either already had a `TODO.md` entry or now has one. `go test ./...`, `go vet` and `gofmt` all pass. `staticcheck` could not run because the installed copy is older than the Go toolchain.

**Survey:** two batch agents read the changed files whole (`prompter.go` with its test, and `demo-driver-install.sh`). A cross-file agent compared their findings, and three re-check agents reviewed the fixes. They found 55 smells: 29 in the Go files, 26 in the script. Seven doc comments were missing an effect or exit, or described the mechanism.

**Rewrote**
- `internal/proxy/prompter.go:63`, `newPrompterBridge`: "Returns a bridge that holds org.gnome.keyring.SystemPrompter on the backend bus and forwards unlock prompts to gnome-shell. It can be created before gnome-shell's prompter is up. Returns (nil, nil) when the name already has an owner on the backend bus, and a bridge that serves nothing when it cannot claim the name."
- `prompter.go:89`, `activate`: "Claims org.gnome.keyring.SystemPrompter on the backend bus and exports the bridge there, so unlock prompts reach gnome-shell. If another process already holds the name, the bridge serves nothing."
- `prompter.go:50`, the `toShell` field: "The route for Prompter calls to gnome-shell. It addresses gnome-shell by name, so each prompt reaches the gnome-shell running at that moment, even one started after a relogin."
- `prompter.go:57`, the `owned` field: "True once prompterBridge.activate has claimed the name and exported the bridge. prompterBridge.close releases the name only then."
- `e2e/gnome/vm/demo-driver-install.sh:138`: "The prompter bridge forwards the unlock prompt to gnome-shell, so the unlock dialog is in the shell actor tree and the locator extension can aim at it by text."

**Fixed**
- `prompter.go:63`: the doc was five sentences long and pointed at "that check", which it never introduced. It now states the contract.
- `prompter.go:63` and `:89`: the "another process holds the name, so the bridge serves nothing" fact was in both docs. `activate`'s doc now owns it.
- `prompter.go:91`: the doc listed only D-Bus failures as errors; that sentence is gone. Re-checks also caught "it" with two possible referents and a redundant clause.
- `prompter.go:50`: the field doc opened with a verb; it is now a noun phrase. In the `owned` doc, the bare words "activate" and "close" are now qualified as method names.
- `demo-driver-install.sh:138`: the comment was four lines, and half of it retold the `rd` command below it. "Modal" is now "dialog", and "locator" is now "locator extension", the names the rest of the file uses.

**Planned:** ten new entries in `TODO.md` under "Unsmell run 2026-11-01 (third pass)":
- In the Go files:
  - The `prompterBridge` type doc is 24 lines of mechanism and history.
  - The const-block doc opens with a fragment, and the `PromptDone` doc gives gnome-keyring's reason for the call.
  - The test mock's doc claims a method it doesn't have.
  - `nameHasOwner` treats a failed lookup as "no owner".
- In the demo script:
  - The header is stale: it says `systemctl restart gdm`, which demo.sh no longer does.
  - Six helpers are copied from `demo-driver.sh`, along with its poll loop and the open-then-place sequence.
  - The unlock command batch is written in two scripts.
  - Two values have no single owner: the fixed-build stash path and the owner-pid lookup.
  - Several comments break the house style.

**Discarded**
- Already planned by earlier runs:
  - `newPrompterBridge` can return a bridge that serves nothing (the "two states behind one pointer" entry).
  - The bridge may now take the name in remote mode during the relogin race. That entry is marked "check first".
  - The type doc says the Callback interface is PromptReady only, and some facts are repeated in several comments.
  - Docs that open with their own name, the frontConn/backendConn trailing comments, and `callbacks` as a bool map.
  - The unused `logger` field, the untyped `systemPrompterPath`, the duplicated unexport call, and the hand-rolled timeouts in the tests.
  - Smaller items in the demo script.
- `mu` and `owned`: `owned` is written before the bridge is shared with anything, and the swap under the lock in `close` keeps `close` safe to call twice.
- `activate` has only one caller, but it is not a pass-through: it claims the name, exports, and rolls back on failure.
- The relogin mention in the field doc and in the test doc are two different facts.
- The cross-file agent flagged the shell comment's "the bridge forwards the prompt to gnome-shell" as a repeat of the Go doc. I kept it: the script depends on that fact, so it says so, without retelling the bridge's reasoning.

**Incomplete:** the third re-check found two more wording problems in `newPrompterBridge`'s doc. I fixed them, but the skill allows only three re-checks, so nobody has reviewed the final wording.

The three re-checks kept disagreeing about how to tell "returns nil" apart from "returns a bridge that serves nothing". Both cases mean another process owns the name. I recorded this on the `TODO.md` entry: the wording problem goes away once the return shape is fixed.

Nothing is staged or committed.