export type SourceKind = "plaid" | "simplefin" | "manual";

export interface Source {
  source_id: string;
  kind: SourceKind;
  display_name: string;
  linked_at: string;
  last_synced_at?: string | null;
  account_count: number;
  error?: string | null;
}

export interface Account {
  account_id: string;
  source_id: string;
  source_kind: SourceKind;
  institution_name?: string | null;
  name: string;
  official_name?: string | null;
  mask?: string | null;
  type: string;
  subtype?: string | null;
  current_balance: number;
  available_balance?: number | null;
  iso_currency_code?: string | null;
  manual: boolean;
}

export interface ManualAccountInput {
  name: string;
  type: "depository" | "investment" | "credit" | "loan" | "brokerage" | "other";
  subtype?: string | null;
  current_balance: number;
  iso_currency_code?: string;
  institution_name?: string | null;
  mask?: string | null;
}

export interface AssetBucket {
  label: string;
  amount: number;
  account_ids: string[];
}

export interface LiabilityBucket {
  label: string;
  amount: number;
  account_ids: string[];
}

export interface NetWorthSnapshot {
  as_of: string;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  assets: AssetBucket[];
  liabilities: LiabilityBucket[];
}

export interface Transaction {
  transaction_id: string;
  account_id: string;
  source_id: string;
  date: string;
  name: string;
  merchant_name?: string | null;
  amount: number;
  iso_currency_code?: string | null;
  category: string[];
  pending: boolean;
  payment_channel?: string | null;
}

export interface Subscription {
  id: string;
  merchant: string;
  average_amount: number;
  frequency: "weekly" | "biweekly" | "monthly" | "quarterly" | "annual" | "irregular";
  last_charge_date: string;
  next_expected_date?: string | null;
  annualized_cost: number;
  sample_transaction_ids: string[];
  status: "active" | "inactive";
  kind: "subscription" | "bill";
}

export interface IncomeDeposit {
  date: string;
  amount: number;
  description: string;
}

export interface IncomeSource {
  name: string;
  average_monthly: number;
  last_payment_date?: string | null;
  last_payment_amount?: number | null;
  transaction_count: number;
  deposits: IncomeDeposit[];
}

export interface IncomeSummary {
  total_monthly: number;
  sources: IncomeSource[];
  window_days: number;
}

export interface Goal {
  id?: string;
  name: string;
  target_amount: number;
  target_date: string;
  current_amount: number;
  monthly_contribution?: number | null;
  notes?: string | null;
  kind: "savings" | "debt_payoff" | "retirement" | "purchase" | "other";
  created_at?: string | null;
}

export interface GoalProjection {
  goal: Goal;
  months_remaining: number;
  required_monthly: number;
  projected_end_amount: number;
  on_track: boolean;
  shortfall: number;
  advice: string[];
}

export interface PlanResponse {
  projections: GoalProjection[];
  total_required_monthly: number;
  available_monthly_surplus: number;
  feasibility: "comfortable" | "tight" | "infeasible";
  summary: string;
}

export interface DashboardSummary {
  net_worth: NetWorthSnapshot;
  monthly_income: number;
  monthly_spending: number;
  monthly_subscriptions_total: number;
  subscription_count: number;
  linked_source_count: number;
  source_counts_by_kind: Record<string, number>;
  account_count: number;
  last_synced_at?: string | null;
}

export interface StatusResponse {
  configured: boolean;
  env: string;
  products: string[];
  country_codes: string[];
  client_name: string;
  linked_source_count: number;
  source_counts_by_kind: Record<string, number>;
  account_count: number;
  last_synced_at?: string | null;
}

export type SpendingCategory = "subscription" | "bill" | "work_expense" | "food" | "vacation" | "other";

export interface SpendingTransaction {
  date: string;
  name: string;
  amount: number;
  merchant_key: string;
  category: string;
}

export interface SpendingBucket {
  total: number;
  transactions: SpendingTransaction[];
}

export interface SpendingBreakdown {
  window_days: number;
  total: number;
  subscriptions: SpendingBucket;
  bills: SpendingBucket;
  work_expenses: SpendingBucket;
  food: SpendingBucket;
  vacation: SpendingBucket;
  other: SpendingBucket;
}

export interface CsvImportResult {
  detected_columns: Record<string, string>;
  row_count: number;
  imported: number;
  skipped: number;
  errors: string[];
}