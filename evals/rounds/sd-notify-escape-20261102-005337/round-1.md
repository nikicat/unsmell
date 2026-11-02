I made four patches and applied none of them, since you asked for patches only. Your working tree and index are unchanged, I asked no questions, and nothing was re-checked after the edits.

**Bug found:** your change escapes the approval notification's body, but the slow-upstream notification body (`internal/notification/slow_upstream.go:80`) still writes item labels, paths and process names unescaped. A crafted label or process name can still inject markup there. Patch **t2** fixes it.

**The patches** (in `.git/unsmell/20261102-005354/fixes/`):

| Patch | Decision | What it does |
|---|---|---|
| `t1.patch` | FIX | Reshapes `formatBody` and its test (details below). |
| `t2.patch` | FIX, bug | Escapes the slow-upstream body and adds `TestSlowUpstreamNotifier_EscapesMarkup` with an exact expected body. |
| `t3.patch` | ASK, applies only after t1 and t2 | Adds a small `markup` writer in a new `markup.go`. Its `text`, `bold` and `italic` methods escape their input, so escaping and tags exist only in that file. Both body formatters use it, and `markup_test.go` covers it. |
| `plan.patch` | PLAN | Adds two entries to `TODO.md` under "Unsmell 2026-11-02: notification markup escaping". |

**What t1 changes:**
- **Duplication:** the default branch wrote "label, N items, search attributes or all" twice, once in bold and once in italics. One `requestSubject(req)` now does it, and each format adds its own tag.
- **Closures:** `writeChain` and `escapedSearchAttrs` become the top-level functions `writeProcessChain` and `formatSearchAttrs`.
- **Long comment:** the six-line comment on the `esc` alias is gone, along with the alias. Its list of escaped fields left out `Client`, `InvokerName` and the SSH destination.
- **Test comment:** deleted. It repeated the code comment and cited "Vuln 7", which nothing in the repo defines.
- **Test:** the seven Contains/NotContains checks become a table of seven cases, one per branch of `formatBody`, each checking the exact body. The old test only covered the GPG branch, and it checked the escaped process name only negatively.
- **False comment:** "parent → child order" was wrong, since the chain runs from the requestor up to its ancestors. It now says so.

**Doc comments rewritten:**
- `formatBody`: "Returns the notification body for req in the markup that notification servers render. All client-controlled text is escaped, because the notification carries approve and deny buttons and injected markup could make a request look trustworthy."
- `writeProcessChain`: "Appends the process chain on a new line, from the requestor up to its ancestors, with each process name escaped."
- `formatSearchAttrs`: "Returns the attributes as "k=v, k=v" with keys and values escaped."
- `requestSubject`: "Returns the escaped text that names what req asks for. It is the item label or item count, the search attributes or "all", or "" for other request types."
- `formatSlowUpstreamBody` (t2): adds "The body is notification markup, so every client-controlled value is HTML-escaped." t3 removes that sentence again.
- `markup` (t3): "A notification body in the markup that notification servers render. Text passed to text, bold and italic is escaped, so client-controlled values cannot inject markup; only raw appends unescaped." This one still joins two ideas with a semicolon, which goes against your doc style. Fix it if you take t3.
- The `formatBody` doc in t1 runs past 80 columns.

**The question for you (t3):** should escaping be a type (t3), or should it stay as a direct `html.EscapeString` call at each value (t1 alone)? I'd take t3. It makes forgetting to escape a new field structurally impossible, which is exactly the mistake slow-upstream shows.

**The other findings:**
- **Planned:** the test file's `contains`/`stringContains` helpers reimplement `strings.Contains`. Also, the `"destination"` key is spelled separately in `sshagent/proxy.go:73` and `desktop.go:627`.
- **Skipped:**
  - Testify in a file that otherwise uses `t.Errorf` (score 2).
  - Search attributes print in random map order (score 4). The new tests use one attribute so they stay deterministic.
- **Discarded:** the `handleCancelled` summary puts `InvokerName` in unescaped. That is correct, because the notification spec makes the summary plain text.

All 14 findings have an entry in `decisions.yaml`, and none is left open. The change spans only two files, so there was one survey batch and no cross-file pass.

**Checks:** each editor ran `go build ./...`, `go vet` and the tests for its own area, and all passed. The t1 test passed against the code before the reshape and again after it, so the output is unchanged. The full test suite and staticcheck have not been run, since nothing was merged.

Everything from the run (findings, decisions, patches) is in `.git/unsmell/20261102-005354/`.