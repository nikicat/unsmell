I made a patch for each task and stopped there, as "patches only" asks. Nothing is merged into your working tree, which still has only your three modified files. No tests, clippy or re-check ran, and no question was asked. Each patch built with `cargo check --all-targets` in its own worktree, and all of them apply cleanly to your current tree with `git apply --check`.

**Survey** (two survey agents plus one cross-file agent; numbers summed from their inventory files) — 3 files read whole · 86 declarations inventoried · 1 lock inventoried, 0 oversized · 3 parameter tables, 5 shared context columns · 4 misplaced rules · 1 request-scoped value threaded · 12 inputs at the edge, 8 unparsed · 13 repeated literals, 9 repeated expressions, 4 facts stated twice · 10 functions split by role, 5 mixing roles, 0 pass-throughs · 45 doc items checked, 3 with an effect or exit missing, 5 leaking mechanism

**Patches** (in `fixes/`)
- **`t1.patch` (FIX).** Covers b2-1, b2-2, b2-3, b2-4, b2-5, cross-1, b1-1, b2-7, b2-8 and b2-16.
  - The rule "use the log's own timestamp, otherwise the block header's" was written three times in `history.rs`. It is now one `log_timestamp` function.
  - `log_to_evm_event(log, timestamp)` no longer sets 0 to mean "unknown". Zero is also a real genesis timestamp, so the old placeholder was ambiguous.
  - The prefetch loop calls `log_timestamp` instead of having its own skip.
  - That rule was stated in five comments. Its one owner is now the doc of `log_timestamp`.
  - A new `anchored_cache()` test helper replaces the header setup that the new test copied from `warm_cache`.
- **`t3.patch` (FIX, b1-2).** `row_to_log` reads columns by name instead of by position. The SQL statements are unchanged.
- **`t4.patch` (ASK, b1-3).** You added a migration but kept `CACHE_VERSION` at 3, which goes against its doc ("Bump this when cache schema … change"). The patch rewords the doc so that a bump is only for changes a migration can't make. The other option is to bump to 4, which throws away every existing cache file.
- **`t5.patch` (PLAN, b2-10, stacked on t1).** Adds a `BlockHeaders { provider, store }` type that owns header lookups (+85/−87 lines). One drawback: three calls that aren't header reads now go through `headers.provider`.
- **`t6.patch` (SKIP, score 3, b1-4).** Deletes a trailing comment in a test.
- **`tp.patch` (PLAN).** Adds 16 entries to `TODO.md` under "Unsmell run 2026-11-02 (`block_timestamp` on `cached_logs`)". It covers b1-5 to b1-15, b2-6, b2-10 to b2-15, b2-17 and cross-2/cross-3.

**Rewrote** (all inside the patches)
- `src/evm/history.rs` `log_timestamp` (new): "Returns the timestamp of the given log's block. Uses the timestamp the log carries when the provider sent one, and otherwise the block's header from [`ensure_block_header_via`]. Errors as that function does."
- `src/evm/history.rs` `ensure_block_header_via`: "Returns the header of the given block from the cache. On a cache miss, it fetches the header from the provider and caches it. Errors when the provider has no such block."
- `src/evm/cache.rs` migration comment: "The timestamp of the log's block, in seconds, when the provider sent it with the eth_getLogs response. NULL when the provider omits it, and on rows written before this migration."
- `src/evm/cache.rs:36` `CACHE_VERSION` (t4): "Bump this when a change to the cache schema or its semantics cannot be applied to an existing cache by a migration in `migrations`. The version is appended to the DB filename, so a bump abandons every existing cache."
- New test doc: "Checks that a log carrying its own block_timestamp needs no block header. The cache holds no header for block 150 and the mock provider has no reply queued, so a header fetch would fail the walk."
- `anchored_cache` doc: "Returns an in-memory cache holding the block-0 and block-200 headers that `make_history` reads to build its anchor."
- Prefetch comment: "// Warm the header cache so that HistBackend::iter needs no RPC per log."

**Behaviour** (`history.rs`, prefetch loop, t1): a log with no block number now prefetches block 0's header, which `iter` already did, and errors are still ignored. Mined logs always carry a block number, so this shouldn't happen in practice.

**Overruled:** b2-16 was proposed as a SKIP. I moved it into t1 because the new `log_timestamp` doc points to `ensure_block_header_via` for its errors, so that doc has to list them.

**Skipped, no patch:**
- b2-9 (score 4): a test for the prefetch skip. After t1, `iter`'s test covers the shared rule.
- b1-15 (score 4): covered by the TODO entry for parsing logs at the edge.
- b2-18 (score 4): the module doc lists its parts.

All 36 findings have an entry in `decisions.yaml`, and none is open. Run directory: `.git/unsmell/20261102-023052/`.