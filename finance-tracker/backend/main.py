"""FastAPI entry point for finance-tracker.

Endpoints
---------
GET  /status                      — configuration + link count
POST /link/token                  — create a Plaid Link token for the frontend
POST /link/exchange               — exchange a public_token and kick off initial sync
GET  /items                       — linked institutions
DELETE /items/{item_id}           — unlink an institution (local + plaid side)
POST /sync                        — refresh accounts/transactions/investments/liabilities
POST /sync/{item_id}              — refresh a single item
GET  /accounts                    — all cached accounts
GET  /transactions                — cached transactions (paginated)
GET  /networth                    — asset/liability breakdown
GET  /subscriptions               — detected recurring charges
GET  /income                      — income summary
GET  /dashboard                   — headline numbers for the overview screen
GET  /goals                       — list goals
POST /goals                       — create/update a goal
DELETE /goals/{goal_id}           — delete a goal
POST /plan                        — run goal projections against cash flow
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import storage
from income import monthly_spending, summarize_income
from models import (
    Account,
    DashboardSummary,
    ExchangeTokenRequest,
    ExchangeTokenResponse,
    Goal,
    LinkedItem,
    LinkTokenResponse,
    NetWorthSnapshot,
    PlanRequest,
    PlanResponse,
    Subscription,
    Transaction,
)
from networth import compute_net_worth
from plaid_client import get_client
from planning import build_plan
from subscriptions import detect_subscriptions

log = logging.getLogger("finance-tracker")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="finance-tracker", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- helpers ----------------------------------------------------------------

def _item_by_id(item_id: str) -> dict:
    item = storage.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return item


def _sync_one(item: dict) -> dict:
    client = get_client()
    access_token = item["access_token"]
    item_id = item["item_id"]
    errors: List[str] = []

    # Accounts
    try:
        accounts = client.get_accounts(access_token)
        for a in accounts:
            a["item_id"] = item_id
            a["institution_name"] = item.get("institution_name")
        storage.replace_accounts_for_item(item_id, accounts)
    except Exception as e:  # pragma: no cover - network path
        log.exception("accounts sync failed for %s", item_id)
        errors.append(f"accounts: {e}")

    # Transactions (incremental via /transactions/sync)
    try:
        result = client.sync_transactions(access_token, item.get("transactions_cursor"))
        storage.upsert_transactions(
            item_id,
            added=result["added"],
            modified=result["modified"],
            removed_ids=result["removed"],
        )
        storage.update_item(item_id, transactions_cursor=result["cursor"])
    except Exception as e:  # pragma: no cover
        log.exception("transactions sync failed for %s", item_id)
        errors.append(f"transactions: {e}")

    # Investments (optional — not every institution has this)
    try:
        inv = client.get_investments(access_token)
        storage.save_investments(item_id, inv)
    except Exception as e:  # pragma: no cover
        log.warning("investments sync failed for %s: %s", item_id, e)

    # Liabilities
    try:
        liab = client.get_liabilities(access_token)
        storage.save_liabilities(item_id, liab)
    except Exception as e:  # pragma: no cover
        log.warning("liabilities sync failed for %s: %s", item_id, e)

    now = datetime.utcnow().isoformat()
    storage.update_item(
        item_id,
        last_synced_at=now,
        error="; ".join(errors) if errors else None,
    )
    return {"item_id": item_id, "last_synced_at": now, "errors": errors}


# --- config / status --------------------------------------------------------

@app.get("/status")
def status():
    client = get_client()
    items = storage.list_items()
    accounts = storage.list_accounts()
    return {
        **client.status(),
        "linked_item_count": len(items),
        "account_count": len(accounts),
        "last_synced_at": max((i.get("last_synced_at") or "" for i in items), default=None) or None,
    }


# --- Plaid link flow --------------------------------------------------------

@app.post("/link/token", response_model=LinkTokenResponse)
def create_link_token():
    client = get_client()
    if not client.configured:
        raise HTTPException(
            status_code=400,
            detail="Plaid client not configured. Set PLAID_CLIENT_ID and PLAID_SECRET in backend/.env.",
        )
    try:
        return LinkTokenResponse(**client.create_link_token())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Plaid error: {e}")


@app.post("/link/exchange", response_model=ExchangeTokenResponse)
def exchange_link_token(req: ExchangeTokenRequest):
    client = get_client()
    try:
        tokens = client.exchange_public_token(req.public_token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Plaid exchange failed: {e}")

    institution_name = req.institution_name
    if req.institution_id and not institution_name:
        inst = client.get_institution(req.institution_id)
        if inst:
            institution_name = inst["name"]

    record = storage.save_item(
        item_id=tokens["item_id"],
        access_token=tokens["access_token"],
        institution_name=institution_name,
        institution_id=req.institution_id,
    )
    # Initial sync so the dashboard has data immediately.
    try:
        _sync_one(record)
    except Exception as e:
        log.exception("initial sync failed")
        storage.update_item(record["item_id"], error=str(e))

    return ExchangeTokenResponse(item_id=tokens["item_id"], institution_name=institution_name)


# --- items ------------------------------------------------------------------

@app.get("/items", response_model=List[LinkedItem])
def list_items():
    items = storage.list_items()
    accounts = storage.list_accounts()
    counts: dict = {}
    for a in accounts:
        counts[a.get("item_id")] = counts.get(a.get("item_id"), 0) + 1
    out: List[LinkedItem] = []
    for i in items:
        out.append(
            LinkedItem(
                item_id=i["item_id"],
                institution_name=i.get("institution_name"),
                institution_id=i.get("institution_id"),
                linked_at=i.get("linked_at") or "",
                last_synced_at=i.get("last_synced_at"),
                account_count=counts.get(i["item_id"], 0),
                error=i.get("error"),
            )
        )
    return out


@app.delete("/items/{item_id}")
def delete_item(item_id: str):
    item = _item_by_id(item_id)
    client = get_client()
    client.remove_item(item["access_token"])
    storage.delete_item(item_id)
    return {"ok": True}


# --- sync -------------------------------------------------------------------

@app.post("/sync")
def sync_all():
    items = storage.list_items()
    results = [_sync_one(i) for i in items]
    return {"synced": len(results), "results": results}


@app.post("/sync/{item_id}")
def sync_one(item_id: str):
    return _sync_one(_item_by_id(item_id))


# --- data -------------------------------------------------------------------

@app.get("/accounts", response_model=List[Account])
def list_accounts():
    return [Account(**a) for a in storage.list_accounts()]


@app.get("/transactions", response_model=List[Transaction])
def list_transactions(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    account_id: Optional[str] = None,
):
    txns = storage.list_transactions()
    if account_id:
        txns = [t for t in txns if t.get("account_id") == account_id]
    txns.sort(key=lambda t: t.get("date", ""), reverse=True)
    sliced = txns[offset : offset + limit]
    return [Transaction(**t) for t in sliced]


@app.get("/networth", response_model=NetWorthSnapshot)
def networth():
    return compute_net_worth(storage.list_accounts())


@app.get("/subscriptions", response_model=List[Subscription])
def subscriptions():
    return detect_subscriptions(storage.list_transactions())


@app.get("/income")
def income(window_days: int = Query(90, ge=30, le=365)):
    return summarize_income(storage.list_transactions(), window_days=window_days)


@app.get("/dashboard", response_model=DashboardSummary)
def dashboard():
    accounts = storage.list_accounts()
    txns = storage.list_transactions()
    items = storage.list_items()
    nw = compute_net_worth(accounts)
    inc = summarize_income(txns, window_days=90)
    subs = detect_subscriptions(txns)
    subs_total = round(sum(s.annualized_cost / 12.0 for s in subs if s.status == "active"), 2)
    spending = monthly_spending(txns)
    last = max((i.get("last_synced_at") or "" for i in items), default=None) or None
    return DashboardSummary(
        net_worth=nw,
        monthly_income=inc.total_monthly,
        monthly_spending=spending,
        monthly_subscriptions_total=subs_total,
        subscription_count=len([s for s in subs if s.status == "active"]),
        linked_item_count=len(items),
        account_count=len(accounts),
        last_synced_at=last,
    )


# --- goals ------------------------------------------------------------------

@app.get("/goals", response_model=List[Goal])
def list_goals():
    return [Goal(**g) for g in storage.list_goals()]


@app.post("/goals", response_model=Goal)
def save_goal(goal: Goal):
    saved = storage.save_goal(goal.model_dump(exclude_none=True))
    return Goal(**saved)


@app.delete("/goals/{goal_id}")
def delete_goal(goal_id: str):
    storage.delete_goal(goal_id)
    return {"ok": True}


# --- planning ---------------------------------------------------------------

@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    txns = storage.list_transactions()
    inc = summarize_income(txns, window_days=90)
    subs = detect_subscriptions(txns)
    subs_total = sum(s.annualized_cost / 12.0 for s in subs if s.status == "active")
    spending = monthly_spending(txns)
    return build_plan(
        goals=req.goals,
        annual_rate=req.assumed_return_annual,
        monthly_income=inc.total_monthly,
        monthly_spending=spending,
        monthly_subscriptions=subs_total,
    )
