"""Income and spending analytics derived from synced transactions."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from models import IncomeSource, IncomeSummary


# Plaid categories that strongly indicate paycheck / income deposits.
_INCOME_CATEGORIES = {"Payroll", "Transfer", "Deposit", "Interest Earned"}
_PAYROLL_KEYWORDS = ("payroll", "direct dep", "direct deposit", "salary", "wages", "paycheck")


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s[:10])


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


def summarize_income(transactions: List[Dict], window_days: int = 90) -> IncomeSummary:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    income = [t for t in transactions if _is_income(t) and _parse_date(t["date"]) >= cutoff]

    groups: Dict[str, List[Dict]] = defaultdict(list)
    for t in income:
        key = (t.get("merchant_name") or t.get("name") or "Unknown").strip() or "Unknown"
        groups[key].append(t)

    sources: List[IncomeSource] = []
    total_monthly = 0.0
    months = max(window_days / 30.0, 1.0)

    for name, txns in groups.items():
        total = -sum(float(t["amount"]) for t in txns)  # flip sign to positive
        monthly = total / months
        last = max(txns, key=lambda t: t["date"])
        sources.append(
            IncomeSource(
                name=name,
                average_monthly=round(monthly, 2),
                last_payment_date=str(last.get("date")),
                last_payment_amount=round(-float(last["amount"]), 2),
                transaction_count=len(txns),
            )
        )
        total_monthly += monthly

    sources.sort(key=lambda s: s.average_monthly, reverse=True)
    return IncomeSummary(
        total_monthly=round(total_monthly, 2),
        sources=sources,
        window_days=window_days,
    )


def monthly_spending(transactions: List[Dict], window_days: int = 30) -> float:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    total = 0.0
    for t in transactions:
        if (t.get("amount") or 0) <= 0 or t.get("pending"):
            continue
        if _parse_date(t["date"]) < cutoff:
            continue
        categories = {c for c in (t.get("category") or [])}
        # Skip internal transfers / credit card payments so we don't double-count.
        if "Transfer" in categories or "Payment" in categories:
            continue
        total += float(t["amount"])
    return round(total, 2)
