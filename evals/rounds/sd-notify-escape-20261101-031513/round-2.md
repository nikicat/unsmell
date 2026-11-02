I ran the full pass: two survey agents, a cross-file agent and two re-checks. The fixes are in place, and tests, vet and build pass. It turned up one real bug: messages containing a quote or apostrophe, like "Don't", would show up as `Don&#39;t` in GNOME notifications.

**Survey:** 6 files read whole · 87 declarations inventoried · 5 locks inventoried, 0 oversized · 7 parameter tables, 3 shared context columns · 7 misplaced rules · 2 request-scoped values threaded · 10 inputs at the edge, 2 unparsed · 13 repeated literals, 12 repeated expressions, 4 facts stated twice · 17 functions split by role, 2 mixing roles, 0 pass-throughs · 18 doc items checked (plus 30 docs that open with their own name, all on unchanged lines), 1 with an effect or exit missing, 3 leaking mechanism.

**Bug**
- `internal/notification/markup.go:19`: `html.EscapeString` writes `'` and `"` as `&#39;` and `&#34;`. GNOME Shell only understands the five named entities, so those codes appeared as raw text. The escaper now replaces only `&`, `<` and `>`, and `markup_test.go` checks that quotes come through unchanged. Notification bodies now show quotes and apostrophes as typed.

**Fixed**
- **Bodies are now a typed value** (`desktop.go:31`, `:162`, `:176`, `:180`, `:209`, `slow_upstream.go:13`): the escaping guarantee used to end at `m.String()`, because `Notify` and `NotifyPersistent` took the body as a plain `string`. They now take `*markup`, so no body can reach the server unescaped. `formatBody` and `formatSlowUpstreamBody` return `*markup`. `handleCancelled` (`desktop.go:533`) used to build its body raw with `fmt.Sprintf` and now goes through `markup`. The mock and two test call sites are updated. This changes the signature of the exported `Notifier` interface. Under "fix everything" I applied that instead of asking. Every implementer is inside the module, and the alternative was to plan it.
- **New `bodyBuilder` type** (`desktop.go:583-665`): four free `write…` functions all took `m *markup`, and the process-chain one sat on `Handler` only to read `showPIDs`. They are now methods of `bodyBuilder`, which embeds `markup` and holds `showPIDs`.
- **One process-chain call** (`desktop.go:583`): `writeProcessChain` was called in three switch arms. It is now called once after the switch.
- **Duplicated comment** (`desktop_test.go:419`): the test comment restated the type doc's escaping rule. It now says only what the test adds.

**Rewrote**
- `markup`: "A notification body in the markup subset of the Desktop Notifications spec. Text written through it is escaped, so the only tags in the body are the ones it writes itself. Notifier takes bodies only in this type, so no body reaches the server unescaped."
- `markupEscaper`: "The escaper for markup text. It replaces only &, < and >, because servers such as GNOME Shell accept only named entities. They would show the numeric &#39; and &#34; that html.EscapeString writes as literal text."
- `bodyBuilder`: "The body of one approval notification while it is being built. It carries the handler's choice of whether to show PIDs to the process chain."
- `sshSubject`: "Appends the key label in bold. If the key's attributes name a destination host, an arrow and the host follow the label."
- `processChain`: "Appends the process chain on a new line, starting with the requesting process. Each process name is followed by its PID when showPIDs is set. An empty chain appends nothing."
- `sender`: "Appends who sent the request, followed by a colon. With an invoker name, it appends the invoker in bold, an "@", the client and the PID in brackets. Without one, it appends the client in bold and the PID in brackets when the PID is nonzero."
- `itemsSubject`: "Returns what a get, write, delete or search request is about. A single item is named by its label. Any other number of items is named by their count. A search is named by its attributes, or by "all" when it has none. The second result is false for every other request type."
- `formatSlowUpstreamBody`: "Returns the body of the slow-upstream notification. It names the items, with a count when there is more than one. If the call has a process chain, the chain follows on its own line."
- Test comment: "Covers a request crafted to look verified. Without escaping, a client could add a fake "Verified" label to the notification that carries the approve and deny buttons."

**Planned** (12 entries in `TODO.md`, under "Unsmell run 2026-11-01 (second pass): typed notification bodies")
- Cross-package duplicates: the request subject is built in both the notification and CLI code, and they already disagree on an empty search ("all" vs "-"). `commitSubject` exists three times.
- Two items change what notifications show: desktop notifications ignore an item's Path when its Label is empty, and the per-request-type rules are spread over three `switch` blocks.
- The rest are on unchanged lines in `desktop.go`, `slow_upstream.go` and both test files.

**Already planned:** the findings that matched entries from the first run's heading were left alone. They cover the " ← " chain duplication, the `"destination"` key, the action keys, the retry and urgency repetition, `cancelledRequests`, `NewHandler`'s parameters, docs that open with their own name, the `contains` helpers and the `body-markup` capability check.

**Discarded**
- `itemsSubject` returning `(string, bool)`: this is Go's standard comma-ok form. Its doc was compressed and is rewritten above.
- `tagged(tag string)`: it is private and only called with `"b"` and `"i"`.
- The "Must be called with n.mu held" docs: they state a correct lock rule.

Every finding from the five agents is accounted for in the lists above.

**Verification:** `go test -race`, `go vet` and `go build` pass, and gofmt is clean. staticcheck could not run because the installed binary is too old for this Go toolchain. The second re-check found three wording problems, which I fixed. No fresh agent re-checked those three last edits, which are one-line comment changes. Nothing is staged or committed.