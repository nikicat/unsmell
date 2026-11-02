I fixed every smell on the lines this change touched. Findings on untouched lines went into `TODO.md` under a new heading, "Smells found by the second unsmell run on the `block_timestamp` change". The full test suite passes (`cargo test --all-features`), and clippy and rustdoc show no new warnings on these files.

**Survey:** I read all 3 files whole, using two survey agents (one for the cache files, one for `history.rs`), one cross-file agent and three re-checks.
- **Declarations:** 68 inventoried.
- **Locks:** 2, none oversized.
- **Parameter tables:** 3, with 3 shared context columns: provider+store, address+topics, `filter_hash`.
- **Misplaced rules:** 13.
- **Request-scoped values passed around:** 1.
- **Inputs at the program's edge:** 12, of which 7 are not parsed into a domain type.
- **Repeats:** 14 literals, 15 expressions and 17 facts stated twice.
- **Role pass:** 17 functions split by role, 2 doing more than one job, 0 pass-throughs.
- **Doc items:** 51 checked. 10 are missing an effect or error case, and 8 describe mechanism.

**Rewrote**
- `src/evm/cache/log_cache.rs:17`: "Expands to the `cached_logs` columns that hold one [`Log`]. The INSERT in [`LogCache::insert_logs`] binds its parameters in this order."
- `log_cache.rs:26`: "Expands to a query that selects [`log_columns`] from `cached_logs`, with the given clauses after the FROM. [`row_to_log`] decodes its rows."
- `log_cache.rs:442`: "Decodes a row selected with [`select_logs`]."
- `src/evm/history.rs:505`: "Returns the timestamp of the block that holds `log`. Errors as [`ensure_block_header_via`] does when the log carries no timestamp of its own."
- `history.rs:525`: "Where the timestamp of a log's block comes from. Because [`log_timestamp`] and [`blocks_needing_header`] both decide by it, the second lists exactly the headers that the first reads."
- `history.rs:530`: "The timestamp the provider put on the log." (on `Log`) and "The header of the block with the given number." (on `Header`)
- `history.rs:543`: "Returns the number of the block whose header has to be read, if any."
- `history.rs:553`: "Returns the numbers of the blocks whose header [`log_timestamp`] reads for `logs`, once per log."
- `history.rs` tests: "The block of [`make_stamped_log`]. [`warm_cache`] holds no header for it." / "The timestamp that [`make_stamped_log`] carries. It differs from every header timestamp in [`warm_cache`]." / "Returns a log that carries its own timestamp."

**Fixed**
- `log_cache.rs:179, 203`: the `SELECT … FROM cached_logs` prefix was written twice. Both queries now use a `select_logs!` macro.
- `log_cache.rs:17`: the doc gave the column order as the order in which a caller binds them. It now states the order as the INSERT's contract.
- `history.rs` new docs:
  - "Block time" was ambiguous, because in this file it means the seconds between blocks. The new docs say "timestamp of the block".
  - "In unix seconds" repeated `arch::Timestamp`'s own doc, so I dropped it.
  - "The provider put it on the log" appeared on both `TimestampSource` and `log_timestamp`. `TimestampSource` now owns it.
  - Its doc used plain words for the functions it serves; it now links them.
- `history.rs:543`: `blocks_needing_header` matched on `TimestampSource`'s variants itself. That rule now lives on the type as `TimestampSource::header_block`.
- `history.rs` tests:
  - The literals `150`, `149` and the names `BH_150`, `BLOCK_150_TS` now come from `STAMPED_BLOCK`, `BH_STAMPED` and `STAMPED_TS: Timestamp`.
  - The `backend` + `Hist::new` setup was copied six times, and the new test added the sixth. A `make_hist` helper replaces all six.

**Behaviour**
- `history.rs:646`: the fetcher now looks up block 0's header for a log with no block number; before the change it skipped such logs. I first added a filter to restore the skip. The re-checks showed that this put a second "is this log mined" rule outside `TimestampSource`, which made its "exactly" claim false. So I took the filter out and left the change's behaviour as it was. The cost is at most one wasted RPC whose error is ignored, and `eth_getLogs` does not normally return such logs. The real fix is the planned `MinedLog` type.

**Planned** (in `TODO.md`, under the new heading):
- **Bug:** `versioned_path("./foo")` returns `".v3./foo"`, because it splits at the dot in `./`.
- **Wrong claim:** the schema comment says reorged logs are excluded from all cache queries, but `get_log_by_ref` does not check `reorged_blocks`. The same fact is stated about five times.
- **Rows read by position:** `get_scanned_ranges`, `compact_ranges` and `get_block_header` still read columns by index, while `row_to_log` now reads them by name.
- **Missing receiver:** `filter_hash` is passed into seven `LogCache` methods, and `EvmLogHistory` keeps it as a sibling field of the store.
- **Inline machinery:** `compute_gaps` is an interval difference written inline.
- **Unnamed tuples:** four tuple return and row types in the cache.
- **Cache docs:** imperative openings, tautologies, docs that give a caller's reason, and long schema comments.
- **History:**
  - the stale comment in `update_tip_to`;
  - two expressions written more than once (`map_err`, `0x` formatting);
  - a hand-written cancellation `select!`;
  - an `Ok`/`Err` match that `?` would replace;
  - the `apply_topics` and warmup-test comments.
- **Prefetch:** the block-0 prefetch above, as part of the `MinedLog` item.

**Discarded**
- The re-check finding about "the stamping reads block 0's header without a prefetch". `iter` only stamps logs from the cache, and every cached log has a block number, so this cannot happen.

**Accounting:** 89 findings in total. 12 fixed, 1 behaviour change kept and planned, 1 discarded, 33 newly planned, and 42 matched entries that were already planned. None is still open.

I staged and committed nothing.