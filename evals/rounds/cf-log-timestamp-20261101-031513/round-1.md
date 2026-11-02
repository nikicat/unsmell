I cleaned up the timestamp change in all three files. The third fresh re-check found nothing more to fix, and the tests pass. Nothing is staged or committed.

**How it ran:** two survey agents read the three changed files whole, one agent compared their findings across files, and three fresh agents re-checked the fixes. Because you said "fix everything", I made the choices myself instead of asking; each is listed below.

**Survey:** 3 files read whole · 46 declarations listed · 2 locks, 1 too big (the `OnceLock` self-reference) · 2 shared parameter groups (provider + store, address + topics) · 6 rules in the wrong place · 8 inputs from outside the program, 5 used without parsing · 16 repeated literals and 14 repeated expressions · 5 facts stated twice, the worst one 5 times · 10 changed functions checked, 4 doing more than one job, 0 that only pass through · 45 doc comments checked, 5 missing an effect or error, 10 describing the wrong layer.

**Rewrote:**
- `src/evm/cache.rs:240`: "The block time of the log in unix seconds, as the provider put it on the eth_getLogs response. Most providers leave it out. It is NULL then, and also on rows written before this column existed."
- `src/evm/history.rs` `log_timestamp`: "Returns the block time of `log`, in unix seconds. Uses the timestamp the provider put on the log when there is one, and the block header otherwise. Errors as [`ensure_block_header_via`] does when the header is needed."
- `TimestampSource`: "Where the block time of a log comes from. Both the per-log lookup and the fetcher's header prefetch decide by it, so they agree on which headers are read."
- `blocks_needing_header`: "Returns the numbers of the blocks whose header [`log_timestamp`] reads for `logs`."
- `log_block_number`: "Returns the number of the block that holds `log`. A pending log has no block number and counts as block 0."
- `log_columns!`: "Expands to the `cached_logs` columns that hold one [`Log`], in the order the INSERT in [`LogCache::insert_logs`] binds them."
- `row_to_log`: "Decodes a row selected with [`log_columns`]."
- The test doc in `history.rs`: "A log that carries its own timestamp is stamped without its block header. No header for block 150 is cached and the mock provider answers no `get_block_by_number`, so a header lookup would fail the stream."

**Fixed:**
- `history.rs`: the rule "use the log's own timestamp, otherwise the header's" was written in three places (the `iter` closure, `log_to_evm_event` and the fetcher). Now `TimestampSource::of` decides it once. `log_timestamp` and `blocks_needing_header` both use it.
- `history.rs` `log_to_evm_event`: it no longer puts in a 0 timestamp for the caller to overwrite later. It takes the resolved timestamp as an argument.
- `history.rs` `build_fetcher`: the loop that both chose which logs need a header and fetched them now gets its list from `blocks_needing_header`.
- The "skip the header fetch" fact was explained in five comments. `log_timestamp` now owns it, and the other four comments are gone.
- `log_cache.rs`: the column list was written out in the INSERT and in both SELECTs. It is now one `log_columns!` macro used through `concat!`.
- `log_cache.rs` `row_to_log`: it read columns by position, as in `row.get(11)`. It now reads them by name.
- Tests:
  - the new history test reuses `warm_cache()` instead of rebuilding its setup;
  - the stamped test log is built once, in a `make_stamped_log` fixture with a `BLOCK_150_TS` constant and a `BH_150` constant;
  - the cache test's repeated literal became a local, and its comments that restated the code are gone.
- I added a test for the fetcher's skip, `blocks_needing_header_skips_logs_with_timestamp`. The change had no test for it.

**Behaviour:** one small change. In `history.rs`, a log with no block number used to be left out of the fetcher's header prefetch, while the per-log lookup read block 0 for it. Now both treat it as block 0, so the prefetch warms the header that the lookup will read.

**Planned:** 41 findings went to `TODO.md` under "Smells left by the `cached_logs.block_timestamp` change". Each is on lines the change did not touch, or needs a bigger refactor. The ones you would most likely want next:
- There is no single parsed type for a log fetched over RPC. Missing fields silently become 0, and `transaction_hash` is optional while its column is `NOT NULL`. A log with no block hash gets two different answers: the cache skips it, but the event conversion uses all zeros.
- `provider` and `store` are passed into every header lookup. They want one `HeaderSource` type.
- The column list in `log_cache.rs` must still match the `?1 … ?13` placeholders and the parameter order by hand.
- Blocks that hold several logs get their header looked up once per log.
- The doc on `CACHE_VERSION` says to bump it on every schema change, but this change (correctly) adds a migration without a bump.

**Discarded:** 5 findings:
- The "bump `CACHE_VERSION`" item is not a bug: the migration covers the schema change, and old rows come back NULL. Only the doc needs fixing, which is planned.
- The re-check's "`provider`/`store` missing receiver" and "column list still split" findings were already planned.
- The two survey agents' "facts stated five times" findings were the same finding.
- The re-check's "`GENESIS_TS + 1800` twice" was fixed by the shared test fixture.

All 87 findings that the agents returned are accounted for above, and none is still open.

**Verification:** `cargo test --all-targets --all-features` passes (114 library tests), and `cargo fmt` was run. `cargo clippy --all-targets --all-features` gives no warnings in the changed files. The only warnings are older ones in `src/evm/log_index.rs` and `examples/`.