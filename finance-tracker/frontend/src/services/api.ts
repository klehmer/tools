import type {
  Account,
  CsvImportResult,
  DashboardSummary,
  Goal,
  IncomeSummary,
  ManualAccountInput,
  NetWorthSnapshot,
  PlanResponse,
  Source,
  SpendingBreakdown,
  SpendingCategory,
  SpendingFrequency,
  StatusResponse,
  Subscription,
  Transaction,
} from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers:
      init?.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail: string;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      detail = await res.text();
    }
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json();
}

export interface PlaidConfigResponse {
  configured: boolean;
  env: string;
  client_id_masked: string | null;
  has_secret: boolean;
  client_name: string;
  products: string[];
  country_codes: string[];
}

export interface PlaidConfigInput {
  client_id: string;
  secret: string;
  env: "sandbox" | "production";
  client_name?: string;
}

export const api = {
  status: () => request<StatusResponse>("/status"),

  getConfig: () => request<PlaidConfigResponse>("/config"),
  saveConfig: (cfg: PlaidConfigInput) =>
    request<PlaidConfigResponse>("/config", {
      method: "POST",
      body: JSON.stringify(cfg),
    }),
  clearConfig: () => request<{ ok: boolean }>("/config", { method: "DELETE" }),

  // --- Plaid link flow
  createLinkToken: () =>
    request<{ link_token: string; expiration?: string }>("/link/token", {
      method: "POST",
    }),
  exchangePublicToken: (
    public_token: string,
    institution_name?: string,
    institution_id?: string
  ) =>
    request<{ source_id: string; institution_name?: string }>("/link/exchange", {
      method: "POST",
      body: JSON.stringify({ public_token, institution_name, institution_id }),
    }),

  // --- SimpleFIN
  claimSimpleFin: (setup_token: string, display_name?: string) =>
    request<{ source_id: string; display_name: string }>("/sources/simplefin/claim", {
      method: "POST",
      body: JSON.stringify({ setup_token, display_name }),
    }),

  // --- Manual accounts
  createManualAccount: (input: ManualAccountInput) =>
    request<Account>("/accounts/manual", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  updateBalance: (account_id: string, current_balance: number) =>
    request<Account>(`/accounts/${account_id}/balance`, {
      method: "PATCH",
      body: JSON.stringify({ current_balance }),
    }),
  deleteAccount: (account_id: string) =>
    request<{ ok: boolean }>(`/accounts/${account_id}`, { method: "DELETE" }),
  importCsv: (account_id: string, file: File, sign_convention = "auto") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("sign_convention", sign_convention);
    return request<CsvImportResult>(`/accounts/${account_id}/csv`, {
      method: "POST",
      body: fd,
    });
  },

  // --- Sources (list + sync + unlink)
  listSources: () => request<Source[]>("/sources"),
  deleteSource: (source_id: string) =>
    request<{ ok: boolean }>(`/sources/${source_id}`, { method: "DELETE" }),
  syncAll: () => request<{ synced: number }>("/sync", { method: "POST" }),
  syncSource: (source_id: string) =>
    request<unknown>(`/sync/${source_id}`, { method: "POST" }),

  // --- Analytics
  dashboard: () => request<DashboardSummary>("/dashboard"),
  networth: () => request<NetWorthSnapshot>("/networth"),
  accounts: () => request<Account[]>("/accounts"),
  transactions: (limit = 200, offset = 0, accountId?: string) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (accountId) params.set("account_id", accountId);
    return request<Transaction[]>(`/transactions?${params.toString()}`);
  },
  subscriptions: () => request<Subscription[]>("/subscriptions"),
  income: (windowDays = 90) =>
    request<IncomeSummary>(`/income?window_days=${windowDays}`),
  spending: (windowDays = 30) =>
    request<SpendingBreakdown>(`/spending?window_days=${windowDays}`),
  categorize: (merchant_name: string, category: SpendingCategory) =>
    request<{ ok: boolean }>("/spending/categorize", {
      method: "PUT",
      body: JSON.stringify({ merchant_name, category }),
    }),
  setFrequency: (merchant_name: string, frequency: SpendingFrequency) =>
    request<{ ok: boolean }>("/spending/frequency", {
      method: "PUT",
      body: JSON.stringify({ merchant_name, frequency }),
    }),

  // --- Goals
  listGoals: () => request<Goal[]>("/goals"),
  saveGoal: (goal: Goal) =>
    request<Goal>("/goals", { method: "POST", body: JSON.stringify(goal) }),
  deleteGoal: (id: string) =>
    request<{ ok: boolean }>(`/goals/${id}`, { method: "DELETE" }),
  runPlan: (goals: Goal[], assumed_return_annual = 0.06) =>
    request<PlanResponse>("/plan", {
      method: "POST",
      body: JSON.stringify({ goals, assumed_return_annual }),
    }),
};

export function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatCurrencyCents(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(amount);
}
