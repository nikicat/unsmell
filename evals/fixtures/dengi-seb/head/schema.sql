CREATE TABLE IF NOT EXISTS txn (
    iban            TEXT NOT NULL,
    entry_reference TEXT NOT NULL,  -- unique per account at SEB; booked only, pending has none
    raw             TEXT NOT NULL CHECK (json_valid(raw)),

    booking_date    TEXT AS (raw ->> '$.booking_date'),
    value_date      TEXT AS (raw ->> '$.value_date'),
    -- signed: negative = money out
    amount_cents    INTEGER AS (CAST(round((raw ->> '$.transaction_amount.amount') * 100) AS INTEGER)
                                * IIF(raw ->> '$.credit_debit_indicator' = 'DBIT', -1, 1)),
    currency        TEXT AS (raw ->> '$.transaction_amount.currency'),
    counterparty    TEXT AS (IIF(raw ->> '$.credit_debit_indicator' = 'DBIT',
                                 raw ->> '$.creditor.name', raw ->> '$.debtor.name')),
    counterparty_iban TEXT AS (IIF(raw ->> '$.credit_debit_indicator' = 'DBIT',
                                   raw ->> '$.creditor_account.iban', raw ->> '$.debtor_account.iban')),
    remittance      TEXT AS (raw ->> '$.remittance_information'),  -- JSON array text, fine for LIKE
    -- ISO 20022 domain/family/sub-family, e.g. PMNT/CCRD/OTHR = card payment
    tx_code         TEXT AS (concat_ws('/', raw ->> '$.bank_transaction_code.description',
                                            raw ->> '$.bank_transaction_code.code',
                                            raw ->> '$.bank_transaction_code.sub_code')),

    PRIMARY KEY (iban, entry_reference)
) STRICT;

CREATE INDEX IF NOT EXISTS txn_date ON txn (iban, booking_date);
