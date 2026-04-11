"""Net worth computation from cached accounts + liabilities."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from models import AssetBucket, LiabilityBucket, NetWorthSnapshot


# Map Plaid account (type, subtype) → our asset/liability bucket label.
def _classify(account: Dict) -> tuple[str, str]:
    """Returns (side, label) where side is 'asset' or 'liability'."""
    t = (account.get("type") or "").lower()
    sub = (account.get("subtype") or "").lower()

    if t == "depository":
        return "asset", "Cash"
    if t in ("investment", "brokerage"):
        if sub in ("401k", "403b", "457b", "ira", "roth", "roth 401k", "rollover ira", "sep ira", "simple ira", "retirement", "pension"):
            return "asset", "Retirement"
        if sub in ("crypto exchange", "crypto"):
            return "asset", "Crypto"
        return "asset", "Investments"
    if t == "loan":
        if sub == "student":
            return "liability", "Student Loans"
        if sub == "mortgage":
            return "liability", "Mortgages"
        if sub in ("auto", "home equity"):
            return "liability", "Auto & Home Equity"
        return "liability", "Other Debt"
    if t == "credit":
        return "liability", "Credit Cards"
    if t == "other":
        return "asset", "Other Assets"
    return "asset", "Other Assets"


def compute_net_worth(accounts: List[Dict]) -> NetWorthSnapshot:
    assets: Dict[str, List[Dict]] = defaultdict(list)
    liabilities: Dict[str, List[Dict]] = defaultdict(list)

    for acc in accounts:
        side, label = _classify(acc)
        balance = float(acc.get("current_balance") or 0.0)
        # For credit accounts Plaid returns the balance as a positive number
        # representing how much you owe, so we use it as-is on the liability
        # side. Loans work the same way.
        if side == "asset":
            assets[label].append({"account_id": acc["account_id"], "amount": balance})
        else:
            liabilities[label].append({"account_id": acc["account_id"], "amount": balance})

    asset_buckets: List[AssetBucket] = []
    for label, items in assets.items():
        asset_buckets.append(
            AssetBucket(
                label=label,
                amount=round(sum(i["amount"] for i in items), 2),
                account_ids=[i["account_id"] for i in items],
            )
        )
    asset_buckets.sort(key=lambda b: b.amount, reverse=True)

    liab_buckets: List[LiabilityBucket] = []
    for label, items in liabilities.items():
        liab_buckets.append(
            LiabilityBucket(
                label=label,
                amount=round(sum(i["amount"] for i in items), 2),
                account_ids=[i["account_id"] for i in items],
            )
        )
    liab_buckets.sort(key=lambda b: b.amount, reverse=True)

    total_assets = round(sum(b.amount for b in asset_buckets), 2)
    total_liabilities = round(sum(b.amount for b in liab_buckets), 2)

    return NetWorthSnapshot(
        as_of=datetime.utcnow().isoformat(),
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=round(total_assets - total_liabilities, 2),
        assets=asset_buckets,
        liabilities=liab_buckets,
    )
