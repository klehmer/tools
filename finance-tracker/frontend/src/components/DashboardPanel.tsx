import { useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  PiggyBank,
  Repeat,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { api, formatCurrency } from "../services/api";
import type { DashboardSummary } from "../types";

export function DashboardPanel() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="text-rose-600">Error: {error}</div>;
  if (!data) return <div className="text-slate-500">Loading dashboard…</div>;

  const cashflow = data.monthly_income - data.monthly_spending;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<TrendingUp className="h-5 w-5" />}
          label="Net worth"
          value={formatCurrency(data.net_worth.net_worth)}
          sub={`${formatCurrency(data.net_worth.total_assets)} assets · ${formatCurrency(
            data.net_worth.total_liabilities
          )} debt`}
          tone="emerald"
        />
        <StatCard
          icon={<ArrowUpRight className="h-5 w-5" />}
          label="Monthly income"
          value={formatCurrency(data.monthly_income)}
          sub="trailing 90-day avg"
          tone="sky"
        />
        <StatCard
          icon={<ArrowDownRight className="h-5 w-5" />}
          label="Monthly spending"
          value={formatCurrency(data.monthly_spending)}
          sub={`${cashflow >= 0 ? "+" : ""}${formatCurrency(cashflow)}/mo cash flow`}
          tone={cashflow >= 0 ? "emerald" : "rose"}
        />
        <StatCard
          icon={<Repeat className="h-5 w-5" />}
          label="Subscriptions"
          value={formatCurrency(data.monthly_subscriptions_total)}
          sub={`${data.subscription_count} active`}
          tone="violet"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Wallet className="h-4 w-4" /> Assets breakdown
          </h3>
          <BucketList items={data.net_worth.assets} total={data.net_worth.total_assets} tone="emerald" />
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <PiggyBank className="h-4 w-4" /> Liabilities
          </h3>
          {data.net_worth.liabilities.length === 0 ? (
            <div className="text-sm text-slate-500">No debt on file. </div>
          ) : (
            <BucketList
              items={data.net_worth.liabilities}
              total={data.net_worth.total_liabilities}
              tone="rose"
            />
          )}
        </div>
      </div>

      <div className="text-xs text-slate-500">
        {data.linked_source_count} source{data.linked_source_count === 1 ? "" : "s"} ·{" "}
        {data.account_count} account{data.account_count === 1 ? "" : "s"}
        {sourceMixLabel(data.source_counts_by_kind)} ·{" "}
        {data.last_synced_at
          ? `last synced ${new Date(data.last_synced_at).toLocaleString()}`
          : "never synced"}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  tone: "emerald" | "sky" | "rose" | "violet";
}) {
  const tones: Record<string, string> = {
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    sky: "bg-sky-50 text-sky-700 ring-sky-200",
    rose: "bg-rose-50 text-rose-700 ring-rose-200",
    violet: "bg-violet-50 text-violet-700 ring-violet-200",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
        <span className={`inline-flex rounded-lg p-1.5 ring-1 ${tones[tone]}`}>{icon}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{sub}</div>
    </div>
  );
}

function sourceMixLabel(counts: Record<string, number>): string {
  const entries = Object.entries(counts).filter(([, n]) => n > 0);
  if (entries.length === 0) return "";
  const parts = entries.map(([kind, n]) => `${n} ${kind}`);
  return ` (${parts.join(", ")})`;
}

function BucketList({
  items,
  total,
  tone,
}: {
  items: { label: string; amount: number }[];
  total: number;
  tone: "emerald" | "rose";
}) {
  const barColor = tone === "emerald" ? "bg-emerald-500" : "bg-rose-500";
  return (
    <ul className="space-y-3">
      {items.map((b) => {
        const pct = total > 0 ? (b.amount / total) * 100 : 0;
        return (
          <li key={b.label}>
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-medium text-slate-700">{b.label}</span>
              <span className="tabular-nums text-slate-600">
                {formatCurrency(b.amount)} <span className="text-slate-400">· {pct.toFixed(0)}%</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100">
              <div className={`h-1.5 rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
