I fixed the smells in the escaping change, and the notification tests and `go vet` pass. Staticcheck couldn't run because the installed binary is too old for this Go toolchain. Nothing is staged or committed.

The main change: a notification body is now passed by value instead of as a pointer, so a nil body (which would have crashed) can't happen. The empty body is the zero value. I also moved the body-rendering code out of `desktop.go` into a new file, `body.go`.

**Survey:** 6 files read whole, in two batches. That gave 54 declarations, 5 locks (none oversized), 9 parameter tables with no shared context, 10 misplaced rules, no request-scoped values threaded, and 11 inputs at the edge (3 unparsed). It also found 14 repeated literals, 9 repeated expressions and 7 facts stated twice. 11 functions were split by role: 5 mix roles and none is a pass-through. 24 docs were checked: 1 is missing an exit and 3 leak mechanism.

```
Rewrote   markup.go:8     "A notification body in the markup subset of the Desktop Notifications spec. Text written through it is escaped, so the only tags in the body are the ones it writes itself. Every notifier takes bodies only in this type."
Rewrote   body.go:42      "The body of one approval notification while it is being built. It carries the handler's PID setting, so the rendering methods need no Handler."
Rewrote   body.go:65      "…Each process name is followed by its PID when the builder shows PIDs. An empty chain appends nothing."
Rewrote   body.go:82      "Appends who sent the request, followed by a colon. If the request names an invoker, the sender is the invoker in bold, followed by "@", the client and the PID. Otherwise the sender is the client in bold, followed by the PID when it is nonzero."
Rewrote   body.go:98      "Returns the label, item count or search attributes that a secret request is about. A search with no attributes is about "all". The second result is false for request types that have no such subject."
Rewrote   slow_upstream.go:95  "Appends the process chain on its own line, joined the way bodyBuilder.processChain joins it, without PIDs."
Fixed     markup.go:11    body passed as `*markup` could be nil and would crash at String() → markup is now a value type over a string. Chose that over a nil-safe String() or a second "finished body" type.
Fixed     markup.go:15    the tag passed to `tagged` was any string, written unescaped → typed `markupTag` with tagBold/tagItalic
Fixed     markup.go:29    "declare a body, write one text, pass its address" written twice → textMarkup(s), used in desktop.go handleCancelled and in the reconnect test
Fixed     desktop.go      rendering code was a separate concept in a 700-line file → formatBody, bodyBuilder, itemsSubject, searchAttrsText moved to new body.go
Fixed     body.go:85      every branch of sender wrote ": " → written once after the switch
Fixed     body.go:42,82,98 docs that misparsed, narrated branch order, or ran to 5 sentences → rewritten (above)
Fixed     markup.go:8     doc named only Notifier → it now covers every notifier
Fixed     desktop_test.go:419  two overlapping escape tests, the "Verified" scenario described three times → one table test with exact expected bodies (the GPG case is now a row)
Fixed     markup_test.go  one test checked two facts under one name → split into TestTextMarkup_EscapesWholeText and TestMarkup_ZeroValueIsEmptyBody
Fixed     slow_upstream.go:95  the comment still pointed at desktop.go after the move → rewritten
Planned   TODO.md "Unsmell run 2026-11-01 (third pass): markup value type", 5 entries:
            "no process chain means remote" is a rule written only in a comment (body.go plus cli and api);
            `@client[0]` is shown for a zero PID, and the name[pid] format is written in 5 places;
            slowUpstreamSummary is a fourth per-request-type switch;
            two slow_upstream docs carry the caller's reason or repeat what another doc says;
            the D-Bus signal body is read by position, plus two facts that are each stated twice in desktop.go
Discarded process-chain duplication with slow_upstream, the " ← " separator, "%d items", "destination", "dialog-password", the Label/Path fallback (cross-file finding), commitSubject, the slow_upstream doc-name/constructor/test-fixture findings, retry-after-reconnect, the urgency/expire values, the action keys, the "?request=" URL → already planned in TODO.md
Discarded the UpstreamCallContext request-scoped finding → only one hop
Discarded the "; " grep hit in the markupEscaper doc → it is inside the literal "&#39;", not a sentence join
Discarded repeated slog keys → a logging convention, not a protocol
Discarded mixed testify and t.Errorf assertions → testify is already used elsewhere in the repo
Discarded the 4-line sender doc → it is plain; the length comes from the zero-PID inconsistency, which is planned
```

- **Behaviour:** none. Every rendered body is byte-identical, and the merged table test pins the exact strings.
- **Stale plan entry:** the first TODO entry still calls the chain renderer `Handler.writeProcessChain`. It's now `bodyBuilder.processChain`. I didn't edit an entry this run didn't own.
- **Re-checks:** I ran two. The first found 4 problems, all fixed. The second found 1, which I fixed; its other 3 are discarded above. The final one-line rewrite of the slow_upstream comment was not re-checked.

**Verification:** `go test ./internal/notification/` passes, `go vet` is clean, gofmt is clean and `go build ./...` succeeds.