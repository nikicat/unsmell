I ran the survey and wrote a patch for every task. As you asked with "patches only", nothing is merged into your working tree, nothing was re-checked after a merge, and no questions were asked. Your two modified files are exactly as they were.

**Survey:** 2 files read whole. 18 declarations inventoried. 1 lock inventoried, 0 oversized. 2 parameter tables covering 8 functions, with 1 shared-context group: the cache key, found as b1-6. 0 misplaced rules. 0 request-scoped values threaded. 5 inputs at the edge, 1 unparsed: the `topic0` blob, found as b1-2. 6 repeated literals, 6 repeated expressions, 1 fact stated twice: the `abi_json` migration. 6 functions split by role. 11 doc items checked, 1 with an effect or exit missing (the transitional `None`) and 1 leaking mechanism.

The changeset is two files, so one batch covered all of it. With only one batch, nothing can span two batches, so the cross-file findings file is empty by construction and I didn't run that agent.

**Tasks and patches** (in `.git/unsmell/20261102-023051/fixes/`)

| Task | Decision | Patch | What it does |
|--|--|--|--|
| t1 (b1-2, b1-3, b1-4) | FIX | `t1.patch` | • Adds `ToSql` and `FromSql` for `Topic` in `src/evm/cache.rs`, beside the ones for `ChainId` and `FilterHash`.<br>• `get_event_signature` now reads straight into `EventSignatureRow` with `query_row(..).optional()`. The tuple, the 32-byte length check and `B256::from_slice` are gone.<br>• Adds a round-trip and wrong-length test.<br>• The test constant `TOPIC0` is now a `Topic`, which removes the three `Topic::from(TOPIC0)` calls.<br>• Rewrites the two field docs. |
| t2 (b1-1) | ASK, stacked on t1 | `t2.patch` | `insert_event_signature` takes `row: &EventSignatureRow` in place of its three loose fields. The adapter builds the row, and each test does one `assert_eq!` on the whole row. |
| t3 (b1-6, b1-8) | PLAN | `t3.patch` | Adds a section to `TODO.md` called "Unsmell run 2026-11-02 (`EventSignatureRow` struct)" with the cache-key clump and the module doc. It also removes the TODO entry "`EventSignatureRow` → named struct", which your changeset completes. |
| t4 (b1-5) | SKIP, score 3 | `t4.patch` | Adds `From<[u8; 32]>` conversions for `Topic` in both directions, so the adapter no longer goes through `B256`. |
| t5 (b1-7) | SKIP, score 3 | `t5.patch` | Moves the error-mapping closure in the adapter into a named `cache_error` function. |
| t6 (b1-9) | SKIP, score 2 | `t6.patch` | Rewords short docs that are true as written. |

**Docs rewritten by the FIX patch (t1):**
- `EventSignatureRow.topic0`: "The keccak256 hash of the signature. A log of this event carries it as its first topic."
- `EventSignatureRow.abi_json`: "The JSON of the matched ABI event item. `None` for rows written before the cache stored it."
- The `FromSql for Topic` doc: "Reads a `Topic` back from its 32-byte `BLOB`. Errors when the value is not a `BLOB`, or with `FromSqlError::InvalidBlobSize` when the blob is not 32 bytes long."

**Behaviour change in t1:** a stored `topic0` that isn't 32 bytes now returns `CacheError::Sqlite`. Today it reads as a cache miss and the signature is resolved again over the network. A corrupt cache row now shows up as an error instead of being silently ignored.

**Decision for you (t2):** applying it changes the signature of `chainfold::evm::EventSignatureCache::insert_event_signature`, which is public. Your changeset already changed that signature, and the adapter is the only caller in the repo. Each write would also clone two strings, but it only runs after a network fetch. I'd take it.

**Discarded:** none.

**Build check:** `cargo check --all-targets --features cli` passes for every patch, including t2 applied on top of t1. The first checks I gave the editors didn't prove anything. The `chainfold` binary needs `--features cli`, so plain `--all-targets` never compiles the adapter. On top of that, the shared target directory reused one worktree's library build for another. I re-ran t1 and t1+t2 one at a time with the feature on and fresh timestamps, and the t4 to t6 editor did the same for its worktrees. Tests and clippy were not run.

Run directory: `.git/unsmell/20261102-023051/`. All 9 findings have an entry in `decisions.yaml`, and none is open.