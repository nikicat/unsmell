I fixed four smells on the changed lines and planned seven more in `TODO.md`. All tests pass with `--all-features`, and a fresh re-check of the fixed code found nothing more to fix.

**Fixes**
- **The insert is a plain SQL string again.** `insert_event_signature` was building its SQL at run time from a shared column list, a separate list of values that had to stay in the same order, and generated `?` placeholders. It is now one fixed `INSERT … VALUES (?1..?6)` with `params!`. I removed `EventSignatureRow::COLUMNS` and `sql_values()` and the imports only they used.
- **The select is a plain SQL string again.** `get_event_signature` no longer runs `format!` on every call before `prepare_cached`.
- **`from_sql` is now `from_row`.** The old name suggested rusqlite's `FromSql` trait, but it maps a whole result row. Its doc only pointed back at `get_event_signature`, which states the "returns `None` when the topic is not 32 bytes" rule, so I deleted it.
- **The `ToSql for Topic` doc no longer opens with its own name.** It now reads: "Persists a topic as its 32 raw bytes in a `BLOB` column. There is no `FromSql`, because each reader decides what a stored topic of the wrong length means."

**Two choices made under "fix everything"**
- I put the fixed SQL strings back instead of keeping one shared column constant. The other option was a `const` SQL string built from the column list. The column names still appear in two places, the `SELECT` text and the names `from_row` reads, but they no longer have to be in the same order. The round-trip tests cover them.
- The malformed-topic rule now lives only on the public `get_event_signature` doc, not on the private helper.

**Planned:** I added five entries under "Unsmell follow-ups — `EventSignatureRow` SQL binding (2026-11-01, fourth pass)" in `TODO.md`. They cover seven findings, all on unchanged lines:
- `CacheDb::open` and `open_in_memory` share the same body.
- The `ToSql` impl docs give the same reason three times, and two of them are long.
- The `CacheDb::open` docs are imperative ("Open a cache…").
- Three stale names in `types.rs` docs: the "block/tx" types in the module doc, `OwnedErc20` in a section header, and the old field names in the `EvmPosition` sentinel.
- `log_cache.rs` copies topic bytes before binding instead of binding the `Topic` directly.

**Discarded:**
- The key columns appear in both the `WHERE` clause and the insert column list. That is just how SQL is written, and the schema's primary key is the owner.
- The `ToSql` bodies of `FilterHash` and `Topic` are the same one line, but only by coincidence.
- The repeated key binding `params![chain_id, address, event_name]` and the near-identical `EventSignatureRow` and `ResolvedEvent` structs are already planned in `TODO.md`.

Every survey finding ends up in one of these groups.

**Survey:** the survey agent read 4 files whole and recorded 33 declarations. Its other counts:
- **Locks:** 1, none oversized.
- **Parameter tables:** 3, with 0 shared context columns.
- **Misplaced rules and threaded values:** 1 misplaced rule and 1 request-scoped value threaded through calls (the event key, already planned).
- **Program inputs:** 2, 1 unparsed.
- **Repeats:** 4 literals, 10 expressions and 6 facts stated twice.
- **Functions:** 2 mixed roles, with 0 pass-throughs.
- **Docs:** 22 checked, 0 missing an effect or exit, 3 leaking mechanism.

There was only one batch of files, so I skipped the cross-file agent: it compares inventories between batches, and there was nothing to compare.

**Verification:** without features, `cargo test` silently skips the `evm` module, so the first run checked nothing. With `--all-features`, every suite passes, including the 4 `event_signature_cache` tests. `cargo clippy --all-targets --all-features` warns only about files outside the changeset (`log_index.rs` and the examples).

Nothing is staged or committed.