I ran a patches-only pass: 11 patches are in the run directory, and nothing has been applied to your working tree. Your two modified files are exactly as you left them, the index wasn't touched, and nothing was run beyond each editor's build check.

**How the run was done**
- One survey agent read the whole changeset (`prompter.go` and `prompter_test.go`) as a single batch.
- With only one batch, I skipped the cross-file agent and wrote an empty `cross.yaml`.
- To save agents, one editor did the four plan/skip patches (t6, t7, t8, t11) in four separate worktrees, instead of one agent per task.

**Survey:** 2 files read whole, 31 declarations inventoried, 5 locks inventoried. Of those, 1 is oversized: `mu` was still used in `activate` only to guard the dead `active`/`closed` flags.

The doc surgery runs through several stacked patches. These are the docs it rewrote:

**Rewrote** (in the patches, not the tree)
- t1, `prompter.go` `activate`: "Claims org.gnome.keyring.SystemPrompter on the backend bus and exports the bridge there. Leaves the bridge inactive when another connection already holds the name. Errors when the claim or the export fails."
- t3, `newPrompterBridge`: "Creates a bridge and claims org.gnome.keyring.SystemPrompter for it on the backend bus. Returns (nil, nil) when the backend bus already has a SystemPrompter, so there is nothing to bridge. If the backend bus refuses the claim because another process took the name, the returned bridge owns nothing. Errors when claiming the name or exporting the bridge fails."
- t3, the `toShell` field: "Forwards Prompter calls to gnome-shell's prompter on the front bus. It looks the prompter up by name at each call, so a gnome-shell restart or a relogin needs nothing from the bridge."
- t3, `TestPrompterBridgeClaimsBackendBeforePrompter`: "Checks that the bridge claims the backend SystemPrompter name before gnome-shell's prompter exists, and forwards to that prompter once it appears. This is the relogin case, where the proxy often starts first."
- t4, the `prompterBridge` type doc: "The only path from the backend gnome-keyring to the GNOME unlock dialog. The backend reaches its unlock prompter over the private bus. Without the bridge, the D-Bus-activated gcr-prompter fallback answers there and draws its own dialog instead of the GNOME one. Holding org.gnome.keyring.SystemPrompter on the backend bus from startup keeps that fallback out. The exchange payload, which carries the DH-encrypted password, passes through verbatim, so the dispatcher never sees the plaintext."

**Fixed** (patches that would be merged)
- t1 `prompter.go:56-57, 103-107, 183`: your removal of `watchFrontPrompter` left the `active`/`closed` fields, the idempotency guard, the lock in `activate` and the "Idempotent, no-op after close()" doc with nothing to serve. They are deleted. Covers b1-1 and b1-5.
- t3 `prompter.go:60-74`, `prompter_test.go:143-150, 167-168, 187-188`: the 14-line constructor doc narrated history and stated the by-name forwarding fact three times. It is now a short contract, and `toShell` owns that fact. Covers b1-4, b1-6 and b1-7.
- t5 `prompter_test.go:75-76, 98`, `e2e/gnome/vm/demo-driver-install.sh:138-139`: these comments still described the front-bus guard you removed and a "re-establishes after relogin" step that no longer happens. They are corrected. Covers b1-8.

**Asked** (no questions were put to you, because of "patches only")
- t4 `prompter.go:28-30` and five other places, b1-3, b1-13: your changeset says the gcr-prompter fallback draws its own GTK dialog (`prompter.go:66-68`, `prompter_test.go:147-149`). The type doc, `TestPrompterBridge`, `forward.go:70-71` and `proxy.go:165-166` still say it is display-less and the unlock hangs. **One of the two is false.** The patch assumes your new claim is the true one, makes the type doc the one place that states it, and has the other places drop the rationale. It also removes the type doc's method-by-method list.
- t2 (stacked on t1), b1-2: when the name claim is refused, the bridge returned today owns nothing. The patch returns `(nil, nil)` in that case, folds `activate` into `newPrompterBridge`, and deletes `owned`.
  - Behaviour change: `Proxy.prompter` becomes nil in that race, and a second `Close` sends a harmless extra `ReleaseName`.
  - It rewrites the constructor doc that t3 also rewrites. If you take both, use t2's version.

**Planned** (patches only, so `TODO.md` was not written; each task has a patch showing the cost)
- t7 `prompter.go:177, 185`: `close()` repeats `unexportCallback`'s unexport-and-delete. The patch adds a `dropCallbackLocked` helper.
- t8 `prompter.go:77-78`, `proxy.go:164-167`: the `(nil, nil)` contract is stated three times.
- t9 `prompter.go:161, 201`: `prompterCallback.logger` is set but never read.
- t10: docs on unchanged lines open with their own declaration's name (b1-10). Some also have semicolons or colons joining a second idea, or use "we" and "us" (b1-17).
- t11: both tests build the same fixtures inline. The patch adds `startBuses`, `connectProxy`, `startShellPrompter` and `connectKeyring`. `prompt_test.go:newPromptTestEnv` repeats the same bus setup (b1-18).
- b1-16, `forward.go:38-40` and the type doc: the "plaintext is never seen" fact is stated twice. It has no patch of its own; t4 covers the type-doc side.

**Skipped**
- t6 `prompter.go:96`: `activate` also means D-Bus activation in nearby prose. Rename to `claimSystemPrompter`, score 4.

**Discarded:** none.

**Bookkeeping:** 18 findings, 18 entries in `decisions.yaml`, none left open. Three findings (b1-16 to b1-18) were reported by editors and added to the findings file.

**Verification:** each patch passes `go build -tags dev ./...` and `go test -tags dev -c` in its worktree, and all 11 apply cleanly to their bases. The test suite and linters were not run. One editor found that the installed staticcheck fails with the current Go toolchain ("export data version 5 is greater than maximum supported version 2"), so it can't run here as installed.

Run directory: `.git/unsmell/20261102-023101/`. The patches are under `fixes/`. t2 and t6/t7 start from t1, t4 and t8 from t3, t10 from t4, and t11 from t3 plus t5.