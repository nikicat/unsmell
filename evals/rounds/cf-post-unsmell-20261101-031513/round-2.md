I fixed all 9 findings on the changed lines and then 4 more that the re-check turned up. The other findings were either already planned in TODO.md or sat on unchanged lines, so I added them to TODO.md as plan entries. All tests pass.

Two departures from the full process:
- **No cross-file agent.** The changeset was a single batch, so there was nothing across batches for it to compare.
- **Second re-check done by me.** I checked the last 4 fixes myself (two doc lines and one test local) rather than starting another fresh agent.

**Survey:** 3 files read whole · 26 declarations inventoried (9 flagged) · 1 lock, 0 oversized · 2 parameter tables, 1 shared column (the event key, already planned) · 0 new misplaced rules · 1 group of per-request values threaded (planned) · 4 inputs at the edge, 1 unparsed (`row.get` by position) · 6 repeated literals, 8 repeated expressions, 2 facts stated twice · 12 functions split by role, 1 mixing roles, 0 pass-throughs · 33 doc items checked, 2 missing an effect or exit, 1 leaking mechanism.

**Rewrote**
- `event_signature_cache.rs:52`: "Reads the cached entry from `row`, one result row of an `event_signatures` query. Returns `None` instead of an error when the stored topic is not a valid [`Topic`] (see [`Topic::try_from_slice`])."
- `get_event_signature`: "Returns the row cached for `event_name` on the contract at `address`, or `None` when no well-formed row is cached."
- `insert_event_signature`: "Stores `row` for `event_name` on the contract at `address`, replacing any row already cached for it."
- `assert_miss`: "Asserts that looking up `event_name` in `cache` finds nothing."

**Fixed**
- **`types.rs:78`, misleading name:** `Topic::from_slice` is now `try_from_slice`. The function returns `Option`, but alloy's `B256::from_slice` with the same name panics.
- **`event_signature_cache.rs:84-102`, positional columns and an inline rule:** a new private `EventSignatureRow::from_sql` reads columns by name and owns the "malformed topic reads as a miss" rule. `get_event_signature` just hands it to `query_row`.
- **`get_event_signature` / `insert_event_signature`, missing docs:** both now state the `None` case and the replace-on-conflict effect.
- **`:89`, comment naming "the resolver":** removed. It said how `resolve_event` behaves after a miss, and `resolve_event`'s own doc already says that.
- **Malformed-topic test, raw SQL duplicating the schema:** it now inserts through the API and corrupts only one column (`UPDATE … SET topic0`). The duplicated `'Short'` and `0xDD` literals are gone.
- **Tests, repeated miss check:** added an `assert_miss` helper and bound `event_name` once.

**Planned** (in TODO.md, new section "Unsmell follow-ups — `src/evm/types.rs` docs and constructors")
- Unchanged lines of `types.rs`: the module doc and the long or compressed type docs, two constructors per newtype, raw integers in `EvmPosition::new`, the `decimals` that must agree, and the repeated fields in `Erc20Transfer/Mint/Burn`.
- `log_cache.rs:446`: `B256::from_slice` panics if a stored topic is too short.
- I also updated the existing `erc20_cache` entry to use the new `try_from_slice` name.

**Discarded**
- **Copies in `From<&ResolvedEvent>`:** it copies two short strings on each `put`, which only happens after a network fetch, so the cost doesn't matter. It also isn't one of the smells this review covers.
- **`open_in_memory().unwrap()` appearing 3 times:** it's one call per test, and wrapping it would just add a pass-through.
- **Already planned in TODO.md:** the event-key clump, the duplicated adapter error mapping, `signature`/`topic0` being able to disagree, `ResolvedEvent.topic0` stored as `[u8;32]`, the unused `open`, the module and type docs, and `erc20_cache`.

**Verify:** `cargo test --all-features` passes (114 lib tests plus the integration tests). `cargo clippy --all-features --all-targets` reports nothing in the changed files; the warnings it does show are in `examples/` and `log_index.rs` and were there before. `cargo doc` is clean. Nothing is staged or committed.