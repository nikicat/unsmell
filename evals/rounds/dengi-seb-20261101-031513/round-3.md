I fixed everything the survey found in `seb.py` and `test_seb.py`. The one new finding in `schema.sql` needs a schema change, so I added it to `TODO.md` instead. All 10 tests pass. Nothing is staged or committed.

One mistake on my side: while checking lint I ran `git stash -u`, which briefly moved all your untracked files into a stash. I restored them right away with `git stash pop`, confirmed every edit was still there, and no stash is left.

All the changed files are untracked, so every line counted as changed. Two survey agents, a cross-file agent and three re-check agents ran; the third re-check ended the loop with one small finding, fixed below.

```
Survey   5 files read whole · 84 declarations inventoried · 0 locks inventoried, 0 oversized · 4 parameter tables, 0 shared context columns · 0 misplaced rules · 1 request-scoped value threaded · 22 inputs at the edge, 1 unparsed (new) · 4 repeated literals, 1 repeated expression, 3 facts stated twice · 36 functions split by role, 3 mixing roles, 0 pass-throughs · 42 doc items checked, 2 with an effect or exit missing, 0 leaking mechanism
```

**Rewrote**
- `seb.py:2` module doc: "Stores the booked transactions of SEB LT accounts, fetched through Enable Banking."
- `Config.from_env`: "Errors with ConfigError on any of these:", followed by a bullet list:
  - EB_APP_ID is unset or not a UUID.
  - The EB_KEY file is missing or cannot be read.
  - The EB_KEY file holds no RSA private key in PEM form.
- `Account.iban` (new comment): "None when the bank gives no IBAN."
- `Account.parse`: "Returns the account in an account entry of an Enable Banking session body."
- `Account.key`: "Returns the identifier stored in txn.iban. It is the IBAN when there is one, and the Enable Banking uid otherwise."
- `Session.parse`: "Returns the session in an Enable Banking session body.", followed by "Errors with BankError on any of these:" and a bullet list:
  - The body has no expiry, or the expiry is not an ISO timestamp.
  - The body has no list of accounts.
  - An account has no uid.
- `TransactionStatus`: "The status of a transaction, in the codes that Enable Banking uses."
- `Transaction.parse`: "… Errors with BankError when the body has no status, or a status that is not a TransactionStatus."
- `Transaction.booked`: "Returns the transaction as booked, or None when the bank has not booked it. …"
- `start_login`: "Starts a bank login for the user. Errors with BankError when the response has no login URL."
- `create_session`: the existing doc, plus "Errors as Session.parse does."
- `transactions`: "… Errors with BankError when a page has no list of transactions, and as Transaction.parse does."
- `ask_redirect_url`: "… returns the URL that they paste after finishing the login."
- `session`: "Errors as Session.load, EnableBanking.start_login, Login.code and EnableBanking.create_session do."
- `Store.__init__`: "Opens the sqlite database at path, or an in-memory one for ":memory:", and creates the txn table when it is missing."
- `Synced`: "What one run stored for one account. Its text is the account's summary line." Its `since` field: "The first day fetched, or None when the bank chose it."
- `sync`: "Stores the account's booked transactions from date_from on, or from its last stored booking day when date_from is None, and returns what was stored. Errors as EnableBanking.transactions and Transaction.booked do."

**Fixed**
- `seb.py` `Transaction.status`: it branched on the string `"BOOK"`. It is now a `TransactionStatus` enum (`StrEnum`), and the tests use its members.
- `seb.py` `Config.from_env`: it called `sys.exit` while its doc said "Errors when". It now raises `ConfigError`, and `main` catches it together with `BankError`.
- `seb.py` `main`: its loop body mixed the resume rule, the progress label, the summary text and the writes. That body is now `sync()`, which returns a `Synced` record whose text is the summary line.
- `seb.py` `Store`: the query `SELECT … FROM txn WHERE iban = ?` was written twice. It is now one helper, `_aggregate`.
- `seb.py` `Store.__init__`: it was typed `Path` but the tests pass `":memory:"`. It now takes `str | Path`.
- `seb.py` `session` and `create_session`: their docs left out exits that can happen. Both now name them.
- `seb.py` `Session.parse` and `Config.from_env`: each listed four error conditions in one sentence. Both now use the "Errors … on any of these:" bullet list.
- `seb.py` facts stated twice: "no IBAN" now lives only on `Account.iban`, and "finish the login in a browser" only on `Login`. The module doc no longer repeats the resume and login rules that `sync` and `session` own.
- `seb.py` program name: `prog="seb"` repeated the script name from `pyproject.toml`, and so did the "no valid session" error message. I removed both. `parse_args` now uses the whole module doc as the description.
- `test_seb.py`: the `amount_cents` sign check sat inside a store test whose name did not cover it. It is now `SchemaTest.test_debit_amount_is_negative_cents`.
- `test_seb.py`: I added `test_unknown_status_is_a_bank_error`.
- `test_seb.py` `tx`: its status now defaults to booked, and its unused `ref` default is gone, so the fixtures are short again.

**Behaviour**
- A transaction with an unknown status is now a `BankError`; before, it was silently treated as not booked. The enum lists the seven statuses Enable Banking documents (BOOK, CNCL, HOLD, OTHR, PDNG, RJCT, SCHD), so if the bank adds a new one, every run will fail until it is added.
- Config errors still print the same message and exit with status 1, but `main` now handles them in the same place as bank errors.
- `python seb.py --help` now shows the program as `seb.py`; the installed `seb` command still shows `seb`.
- The "no valid session" message now says "Run this from a terminal" instead of "Run seb from a terminal".

**Planned**
- `schema.sql:4`: `entry_reference` is stored both as a column and inside `raw`, and nothing checks that they agree. The entry is in `TODO.md` under "Unsmell run 2026-11-01, third pass".

**Discarded**
- `Store` methods taking `account`: the account is the item being worked on, not shared context. The duplicated SQL was the real problem, and it is fixed.
- The progress line in `counted` printed twice: the two prints are three lines apart and differ in their arguments, so a helper would not pay.
- `Psu-User-Agent: "dengi"` repeating the project name: the bank never reads that value back, so nothing has to stay in sync with it.
- Everything else the agents raised matches an entry already in `TODO.md`.

All 20 findings are accounted for above, and none is still open.

**Verification:** `python -m unittest test_seb` passes (10 tests). `ruff check` reports only the import-sorting nit in `test_seb.py` that was there before this run. Running without `EB_APP_ID` still prints the same config error and exits with status 1.