I replaced the hand-escaping in `formatBody` with a small `markup` type that escapes all text written into it, so a new field can't be added to the notification body unescaped. Doing this turned up a real bug: the sibling `formatSlowUpstreamBody` put item labels and process names into the same markup body without escaping. That is now fixed too. Tests and `go vet` pass. Nothing is staged or committed.

The changeset was one batch: `desktop.go` with its test. With only one batch, the cross-file agent had nothing to compare, so I skipped it. The survey agent read `slow_upstream.go` too, so the cross-file duplicates were still found. Three fresh re-checks ran after the fixes, and the third found nothing.

```
Survey   3 files read whole · 16 declarations inventoried (13 ✗) · 5 locks inventoried, 0 oversized · 2 parameter tables, 3 shared context columns · 3 misplaced rules · 1 request-scoped value threaded (unchanged lines) · 9 inputs at the edge, 2 unparsed · 6 repeated literals, 6 repeated expressions, 3 facts stated twice · 4 functions split by role, 1 mixing roles, 0 pass-throughs (plus the esc alias) · 11 doc items checked, 0 with an effect or exit missing, 2 leaking mechanism
```

**Rewrote**
- `markup.go:9`: "A notification body in the markup subset of the Desktop Notifications spec. Text written through it is escaped, so the only markup in the body is the tags that it writes itself."
- `desktop.go` `writeGPGSubject`: "Appends the repository in bold and the commit subject in italics."
- `desktop.go` `writeSSHSubject`: "Appends the key label in bold and the destination host, when the request names one."
- `desktop.go` `writeProcessChain`: "Appends the process chain on a new line, starting with the requesting process. Each process name is followed by its PID when the handler shows PIDs."
- `desktop.go` `writeSender`: "Appends who sent the request. With an invoker name, the invoker is bold and the client and PID follow it. Otherwise the client is bold, followed by the PID when it is nonzero."
- `desktop.go` `itemsSubject`: "Returns what a get, write, delete or search request is about. For a single item, that is its label, and for any other number of items, the count. For a search, it is the search attributes, or "all" when there are none. The second result is false for any other request type."
- `desktop.go` `searchAttrsText`: "Returns the search attributes as "k=v, k=v", sorted by key."
- `slow_upstream.go` `formatSlowUpstreamBody`: "Returns the notification body. It names the items, and the process chain on its own line when the request has one."
- `desktop_test.go` escape test: "Client-supplied values must reach the body as escaped text. The notification carries the approve and deny buttons, so markup injected by a client could make a malicious request look trustworthy."

**Fixed**
- `desktop.go:582`: every value was escaped by hand with `esc(...)` (about 7 places), and the closures shared `b` and `showPIDs` → new `markup` type in `markup.go`; the closures became `Handler.writeProcessChain` and `writeSender`.
- `desktop.go:636` and `:661`: the label / "N items" / attributes / "all" switch was written twice, differing only in `<b>` vs `<i>` → one `itemsSubject`, and each branch picks bold or italic.
- `desktop.go:582`: the function mixed detail, decisions and assembly → it is now a type switch over named helpers: `writeGPGSubject`, `writeSSHSubject`, `itemsSubject`, `writeSender`, `writeProcessChain`.
- `desktop.go:591`: the `esc` alias, and its 6-line comment with the threat model and a field list → deleted. The type doc now holds the rule, and the test holds the reason.
- `desktop.go:585, 593, 608`: docs that opened with their own name → replaced by the docs above.
- `desktop.go` process-chain doc: it said "parent first", but `procutil` builds the chain child first. This was already wrong in HEAD → corrected.
- `slow_upstream.go:77, 82, 85`: a doc that opened with its own name, a comment repeating `itemDisplayLabel`'s rule, and a `// no items` that restated `case 0` → rewritten or deleted.
- `desktop_test.go:419`: a doc that opened with its own name, the external "Vuln 7" reference, and the consent reason stated twice → rewritten. Removed the redundant `Contains` at :453.
- New escape tests in `desktop_test.go` (SSH, search, remote sender), `slow_upstream_test.go` and `markup_test.go`.

**Bug**
- `slow_upstream.go:formatSlowUpstreamBody`: item labels, paths and process names went into the markup body unescaped. This is the same injection the change fixes, in its sibling. They are escaped now, so a label containing `<` now shows as escaped text.

**Behaviour**
- `desktop.go` `searchAttrsText`: search attributes are now sorted by key instead of following random map order. The output is deterministic and can be tested.
- Quotes now escape as `&#34;` and `&#39;`, which is still valid markup. Everything else is byte-identical to HEAD; the first re-check compared every branch against HEAD.

**Planned**: in `TODO.md`, under "Unsmell run 2026-11-01: notification markup escaping", 9 entries:
- the process-chain rendering is duplicated between `desktop.go` and `slow_upstream.go`;
- the "k=v" formatting is duplicated with `cli/format.go`;
- the `"destination"` key is a literal shared with `sshagent/proxy.go`;
- action-key literals, and a stale `Action` doc;
- the reconnect-retry is written three times, and urgency `2` is a magic number;
- `cancelledRequests` is never read;
- `NewHandler` takes 6 parameters;
- about 25 doc comments open with their own name, and the test file has its own `contains` helper;
- nothing checks the server's `body-markup` capability.

**Discarded**
- The new test uses testify while the rest of the file uses `t.Errorf`. No written rule forbids it, and testify is already in `go.mod`.
- `writeProcessChain`'s chain parameter "never varies". It is the input being rendered, not context.
- `m *markup` passed to two helpers. It is the output being built, not a value threaded through.

Every finding from the three agents is accounted for above.

**Verification:** `gofmt`, `go vet` and `go test -race ./internal/notification/` pass, and so does `go test ./...` across the repo. staticcheck could not run because the installed binary is older than Go 1.26 and fails with "export data version" errors.