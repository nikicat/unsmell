I stopped at the patches, as you asked: nothing was merged into your working tree, no question was asked, and no re-check ran. Your two modified files and your index are as you left them. The run made 9 patches. Each one passed `cargo check --all-targets` in its own worktree, but none was tested or linted.

I made two small departures from the skill. With only one batch there was nothing to compare across batches, so I wrote an empty `findings/cross.yaml` instead of running a cross-file agent. I also wrote the TODO.md patch (t9) myself rather than through an editor.

**Survey:** 2 files read whole: `src/evm/cache/event_signature_cache.rs` and `src/bin/chainfold/signature_cache.rs`.

| What was checked | Count | Result |
|---|---|---|
| Declarations | 17 | |
| Locks | 1 | not oversized |
| Parameter tables | 2 | one shared 3-value key, b1-12 |
| Misplaced rules | 1 | b1-1 |
| Inputs at the edge | 3 | |
| Repeated literals | 6 | |
| Repeated expressions | 4 | |
| Facts in comments | 7 | 2 stated twice |
| Functions split by role | 7 | 0 pass-throughs |
| Doc items | 12 | 2 open with their own name; 1 leaves out what its None means |

**Patches to apply** (in `.git/unsmell/20261102-005400/fixes/`):
- **t1** (b1-1 and b1-5, score 7). The Topic BLOB encoding was written by hand inside `get_event_signature` and `insert_event_signature`. The patch adds `ToSql`/`FromSql` for `Topic` in `src/evm/cache.rs`, next to the ones for `ChainId` and `FilterHash`. The row closure now builds `EventSignatureRow` directly, and the tuple, the `len()==32` guard and the match are gone. The test constant `TOPIC0` is now a `Topic`, a test for a wrong-length BLOB is added, and arch.md is updated.
  - **Behaviour change:** a `topic0` BLOB that is not 32 bytes is now an error. Today it is a silent cache miss.
- **t2** (b1-6 and b1-7, score 5). It rewrites the two field docs on `EventSignatureRow` in `event_signature_cache.rs`:
  ```rust
  /// The keccak256 hash of `signature`. Logs of this event carry it as
  /// topic 0.
  /// The JSON of this event's entry in the contract's ABI. It is None on
  /// rows cached before the `abi_json` column was added.
  ```

**Open question (b1-2 and b1-4, score 6), patch t3, built on top of t1 and t2.** Your new `EventSignatureRow` has the same three fields as `signatures::ResolvedEvent`, and the adapter copies one into the other field by field.
- **(a)** Delete `EventSignatureRow`. The cache then returns and takes `&ResolvedEvent`, which also turns `insert_event_signature` into a 4-argument function. Net change is −43 lines. Note that rusqlite's own `[u8; 32]` mapping makes t1's `Topic` impls unnecessary, so t3 removes them again.
- **(b)** Keep both types and add a `From` impl between them.

I'd pick (a). It changes the public `EventSignatureRow` type that `chainfold::evm` re-exports, which is why it needs your decision. I recorded it as a plan entry with both options.

**Planned** (t9 adds these to TODO.md under "## unsmell run 2026-11-02 (`EventSignatureRow` struct)"):
- The open question above.
- b1-12: the cache key `(chain_id, address, event_name)` travels as three parameters through six functions. Patch t5 adds an `EventKey<'a>` in `signatures.rs`, built on top of t3.
- b1-11: `EventSignatureCache::open` has no callers, and `open_in_memory` is only used by the file's own tests. Patch t4.
- b1-13: `erc20_cache.rs` writes the same U256 BLOB decode twice. Patch t6.

t9 also removes the Tier-1 TODO entry "`EventSignatureRow` → named struct", because your changeset already did that work.

**Discarded:** b1-3 wanted the `SignatureCache` trait and `ResolvedEvent.topic0` to use `Topic`/`ChainId`/`Address`. The module doc of `src/signatures.rs` says it "knows nothing about the rest of chainfold", so those conversions belong in the CLI adapter.

**Skipped** (under the threshold of 5; patches show what each would cost):
- b1-8 (score 2): the struct doc reads the declaration back. Patch t7.
- b1-9 (score 3): the module doc still spells the row as a tuple. Patch t7.
- b1-10 (score 4): the `map_err(... e.to_string())` in the adapter drops the error source. Patch t8.

All 13 findings have an entry in `decisions.yaml`, and none is open. Everything is in `.git/unsmell/20261102-005400/`.