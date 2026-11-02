I ran the survey, triaged the findings and wrote a patch for every task. As you asked, nothing went into your working tree, the full check and re-check did not run, and I asked no questions. Your index is untouched.

## Patches

All patches are in `.git/unsmell/20261102-135502/fixes/`. t1, t2 and t6 start from a snapshot of your working tree. t3, t4, t5, t8, t9 and t10 are stacked on t1.

| Task | Decision | Findings | Patch |
|--|--|--|--|
| **t1** | FIX | b1-2, 4, 6, 7, 8, 9, 13, 14, 15 | `seb.py` restructured, ~260-line patch. `EnableBanking` holds the API client state; it replaces the module globals and the `global PSU` that `main` set. `Ledger` gets `open`, `last_booking_date`, `count` and `upsert`. The date argument goes through `argparse` with `date.fromisoformat`, and is read once instead of again for every account. `session()` loads the saved session or logs in, and saves it. `transactions()` yields across pages. |
| **t2** | FIX | b1-1, cross-2 | `.gitignore` now ignores `private.pem`, `session.json` and `dengi.db`. |
| **t7** | FIX (was ASK) | b1-12 | The `tx_code` comment was false. Enable Banking calls `description` "Arbitrary transaction categorization description", so a real value looks like `Utlandsbetalning/12/32`, not `PMNT/CCRD/OTHR`. The patch fixes only the comment; the stored column is unchanged. |
| t3 | ASK | b1-3, b1-18 | `pydantic-settings` `Settings` with an `EB_` prefix. `EB_APP_ID` becomes required (the all-zero placeholder is gone), the key file is validated, and the session and database paths can be set from the environment. Risk: `HttpUrl` adds a trailing slash to `EB_REDIRECT`, which may then not match the redirect registered with the bank. |
| t4 | ASK | b1-5 | `pydantic` models for the API responses (`Session`, `Account`, `TransactionPage`, `Transaction`). The raw JSON is kept, so `session.json` and the stored rows are byte-identical. |
| t5 | ASK | b1-10 | **Probable bug.** Enable Banking says a `uid` is valid only while its session is authorized, so an account without an IBAN gets a new key at every login and its history is stored twice. The patch keys such accounts by `identification_hash` instead, and renames the column `iban` → `account`. That rename does not migrate an existing `dengi.db`. |
| t6 | ASK | b1-11 | Adds a generated `debit` column, which replaces the `DBIT` test written three times. Checked to give the same results as before. It is a stored-schema change, and `CREATE TABLE IF NOT EXISTS` won't add the column to an existing database. |
| t8 | ASK | b1-17, cross-1 | Moves the files into a `dengi/` package and reads the schema with `importlib.resources`. The wheel builds. After this, `python dengi/seb.py` run directly no longer works; the `seb` command still does. |
| t9 | SKIP (4) | b1-16 | Adds a docstring to `call`, saying that it exits the program on an API error. |
| t10 | SKIP (3) | b1-19 | Spells `datetime.now(timezone.utc)` as `datetime.now(UTC)`. |

**Rewrote** (in t1, as written):
- module: "Imports the booked transactions of your SEB Lithuania accounts from Enable Banking into dengi.db. / Without a date, the import resumes from the last stored booking day. When there is no valid session, it asks you to log in with Smart-ID first."
- `psu_headers`: "Returns the PSU headers that mark a request as user-present. / The bank then lifts its limit of about four unattended accesses a day. Returns no headers when stdin is not a terminal, because an unattended run must not claim that the user is there."
- `redirect_code`: "Returns the authorization code from the URL that the bank redirected to. / Exits when the URL has no code or carries a state other than the given one. The exit message is the bank's error when the URL has one."
- `Ledger.upsert`: "Stores the given transactions of the account. / A transaction that is already stored under its entry reference is updated, not added again."
- New one-line docs on `EnableBanking`, `session`, `authorize`, `start_auth`, `Ledger`, `Ledger.open` and `progress`. Most are verb-first; the class docs are noun phrases.

**Bug** (t1): when you cancel the bank login, it redirects back with `error=` instead of a code, and the script crashed with a `KeyError` on `q["code"][0]`. With t1 it exits with the bank's error message.

**Behaviour** (t1):
- A malformed date argument is now rejected with a usage error, and `--help` exists.
- `private.pem` is read when the program starts, not when the module is imported.
- The progress line on stderr updates once per transaction instead of once per page.

**Discarded**:
- cross-3: the schema comment it cites says nothing about the IBAN/uid fallback.
- cross-4: a query naming its own table's columns is not a smell.
- cross-5 and cross-6: by the cross-file agent's own reasoning, each place states a different fact.

**Planned**: none. The ASKs stay open as patches for you to decide on.

## Survey

4 files read whole · 45 declarations inventoried (25 flagged) · 0 locks · 7 functions in the parameter tables, 2 shared context columns · 6 misplaced rules · 0 request-scoped values threaded · 19 inputs at the edge, 16 unparsed · 12 repeated literals, 5 repeated expressions, 12 facts stated in comments (2 flagged) · 7 functions split by role, 4 mixing roles, 0 pass-throughs · 10 doc items checked, 2 with an effect or exit missing, 1 leaking mechanism.

All 25 findings (19 in b1, 6 in cross) have an entry in `decisions.yaml`; none is open.

## Deviations

- I wrote the three-line patches t2, t9 and t10 myself instead of starting an editor agent for each.
- I changed b1-12 from ASK to FIX after the docs showed the comment was false and the fix touches only the comment.

## Verification

Only the per-task build checks ran: `py_compile` on each, the schema executed in an in-memory sqlite, and for t8 the wheel built. The project has no tests or linters. In t3 and t4, uv couldn't install pydantic offline, so those import checks used a temporary environment instead of the project's own.

Run directory: `.git/unsmell/20261102-135502/` (`batches.yaml`, `inventory/`, `findings/`, `decisions.yaml`, `fixes/`).