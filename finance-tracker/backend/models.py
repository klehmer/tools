"""Pydantic models for the finance-tracker API."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


SourceKind = Literal["plaid", "simplefin", "manual"]


# --- Plaid credential config -------------------------------------------------

class PlaidConfigRequest(BaseModel):
    client_id: str
    secret: str
    env: Literal["sandbox", "production"] = "sandbox"
    client_name: Optional[str] = None


class PlaidConfigResponse(BaseModel):
    configured: bool
    env: str
    client_id_masked: Optional[str] = None
    has_secret: bool
    client_name: str
    products: List[str]
    country_codes: List[str]


# --- Plaid Link flow ---------------------------------------------------------

class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: Optional[str] = None


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_name: Optional[str] = None
    institution_id: Optional[str] = None


class ExchangeTokenResponse(BaseModel):
    source_id: str
    institution_name: Optional[str] = None


# --- SimpleFIN ---------------------------------------------------------------

class SimpleFinClaimRequest(BaseModel):
    setup_token: str
    display_name: Optional[str] = None


class SimpleFinClaimResponse(BaseModel):
    source_id: str
    display_name: str


# --- Sources -----------------------------------------------------------------

class Source(BaseModel):
    source_id: str
    kind: SourceKind
    display_name: str
    linked_at: str
    last_synced_at: Optional[str] = None
    account_count: int = 0
    error: Optional[str] = None


# --- Accounts ----------------------------------------------------------------

class Account(BaseModel):
    account_id: str
    source_id: str
    source_kind: SourceKind = "plaid"
    institution_name: Optional[str] = None
    name: str
    official_name: Optional[str] = None
    mask: Optional[str] = None
    type: str  # depository, investment, credit, loan, brokerage, other
    subtype: Optional[str] = None
    current_balance: float = 0.0
    available_balance: Optional[float] = None
    iso_currency_code: Optional[str] = "USD"
    manual: bool = False  # convenience: same as source_kind == "manual"


class ManualAccountInput(BaseModel):
    name: str
    type: Literal["depository", "investment", "credit", "loan", "brokerage", "other"] = "depository"
    subtype: Optional[str] = None
    current_balance: float = 0.0
    iso_currency_code: str = "USD"
    institution_name: Optional[str] = None
    mask: Optional[str] = None


class ManualBalanceUpdate(BaseModel):
    current_balance: float


class ManualTransactionInput(BaseModel):
    date: str
    name: str
    amount: float  # Plaid convention: positive = money out
    merchant_name: Optional[str] = None
    category: List[str] = Field(default_factory=list)


class CsvImportResult(BaseModel):
    detected_columns: Dict[str, str]
    row_count: int
    imported: int
    skipped: int
    errors: List[str] = Field(default_factory=list)


# --- Transactions ------------------------------------------------------------

class Transaction(BaseModel):
    transaction_id: str
    account_id: str
    source_id: str
    date: str
    name: str
    merchant_name: Optional[str] = None
    amount: float
    iso_currency_code: Optional[str] = "USD"
    category: List[str] = Field(default_factory=list)
    pending: bool = False
    payment_channel: Optional[str] = None


# --- Net worth ---------------------------------------------------------------

class AssetBucket(BaseModel):
    label: str
    amount: float
    account_ids: List[str] = Field(default_factory=list)


class LiabilityBucket(BaseModel):
    label: str
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

SpendingCategory = Literal["subscription", "bill", "work_expense", "food", "vacation", "other"]
SpendingFrequency = Literal["one_time", "weekly", "biweekly", "monthly", "quarterly", "annual"]


class CategoryRuleRequest(BaseModel):
    merchant_name: str
    category: SpendingCategory


class FrequencyRuleRequest(BaseModel):
    merchant_name: str
    frequency: SpendingFrequency


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
    kind: Literal["subscription", "bill"] = "subscription"


# --- Income ------------------------------------------------------------------

class IncomeDeposit(BaseModel):
    date: str
    amount: float
    description: str


class IncomeSource(BaseModel):
    name: str
    average_monthly: float
    last_payment_date: Optional[str] = None
    last_payment_amount: Optional[float] = None
    transaction_count: int = 0
    deposits: List[IncomeDeposit] = []


class IncomeSummary(BaseModel):
    total_monthly: float
    sources: List[IncomeSource]
    window_days: int


# --- Goals & planning --------------------------------------------------------

class Goal(BaseModel):
    id: Optional[str] = None
    name: str
    target_amount: float
    target_date: str
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
    assumed_return_annual: float = 0.06


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
    linked_source_count: int
    source_counts_by_kind: Dict[str, int]
    account_count: int
    last_synced_at: Optional[str] = None
