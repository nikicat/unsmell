#!/usr/bin/env python
"""Fetch SEB LT account history via Enable Banking.

Usage: uv run seb [date_from YYYY-MM-DD]
Upserts booked transactions into dengi.db; without date_from, resumes from the last stored day.
"""
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt
import requests

API = "https://api.enablebanking.com"
APP_ID = os.environ.get("EB_APP_ID", "00000000-0000-4000-8000-000000000000")
KEY = Path(os.environ.get("EB_KEY", "private.pem")).read_bytes()
REDIRECT = os.environ.get("EB_REDIRECT", "https://localhost/")  # must match one registered on the app
SESSION = Path("session.json")
PSU = {}  # set in main()


def headers():
    now = int(datetime.now(timezone.utc).timestamp())
    token = jwt.encode(
        {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": now, "exp": now + 3600},
        KEY, algorithm="RS256", headers={"kid": APP_ID},
    )
    return {"Authorization": f"Bearer {token}"} | PSU


def psu_headers():
    """Mark the request as user-present, which lifts the bank's ~4/day unattended-access cap.
    Only when run from a terminal: an unattended run must not claim the user is there."""
    if not sys.stdin.isatty():
        return {}
    ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
    return {"Psu-Ip-Address": ip, "Psu-User-Agent": "dengi"}


def call(method, path, **kw):
    r = requests.request(method, API + path, headers=headers(), timeout=60, **kw)
    if not r.ok:
        sys.exit(f"{method} {path}: {r.status_code} {r.text}")
    return r.json()


def authorize():
    state = str(uuid.uuid4())
    valid_until = datetime.now(timezone.utc) + timedelta(days=180)  # PSD2 max; bank may cap lower
    url = call("POST", "/auth", json={
        "access": {"valid_until": valid_until.isoformat()},
        "aspsp": {"name": os.environ.get("EB_ASPSP", "SEB"), "country": "LT"},
        "state": state,
        "redirect_url": REDIRECT,
        "psu_type": "personal",
    })["url"]
    print(f"Open, log in with Smart-ID, then paste the URL you land on:\n{url}")
    q = parse_qs(urlparse(input("> ").strip()).query)
    if q.get("state") != [state]:
        sys.exit(f"bad redirect: {q}")
    session = call("POST", "/sessions", json={"code": q["code"][0]})
    SESSION.write_text(json.dumps(session, indent=2))
    return session


def load_session():
    if SESSION.exists():
        s = json.loads(SESSION.read_text())
        if datetime.fromisoformat(s["access"]["valid_until"]) > datetime.now(timezone.utc):
            return s
    return authorize()


def transactions(uid, date_from):
    params, out = {"date_from": date_from} if date_from else {}, []
    while True:
        page = call("GET", f"/accounts/{uid}/transactions", params=params)
        out += page["transactions"]
        print(f"\r{uid}: {len(out)} transactions", end="", file=sys.stderr, flush=True)
        if not page.get("continuation_key"):
            print(file=sys.stderr)
            return out
        params["continuation_key"] = page["continuation_key"]


def main():
    global PSU
    PSU = psu_headers()
    db = sqlite3.connect("dengi.db")
    db.executescript(Path(__file__).with_name("schema.sql").read_text())
    for acc in load_session()["accounts"]:
        iban = acc.get("account_id", {}).get("iban") or acc["uid"]
        # default: resume from last stored day; overlap is deduped by the upsert
        date_from = sys.argv[1] if len(sys.argv) > 1 else db.execute(
            "SELECT max(booking_date) FROM txn WHERE iban = ?", (iban,)).fetchone()[0]
        txs = [t for t in transactions(acc["uid"], date_from) if t["status"] == "BOOK"]
        count = lambda: db.execute("SELECT count(*) FROM txn WHERE iban = ?", (iban,)).fetchone()[0]
        before = count()
        with db:
            db.executemany(
                "INSERT INTO txn (iban, entry_reference, raw) VALUES (?, ?, ?)"
                " ON CONFLICT DO UPDATE SET raw = excluded.raw WHERE raw IS NOT excluded.raw",
                [(iban, t["entry_reference"], json.dumps(t, ensure_ascii=False)) for t in txs])
        print(f"{iban}: {len(txs)} booked fetched since {date_from}, {count() - before} new")


if __name__ == "__main__":
    main()
