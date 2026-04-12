"""Income and spending analytics derived from synced transactions.

Only transactions from depository-type accounts (checking, savings, cash
management) are considered. Investment/brokerage buys, 401k contributions,
and loan payments look like spending but aren't — they distort the numbers.

SimpleFIN sometimes surfaces the same underlying bank transaction across
multiple sub-accounts (e.g. "Spend" and "Reserve" buckets at the same
bank). We deduplicate by (date, amount, normalized name) before counting.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from models import IncomeDeposit, IncomeSource, IncomeSummary


# Plaid categories that strongly indicate paycheck / income deposits.
_INCOME_CATEGORIES = {"Payroll", "Transfer", "Deposit", "Interest Earned"}
_PAYROLL_KEYWORDS = (
    "payroll", "direct dep", "direct deposit", "salary", "wages", "paycheck",
    "employer", "compensation", "ach deposit",
)

# Keywords that signal internal transfers between the user's own accounts,
# which should NOT be counted as income or spending. These catch transfers
# that lack Plaid categories (SimpleFIN / CSV imports).
_TRANSFER_KEYWORDS = (
    "transfer", "xfer", "ach transfer", "wire transfer", "zelle",
    "venmo", "cashapp", "paypal transfer", "payment thank you",
    "autopay", "online payment", "bill pay", "payment from",
    "payment to", "credit card payment", "loan payment",
)

# Account types whose transactions are relevant for income detection.
_INCOME_ACCOUNT_TYPES = {"depository"}
# Account types whose transactions are relevant for spending.
# Includes credit cards so purchases show up, but credit card *payments*
# from checking are filtered out as transfers to avoid double-counting.
_SPENDING_ACCOUNT_TYPES = {"depository", "credit"}

# Used to strip trailing reference codes when deduplicating.
_TRAILING_REF_RE = re.compile(r"\s+[A-Z0-9]{6,}$")


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s[:10])


def _account_ids_for_types(accounts: List[Dict], types: Set[str]) -> Set[str]:
    return {
        a["account_id"]
        for a in accounts
        if (a.get("type") or "").lower() in types
    }


def _dedup_key(t: Dict) -> str:
    """Build a key that matches the same real-world transaction across accounts.

    SimpleFIN can report the same ACH credit/debit on multiple sub-accounts
    at the same bank. We collapse them by (date, amount, name-without-ref).
    """
    name = (t.get("name") or "").strip()
    # Strip trailing alphanumeric reference codes that vary per sub-account
    name = _TRAILING_REF_RE.sub("", name).lower()
    return f"{t.get('date', '')}|{float(t.get('amount', 0)):.2f}|{name}"


def _deduplicate(transactions: List[Dict]) -> List[Dict]:
    """Remove duplicate transactions that appear across sub-accounts."""
    seen: Dict[str, Dict] = {}
    for t in transactions:
        key = _dedup_key(t)
        if key not in seen:
            seen[key] = t
    return list(seen.values())


def _looks_like_transfer(t: Dict) -> bool:
    """Heuristic: does this transaction look like an internal transfer?"""
    # Plaid categories tell us directly.
    categories = {c for c in (t.get("category") or [])}
    if "Transfer" in categories or "Payment" in categories:
        return True
    # Fall back to name matching (SimpleFIN / CSV have no categories).
    name = ((t.get("name") or "") + " " + (t.get("merchant_name") or "")).lower()
    return any(k in name for k in _TRANSFER_KEYWORDS)


def _is_income(t: Dict) -> bool:
    # In Plaid's convention, money IN is a negative amount.
    if (t.get("amount") or 0) >= 0:
        return False
    if t.get("pending"):
        return False
    categories = {c for c in (t.get("category") or [])}
    if categories & _INCOME_CATEGORIES:
        if "Transfer" in categories:
            # Transfers include a LOT of noise — require keyword confirmation.
            name = ((t.get("name") or "") + " " + (t.get("merchant_name") or "")).lower()
            return any(k in name for k in _PAYROLL_KEYWORDS)
        return True
    name = ((t.get("name") or "") + " " + (t.get("merchant_name") or "")).lower()
    return any(k in name for k in _PAYROLL_KEYWORDS)


def _estimate_monthly(txns: List[Dict], avg_amount: float, window_days: int) -> float:
    """Estimate monthly income from a group of same-source transactions.

    With 2+ transactions we detect the cadence from the gaps between them
    (e.g. ~14 days → biweekly → ~2.14 per month). With only 1 transaction
    we fall back to dividing by the window in months.
    """
    if len(txns) < 2:
        months = max(window_days / 30.0, 1.0)
        return avg_amount / months

    dates = sorted(_parse_date(t["date"]) for t in txns)
    gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    avg_gap = sum(gaps) / len(gaps)

    if avg_gap <= 0:
        avg_gap = 30.0

    payments_per_month = 30.0 / avg_gap
    return avg_amount * payments_per_month


def summarize_income(
    transactions: List[Dict],
    window_days: int = 90,
    accounts: Optional[List[Dict]] = None,
) -> IncomeSummary:
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    if accounts:
        valid_ids = _account_ids_for_types(accounts, _INCOME_ACCOUNT_TYPES)
        scoped = [t for t in transactions if t.get("account_id") in valid_ids]
    else:
        scoped = transactions

    scoped = _deduplicate(scoped)
    income = [t for t in scoped if _is_income(t) and _parse_date(t["date"]) >= cutoff]

    groups: Dict[str, List[Dict]] = defaultdict(list)
    for t in income:
        key = (t.get("merchant_name") or t.get("name") or "Unknown").strip() or "Unknown"
        groups[key].append(t)

    sources: List[IncomeSource] = []
    total_monthly = 0.0

    for name, txns in groups.items():
        avg_amount = -sum(float(t["amount"]) for t in txns) / len(txns)
        monthly = _estimate_monthly(txns, avg_amount, window_days)
        last = max(txns, key=lambda t: t["date"])
        deposits = sorted(
            [
                IncomeDeposit(
                    date=t["date"],
                    amount=round(-float(t["amount"]), 2),
                    description=(t.get("name") or "").strip(),
                )
                for t in txns
            ],
            key=lambda d: d.date,
            reverse=True,
        )
        sources.append(
            IncomeSource(
                name=name,
                average_monthly=round(monthly, 2),
                last_payment_date=str(last.get("date")),
                last_payment_amount=round(-float(last["amount"]), 2),
                transaction_count=len(txns),
                deposits=deposits,
            )
        )
        total_monthly += monthly

    sources.sort(key=lambda s: s.average_monthly, reverse=True)
    return IncomeSummary(
        total_monthly=round(total_monthly, 2),
        sources=sources,
        window_days=window_days,
    )


def _get_spending_transactions(
    transactions: List[Dict],
    window_days: int = 30,
    accounts: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Return deduplicated, non-transfer outflows from spending-eligible accounts."""
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    if accounts:
        valid_ids = _account_ids_for_types(accounts, _SPENDING_ACCOUNT_TYPES)
        scoped = [t for t in transactions if t.get("account_id") in valid_ids]
    else:
        scoped = transactions

    scoped = _deduplicate(scoped)
    result = []
    for t in scoped:
        if (t.get("amount") or 0) <= 0 or t.get("pending"):
            continue
        if _parse_date(t["date"]) < cutoff:
            continue
        if _looks_like_transfer(t):
            continue
        result.append(t)
    return result


