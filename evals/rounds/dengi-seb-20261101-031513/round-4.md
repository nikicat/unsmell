I made nine fixes in `seb.py` and `test_seb.py` and rewrote six doc comments; all 10 tests pass. The main structural change is a new `Run` class that replaces the free functions `session()` and `sync()`. Nothing is staged or committed.

This was a full run: two survey agents, one cross-file agent and three re-check agents. Most of what they found was already in `TODO.md` from earlier runs, so it was set aside rather than reported again.

```
Survey   5 files read whole · 89 declarations inventoried · 0 locks inventoried, 0 oversized · 2 parameter tables, 1 shared context column · 0 misplaced rules · 1 request-scoped value threaded · 25 inputs at the edge, 0 unparsed (new) · 26 repeated literals, 11 repeated expressions, 1 fact stated twice · 36 functions split by role, 1 mixing roles, 0 pass-throughs · 55 doc items checked, 2 with an effect or exit missing, 0 leaking mechanism
Rewrote  seb.py:30   "A failed Enable Banking call or bank login, or a saved session that cannot be read."
Rewrote  seb.py:49   "The Enable Banking app that this program runs as, and the bank it asks for consent."
Rewrote  seb.py:146  "Checks whether the consent has run out."
Rewrote  seb.py:370  "One run of the program over the accounts of the user's session."
Rewrote  seb.py:374  "# The first day that the user asked to fetch, if any."
Rewrote  seb.py:391  "Stores the account's booked transactions and returns what was stored. They start at Run.date_from, or at the account's last stored booking day when Run.date_from is None. If the account has no stored rows either, they start where EnableBanking.transactions starts when it is given no date_from. Errors as EnableBanking.transactions and Transaction.booked do."
Rewrote  seb.py:~402 parse_args: "Returns the date_from argument, or None when it is not given. Exits with a usage message when it is not an ISO 8601 date."
Fixed    seb.py:30   BankError doc said less than the code (Session.load also raises it) → added the unreadable saved session
Fixed    seb.py:49   Config and EnableBanking docs both said who signs the requests → the fact now lives only in EnableBanking
Fixed    seb.py:142  expiry rule written inline in Session.load → new Session.expired property
Fixed    seb.py:368  missing receiver: session(bank) and sync(bank, store, account, date_from), with main passing the same bank, store and date_from on every call → frozen dataclass Run(bank, store, date_from), built once in main. Alternative: keep the free functions.
Fixed    seb.py:391  sync doc left out the case with no date_from and no stored rows → now covered, pointing to EnableBanking.transactions
Fixed    seb.py:362  misleading name: Synced.fetched counts only booked transactions, while the progress label "fetched" counts all of them → renamed to Synced.booked
Fixed    seb.py:~402 parse_args doc was false: fromisoformat also takes 20261001 and 2026-W40-4, and argparse exits instead of raising → doc corrected
Fixed    test_seb.py:35 Account("uid", "LT01") built inline twice → WITH_IBAN constant next to NO_IBAN
Fixed    TODO.md:23  the naive valid_until entry still pointed at Session.load → now points at Session.expired
Discarded seb.py:338  "account threaded through the Store methods" → the account is the input each method works on, and it already has its own type (Account)
Discarded test_seb.py:93 "the test queries txn, against the Store doc" → a schema test has to read the generated column; the doc is about the program's code
Discarded .gitignore  dist/ is not ignored → a missing ignore rule, not a code smell
Discarded  —          the re-check findings were all fixed above, in three rounds; the third round's one finding (a sentence in the date_from comment that repeated the sync doc) was deleted
Planned   —          about 25 findings matched entries already in TODO.md (schema columns, runtime file names, unchecked types, etc.); dengi.db-journal is covered by the existing .gitignore:3-5 entry
```

No behaviour changed and nothing was a bug fix: these are renames, doc fixes and a move of the same logic into `Run`.

Verification: all 10 tests pass (pytest). `ruff check` reports one I001 (unsorted imports) on the `from seb import …` line in `test_seb.py`. I didn't touch that line, so I left the warning alone.