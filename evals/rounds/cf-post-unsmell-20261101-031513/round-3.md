I fixed every finding on the changed lines in the event-signature cache change and moved the rest into `TODO.md`. All 195 tests pass (`cargo test --all-features`), clippy reports nothing in the touched files, and nothing is staged or committed.

**How the run went:** one fresh agent read all 3 changed files whole. A cross-file agent wasn't needed, since there was only one batch. Two fresh re-check agents followed. The last re-check's one finding was a sentence to delete, which I deleted; I didn't run another re-check for a deletion.

```
Survey   3 files read whole · 27 declarations inventoried · 1 lock inventoried, 0 oversized · 1 parameter table, 0 shared context columns (1 key clump, already planned) · 2 misplaced rules · 1 request-scoped value threaded (planned) · 3 inputs at the edge, 0 unparsed on changed lines · 6 repeated literals, 7 repeated expressions, 3 facts stated twice · 11 functions split by role, 0 mixing roles, 0 pass-throughs · 17 doc items checked, 0 with an effect or exit missing, 1 leaking mechanism
```

**Rewrote**
- `event_signature_cache.rs` `get_event_signature`: "Returns the row cached for `event_name` on the contract at `address` on chain `chain_id`. Returns `None` when no row is cached, or when the cached row's topic is not 32 bytes long."
- `event_signature_cache.rs` `insert_event_signature`: "Stores `row` for `event_name` on the contract at `address` on chain `chain_id`. It replaces any row already cached for the same event name, contract and chain."
- `event_signature_cache.rs` `from_sql`: "Reads the cached entry from one result row of an `event_signatures` query. It returns `None` for a malformed row, as [`EventSignatureCache::get_event_signature`] describes."
- `event_signature_cache.rs` `COLUMNS`: "The `event_signatures` columns that a row fills. [`Self::sql_values`] binds them in this order."
- `cache.rs` `ToSql for Topic`: "`Topic` persists as its 32 raw bytes in a `BLOB` column. It has no `FromSql`, because each reader decides what a stored topic of the wrong length means."

**Fixed**
- `event_signature_cache.rs` `EventSignatureRow`: the column names were written separately in the SELECT, the INSERT and the reader, and the binding of fields to SQL values sat in the cache. The row now owns `COLUMNS` and `sql_values` next to `from_sql`. Both queries use them, and the INSERT placeholders are counted from the bound values.
- `cache.rs`: added `impl ToSql for Topic` next to the `ChainId` and `FilterHash` impls, so the row binds `topic0` directly.
- `types.rs`: replaced the new `Topic::try_from_slice -> Option` with the standard `TryFrom<&[u8]>`. `TODO.md` entries that mentioned the old name now say `Topic::try_from`.
- `event_signature_cache.rs` tests: the row and the in-memory cache were built inline three times each. They now go through `row(..)` and `cache_with(..)` helpers.
- The INSERT and SELECT now bind the key the same way (`params!`).
- The "malformed topic reads as a miss" rule is now stated only on `get_event_signature`. The other docs point to it.

**Planned** (in `TODO.md`, under "Unsmell follow-ups — `EventSignatureRow` SQL binding (2026-11-01, third pass)")
- `EventSignatureRow` and `ResolvedEvent` are twin structs. I recommend merging them once the existing "`ResolvedEvent.topic0: [u8; 32]`" entry is decided. Since the plan already chose a separate struct with a `Topic` field, I planned this instead of merging.
- `types.rs`: the docs on `Topic::b256` and `EvmEvent` explain why callers want them. These lines weren't changed in this run.
- `types.rs`: `FilterHash::as_bytes` and `as_slice` return the same bytes. These lines weren't changed in this run either.
- I also replaced the stale line number in the existing `EventSignatureCache::open` entry with the function's name.

**Discarded**
- Converting the topic bytes inline (`b256().0` and `Topic::new(B256::from(..))`): the two `From` impls are the right place for it. A third constructor would also make the planned "two constructors per newtype" smell worse.
- The `(chain_id, address, event_name)` lookup key, the duplicated adapter error mapping, `signature` and `topic0` being able to disagree, and the various module and type docs: all of these are already in `TODO.md`.