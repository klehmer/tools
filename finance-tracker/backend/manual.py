"""Manual accounts and CSV import.

Manual accounts live on the auto-created ``Manual accounts`` source. A user
can type in balances, add transactions one-at-a-time, or upload a CSV export
from their bank. We try to auto-detect the column layout so the common case
(Chase / Amex / Mint / Rocket Money exports) works out of the box.
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import storage


# --- manual sources / accounts ----------------------------------------------

def create_manual_account(inp: Dict[str, Any]) -> Dict[str, Any]:
    source = storage.get_or_create_default_manual_source()
    acc_id = f"manual_{int(datetime.utcnow().timestamp() * 1_000_000)}"
    account = {
        "account_id": acc_id,
        "source_id": source["source_id"],
        "source_kind": "manual",
        "institution_name": inp.get("institution_name") or "Manual",
        "name": inp["name"],
        "official_name": inp.get("name"),
        "mask": inp.get("mask"),
        "type": inp.get("type") or "depository",
        "subtype": inp.get("subtype"),
        "current_balance": float(inp.get("current_balance") or 0.0),
        "available_balance": None,
        "iso_currency_code": inp.get("iso_currency_code") or "USD",
        "manual": True,
    }
    storage.upsert_account(account)
    storage.update_source(source["source_id"], last_synced_at=datetime.utcnow().isoformat())
    return account


def set_manual_balance(account_id: str, balance: float) -> Dict[str, Any]:
    acc = storage.get_account(account_id)
    if not acc:
        raise ValueError(f"account {account_id} not found")
    if acc.get("source_kind") != "manual":
        raise ValueError("only manual accounts can have their balance edited directly")
    acc["current_balance"] = round(float(balance), 2)
    return storage.upsert_account(acc)


def add_manual_transaction(account_id: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    acc = storage.get_account(account_id)
    if not acc:
        raise ValueError(f"account {account_id} not found")
    tx_id = _make_txid(
        account_id=account_id,
        date=inp["date"],
        name=inp["name"],
        amount=float(inp["amount"]),
    )
    tx = {
        "transaction_id": tx_id,
        "account_id": account_id,
        "source_id": acc["source_id"],
        "date": inp["date"],
        "name": inp["name"],
        "merchant_name": inp.get("merchant_name") or inp["name"],
        "amount": round(float(inp["amount"]), 2),
        "iso_currency_code": acc.get("iso_currency_code") or "USD",
        "category": inp.get("category") or [],
        "pending": False,
        "payment_channel": None,
    }
    storage.upsert_transactions(acc["source_id"], added=[tx])
    return tx


# --- CSV parsing ------------------------------------------------------------

_DATE_CANDIDATES = ["date", "transaction date", "posted date", "posting date", "post date", "trans date"]
_DESC_CANDIDATES = ["description", "name", "payee", "merchant", "memo", "details", "transaction"]
_AMOUNT_CANDIDATES = ["amount", "transaction amount"]
_DEBIT_CANDIDATES = ["debit", "withdrawal", "withdrawals", "outflow", "out"]
_CREDIT_CANDIDATES = ["credit", "deposit", "deposits", "inflow", "in"]

# Fidelity's standard activity export has a consistent column set. We detect
# it up front and use a dedicated parser so we keep the Action verb in the
# description and pin the sign convention correctly (Fidelity uses
# inflow-positive, which we flip to our outflow-positive canonical form).
_FIDELITY_SIGNATURE = {"run date", "action", "amount ($)"}


def _norm(h: str) -> str:
    return (h or "").strip().lower().lstrip("\ufeff")


def _pick(headers_norm: List[str], candidates: List[str]) -> Optional[int]:
    for i, h in enumerate(headers_norm):
        if h in candidates:
            return i
    # Fallback: substring match.
    for i, h in enumerate(headers_norm):
        if any(c in h for c in candidates):
            return i
    return None


def _parse_date(value: str) -> Optional[str]:
    v = (value or "").strip()
    if not v:
        return None
    fmts = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for f in fmts:
        try:
            return datetime.strptime(v, f).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(value: str) -> Optional[float]:
    v = (value or "").strip()
    if not v:
        return None
    v = v.replace("$", "").replace(",", "").replace(" ", "")
    # Parens = negative, a common accounting convention.
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]
    try:
        return float(v)
    except ValueError:
        return None


def _make_txid(account_id: str, date: str, name: str, amount: float) -> str:
    raw = f"{account_id}|{date}|{name}|{amount:.2f}"
    return "csv_" + hashlib.sha1(raw.encode()).hexdigest()[:20]


def import_csv(
    account_id: str,
    file_bytes: bytes,
    sign_convention: str = "auto",  # "auto", "outflow_positive", "inflow_positive"
) -> Dict[str, Any]:
    """Parse a CSV and insert its rows as transactions on ``account_id``.

    Returns a result dict with detected column mapping, import counts, and
    any per-row errors.
    """
    acc = storage.get_account(account_id)
    if not acc:
        raise ValueError(f"account {account_id} not found")

    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV is empty")

    # Fast path: Fidelity activity export.
    fid_header_idx = _find_fidelity_header(rows)
    if fid_header_idx is not None:
        fid_header = rows[fid_header_idx]
        fid_header_norm = [_norm(h) for h in fid_header]
        return _import_fidelity(
            account_id, acc, rows, fid_header_idx, fid_header, fid_header_norm
        )

    header = rows[0]
    header_norm = [_norm(h) for h in header]

    date_idx = _pick(header_norm, _DATE_CANDIDATES)
    desc_idx = _pick(header_norm, _DESC_CANDIDATES)
    amount_idx = _pick(header_norm, _AMOUNT_CANDIDATES)
    debit_idx = _pick(header_norm, _DEBIT_CANDIDATES)
    credit_idx = _pick(header_norm, _CREDIT_CANDIDATES)

    if date_idx is None:
        raise ValueError("could not find a date column (looked for: date / transaction date / posted)")
    if desc_idx is None:
        raise ValueError("could not find a description column (looked for: description / name / payee / memo)")
    if amount_idx is None and (debit_idx is None or credit_idx is None):
        raise ValueError(
            "could not find an amount column — need either `amount` or both `debit` and `credit` columns"
        )

    detected = {
        "date": header[date_idx],
        "description": header[desc_idx],
    }
    if amount_idx is not None:
        detected["amount"] = header[amount_idx]
    if debit_idx is not None:
        detected["debit"] = header[debit_idx]
    if credit_idx is not None:
        detected["credit"] = header[credit_idx]

    imported: List[Dict[str, Any]] = []
    errors: List[str] = []
    skipped = 0

    # First pass: collect parsed rows without yet deciding the sign.
    parsed: List[Tuple[str, str, float]] = []
    for i, row in enumerate(rows[1:], start=2):
        if not row or all(not c for c in row):
            skipped += 1
            continue
        try:
            date_raw = row[date_idx] if date_idx < len(row) else ""
            desc_raw = row[desc_idx] if desc_idx < len(row) else ""
            date = _parse_date(date_raw)
            if not date:
                errors.append(f"row {i}: unparseable date {date_raw!r}")
                skipped += 1
                continue
            desc = desc_raw.strip() or "(unknown)"

            if amount_idx is not None:
                raw = row[amount_idx] if amount_idx < len(row) else ""
                amt = _parse_amount(raw)
                if amt is None:
                    errors.append(f"row {i}: unparseable amount {raw!r}")
                    skipped += 1
                    continue
            else:
                debit_raw = row[debit_idx] if debit_idx is not None and debit_idx < len(row) else ""
                credit_raw = row[credit_idx] if credit_idx is not None and credit_idx < len(row) else ""
                d = _parse_amount(debit_raw) or 0.0
                c = _parse_amount(credit_raw) or 0.0
                # Debit/credit columns already tell us direction explicitly —
                # debits are outflows (positive in our convention), credits
                # are inflows (negative).
                amt = d - c
            parsed.append((date, desc, amt))
        except Exception as e:
            errors.append(f"row {i}: {e}")
            skipped += 1

    # Decide the sign convention.
    flip = False
    if amount_idx is not None:
        if sign_convention == "inflow_positive":
            flip = True
        elif sign_convention == "outflow_positive":
            flip = False
        else:
            # Heuristic: in most bank exports the "amount" column is negative
            # for debits and positive for deposits (inflow_positive). Flip so
            # that outflows are positive to match Plaid convention.
            n_neg = sum(1 for _, _, a in parsed if a < 0)
            n_pos = sum(1 for _, _, a in parsed if a > 0)
            if n_neg >= n_pos:
                flip = True
    # debit/credit mode already produces outflow-positive; never flip.

    for date, desc, amt in parsed:
        final_amt = -amt if flip else amt
        tx = {
            "transaction_id": _make_txid(account_id, date, desc, final_amt),
            "account_id": account_id,
            "source_id": acc["source_id"],
            "date": date,
            "name": desc,
            "merchant_name": desc,
            "amount": round(final_amt, 2),
            "iso_currency_code": acc.get("iso_currency_code") or "USD",
            "category": [],
            "pending": False,
            "payment_channel": None,
        }
        imported.append(tx)

    n_added = storage.upsert_transactions(acc["source_id"], added=imported)
    storage.update_source(acc["source_id"], last_synced_at=datetime.utcnow().isoformat())

    return {
        "detected_columns": detected,
        "row_count": len(rows) - 1,
        "imported": n_added,
        "skipped": skipped + (len(imported) - n_added),  # dupes + row parse errors
        "errors": errors[:50],
        "flipped_sign": flip,
    }


# --- Fidelity-specific CSV parser -------------------------------------------

def _find_fidelity_header(rows: List[List[str]]) -> Optional[int]:
    """Locate the Fidelity header row.

    Fidelity's CSV export sometimes has a couple of preamble rows (account
    name, date range) before the actual header, so we scan the first 20 rows
    instead of assuming row 0.
    """
    for i, row in enumerate(rows[:20]):
        norm = {_norm(h) for h in row}
        if _FIDELITY_SIGNATURE.issubset(norm):
            return i
    return None


def _import_fidelity(
    account_id: str,
    acc: Dict[str, Any],
    rows: List[List[str]],
    header_idx: int,
    header: List[str],
    header_norm: List[str],
) -> Dict[str, Any]:
    """Parse a Fidelity activity CSV into transactions for a single account.

    Supports both Fidelity export formats:
    - Single-account: ``Security Description`` column, may have ``Cash Balance ($)``
    - Multi-account (all-accounts export): ``Account``, ``Account Number``,
      ``Description`` column

    We build a richer description than the generic parser (``YOU BOUGHT VOO
    (VANGUARD S&P 500 ETF)``) and pin sign convention since Fidelity is always
    inflow-positive.
    """
    parsed = _parse_fidelity_rows(rows, header_idx, header, header_norm)

    detected = parsed["detected"]
    imported: List[Dict[str, Any]] = []

    for tx_row in parsed["transactions"]:
        tx = {
            "transaction_id": _make_txid(account_id, tx_row["date"], tx_row["desc"], tx_row["amount"]),
            "account_id": account_id,
            "source_id": acc["source_id"],
            "date": tx_row["date"],
            "name": tx_row["desc"],
            "merchant_name": tx_row["symbol"] or tx_row["desc"],
            "amount": tx_row["amount"],
            "iso_currency_code": acc.get("iso_currency_code") or "USD",
            "category": ["Fidelity"],
            "pending": False,
            "payment_channel": None,
        }
        imported.append(tx)

    n_added = storage.upsert_transactions(acc["source_id"], added=imported)
    storage.update_source(acc["source_id"], last_synced_at=datetime.utcnow().isoformat())

    data_row_count = len(rows) - (header_idx + 1)
    return {
        "detected_columns": detected,
        "row_count": max(data_row_count, 0),
        "imported": n_added,
        "skipped": parsed["skipped"] + (len(imported) - n_added),
        "errors": parsed["errors"][:50],
        "flipped_sign": True,
        "format": "fidelity",
    }


def _parse_fidelity_rows(
    rows: List[List[str]],
    header_idx: int,
    header: List[str],
    header_norm: List[str],
) -> Dict[str, Any]:
    """Parse Fidelity rows into a list of transaction dicts grouped by account.

    Returns ``{detected, transactions, by_account, skipped, errors}`` where
    ``transactions`` is a flat list and ``by_account`` groups them by account
    name (present only for multi-account exports).
    """

    def col(name: str) -> Optional[int]:
        try:
            return header_norm.index(name)
        except ValueError:
            return None

    date_idx = col("run date")
    action_idx = col("action")
    symbol_idx = col("symbol")
    amount_idx = col("amount ($)")
    # Fidelity uses "security description" or "description" depending on export type
    secdesc_idx = col("security description") or col("description")
    # Multi-account exports include these columns
    account_name_idx = col("account")
    account_num_idx = col("account number")
    cash_bal_idx = col("cash balance ($)")

    assert date_idx is not None and action_idx is not None and amount_idx is not None

    detected: Dict[str, str] = {
        "date": header[date_idx],
        "action": header[action_idx],
        "amount": header[amount_idx],
    }
    if secdesc_idx is not None:
        detected["description"] = header[secdesc_idx]
    if symbol_idx is not None:
        detected["symbol"] = header[symbol_idx]
    if account_name_idx is not None:
        detected["account"] = header[account_name_idx]

    transactions: List[Dict[str, Any]] = []
    by_account: Dict[str, List[Dict[str, Any]]] = {}
    errors: List[str] = []
    skipped = 0

    def cell(row: List[str], idx: Optional[int]) -> str:
        if idx is None or idx >= len(row):
            return ""
        return (row[idx] or "").strip()

    for i, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not row or all(not (c or "").strip() for c in row):
            skipped += 1
            continue
        try:
            date = _parse_date(cell(row, date_idx))
            if not date:
                skipped += 1
                continue
            amt = _parse_amount(cell(row, amount_idx))
            if amt is None:
                skipped += 1
                continue

            action = cell(row, action_idx)
            symbol = cell(row, symbol_idx)
            secdesc = cell(row, secdesc_idx)

            parts: List[str] = []
            if action:
                parts.append(action)
            if symbol and symbol.lower() not in action.lower():
                parts.append(symbol)
            if secdesc and secdesc.lower() not in action.lower():
                parts.append(f"({secdesc})")
            desc = " ".join(parts).strip() or "(fidelity)"

            # Fidelity amounts are inflow-positive → flip to outflow-positive
            final_amt = round(-amt, 2)

            acct_name = cell(row, account_name_idx) if account_name_idx is not None else None
            acct_num = cell(row, account_num_idx) if account_num_idx is not None else None

            tx_row: Dict[str, Any] = {
                "date": date,
                "desc": desc,
                "symbol": symbol,
                "amount": final_amt,
                "account_name": acct_name,
                "account_number": acct_num,
            }
            transactions.append(tx_row)

            if acct_name:
                key = acct_name
                if acct_num:
                    key = f"{acct_name} ({acct_num})"
                by_account.setdefault(key, []).append(tx_row)
        except Exception as e:
            errors.append(f"row {i}: {e}")
            skipped += 1

    return {
        "detected": detected,
        "transactions": transactions,
        "by_account": by_account,
        "skipped": skipped,
        "errors": errors,
        "has_account_column": account_name_idx is not None,
    }