def monthly_spending(
    transactions: List[Dict],
    window_days: int = 30,
    accounts: Optional[List[Dict]] = None,
) -> float:
    spending = _get_spending_transactions(transactions, window_days, accounts)
    return round(sum(float(t["amount"]) for t in spending), 2)


_BUCKET_NAMES = ("subscriptions", "bills", "work_expenses", "food", "vacation", "other")

# Map category rule values → bucket keys
_CATEGORY_TO_BUCKET = {
    "subscription": "subscriptions",
    "subscriptions": "subscriptions",
    "bill": "bills",
    "bills": "bills",
    "work_expense": "work_expenses",
    "work_expenses": "work_expenses",
    "food": "food",
    "vacation": "vacation",
    "other": "other",
}


_CHECK_NUMBER_RE = re.compile(r"check\s*#?\s*(\d+)", re.IGNORECASE)

# Frequency → monthly multiplier
_FREQ_TO_MONTHLY: Dict[str, float] = {
    "weekly": 52.0 / 12.0,
    "biweekly": 26.0 / 12.0,
    "monthly": 1.0,
    "quarterly": 1.0 / 3.0,
    "annual": 1.0 / 12.0,
}


def spending_breakdown(
    transactions: List[Dict],
    merchant_categories: Dict[str, str],
    window_days: int = 30,
    accounts: Optional[List[Dict]] = None,
    frequency_rules: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Categorize spending into subscriptions, bills, work expenses, food, other.

    ``merchant_categories`` maps normalized merchant names to a category
    string. Both auto-detected (from subscriptions.py) and user-defined
    rules should be merged before passing — user rules take priority.

    ``frequency_rules`` maps normalized merchant names to a frequency string
    (weekly, biweekly, monthly, quarterly, annual). Used to calculate
    projected costs for subscription and bill buckets.
    """
    frequency_rules = frequency_rules or {}
    spending = _get_spending_transactions(transactions, window_days, accounts)

    # Build account lookup
    account_map: Dict[str, str] = {}
    if accounts:
        for a in accounts:
            label = a.get("name") or ""
            inst = a.get("institution_name")
            if inst:
                label = f"{inst} — {label}"
            account_map[a["account_id"]] = label

    buckets: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _BUCKET_NAMES}
    totals: Dict[str, float] = {k: 0.0 for k in _BUCKET_NAMES}

    for t in spending:
        merchant_key = _normalize_for_match(t.get("merchant_name") or t.get("name") or "")
        raw_kind = merchant_categories.get(merchant_key, "other")
        bucket = _CATEGORY_TO_BUCKET.get(raw_kind, "other")

        name = (t.get("name") or "").strip()
        entry: Dict[str, Any] = {
            "date": t["date"],
            "name": name,
            "amount": round(float(t["amount"]), 2),
            "merchant_key": merchant_key,
            "category": bucket,
            "account_name": account_map.get(t.get("account_id", ""), ""),
        }

        # Extract check number if present
        check_match = _CHECK_NUMBER_RE.search(name) or _CHECK_NUMBER_RE.search(
            t.get("merchant_name") or ""
        )
        if check_match:
            entry["check_number"] = check_match.group(1)

        # Include frequency if set
        freq = frequency_rules.get(merchant_key)
        if freq:
            entry["frequency"] = freq

        buckets[bucket].append(entry)
        totals[bucket] += float(t["amount"])

    for b in buckets.values():
        b.sort(key=lambda x: x["date"], reverse=True)

    result: Dict[str, Any] = {
        "window_days": window_days,
        "total": round(sum(totals.values()), 2),
    }
    for k in _BUCKET_NAMES:
        bucket_data: Dict[str, Any] = {
            "total": round(totals[k], 2),
            "transactions": buckets[k],
        }
        # For subscriptions and bills, compute projected costs from frequencies
        if k in ("subscriptions", "bills"):
            bucket_data.update(_compute_projected_costs(buckets[k], frequency_rules))
        result[k] = bucket_data
    return result


def _compute_projected_costs(
    transactions: List[Dict[str, Any]],
    frequency_rules: Dict[str, str],
) -> Dict[str, Any]:
    """Aggregate per-merchant costs and project monthly/annual equivalents."""
    # Group by merchant_key, compute average amount per merchant
    merchant_amounts: Dict[str, List[float]] = defaultdict(list)
    for t in transactions:
        merchant_amounts[t["merchant_key"]].append(t["amount"])

    monthly_total = 0.0
    for merchant_key, amounts in merchant_amounts.items():
        avg = sum(amounts) / len(amounts)
        freq = frequency_rules.get(merchant_key)
        multiplier = _FREQ_TO_MONTHLY.get(freq or "", 0.0)
        if multiplier:
            monthly_total += avg * multiplier

    return {
        "monthly_equivalent": round(monthly_total, 2),
        "annual_equivalent": round(monthly_total * 12, 2),
    }


def _normalize_for_match(name: str) -> str:
    """Normalize a merchant name for matching against subscription merchants."""
    n = (name or "").lower()
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = re.sub(r"\s+\d+$", "", n)
    n = " ".join(n.split())
    for prefix in ("sq ", "tst ", "pp ", "paypal ", "venmo ", "cashout "):
        if n.startswith(prefix):
            n = n[len(prefix):]
    return n.strip()
