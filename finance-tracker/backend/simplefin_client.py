"""SimpleFIN bridge client.

SimpleFIN (https://www.simplefin.org/) is a dead-simple account aggregation
protocol. Flow:

1. User goes to https://beta-bridge.simplefin.org, connects their bank, and
   gets a **setup token** — a base64-encoded URL.
2. The token is claimed exactly once: decode it, POST to that URL with no
   body, and the response is an **access URL** of the form
   ``https://USER:PASSWORD@beta-bridge.simplefin.org/simplefin``. That URL
   is long-lived and replaces the setup token.
3. To pull data, GET ``{access_url}/accounts?start-date=<unix>``. The
   response contains accounts with balances and a ``transactions`` array.

SimpleFIN's sign convention for transactions is the opposite of Plaid's —
money *in* is positive, money *out* is negative. We flip it on ingest so
everything downstream can pretend it's Plaid.
"""
from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import requests


class SimpleFinError(RuntimeError):
    pass


def _normalize_setup_token(token: str) -> str:
    """Setup tokens are base64-encoded URLs. Some bridges return the URL
    directly, so accept either."""
    token = (token or "").strip()
    if not token:
        raise SimpleFinError("setup token is empty")
    if token.startswith("http://") or token.startswith("https://"):
        return token
    # Accept tokens with or without padding.
    padded = token + "=" * (-len(token) % 4)
    try:
        decoded = base64.b64decode(padded).decode("utf-8").strip()
    except Exception as e:
        raise SimpleFinError(f"could not decode setup token: {e}")
    if not decoded.startswith("http"):
        raise SimpleFinError("decoded setup token is not a URL")
    return decoded


def claim_setup_token(setup_token: str) -> str:
    """Exchange a SimpleFIN setup token for a long-lived access URL.

    The returned access URL includes basic-auth credentials and should be
    treated as a secret.
    """
    claim_url = _normalize_setup_token(setup_token)
    try:
        resp = requests.post(claim_url, data="", timeout=30)
    except requests.RequestException as e:
        raise SimpleFinError(f"network error claiming setup token: {e}")
    if resp.status_code != 200:
        raise SimpleFinError(
            f"setup token claim failed ({resp.status_code}): {resp.text[:200]}"
        )
    access_url = resp.text.strip()
    if not access_url.startswith("http"):
        raise SimpleFinError(f"bridge returned unexpected body: {access_url[:200]}")
    return access_url


def _bridge_host(access_url: str) -> str:
    parts = urlparse(access_url)
    return parts.hostname or "simplefin"


def fetch_accounts(
    access_url: str,
    start_days: int = 90,
) -> Dict[str, Any]:
    """Fetch accounts + transactions from the SimpleFIN bridge.

    Returns the raw SimpleFIN payload with added-in ``_normalized`` accounts
    and transactions that match the internal Plaid-shaped schema.

    ``start_days`` defaults to 90 because the bridge caps requests at 90 days
    anyway — asking for more just produces a warning message in the payload.
    """
    start_ts = int((datetime.utcnow() - timedelta(days=start_days)).timestamp())
    url = f"{access_url.rstrip('/')}/accounts?start-date={start_ts}"
    try:
        resp = requests.get(url, timeout=60)
    except requests.RequestException as e:
        raise SimpleFinError(f"network error fetching SimpleFIN accounts: {e}")
    if resp.status_code != 200:
        raise SimpleFinError(
            f"SimpleFIN GET /accounts failed ({resp.status_code}): {resp.text[:200]}"
        )
    try:
        payload = resp.json()
    except ValueError as e:
        raise SimpleFinError(f"invalid JSON from SimpleFIN: {e}")
    return payload


