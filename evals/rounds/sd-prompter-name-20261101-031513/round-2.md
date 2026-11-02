I've fixed the smells on the changed lines and planned the rest in `TODO.md`. One thing to check before you commit: the survey found what looks like a regression in remote mode.

**Possible regression.** `newPrompterBridge` now claims SystemPrompter on the backend bus at startup. In remote mode the backend is your own session bus. If the proxy starts before gnome-shell registers its prompter (the relogin race), the bridge takes the name there, and gnome-shell then finds it taken. The deferred activation you removed prevented that. I didn't change it, because it is a design question, not a smell. It is the first entry under the new `TODO.md` heading, with two options: bridge only in local takeover, or keep a watch for remote mode.

**Run notes.**
- The changeset was 3 files, so one survey batch covered it. I skipped the cross-file agent: with only one batch there is nothing to compare across batches.
- Three fresh re-checks ran; that is the limit. All their findings were fixed, but the last two fixes were not re-checked again.
- The plan entries from the earlier run in `TODO.md` were left alone, and findings that matched them were dropped.

```
Survey   3 files read whole · 34 declarations inventoried · 1 lock inventoried, 0 oversized · 10 parameter-table rows, 0 shared context columns · 0 misplaced rules · 0 request-scoped values threaded · 5 inputs at the edge, 0 unparsed · 10 repeated literals, 8 repeated expressions, 10 facts stated twice · 5 changed functions split by role, 1 mixing roles, 0 actionable pass-throughs · 28 doc items checked, 4 with an effect or exit missing, 5 leaking mechanism
```

**Rewrote**
- `internal/proxy/prompter.go:62` (doc on `newPrompterBridge`): "Returns a bridge for a backend bus that has no prompter of its own. The bridge takes SystemPrompter on the backend bus before it returns, even if gnome-shell's prompter is not up yet. Returns (nil, nil) when the backend bus already has a prompter. If another process takes the name after that check, the returned bridge serves no prompts. Errors as activate does."
- `prompter.go` (doc on `activate`): added "Errors when the name request or the export fails."
- `prompter.go:50` (on the `toShell` field): "Forwards Prompter calls to gnome-shell by name, so each prompt reaches the gnome-shell running at that moment, even one started after a relogin."
- `prompter.go:57` (on the `owned` field): "True once activate has claimed the name and exported the bridge. close releases the name only then."
- `e2e/gnome/vm/demo-driver-install.sh:138`: "The prompter bridge forwards the unlock prompt to gnome-shell, so the unlock modal is in the shell actor tree and the locator can aim at it by text. Type the password and press Enter, as in the try demo's unlock, then click Approve on the notification."

**Fixed**
- `prompter.go` `newPrompterBridge` doc: it narrated the call to `activate` and had no error contract. Rewritten as above, including the case where another process takes the name first and the bridge serves nothing.
- `prompter.go` `activate`: `b.owned = false` after a failed Export was a dead write left over from the old deferred path. `owned` is now set only after Export succeeds.
- `prompter.go`: the reason `toShell` calls gnome-shell by name was a comment inside the struct literal. It now sits on the field.
- `prompter.go` `owned`: its comment didn't match the new meaning and said nothing about why the field exists. Rewritten.
- `prompter_test.go`: renamed the test to `TestPrompterBridgeClaimsBackendNameBeforeShellPrompter`. The old name said it "claims the backend".
- `demo-driver-install.sh:138`: the comment was hard to read and wrong in two places. It said the bridge forwards "to the modal", and it said the try demo clicks Approve after the unlock (it clicks Deny there).

**Planned** in `TODO.md`, under "Unsmell run 2026-11-01 (second pass)":
- the remote-mode regression above;
- the Callback doc leaves out PromptDone;
- two facts each stated four times: the payload is forwarded verbatim, and gnome-shell owns the prompter name;
- the `BeginPrompting` doc doesn't mention its error, and several docs join ideas with colons or semicolons;
- `callbacks` is a map used as a set;
- `prompterCallback.logger` is never read;
- the test hand-rolls a receive with a timeout three times;
- `promptCall.sender` is a plain string;
- the `nameHasOwner` doc explains the bridge's reasons instead of its own;
- the demo script has stale names, a duplicated block and repeated literals.

**Discarded**
- The leftover word "activate" in the test message: `activate` still exists.
- The lock as oversized: `mu` still guards `callbacks`.
- The `activate` name as misleading: it still turns the bridge on.
- `PerformPrompt`, `PromptReady` and `PromptDone` as pass-throughs: godbus needs those method names.
- Findings that matched entries the earlier run had already planned: the type doc's fallback claim, `(nil, nil)` meaning two states, the duplicated test setup, the repeated `Export(nil, …)` call, the untyped `systemPrompterPath`, docs that open with their own name, and the `proxy.go` comment that repeats the contract.

**Verification:** `go vet` passes, `go test ./internal/proxy/` passes, `bash -n` on the script passes, and gofmt is clean. `staticcheck` could not run: the installed binary is older than the Go toolchain.

Nothing is staged or committed.