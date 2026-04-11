"""Thin wrapper around the Plaid API.

We keep all Plaid SDK imports local to this module so the rest of the app can
be reasoned about without knowing the SDK's slightly awkward model classes.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

from plaid import Configuration, ApiClient, Environment
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest


ENV_MAP = {
    "sandbox": Environment.Sandbox,
    "development": Environment.Development,
    "production": Environment.Production,
}


def _split(val: str) -> List[str]:
    return [v.strip() for v in (val or "").split(",") if v.strip()]


class PlaidClient:
    def __init__(self) -> None:
        self.client_id = os.getenv("PLAID_CLIENT_ID", "")
        self.secret = os.getenv("PLAID_SECRET", "")
        env_name = os.getenv("PLAID_ENV", "sandbox").lower()
        self.env_name = env_name
        host = ENV_MAP.get(env_name, Environment.Sandbox)

        self.products = [Products(p) for p in _split(os.getenv("PLAID_PRODUCTS", "transactions,investments,liabilities"))]
        self.country_codes = [CountryCode(c) for c in _split(os.getenv("PLAID_COUNTRY_CODES", "US"))]
        self.client_name = os.getenv("PLAID_CLIENT_NAME", "Finance Tracker")

        cfg = Configuration(
            host=host,
            api_key={"clientId": self.client_id, "secret": self.secret},
        )
        self.client = plaid_api.PlaidApi(ApiClient(cfg))

    # --- configuration ------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.secret)

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.configured,
            "env": self.env_name,
            "products": [p.value for p in self.products],
            "country_codes": [c.value for c in self.country_codes],
            "client_name": self.client_name,
        }

    # --- link flow ----------------------------------------------------------

    def create_link_token(self, user_id: str = "local-user") -> Dict[str, Any]:
        req = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=user_id),
            client_name=self.client_name,
            products=self.products,
            country_codes=self.country_codes,
            language="en",
        )
        resp = self.client.link_token_create(req)
        return {"link_token": resp["link_token"], "expiration": str(resp.get("expiration", ""))}

    def exchange_public_token(self, public_token: str) -> Dict[str, str]:
        resp = self.client.item_public_token_exchange(
            ItemPublicTokenExchangeRequest(public_token=public_token)
        )
        return {"access_token": resp["access_token"], "item_id": resp["item_id"]}

    def get_institution(self, institution_id: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.client.institutions_get_by_id(
                InstitutionsGetByIdRequest(
                    institution_id=institution_id,
                    country_codes=self.country_codes,
                )
            )
            inst = resp["institution"]
            return {"institution_id": inst["institution_id"], "name": inst["name"]}
        except ApiException:
            return None

    # --- data pulls ---------------------------------------------------------

    def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        resp = self.client.accounts_get(AccountsGetRequest(access_token=access_token))
        out = []
        for acc in resp["accounts"]:
            balances = acc.get("balances", {}) or {}
            out.append(
                {
                    "account_id": acc["account_id"],
                    "name": acc.get("name", ""),
                    "official_name": acc.get("official_name"),
                    "mask": acc.get("mask"),
                    "type": str(acc.get("type", "")),
                    "subtype": str(acc.get("subtype", "")) if acc.get("subtype") else None,
                    "current_balance": float(balances.get("current") or 0.0),
                    "available_balance": float(balances["available"]) if balances.get("available") is not None else None,
                    "iso_currency_code": balances.get("iso_currency_code") or "USD",
                }
            )
        return out

    def sync_transactions(self, access_token: str, cursor: Optional[str]) -> Dict[str, Any]:
        """Use the /transactions/sync incremental endpoint; loop until has_more=False."""
        added: List[Dict[str, Any]] = []
        modified: List[Dict[str, Any]] = []
        removed: List[str] = []
        next_cursor = cursor or ""

        while True:
            kwargs: Dict[str, Any] = {"access_token": access_token}
            if next_cursor:
                kwargs["cursor"] = next_cursor
            req = TransactionsSyncRequest(**kwargs)
            resp = self.client.transactions_sync(req)
            added.extend(self._tx_to_dict(t) for t in resp.get("added", []))
            modified.extend(self._tx_to_dict(t) for t in resp.get("modified", []))
            removed.extend(t["transaction_id"] for t in resp.get("removed", []))
            next_cursor = resp.get("next_cursor", "")
            if not resp.get("has_more", False):
                break
        return {"added": added, "modified": modified, "removed": removed, "cursor": next_cursor}

    @staticmethod
    def _tx_to_dict(t: Any) -> Dict[str, Any]:
        return {
            "transaction_id": t["transaction_id"],
            "account_id": t["account_id"],
            "date": str(t.get("date", "")),
            "name": t.get("name", ""),
            "merchant_name": t.get("merchant_name"),
            "amount": float(t.get("amount") or 0.0),
            "iso_currency_code": t.get("iso_currency_code") or "USD",
            "category": list(t.get("category") or []),
            "pending": bool(t.get("pending", False)),
            "payment_channel": t.get("payment_channel"),
        }

    def get_investments(self, access_token: str) -> Dict[str, Any]:
        try:
            resp = self.client.investments_holdings_get(
                InvestmentsHoldingsGetRequest(access_token=access_token)
            )
        except ApiException as e:
            return {"error": str(e), "holdings": [], "securities": []}
        holdings = []
        for h in resp.get("holdings", []):
            holdings.append(
                {
                    "account_id": h["account_id"],
                    "security_id": h["security_id"],
                    "quantity": float(h.get("quantity") or 0.0),
                    "institution_value": float(h.get("institution_value") or 0.0),
                    "cost_basis": float(h["cost_basis"]) if h.get("cost_basis") is not None else None,
                    "iso_currency_code": h.get("iso_currency_code") or "USD",
                }
            )
        securities = []
        for s in resp.get("securities", []):
            securities.append(
                {
                    "security_id": s["security_id"],
                    "name": s.get("name"),
                    "ticker_symbol": s.get("ticker_symbol"),
                    "type": str(s.get("type", "")),
                    "close_price": float(s["close_price"]) if s.get("close_price") is not None else None,
                }
            )
        return {"holdings": holdings, "securities": securities}

    def get_liabilities(self, access_token: str) -> Dict[str, Any]:
        try:
            resp = self.client.liabilities_get(LiabilitiesGetRequest(access_token=access_token))
        except ApiException as e:
            return {"error": str(e)}
        liabilities = resp.get("liabilities", {}) or {}
        out: Dict[str, Any] = {}
        if liabilities.get("credit"):
            out["credit"] = [
                {
                    "account_id": c["account_id"],
                    "last_statement_balance": float(c.get("last_statement_balance") or 0.0),
                    "minimum_payment_amount": float(c.get("minimum_payment_amount") or 0.0),
                }
                for c in liabilities.get("credit", [])
            ]
        if liabilities.get("student"):
            out["student"] = [
                {
                    "account_id": s["account_id"],
                    "outstanding_interest_amount": float(s.get("outstanding_interest_amount") or 0.0),
                }
                for s in liabilities.get("student", [])
            ]
        if liabilities.get("mortgage"):
            out["mortgage"] = [
                {
                    "account_id": m["account_id"],
                    "current_late_fee": float(m.get("current_late_fee") or 0.0),
                }
                for m in liabilities.get("mortgage", [])
            ]
        return out

    def remove_item(self, access_token: str) -> None:
        try:
            self.client.item_remove(ItemRemoveRequest(access_token=access_token))
        except ApiException:
            pass


_singleton: Optional[PlaidClient] = None


def get_client() -> PlaidClient:
    global _singleton
    if _singleton is None:
        _singleton = PlaidClient()
    return _singleton


def reset_client() -> None:
    """For tests / hot reload."""
    global _singleton
    _singleton = None
