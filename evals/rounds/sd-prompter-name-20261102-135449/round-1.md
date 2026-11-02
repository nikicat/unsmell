I ran the survey and made a patch for every task. As you asked, nothing is merged into your working tree, nothing was re-checked after the patches, and I asked no questions. Your index and working tree are as they were.

The changeset is two files, so I made one batch. One fresh agent surveyed it, a second agent looked for problems that span files, and each task's editor worked in its own worktree.

**Survey:** 2 files read whole · 34 declarations inventoried · 1 lock (`mu`), which no longer needs to guard `active`/`closed` · 2 parameter tables, 1 shared context column (`frontConn, backendConn, logger`, in `prompter.go` and `signals.go`) · 0 misplaced rules · 0 request-scoped values threaded · 4 inputs at the edge, 0 unparsed · 9 repeated literals or expressions, 6 facts stated twice (one of them contradicts the others) · 13 functions split by role, 2 mixing roles (`activate`, the test fixtures), 3 pass-throughs, all kept because the D-Bus interface needs those method names · 30 doc items checked, 13 open with their own name.

**Patches** (in `fixes/`; t3 and t4 start from t1's result):

| Task | Decision | Findings | What the patch does |
|---|---|---|---|
| t1 | FIX | b1-1, b1-5, b1-9, cross-2, cross-3 | Since the changeset deleted `awaitFrontPrompter`, `activate` has one caller left. The patch folds it into `newPrompterBridge` and deletes the dead `active`/`closed` fields, their lock use and `b.closed = true`. It cuts the new 15-line constructor doc and the 8-line test doc down: they had history, capital letters, and copies of facts other docs own. It also removes "(which the bridge now re-establishes after the relogin)" from `e2e/gnome/vm/demo-driver-install.sh:138`. |
| t2 | FIX | b1-4 | Fixes the comment at `prompter_test.go:75` and the assertion message at `:98`. Both still described the front-bus check the changeset removed. |
| t3 (after t1) | FIX | b1-3 | When the name can't be claimed, the constructor now returns `nil, nil` instead of a bridge that does nothing. That removes the `owned` field, and `close()` always releases the name. |
| t4 (after t1) | **ASK** | b1-2, cross-1, b1-6, b1-8 | Gives the "why the bridge owns the name" fact one home, the `prompterBridge` type doc, and removes the copies in `proxy.go`, `forward.go` and the tests. |
| t5, t6, t7, t8 | PLAN | b1-10, b1-11, b1-7, cross-4 | t5 removes the unused `prompterCallback.logger` field. t6 removes the own-name openings from docs on unchanged lines. t7 extracts the duplicated test fixture and adds one generic `recvWithin[T]`. t8 adds a `busPair` struct, because `newSignalForwarder` and `newPrompterBridge` take the two connections in opposite orders. |
| t9 | SKIP (score 3) | b1-12 | The two-line unexport code appears twice; this extracts it into a helper. |
| plan | — | — | Adds the four PLAN entries to `TODO.md` under "Smells planned by unsmell run 20261102-135503". It is not applied. |

**The question I didn't ask (t4):** the docs disagree about the gcr-prompter fallback. The text the changeset added says that in the local-takeover setup the fallback **draws its own GTK dialog**. The older text says it is **display-less and the unlock hangs forever**: the type doc, the `TestPrompterBridge` doc, `proxy.go:165` and `forward.go:71`. One of them is false. The t4 patch assumes your newer text is right. If the older text is right, t4 only needs the type doc's sentence changed back.

**Doc rewrites** (verbatim; the t4 one is only a proposal):
- `newPrompterBridge` (t1): "Returns a bridge that owns org.gnome.keyring.SystemPrompter on the backend bus from the start, so gnome-keyring's unlock prompts reach gnome-shell's prompter even before it is up. Returns nil when the backend bus already has a prompter. Errors when the name cannot be requested or the bridge cannot be exported." t3 changes the nil sentence to "…already has a prompter or another process owns the name."
- `TestPrompterBridgeClaimsBackendBeforePrompter` (t1): "Checks that the bridge owns the backend prompter name before gnome-shell's prompter exists, and forwards to that prompter once it appears."
- `prompterBridge` (t4): "The only route from the backend gnome-keyring to the user's unlock dialog. It owns the system prompter name on the backend bus, so D-Bus never starts the gcr-prompter fallback there. That fallback would draw its own dialog instead of gnome-shell's. The bridge relays the prompter conversation to gnome-shell on the front bus without reading it."
- `nameHasOwner` (t4): "Checks whether name currently has an owner on conn. A name that is activatable but not running has none. Returns false when the query fails."

**Behaviour changes:**
- t1: none.
- t3: when another process already owns the name, `ConnectWith` gets no bridge instead of one that does nothing.
- t7: only the timeout failure messages in the tests change.

**Discarded:** cross-5 (`nameHasOwner` lives in `forward.go`) repeats b1-8, and that placement was already there before your change.

**Notes:**
- I edited t4's patch by hand to fix two slips its editor introduced: a semicolon joining two ideas, and a doc that opened with its own name ("PromptReady relays…").
- Applied in order t1, t2, t3, t4 to a throwaway copy, t4 needs a three-way apply (`git apply -3`) because of nearby lines t3 changed; with it, everything applies.
- The cross-file agent read only line ranges, not whole files. That is all its job needs.
- All 17 findings have an entry in `decisions.yaml`.

**Verification:** each patch passes `go build ./...` and `go vet ./internal/proxy/`, and so does t1 through t4 applied together. I didn't run the tests or staticcheck, because patches-only mode stops before the full check.

Everything is in `.git/unsmell/20261102-135503/`: the findings, the decisions and all ten patches in `fixes/`.