I fixed everything the survey found on the changed lines and planned the rest in `TODO.md`. Tests and clippy pass. Nothing is staged or committed.

The two files were small enough to survey as one batch, so a single survey agent ran, plus two re-check agents on the fixes. No cross-file agent was needed. The second re-check found one test duplication, which I fixed; that last small fix was not re-checked again.

**Survey:** 2 files read whole · 27 declarations inventoried (10 flagged) · 2 locks inventoried, 0 oversized · 2 parameter tables, 0 shared context columns · 4 misplaced rules · 1 request-scoped value threaded · 5 inputs at the edge, 2 unparsed · 6 repeated literals, 8 repeated expressions, 6 facts stated twice · 1 function mixing roles, 0 pass-throughs · 9 doc items checked, 1 with an effect or exit missing, 4 leaking mechanism. The survey returned 24 findings and the re-checks 5 more.

**Rewrote** (`src/evm/cache/event_signature_cache.rs`)
- `EventSignatureRow`: "One cached resolution of an event name to its signature, as [`EventSignatureCache`] stores and returns it."
- `topic0`: "The keccak256 hash of `signature`. Logs of this event carry it as their first topic."
- `abi_json`: "The JSON of the ABI event item that `signature` was taken from, when the row has one (see [`ResolvedEvent::abi_json`])."
- New `Topic::from_slice` in `src/evm/types.rs`: "Returns the topic held in `bytes`, or `None` when `bytes` is not 32 bytes long."

**Fixed**
- **`insert_event_signature`:** it took `signature`, `topic0` and `abi_json` as separate arguments, which are exactly the fields of the new struct. It now takes `row: &EventSignatureRow`. I made this call myself under "fix everything": it changes a public signature, but the only callers are the adapter and the tests. The alternative was to keep the loose arguments.
- **Row ↔ `ResolvedEvent` conversion:** the adapter (`src/bin/chainfold/signature_cache.rs`) copied the fields by hand in both directions. Two `From` impls in `event_signature_cache.rs` now own the conversion, and the adapter calls them. That adds a dependency from the EVM layer on `signatures`, which is the right direction because `signatures` stays standalone.
- **32-byte topic check:** it was written inline in the cache method. It now lives on `Topic` as `Topic::from_slice`.
- **Reading the row:** the hand-written `query_map` + `rows.next()` + `match` is now `query_row(..).optional()`, and the topic is parsed inside the row closure. The outer binding is now `found`, so it no longer shares the name `row` with the closure's argument.
- **Tests:** `TOPIC0` is a `Topic` const and there is a new `CHAIN` const. Tests compare whole rows, and the two round-trip tests share one `assert_round_trips` helper. A new test, `signature_malformed_topic_reads_as_miss`, pins the existing behaviour (a topic that isn't 32 bytes reads as a miss) before the parsing moved.

**Planned** in `TODO.md`, under "Unsmell follow-ups — `EventSignatureRow` struct change (2026-11-01)":
- the `(chain_id, address, event_name)` key that travels as three loose values;
- the adapter's error mapping and key conversion, each written twice;
- `signature` and `topic0` being stored separately, so they can disagree;
- `ResolvedEvent.topic0` being a raw `[u8; 32]`;
- `EventSignatureCache::open`, which nothing calls, and its `path: &str`;
- the module, type, `open` and `open_in_memory` docs, the "abi null" and "zero-network" facts stated in several places, and the "Adapter:" doc;
- the same hand-written row read and inline 32-byte check in `erc20_cache.rs`.

I also marked the existing `EventSignatureRow → named struct` entry in `TODO.md` as done, since your change implements it. The "Suggested next batch" paragraph further down still lists it; I left that alone.

**Discarded**
- The malformed-topic test spells out the table's columns a second time. That is deliberate: the test has to plant a row the typed insert cannot write.
- The duplication between `EventSignatureRow` and `ResolvedEvent` is the intended layering, since `signatures` is source-agnostic. Its real problem, the conversion having no single owner, is fixed above.

**Verification:** `cargo test --features cli` passes and `cargo clippy --features cli --all-targets` shows no warnings in these files. The changes also touch `src/evm/types.rs` and `TODO.md`.