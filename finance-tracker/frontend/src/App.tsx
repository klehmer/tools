import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Wallet,
  Repeat,
  ArrowUpRight,
  Target,
  RefreshCw,
  Settings,
  Plus,
} from "lucide-react";
import { api } from "./services/api";
import type { StatusResponse } from "./types";
import { DashboardPanel } from "./components/DashboardPanel";
import { AccountsPanel } from "./components/AccountsPanel";
import { SubscriptionsPanel } from "./components/SubscriptionsPanel";
import { IncomePanel } from "./components/IncomePanel";
import { GoalsPanel } from "./components/GoalsPanel";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AddSourceModal } from "./components/AddSourceModal";
import { SettingsModal } from "./components/SettingsModal";

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
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const loadStatus = () => {
    setStatusError(null);
    api.status().then(setStatus).catch((e) => setStatusError(e.message));
  };
  useEffect(loadStatus, [reloadKey]);

  const bump = () => setReloadKey((k) => k + 1);

  const handleSourceAdded = () => {
    bump();
    setTab("accounts");
  };

  const handleSettingsSaved = () => {
    setSettingsOpen(false);
    bump();
  };

  const syncAll = async () => {
    setSyncing(true);
    try {
      await api.syncAll();
      bump();
    } catch (e: any) {
      setStatusError(e.message);
    } finally {
      setSyncing(false);
    }
  };

  const totalSources = status?.linked_source_count ?? 0;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Finance Tracker</h1>
            <p className="text-xs text-slate-500">
              Read-only aggregation · Plaid / SimpleFIN / manual · local-first
              {status?.env ? ` · Plaid env: ${status.env}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSettingsOpen(true)}
              title="Configure Plaid & SimpleFIN"
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Settings className="h-4 w-4" />
              Settings
            </button>
            <button
              onClick={syncAll}
              disabled={syncing || totalSources === 0}
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
              {syncing ? "Syncing…" : "Sync all"}
            </button>
            <button
              onClick={() => setAddSourceOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
            >
              <Plus className="h-4 w-4" />
              Add source
            </button>
          </div>
        </div>
      </header>

      {statusError && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-2 text-sm text-rose-800">
          {statusError}
        </div>
      )}

      <div className="mx-auto max-w-6xl px-6 py-8">
        {status === null ? (
          <div className="text-center text-slate-500">Loading…</div>
        ) : (
          <>
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
              <ErrorBoundary label={tab}>
                {tab === "dashboard" && <DashboardPanel key={reloadKey} />}
                {tab === "accounts" && (
                  <AccountsPanel reloadKey={reloadKey} onChange={bump} />
                )}
                {tab === "subscriptions" && <SubscriptionsPanel key={reloadKey} />}
                {tab === "income" && <IncomePanel key={reloadKey} />}
                {tab === "goals" && <GoalsPanel key={reloadKey} />}
              </ErrorBoundary>
            </main>
          </>
        )}
      </div>

      <ErrorBoundary label="add-source">
        <AddSourceModal
          open={addSourceOpen}
          onClose={() => setAddSourceOpen(false)}
          onSourceAdded={handleSourceAdded}
          onOpenSettings={() => {
            setAddSourceOpen(false);
            setSettingsOpen(true);
          }}
          status={status}
        />
      </ErrorBoundary>

      <ErrorBoundary label="settings">
        <SettingsModal
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          onSaved={handleSettingsSaved}
          status={status}
        />
      </ErrorBoundary>
    </div>
  );
}
