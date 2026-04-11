"""Pydantic models for the finance-tracker API."""
from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# --- Plaid Link flow ---------------------------------------------------------

class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: Optional[str] = None


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_name: Optional[str] = None
    institution_id: Optional[str] = None


class ExchangeTokenResponse(BaseModel):
    item_id: str
    institution_name: Optional[str] = None


# --- Accounts ----------------------------------------------------------------

class Account(BaseModel):
    account_id: str
    item_id: str
    institution_name: Optional[str] = None
    name: str
    official_name: Optional[str] = None
    mask: Optional[str] = None
    type: str  # depository, investment, credit, loan, brokerage, other
    subtype: Optional[str] = None
    current_balance: float = 0.0
    available_balance: Optional[float] = None
    iso_currency_code: Optional[str] = "USD"


class LinkedItem(BaseModel):
    item_id: str
    institution_name: Optional[str] = None
    institution_id: Optional[str] = None
    linked_at: str
    last_synced_at: Optional[str] = None
    account_count: int = 0
    error: Optional[str] = None


# --- Transactions ------------------------------------------------------------

class Transaction(BaseModel):
    transaction_id: str
    account_id: str
    item_id: str
    date: str  # ISO date
    name: str
    merchant_name: Optional[str] = None
    amount: float  # Plaid convention: positive = money out, negative = money in
    iso_currency_code: Optional[str] = "USD"
    category: List[str] = Field(default_factory=list)
    pending: bool = False
    payment_channel: Optional[str] = None


# --- Net worth ---------------------------------------------------------------

class AssetBucket(BaseModel):
    label: str  # Cash, Investments, Retirement, Real Estate, Crypto, Other Assets
    amount: float
    account_ids: List[str] = Field(default_factory=list)


class LiabilityBucket(BaseModel):
    label: str  # Credit Cards, Student Loans, Mortgages, Other Debt
    amount: float
    account_ids: List[str] = Field(default_factory=list)


class NetWorthSnapshot(BaseModel):
    as_of: str
    total_assets: float
    total_liabilities: float
    net_worth: float
    assets: List[AssetBucket]
    liabilities: List[LiabilityBucket]


# --- Subscriptions -----------------------------------------------------------

class Subscription(BaseModel):
    id: str
    merchant: str
    average_amount: float
    frequency: Literal["weekly", "biweekly", "monthly", "quarterly", "annual", "irregular"]
    last_charge_date: str
    next_expected_date: Optional[str] = None
    annualized_cost: float
    sample_transaction_ids: List[str] = Field(default_factory=list)
    status: Literal["active", "inactive"] = "active"


# --- Income ------------------------------------------------------------------

class IncomeSource(BaseModel):
    name: str
    average_monthly: float
    last_payment_date: Optional[str] = None
    last_payment_amount: Optional[float] = None
    transaction_count: int = 0


class IncomeSummary(BaseModel):
    total_monthly: float
    sources: List[IncomeSource]
    window_days: int


# --- Goals & planning --------------------------------------------------------

class Goal(BaseModel):
    id: Optional[str] = None
    name: str
    target_amount: float
    target_date: str  # ISO date
    current_amount: float = 0.0
    monthly_contribution: Optional[float] = None
    notes: Optional[str] = None
    kind: Literal["savings", "debt_payoff", "retirement", "purchase", "other"] = "savings"
    created_at: Optional[str] = None


class GoalProjection(BaseModel):
    goal: Goal
    months_remaining: int
    required_monthly: float
    projected_end_amount: float
    on_track: bool
    shortfall: float
    advice: List[str]


class PlanRequest(BaseModel):
    goals: List[Goal]
    assumed_return_annual: float = 0.06  # 6% default


class PlanResponse(BaseModel):
    projections: List[GoalProjection]
    total_required_monthly: float
    available_monthly_surplus: float
    feasibility: Literal["comfortable", "tight", "infeasible"]
    summary: str


# --- Dashboard ---------------------------------------------------------------

class DashboardSummary(BaseModel):
    net_worth: NetWorthSnapshot
    monthly_income: float
    monthly_spending: float
    monthly_subscriptions_total: float
    subscription_count: int
    linked_item_count: int
    account_count: int
    last_synced_at: Optional[str] = None
