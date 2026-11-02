# Editor brief (shared by all editors of this run)

You are an editor agent for an /unsmell run. Edit ONLY inside your worktree
(given in your prompt). Do not touch the main working tree, do not commit, do
not run git add.

Read §5 and §6 of /home/nb/src/unsmell/skills/unsmell/SKILL.md first, and §4
(the catalog) for the self-check.

Findings: .git/unsmell/20261102-135509/findings/b1.yaml (relative to the repo
/home/nb/.cache/unsmell-eval/runs/cf-post-unsmell-20261102-135449/repo).
Line numbers there refer to the pre-run working tree; your worktree may
already contain task t1's patch (fixes/t1.patch), which turned
EventSignatureRow into the argument of insert_event_signature, added
FromSql/ToSql for Topic in src/evm/cache.rs, and made get_event_signature use
query_row(...).optional().

Style: Cargo.toml [lints.clippy] all+pedantic warn; absolute_paths warn
(clippy.toml allows only std/core/alloc as path prefixes) — bring names in via
`use`. Doc house style: plain short Google-API-style sentences, verb first,
"Errors when…" never "Returns an error if…", no doc opening with the item's
own name, no compressed docs (colon/semicolon joins, appositives).

Build check, from your worktree:
  CARGO_TARGET_DIR=/home/nb/.cache/unsmell-eval/runs/cf-post-unsmell-20261102-135449/repo/.git/unsmell/20261102-135509/target cargo check --all-targets --all-features
Never run tests, clippy or other builds. Then read your own `git diff` against
the §4 catalog and fix any smell your change adds (residue, duplication, a
half-done shape). If the task cannot be done as described, say so and stop.
Reply with a short summary of what changed and the build result.