def _classify_type(sf_account: Dict[str, Any]) -> tuple[str, Optional[str]]:
    """SimpleFIN doesn't have a strict type taxonomy — it's mostly free-form
    strings in the organization name and account name. We do a best-effort
    map to the same type/subtype vocabulary our Plaid client uses so net-
    worth bucketing works.
    """
    name = (sf_account.get("name") or "").lower()
    org = ((sf_account.get("org") or {}).get("name") or "").lower()
    joined = f"{name} {org}"

    if any(k in joined for k in ("credit card", "credit ", "visa", "mastercard", "amex")):
        return "credit", "credit card"
    if any(k in joined for k in ("mortgage",)):
        return "loan", "mortgage"
    if "student" in joined and "loan" in joined:
        return "loan", "student"
    if "loan" in joined or "auto" in joined:
        return "loan", None
    if any(k in joined for k in ("401", "ira", "roth", "403b", "retirement")):
        return "investment", "401k" if "401" in joined else "ira"
    if any(k in joined for k in ("brokerage", "invest", "robinhood", "vanguard", "fidelity", "schwab")):
        return "investment", None
    if any(k in joined for k in ("savings",)):
        return "depository", "savings"
    if any(k in joined for k in ("checking",)):
        return "depository", "checking"
    if any(k in joined for k in ("cash",)):
        return "depository", "cash management"
    return "depository", None


def normalize_payload(
    source_id: str,
    display_name: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Turn a raw SimpleFIN ``/accounts`` payload into ``{accounts, transactions}``
    matching the internal schema used by the rest of the app.
    """
    accounts: List[Dict[str, Any]] = []
    transactions: List[Dict[str, Any]] = []
    # Filter out the harmless "date range exceeds 90 days" cap warning — we
    # already default to 90 days, and the bridge caps anyway. Anything else
    # in payload.errors is a real problem the user should see.
    errors = [
        e
        for e in (payload.get("errors") or [])
        if "90 days" not in str(e).lower() and "capped" not in str(e).lower()
    ]

    for acc in payload.get("accounts", []):
        acc_id = f"sf_{acc['id']}" if not str(acc.get("id", "")).startswith("sf_") else acc["id"]
        a_type, a_sub = _classify_type(acc)
        org_name = (acc.get("org") or {}).get("name") or display_name
        try:
            balance = float(acc.get("balance") or 0.0)
        except (TypeError, ValueError):
            balance = 0.0
        # Credit-card balances are often reported as a negative ("you owe $X")
        # on SimpleFIN, but our liability classifier expects positive values.
        if a_type in ("credit", "loan") and balance < 0:
            balance = abs(balance)
        accounts.append(
            {
                "account_id": acc_id,
                "source_id": source_id,
                "source_kind": "simplefin",
                "institution_name": org_name,
                "name": acc.get("name", org_name),
                "official_name": acc.get("name"),
                "mask": None,
                "type": a_type,
                "subtype": a_sub,
                "current_balance": round(balance, 2),
                "available_balance": None,
                "iso_currency_code": acc.get("currency") or "USD",
                "manual": False,
            }
        )

        for tx in acc.get("transactions") or []:
            try:
                posted_ts = int(tx.get("posted") or 0)
                tx_date = datetime.utcfromtimestamp(posted_ts).date().isoformat() if posted_ts else ""
            except (TypeError, ValueError):
                tx_date = ""
            try:
                amt = float(tx.get("amount") or 0.0)
            except (TypeError, ValueError):
                amt = 0.0
            # SimpleFIN: positive = money in. Our convention: positive = out.
            flipped = -amt
            transactions.append(
                {
                    "transaction_id": f"sf_{tx['id']}" if not str(tx.get('id', '')).startswith("sf_") else tx["id"],
                    "account_id": acc_id,
                    "source_id": source_id,
                    "date": tx_date,
                    "name": tx.get("description") or tx.get("payee") or "(unknown)",
                    "merchant_name": tx.get("payee"),
                    "amount": round(flipped, 2),
                    "iso_currency_code": acc.get("currency") or "USD",
                    "category": [],
                    "pending": bool(tx.get("pending", False)),
                    "payment_channel": None,
                }
            )

    return {"accounts": accounts, "transactions": transactions, "errors": errors}
