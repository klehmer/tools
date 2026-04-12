"""FastAPI entry point for finance-tracker.

Sources
-------
A **source** is the unit of linked financial data. Three kinds are supported:

- ``plaid``    — account linked through Plaid Link
- ``simplefin``— SimpleFIN bridge connection (single access URL)
- ``manual``   — hand-entered accounts + CSV-imported transactions

The same user can combine all three: linked Plaid checking, SimpleFIN
brokerage, and a manual cash envelope, all rolled up into the same net
worth / subscriptions / goals panels.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import manual
import simplefin_client
import storage
from income import monthly_spending, spending_breakdown, summarize_income
from models import (
    Account,
    CategoryRuleRequest,
    CsvImportResult,
    DashboardSummary,
    ExchangeTokenRequest,
    ExchangeTokenResponse,
    Goal,
    LinkTokenResponse,
    ManualAccountInput,
    ManualBalanceUpdate,
    ManualTransactionInput,
    NetWorthSnapshot,
    PlaidConfigRequest,
    PlaidConfigResponse,
    PlanRequest,
    PlanResponse,
    SimpleFinClaimRequest,
    SimpleFinClaimResponse,
    Source,
    Subscription,
    Transaction,
)
from networth import compute_net_worth
from plaid_client import get_client, reset_client
from planning import build_plan
from subscriptions import detect_subscriptions

log = logging.getLogger("finance-tracker")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="finance-tracker", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- helpers ----------------------------------------------------------------

def _source_by_id(source_id: str) -> dict:
    source = storage.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    return source


def _config_response() -> PlaidConfigResponse:
    client = get_client()
    masked: Optional[str] = None
    if client.client_id:
        cid = client.client_id
        masked = f"{cid[:4]}…{cid[-4:]}" if len(cid) > 8 else "••••"
    return PlaidConfigResponse(
        configured=client.configured,
        env=client.env_name,
        client_id_masked=masked,
        has_secret=bool(client.secret),
        client_name=client.client_name,
        products=[p.value for p in client.products],
        country_codes=[c.value for c in client.country_codes],
    )


def _sync_plaid(source: dict) -> dict:
    client = get_client()
    if not client.configured:
        raise HTTPException(status_code=400, detail="Plaid is not configured")
    cfg = source.get("config") or {}
    access_token = cfg.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Plaid source has no access_token")
    source_id = source["source_id"]
    errors: List[str] = []

    try:
        accounts = client.get_accounts(access_token)
        for a in accounts:
            a["source_id"] = source_id
            a["source_kind"] = "plaid"
            a["institution_name"] = source.get("display_name")
            a["manual"] = False
        storage.replace_accounts_for_source(source_id, accounts)
    except Exception as e:
        log.exception("accounts sync failed for %s", source_id)
        errors.append(f"accounts: {e}")

    try:
        result = client.sync_transactions(access_token, cfg.get("transactions_cursor"))
        storage.upsert_transactions(
            source_id,
            added=result["added"],
            modified=result["modified"],
            removed_ids=result["removed"],
        )
        storage.update_source(source_id, config={"transactions_cursor": result["cursor"]})
    except Exception as e:
        log.exception("transactions sync failed for %s", source_id)
        errors.append(f"transactions: {e}")

    try:
        inv = client.get_investments(access_token)
        storage.save_investments(source_id, inv)
    except Exception as e:
        log.warning("investments sync failed for %s: %s", source_id, e)

    try:
        liab = client.get_liabilities(access_token)
        storage.save_liabilities(source_id, liab)
    except Exception as e:
        log.warning("liabilities sync failed for %s: %s", source_id, e)

    now = datetime.utcnow().isoformat()
    storage.update_source(
        source_id,
        last_synced_at=now,
        error="; ".join(errors) if errors else None,
    )
    return {"source_id": source_id, "kind": "plaid", "last_synced_at": now, "errors": errors}


def _sync_simplefin(source: dict) -> dict:
    cfg = source.get("config") or {}
    access_url = cfg.get("access_url")
    if not access_url:
        raise HTTPException(status_code=400, detail="SimpleFIN source has no access_url")
    source_id = source["source_id"]
    errors: List[str] = []
    try:
        payload = simplefin_client.fetch_accounts(access_url)
        normalized = simplefin_client.normalize_payload(
            source_id=source_id,
            display_name=source.get("display_name") or "SimpleFIN",
            payload=payload,
        )
        storage.replace_accounts_for_source(source_id, normalized["accounts"])
        storage.upsert_transactions(source_id, added=normalized["transactions"])
        errors.extend(normalized.get("errors") or [])
    except Exception as e:
        log.exception("simplefin sync failed for %s", source_id)
        errors.append(str(e))

    now = datetime.utcnow().isoformat()
    storage.update_source(
        source_id,
        last_synced_at=now,
        error="; ".join(errors) if errors else None,
    )
    return {"source_id": source_id, "kind": "simplefin", "last_synced_at": now, "errors": errors}


def _sync_one(source: dict) -> dict:
    kind = source.get("kind")
    if kind == "plaid":
        return _sync_plaid(source)
    if kind == "simplefin":
        return _sync_simplefin(source)
    if kind == "manual":
        now = datetime.utcnow().isoformat()
        storage.update_source(source["source_id"], last_synced_at=now, error=None)
        return {"source_id": source["source_id"], "kind": "manual", "last_synced_at": now, "errors": []}
    raise HTTPException(status_code=400, detail=f"unknown source kind: {kind}")


# --- status -----------------------------------------------------------------

@app.get("/status")
def status():
    client = get_client()
    sources = storage.list_sources()
    accounts = storage.list_accounts()
    kind_counts: dict = {}
    for s in sources:
        kind_counts[s.get("kind", "unknown")] = kind_counts.get(s.get("kind", "unknown"), 0) + 1
    return {
        **client.status(),
        "linked_source_count": len(sources),
        "source_counts_by_kind": kind_counts,
        "account_count": len(accounts),
        "last_synced_at": max((s.get("last_synced_at") or "" for s in sources), default=None) or None,
    }


# --- Plaid credential config -----------------------------------------------

@app.get("/config", response_model=PlaidConfigResponse)
def get_config():
    return _config_response()


@app.post("/config", response_model=PlaidConfigResponse)
def save_config(req: PlaidConfigRequest):
    if not req.client_id.strip() or not req.secret.strip():
        raise HTTPException(status_code=400, detail="client_id and secret are required")
    storage.save_plaid_config(
        client_id=req.client_id,
        secret=req.secret,
        env=req.env,
        client_name=req.client_name or None,
    )
    reset_client()
    try:
        get_client().create_link_token()
    except Exception as e:
        storage.clear_plaid_config()
        reset_client()
        raise HTTPException(status_code=400, detail=f"Plaid rejected those credentials: {e}")
    return _config_response()


@app.delete("/config")
def clear_config():
    storage.clear_plaid_config()
    reset_client()
    return {"ok": True}


# --- Plaid link flow --------------------------------------------------------

@app.post("/link/token", response_model=LinkTokenResponse)
def create_link_token():
    client = get_client()
    if not client.configured:
        raise HTTPException(
            status_code=400,
            detail="Plaid client not configured. Set Plaid credentials in Settings first.",
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

    record = storage.save_source(
        source_id=tokens["item_id"],
        kind="plaid",
        display_name=institution_name or "Plaid",
        config={
            "access_token": tokens["access_token"],
            "institution_id": req.institution_id,
        },
    )
    try:
        _sync_plaid(record)
    except Exception as e:
        log.exception("initial plaid sync failed")
        storage.update_source(record["source_id"], error=str(e))

    return ExchangeTokenResponse(source_id=tokens["item_id"], institution_name=institution_name)


# --- SimpleFIN --------------------------------------------------------------

@app.post("/sources/simplefin/claim", response_model=SimpleFinClaimResponse)
def simplefin_claim(req: SimpleFinClaimRequest):
    try:
        access_url = simplefin_client.claim_setup_token(req.setup_token)
    except simplefin_client.SimpleFinError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing = storage.get_source_by_config("access_url", access_url)
    source_id = existing["source_id"] if existing else f"sf_{int(datetime.utcnow().timestamp() * 1000)}"
    display_name = req.display_name or simplefin_client._bridge_host(access_url)
    record = storage.save_source(
        source_id=source_id,
        kind="simplefin",
        display_name=display_name,
        config={"access_url": access_url},
    )
    try:
        _sync_simplefin(record)
    except Exception as e:
        log.exception("initial simplefin sync failed")
        storage.update_source(record["source_id"], error=str(e))

    return SimpleFinClaimResponse(source_id=source_id, display_name=display_name)


# --- Manual accounts --------------------------------------------------------

@app.post("/accounts/manual", response_model=Account)
def create_manual_account(inp: ManualAccountInput):
    acc = manual.create_manual_account(inp.model_dump())
    return Account(**acc)


@app.patch("/accounts/{account_id}/balance", response_model=Account)
def update_manual_balance(account_id: str, body: ManualBalanceUpdate):
    try:
        acc = manual.set_manual_balance(account_id, body.current_balance)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Account(**acc)


@app.post("/accounts/{account_id}/transactions", response_model=Transaction)
def add_manual_transaction(account_id: str, body: ManualTransactionInput):
    try:
        tx = manual.add_manual_transaction(account_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Transaction(**tx)


@app.delete("/accounts/{account_id}")
def delete_manual_account(account_id: str):
    acc = storage.get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="account not found")
    if acc.get("source_kind") != "manual":
        raise HTTPException(
            status_code=400,
            detail="only manual accounts can be deleted directly — unlink the source to remove a Plaid/SimpleFIN account",
        )
    storage.delete_account(account_id)
    return {"ok": True}


@app.post("/accounts/{account_id}/csv", response_model=CsvImportResult)
async def import_account_csv(
    account_id: str,
    file: UploadFile = File(...),
    sign_convention: str = Form("auto"),
):
    content = await file.read()
    try:
        result = manual.import_csv(account_id, content, sign_convention=sign_convention)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CsvImportResult(
        detected_columns=result["detected_columns"],
        row_count=result["row_count"],
        imported=result["imported"],
        skipped=result["skipped"],
        errors=result["errors"],
    )


# --- Sources (list / delete / sync) ----------------------------------------

@app.get("/sources", response_model=List[Source])
def list_sources():
    sources = storage.list_sources()
    accounts = storage.list_accounts()
    counts: dict = {}
    for a in accounts:
        counts[a.get("source_id")] = counts.get(a.get("source_id"), 0) + 1
    return [
        Source(
            source_id=s["source_id"],
            kind=s.get("kind", "plaid"),
            display_name=s.get("display_name") or "",
            linked_at=s.get("linked_at") or "",
            last_synced_at=s.get("last_synced_at"),
            account_count=counts.get(s["source_id"], 0),
            error=s.get("error"),
        )
        for s in sources
    ]


@app.delete("/sources/{source_id}")
def delete_source(source_id: str):
    source = _source_by_id(source_id)
    if source.get("kind") == "plaid":
        client = get_client()
        token = (source.get("config") or {}).get("access_token")
        if token:
            client.remove_item(token)
    storage.delete_source(source_id)
    return {"ok": True}


@app.post("/sync")
def sync_all():
    results = []
    for s in storage.list_sources():
        try:
            results.append(_sync_one(s))
        except HTTPException as e:
            results.append({"source_id": s["source_id"], "error": e.detail})
        except Exception as e:
            results.append({"source_id": s["source_id"], "error": str(e)})
    return {"synced": len(results), "results": results}


@app.post("/sync/{source_id}")
def sync_one(source_id: str):
    return _sync_one(_source_by_id(source_id))


# --- Data -------------------------------------------------------------------

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
    return [Transaction(**t) for t in txns[offset : offset + limit]]


@app.get("/networth", response_model=NetWorthSnapshot)
def networth():
    return compute_net_worth(storage.list_accounts())


@app.get("/subscriptions", response_model=List[Subscription])
def subscriptions():
    return detect_subscriptions(storage.list_transactions(), accounts=storage.list_accounts())


@app.get("/income")
def income(window_days: int = Query(90, ge=30, le=365)):
    return summarize_income(storage.list_transactions(), window_days=window_days, accounts=storage.list_accounts())


@app.get("/spending")
def spending(window_days: int = Query(30, ge=7, le=365)):
    accs = storage.list_accounts()
    txns = storage.list_transactions()
    subs = detect_subscriptions(txns, accounts=accs)
    # Build auto-detected merchant categories, then overlay user rules
    from subscriptions import _normalize_merchant
    categories: dict = {}
    for s in subs:
        key = _normalize_merchant(s.merchant)
        categories[key] = "subscription" if s.kind == "subscription" else "bill"
    # User rules take priority over auto-detection
    categories.update(storage.get_category_rules())
    return spending_breakdown(txns, categories, window_days=window_days, accounts=accs)


@app.put("/spending/categorize")
def categorize_merchant(req: CategoryRuleRequest):
    from income import _normalize_for_match
    key = _normalize_for_match(req.merchant_name)
    if not key:
        raise HTTPException(status_code=400, detail="merchant name is empty")
    storage.save_category_rule(key, req.category)
    return {"ok": True, "merchant": key, "category": req.category}


@app.get("/spending/rules")
def get_category_rules():
    return storage.get_category_rules()


@app.delete("/spending/rules/{merchant}")
def delete_category_rule(merchant: str):
    storage.delete_category_rule(merchant)
    return {"ok": True}


@app.get("/dashboard", response_model=DashboardSummary)
def dashboard():
    accounts = storage.list_accounts()
    txns = storage.list_transactions()
    sources = storage.list_sources()
    nw = compute_net_worth(accounts)
    inc = summarize_income(txns, window_days=90, accounts=accounts)
    subs = detect_subscriptions(txns, accounts=accounts)
    active_subs = [s for s in subs if s.status == "active" and s.kind == "subscription"]
    subs_total = round(sum(s.annualized_cost / 12.0 for s in active_subs), 2)
    spending = monthly_spending(txns, accounts=accounts)
    last = max((s.get("last_synced_at") or "" for s in sources), default=None) or None
    kind_counts: dict = {}
    for s in sources:
        kind_counts[s.get("kind", "unknown")] = kind_counts.get(s.get("kind", "unknown"), 0) + 1
    return DashboardSummary(
        net_worth=nw,
        monthly_income=inc.total_monthly,
        monthly_spending=spending,
        monthly_subscriptions_total=subs_total,
        subscription_count=len(active_subs),
        linked_source_count=len(sources),
        source_counts_by_kind=kind_counts,
        account_count=len(accounts),
        last_synced_at=last,
    )


# --- Goals ------------------------------------------------------------------

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


@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    txns = storage.list_transactions()
    accs = storage.list_accounts()
    inc = summarize_income(txns, window_days=90, accounts=accs)
    subs = detect_subscriptions(txns, accounts=accs)
    subs_total = sum(s.annualized_cost / 12.0 for s in subs if s.status == "active" and s.kind == "subscription")
    spending = monthly_spending(txns, accounts=accs)
    return build_plan(
        goals=req.goals,
        annual_rate=req.assumed_return_annual,
        monthly_income=inc.total_monthly,
        monthly_spending=spending,
        monthly_subscriptions=subs_total,
    )
