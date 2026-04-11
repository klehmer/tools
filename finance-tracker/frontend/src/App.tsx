import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Wallet,
  Repeat,
  ArrowUpRight,
  Target,
  RefreshCw,
} from "lucide-react";
import { api } from "./services/api";
import type { StatusResponse } from "./types";
import { DashboardPanel } from "./components/DashboardPanel";
import { AccountsPanel } from "./components/AccountsPanel";
import { SubscriptionsPanel } from "./components/SubscriptionsPanel";
import { IncomePanel } from "./components/IncomePanel";
import { GoalsPanel } from "./components/GoalsPanel";
import { LinkAccountButton } from "./components/LinkAccountButton";

type Tab = "dashboard" | "accounts" | "subscriptions" | "income" | "goals";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "accounts", label: "Accounts", icon: <Wallet className="h-4 w-4" /> },
  { id: "subscriptions", label: "Subscriptions", icon: <Repeat className="h-4 w-4" /> },
  { id: "income", label: "Income", icon: <ArrowUpRight className="h-4 w-4" /> },
  { id: "goals", label: "Goals & plan", icon: <Target className="h-4 w-4" /> },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [syncing, setSyncing] = useState(false);

  const loadStatus = () => api.status().then(setStatus).catch((e) => setStatusError(e.message));
  useEffect(loadStatus, [reloadKey]);

  const handleLinked = () => {
    setReloadKey((k) => k + 1);
    setTab("accounts");
  };

  const syncAll = async () => {
    setSyncing(true);
    try {
      await api.syncAll();
      setReloadKey((k) => k + 1);
    } catch (e: any) {
      setStatusError(e.message);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Finance Tracker</h1>
            <p className="text-xs text-slate-500">
              Read-only aggregation via Plaid · local-first · {status?.env || "—"} environment
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={syncAll}
              disabled={syncing || (status?.linked_item_count ?? 0) === 0}
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
              {syncing ? "Syncing…" : "Sync all"}
            </button>
            <LinkAccountButton onLinked={handleLinked} disabled={!status?.configured} />
          </div>
        </div>
      </header>

      {status && !status.configured && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-800">
          <strong>Plaid is not configured.</strong> Copy{" "}
          <code className="rounded bg-amber-100 px-1">backend/.env.example</code> to{" "}
          <code className="rounded bg-amber-100 px-1">backend/.env</code> and fill in your{" "}
          <code>PLAID_CLIENT_ID</code> and <code>PLAID_SECRET</code>, then restart the backend.
        </div>
      )}
      {statusError && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-800">
          {statusError}
        </div>
      )}

      <div className="mx-auto max-w-6xl px-6 py-6">
        <nav className="mb-6 flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`inline-flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
                tab === t.id
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </nav>

        <main>
          {tab === "dashboard" && <DashboardPanel key={reloadKey} />}
          {tab === "accounts" && <AccountsPanel reloadKey={reloadKey} />}
          {tab === "subscriptions" && <SubscriptionsPanel key={reloadKey} />}
          {tab === "income" && <IncomePanel key={reloadKey} />}
          {tab === "goals" && <GoalsPanel key={reloadKey} />}
        </main>
      </div>
    </div>
  );
}
