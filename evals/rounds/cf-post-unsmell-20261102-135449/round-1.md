I ran the "patches only" pass: I wrote 8 patches and left your working tree and index as they were (still your original 2-file diff). Since nothing was merged, I asked no questions and ran no tests or re-check.

There are two things you should know first:

- **The build check I gave the editors at first did nothing.** Plain `cargo check --all-targets` never compiles the evm/cli code, because those features are off by default. One editor caught it. I then re-ran every patch with `cargo check --all-targets --all-features`, and all 8 pass (the only warning is the existing note about `proc-macro-error2`).
- **TODO.md lines 83-86** ("`EventSignatureRow` → named struct") describe exactly what your change already does. That entry is now obsolete, and I left it alone.

```
Survey   2 files read whole · 37 declarations inventoried · 1 lock inventoried, 0 oversized · 2 parameter tables, 3 shared columns (the lookup key) · 2 misplaced rules · 3 request-scoped values threaded · 3 inputs at the edge, 1 unparsed · 4 repeated literals, 5 repeated expressions, 5 facts stated twice · 8 functions split by role, 1 mixing roles, 0 pass-throughs · 9 doc items checked, 2 with an effect or exit missing, 3 leaking mechanism
Rewrote  src/evm/cache/event_signature_cache.rs:21  "The keccak256 hash of `signature`."
Rewrote  src/evm/cache/event_signature_cache.rs:23  "JSON of the matched ABI event item. None on rows written before the column was added."
Rewrote  src/evm/cache.rs (new)  "Stores a topic as its 32 raw bytes in a `BLOB` column."
Rewrote  src/evm/cache.rs (new)  "Reads a topic from a 32-byte `BLOB` column. Errors when the value is not a blob or has another length."
Fixed    event_signature_cache.rs:78   data clump → insert_event_signature takes &EventSignatureRow                         [t1]
Fixed    event_signature_cache.rs:59   unparsed input → FromSql/ToSql for Topic beside ChainId/FilterHash; query_row().optional()  [t1]
Fixed    event_signature_cache.rs:173  repeated derivation → const TOPIC0: Topic                                            [t1]
Fixed    event_signature_cache.rs:20,22  tautological / vague field docs → rewritten as above                             [t1]
Behaviour event_signature_cache.rs:59  a topic0 blob that is not 32 bytes now errors instead of reading as a cache miss   [t1]
Asked    event_signature_cache.rs:15   EventSignatureRow copies ResolvedEvent → recommend B, From impls in the lib (patch t2, stacked on t1); alternative A, the cache stores ResolvedEvent and Topic leaves the cache layer
Planned  event_signature_cache.rs:50   (chain_id, address, event_name) clump → EventKey through trait, resolver and cache; changes pub API, 6 files ±75 (patch t3)
Planned  signature_cache.rs:37,56      duplicated map_err → private cache_error fn (patch t4)
Planned  event_signature_cache.rs:79   name hides INSERT OR REPLACE → rename to put_event_signature + doc (patch t5)
Planned  event_signature_cache.rs:36   EventSignatureCache::open has no callers → delete; pub API (patch t6, with b1-12)
Skipped  event_signature_cache.rs:1-8  module doc: naming history and the caller's reason → score 4 (patch t7)
Skipped  event_signature_cache.rs:36-45  open/open_in_memory docs narrate → score 3 (patch t6)
Skipped  event_signature_cache.rs:tests  repeated fixture literals → score 3 (patch t8)
```

- **All 13 findings are accounted for:** 5 fixed, 1 asked, 4 planned, 3 skipped, 0 still open.
- **Planned items:** under "patches only" I did not write the PLAN entries into TODO.md. They exist only as `decisions.yaml` entries and patches until someone merges them.
- **Order:** t2, t3, t4, t5 and t8 build on t1, so apply t1 first. t6 and t7 apply to your changeset as it is now.
- **Cross-file agent:** the changeset is a single batch, so there was nothing for it to compare, and I didn't run it.
- **Next steps:** merge t1, answer the t2 question, then run tests and clippy. Clippy pedantic may flag `cache_error` in t4 with `needless_pass_by_value`.

Verification: `cargo check --all-targets --all-features` passes on every patch. I didn't run tests or clippy.

Everything is in `.git/unsmell/20261102-135509/`: `batches.yaml`, `inventory/`, `findings/`, `decisions.yaml` and `fixes/t1.patch` … `t8.patch`. The shared build directory `target/` in there takes about 1 GB; you can delete it.