"""Detect recurring charges (subscriptions) from a list of transactions.

Plaid has a /transactions/recurring/get endpoint but it requires the
``transactions_recurring`` product. To stay portable and work with just the
base ``transactions`` product we roll our own detector:

1. Group charges by normalized merchant name.
2. For each group, inspect the gaps between consecutive charge dates and the
   variance of the amounts.
3. A subscription is a merchant with 3+ charges, reasonably stable amounts
   (coefficient of variation < 0.25), and gaps that cluster around a known
   cadence (weekly / bi-weekly / monthly / quarterly / annual) within a
   tolerance.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Dict, List

from models import Subscription


_CADENCES = [
    ("weekly", 7, 2),
    ("biweekly", 14, 3),
    ("monthly", 30, 6),
    ("quarterly", 91, 10),
    ("annual", 365, 20),
]

_FREQ_MULTIPLIER = {
    "weekly": 52,
    "biweekly": 26,
    "monthly": 12,
    "quarterly": 4,
    "annual": 1,
    "irregular": 0,
}

_STRIP_RE = re.compile(r"[^a-z0-9 ]+")
_NUM_TAIL_RE = re.compile(r"\s+\d+$")


def _normalize_merchant(name: str) -> str:
    n = (name or "").lower()
    n = _STRIP_RE.sub(" ", n)
    n = _NUM_TAIL_RE.sub("", n)
    n = " ".join(n.split())
    # Strip common payment-processor prefixes.
    for prefix in ("sq ", "tst ", "pp ", "paypal ", "venmo ", "cashout "):
        if n.startswith(prefix):
            n = n[len(prefix):]
    return n.strip()


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s[:10])


def _classify_cadence(gaps_days: List[float]) -> str:
    if not gaps_days:
        return "irregular"
    avg = mean(gaps_days)
    for name, target, tolerance in _CADENCES:
        if abs(avg - target) <= tolerance:
            return name
    return "irregular"


def detect_subscriptions(transactions: List[Dict]) -> List[Subscription]:
    # Only consider outflows (positive amounts in Plaid's sign convention).
    outflows = [t for t in transactions if (t.get("amount") or 0) > 0 and not t.get("pending")]
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for t in outflows:
        key = _normalize_merchant(t.get("merchant_name") or t.get("name") or "")
        if not key:
            continue
        groups[key].append(t)

    subs: List[Subscription] = []
    for merchant, txns in groups.items():
        if len(txns) < 3:
            continue
        txns.sort(key=lambda t: t["date"])
        amounts = [float(t["amount"]) for t in txns]
        dates = [_parse_date(t["date"]) for t in txns]

        # Coefficient of variation — low means amounts are stable.
        avg_amt = mean(amounts)
        if avg_amt <= 0:
            continue
        cv = (pstdev(amounts) / avg_amt) if len(amounts) > 1 else 0.0
        if cv > 0.25:
            continue

        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        cadence = _classify_cadence(gaps)
        if cadence == "irregular":
            continue

        last = dates[-1]
        target_gap = next((t for n, t, _ in _CADENCES if n == cadence), 30)
        next_expected = last + timedelta(days=target_gap)

        # Mark as inactive if the last charge is more than two cycles old.
        status = "active" if (datetime.utcnow() - last).days <= target_gap * 2 else "inactive"

        subs.append(
            Subscription(
                id=f"sub_{merchant.replace(' ', '_')}",
                merchant=merchant.title(),
                average_amount=round(avg_amt, 2),
                frequency=cadence,  # type: ignore[arg-type]
                last_charge_date=last.date().isoformat(),
                next_expected_date=next_expected.date().isoformat(),
                annualized_cost=round(avg_amt * _FREQ_MULTIPLIER[cadence], 2),
                sample_transaction_ids=[t["transaction_id"] for t in txns[-5:]],
                status=status,  # type: ignore[arg-type]
            )
        )

    subs.sort(key=lambda s: s.annualized_cost, reverse=True)
    return subs
