import type {
  Account,
  DashboardSummary,
  Goal,
  IncomeSummary,
  LinkedItem,
  NetWorthSnapshot,
  PlanResponse,
  StatusResponse,
  Subscription,
  Transaction,
} from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
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

export const api = {
  status: () => request<StatusResponse>("/status"),

  createLinkToken: () =>
    request<{ link_token: string; expiration?: string }>("/link/token", {
      method: "POST",
    }),

  exchangePublicToken: (
    public_token: string,
    institution_name?: string,
    institution_id?: string
  ) =>
    request<{ item_id: string; institution_name?: string }>("/link/exchange", {
      method: "POST",
      body: JSON.stringify({ public_token, institution_name, institution_id }),
    }),

  listItems: () => request<LinkedItem[]>("/items"),
  deleteItem: (itemId: string) =>
    request<{ ok: boolean }>(`/items/${itemId}`, { method: "DELETE" }),

  syncAll: () => request<{ synced: number }>("/sync", { method: "POST" }),
  syncItem: (itemId: string) =>
    request<unknown>(`/sync/${itemId}`, { method: "POST" }),

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
