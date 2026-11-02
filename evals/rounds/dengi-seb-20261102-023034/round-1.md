I ran the run up to the patches and stopped there, as you asked. Nothing is merged, staged or committed, and your working tree still holds only its four untracked files. I wrote ten patches. The four FIX patches (t1–t3 on the base, then t4 for review) apply together cleanly, but no tests ran on the combined result.

**How this run differed from the full process:**
- There was no cross-file agent. The changeset was one batch, so nothing could cross batches; `findings/cross.yaml` is empty.
- I grouped the editors into fewer agents (t2–t4 in one, t5–t6 in one, t7–t10 in one). Each task still got its own worktree and its own patch.
- There was no re-check. That step follows the merge, which "patches only" skips.
- One `uv run` call of mine created `uv.lock` and `.venv` in the repo. I deleted both and rebuilt the base snapshot without them.

**Survey:** 4 files read whole · 52 declarations, 27 say less than the value holds · 0 locks · 1 parameter table, 2 shared context columns · 6 misplaced rules · 0 request-scoped values · 17 inputs at the edge, 12 unparsed · 16 repeated literals, 4 repeated expressions, 2 facts stated twice · 7 functions split by role, 6 mixing roles, 0 pass-throughs · 10 doc items checked, 1 missing an effect or exit, 0 leaking mechanism.

## Tasks and patches
All patches are in `.git/unsmell/20261102-023055/fixes/`.

| Task | Decision | Findings | Patch |
|--|--|--|--|
| t1 | FIX | b1-1, 2, 3, 4, 6, 7, 8, 9, 13 | `t1.patch` (186+/82−) |
| t2 | FIX | b1-10 | `t2.patch` |
| t3 | FIX | b1-11 | `t3.patch` |
| t4 | ASK | b1-12 | `t4.patch` |
| t5 (after t1) | ASK | b1-5 | `t5.patch` |
| t6 (after t1) | PLAN | b1-14 | `t6.patch` |
| t7–t10 (after t1) | SKIP | b1-15 to b1-18 | `t7.patch` to `t10.patch` |

**What each patch does:**
- **t1:** `seb.py` gets a few small types:
  - `Config.from_env()`. The key file is no longer read when the module is imported.
  - An `EnableBanking` client. It replaces the `PSU` global that `main()` had to set before anything else worked.
  - `Session` and `Account`, which now own the expiry check and the rule for the storage key.
  - A `Store` that holds the SQL, unchanged.
  - `parse_date_from`, which checks the date argument once, at the start.

  `main` now reads as a list of steps.
- **t2:** rewrites the module doc.
- **t3:** `.gitignore` now also ignores `private.pem`, `session.json` and `dengi.db`. Before this, one `git add` of the directory would have committed a private key and your bank data.
- **t4:** adds a generated `debit` column to `schema.sql`, so the debit test is written once instead of three times. On test rows it gives the same results as the old schema.
- **t5:** a confirmed bug fix, but it needs your decision. The Enable Banking docs say `uid` is only valid while its session is authorized. The ID that matches an account across sessions is `identification_hash`. So today an account with no IBAN starts a new set of rows after every re-login. The patch keys those accounts by `identification_hash` and renames the column from `iban` to `account`. An existing `dengi.db` would then fail with "no such column: account" unless you also take t6 or run a one-off `ALTER TABLE`.
- **t6:** a small version number for the schema (`PRAGMA user_version`). When the number goes up, `txn` is rebuilt from the stored `raw` JSON. I tested it on an old-schema database.
- **t7–t10:** each shows what a skipped finding would cost, so you can lower the bar later.

## Rewrote
```
"""Fetches the SEB LT account history through Enable Banking.

Usage: uv run seb [date_from YYYY-MM-DD]

Upserts the booked transactions of each account into dengi.db. Without
date_from, each account resumes from its last stored booking day. When no
valid session is stored, the program asks you to log in with Smart-ID and to
paste the URL you land on. It exits when that URL does not belong to this
login.
"""
```
- `psu_headers`: "Returns the PSU headers, which tell the bank that the user is present. With them, the bank lifts its cap of about four unattended requests a day. Returns no headers when stdin is not a terminal, because an unattended run must not claim that the user is there."
- `authorize`: "Logs the user in at the bank and stores the new session. Exits when the pasted URL does not belong to this login."
- `session`: "Returns a session that has not expired. Authorizes a new one when none is stored or the stored one has expired."
- `upsert`: "Stores txs under the account key and returns how many were new. A stored transaction is updated when its JSON has changed."
- `parse_date_from`: "Returns the date_from argument, or None when it is not given. Exits when it is not a YYYY-MM-DD date."
- `seb.py` resume comment: "# The upsert dedupes the day that overlaps the last run."
- `seb.py` 180-day comment: "# 180 days is the PSD2 maximum. The bank may grant less."
- `schema.sql`: "-- Unique per account at SEB. Only booked transactions have one, so pending ones are not stored."

## Decisions
- **Fixed:** b1-1, b1-2, b1-3, b1-4, b1-6, b1-7, b1-8, b1-9, b1-13 (all t1), b1-10 (t2), b1-11 (t3).
- **Behaviour changes in t1:**
  - A bad `date_from` now exits early with a usage message. An empty string, which used to mean "no date", also exits.
  - The summary line says "full history" instead of "since None".
- **Asked, no answer yet:**
  - b1-5 (t5): change the key for IBAN-less accounts and rename the column?
  - b1-12 (t4): add the `debit` column?
- **Planned, but not written anywhere:** b1-14 (schema versioning, t6) and e-1. e-1 came up while t5 was being written: the docs say `uid` is optional, but `Account.from_json` reads `d["uid"]` directly, so a closed account would crash it. The repo has no TODO file or tracker. Tell me where plans should go and I'll add both entries.
- **Skipped** (score under the bar of 5):
  - b1-15, paging generator: 4.
  - b1-16, require `EB_APP_ID`: 4.
  - b1-17, report the bank's error on a refused login: 4.
  - b1-18, `ApiError` instead of `sys.exit`: 3.
  - b1-19, split up `psu_headers`: 2. Its proposed fix was no change, so it has no patch.
- **Discarded:** b1-20. The JWT audience only looks like the API host. Enable Banking fixes it separately.

All 21 findings have an entry in `decisions.yaml` (20 from the survey, plus e-1), and none is still open.

**Checks:** every patch passes the build check (`py_compile`, an import without `private.pem`, the schema on an in-memory database). There are no tests or linters in the repo, so the full check is absent. The t1 smoke test passed.

Run directory: `.git/unsmell/20261102-023055/`