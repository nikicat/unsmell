I made six small fixes, all to doc comments and a test fixture, and added two new entries to `TODO.md`. Tests pass and clippy shows no new warnings. Nothing is staged or committed. This is the fourth pass on this change, so most of what the agents found was already in `TODO.md`.

```
Survey   7 files read whole · 43 declarations inventoried · 4 locks inventoried, 0 oversized · 7 parameter tables, 4 shared context columns (all already planned) · 11 misplaced rules (1 new) · 1 request-scoped value threaded (planned) · 13 inputs at the edge, 4 unparsed (planned) · 22 repeated literals, 18 repeated expressions, 5 facts stated twice (3 new) · 31 functions split by role, 2 mixing roles (planned), 0 pass-throughs · 17 doc items checked, 0 with an effect or exit missing, 0 leaking mechanism
```

**Rewrote**
- `src/evm/cache/log_cache.rs:17` "Expands to the `cached_logs` columns that hold one [`Log`]. The list leaves out `filter_hash`, which keys the row rather than the log."
- `src/evm/cache/log_cache.rs:26` "Expands to a query that selects [`log_columns`] from `cached_logs`, with the given clauses after the FROM."
- `src/evm/cache.rs:241` "The block time of the log in unix seconds, as the provider put it on the eth_getLogs response. The column is NULL when the provider leaves the time out, and on rows written before the column existed."
- `src/evm/history.rs:534` "The source of the timestamp of a log's block. [`log_timestamp`] and [`blocks_needing_header`] both decide through this type whether a log needs its block header, so they never disagree."
- `src/evm/history.rs:775` "Returns a history over the [`warm_cache`] logs, from the earliest cut through the end of block 200. Block 200 is the last block that the cache has scanned."

**Fixed**
- `log_cache.rs:18`, wrong-layer doc: the old text named its caller, `insert_logs`, and gave the wrong bind order (the parameters bind as `?2..?13`, not `?1..?12`). It now states the fact that explains the offset.
- `log_cache.rs:27`, duplicated knowledge: the doc of `select_logs!` and the doc of `row_to_log` both stated that the two go together. `row_to_log` now owns that fact.
- `cache.rs:242`, compressed doc: "It is NULL then, and also…" is now one plain sentence.
- `history.rs:534`, duplicated knowledge: "where the timestamp comes from" appeared twice in two sentences. The re-check then found an unclear "it" in my first rewrite, and that is fixed too.
- `history.rs` tests, repeated derivation: four tests repeated the same setup, ending in `warm_cache → make_history → hist(earliest, end of block 200)`. They now call one new fixture, `warm_hist()`.
- `history.rs:725`: `BH_STAMPED` moved next to `STAMPED_BLOCK` and `STAMPED_TS`.
- `history.rs:775`, compressed doc in the new `warm_hist` doc (found by the re-check).

**Planned** (`TODO.md`, under "Smells found by the fourth unsmell run…")
- `arch.rs:225`: every history source still converts itself to `Arc<dyn HistBackend>` by hand before calling `Hist::new`. That is about 25 sites, in matcher, merge, the combinators and four test files, none in the changeset. I planned this instead of fixing it despite "fix everything", because it changes the public `Hist::new` signature across 10 files that the change never touched. The entry recommends making `Hist::new` generic; the alternative is a second generic constructor beside it.
- `history_explorer.rs:258-293` and `events.rs:72-105`: the example and the `chainfold` binary each have their own copy of the forward walk and the follow loop, and this change had to edit both the same way. Fixing it needs a shared helper that both can use.

**Discarded**
- `log_cache.rs:17`, "hold one Log" read as a repeat of the schema comment in `cache.rs`: the doc says what the column list is, not the schema's 1:1 rule.
- `EvmLogHistory::hist` takes two `EvmPosition` arguments in a row, which could be swapped by mistake: it copies the shape of `Hist::new`.
- `let hist = …; hist.iter()` binds a variable used only once: it is not left over from the change, and it reads fine.
- About 30 findings from the four agents (three survey, one cross-file) matched entries already in `TODO.md`, so I left them there.

Every finding is accounted for and none is still open. The first re-check found the two doc problems above. A second re-check of those rewrites found nothing.

**Verification:** `cargo test --all-features` passes (all suites, 0 failed). `cargo clippy --all-targets --all-features` shows only the 5 warnings that were there before, all on unchanged lines.