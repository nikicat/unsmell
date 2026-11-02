I've cleaned up the whole changeset (`seb.py`, `schema.sql`, `pyproject.toml`, `.gitignore`) and checked it against the original behaviour. Six findings that would change the stored schema or need a decision are written into a new `TODO.md`. Nothing is staged or committed.

The run is complete: one fresh survey agent read all four files whole, then I ran three re-check rounds after the fixes, which is the limit. The last round found three small issues, now fixed. No re-check ran after those last edits, so they were verified only by the checks and lint below.

**Survey** (from the agents' inventory files): 4 files read whole · 49 declarations, 32 flagged · 0 locks · 7 functions in the parameter tables, 1 shared context (the Enable Banking client, reached through globals) · 9 misplaced rules · 0 request-scoped values in the first pass, 1 in re-check 2 (the login `state`) · 13 inputs at the edge, 9 unparsed · 17 repeated literals, 6 repeated expressions, 3 facts stated twice · 7 functions split by role, all 7 mixing roles, 0 pass-throughs · 10 doc items checked, 2 missing an effect or exit, 2 leaking mechanism.

**What changed in `seb.py`**
- **Config:** all settings are read and checked once at startup. `EB_APP_ID` must be a UUID and the key file is parsed there, so import-time file reads are gone.
- **Enable Banking client:** an `EnableBanking` class replaces the module globals `PSU` and `KEY` and the free functions `headers` and `call`. It builds the user-present headers from the user's IP, and `call` raises `BankError` instead of exiting.
- **Session and login:** `Session` owns `session.json` (`parse`, `load`, `save`) and the expiry check. `Account.key` holds the "IBAN, or uid if none" rule. A `Login` object holds the `state` and checks the pasted redirect URL. `session()` runs the terminal prompt, outside the client.
- **Store:** a `Store` class owns all the SQL, and `upsert` returns how many rows were new.
- **Smaller fixes:**
  - `transactions` became a generator, and the stderr progress line moved into a small `counted` helper.
  - The booked-only filter has a name (`booked`), and `BookedTransaction` marks filtered transactions.
  - The magic numbers became named constants (token and consent lifetimes, API host).
  - `date_from` is parsed with `argparse` before the account loop.
  - All docs and comments are rewritten as plain sentences with "Errors with … when …".
- **Schema:** a new `is_debit` generated column replaces the three repeated `'DBIT'` tests. The comments are rewritten.
- **`pyproject.toml`:** `cryptography` is now a declared dependency, because the code imports it directly.

**Bugs fixed**
- With no stored rows and no `date_from`, the summary printed "since None". It now says "since the first available day".
- A pasted redirect URL without `code` crashed with a `KeyError`. It now exits with "bad redirect".
- An unattended run with no valid session crashed on `input()`. It now exits with a clear message.
- A corrupt `session.json` gave a traceback. It now exits with an error message.
- `.gitignore` did not cover `dengi.db`, `session.json` (a live bank session) or `*.pem` (the signing key). It now does.

**Behaviour changes you can notice**
- `EB_APP_ID` has no default any more. The all-zero placeholder only produced an invalid token. The alternative was to keep the default and just parse it.
- The ipify reply must be an IP address with a successful status before it goes into a header.
- `seb --help` works now, and extra arguments are rejected.
- The progress label changed from `uid: N transactions` to `<iban> fetched: N`.

**Planned, in `TODO.md`:**
- the `iban` column also holding a uid;
- `remittance` holding a JSON array;
- `amount_cents` assuming two decimals;
- the doubtful ISO 20022 mapping in the `tx_code` comment;
- `EB_ASPSP` being configurable while the country and the docs assume SEB LT;
- an existing `dengi.db` not getting the new `is_debit` column (nothing reads it yet).

You had no plan file, so I created `TODO.md` rather than asking where plans go.

**Not fixed, on purpose:**
- `schema.sql` is named both in the loader and in the wheel include list in `pyproject.toml`. A build manifest can't share a constant.
- Table and column names appear both in the schema and in the SQL. That is inherent to SQL, and the SQL now lives only in `Store`.
- `datetime.now(UTC)` is a standard-library call, not a repeated derivation.
- A naive timestamp in the session would raise an error, but Enable Banking sends timestamps with a timezone.

Every finding from the four agent reports ended up fixed, planned or set aside as above; none is open.

**Verification:** there is no test suite. I wrote a check script outside the working tree, in `.git/unsmell/check.py`. It runs the generated columns of the original and new schema on sample transactions and compares them, and it covers `Store`, the login check, `Session`, argument parsing and a JWT round-trip. It passes, as does `ruff check`. I also made `seb.py` executable to match its shebang. Nothing was run against the real bank API.