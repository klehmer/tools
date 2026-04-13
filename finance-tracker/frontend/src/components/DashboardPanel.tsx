import { useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  PiggyBank,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { api, formatCurrency } from "../services/api";
import type { DashboardSummary, PeriodProjection, CategorySummary } from "../types";

const CAT_COLORS = [
  "text-indigo-700",
  "text-amber-700",
  "text-emerald-700",
  "text-orange-700",
  "text-cyan-700",
  "text-slate-700",
  "text-rose-700",
  "text-purple-700",
  "text-teal-700",
  "text-pink-700",
  "text-lime-700",
  "text-sky-700",
];

const CAT_DOT_COLORS = [
  "bg-indigo-500",
  "bg-amber-500",
  "bg-emerald-500",
  "bg-orange-500",
  "bg-cyan-500",
  "bg-slate-500",
  "bg-rose-500",
  "bg-purple-500",
  "bg-teal-500",
  "bg-pink-500",
  "bg-lime-500",
  "bg-sky-500",
];

export function DashboardPanel() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="text-rose-600">Error: {error}</div>;
  if (!data) return <div className="text-slate-500">Loading dashboard…</div>;

  return (
    <div className="space-y-6">
      {/* Top stat cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
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
          value={formatCurrency(data.income.monthly)}
          sub={`${formatCurrency(data.income.annual)}/yr`}
          tone="sky"
        />
        <StatCard
          icon={<ArrowDownRight className="h-5 w-5" />}
          label="Monthly cash flow"
          value={`${data.cash_flow.monthly >= 0 ? "+" : ""}${formatCurrency(data.cash_flow.monthly)}`}
          sub={`${data.cash_flow.annual >= 0 ? "+" : ""}${formatCurrency(data.cash_flow.annual)}/yr`}
          tone={data.cash_flow.monthly >= 0 ? "emerald" : "rose"}
        />
      </div>

      {/* Financial projections table */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-slate-700">Financial projections</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
              <th className="pb-2 text-left font-medium">Category</th>
              <th className="pb-2 text-right font-medium">Monthly</th>
              <th className="pb-2 text-right font-medium">Quarterly</th>
              <th className="pb-2 text-right font-medium">Annual</th>
            </tr>
          </thead>
          <tbody>
            <ProjectionRow
              label="Income"
              icon={<ArrowUpRight className="h-3.5 w-3.5 text-sky-500" />}
              proj={data.income}
              tone="text-sky-700"
            />
            <ProjectionRow
              label="Total spending"
              icon={<ArrowDownRight className="h-3.5 w-3.5 text-rose-500" />}
              proj={data.spending}
              tone="text-rose-700"
              prefix="-"
            />
            {data.category_summaries.map((cs, i) => (
              <CategoryRow key={cs.key} cs={cs} colorIdx={i} />
            ))}
            <tr className="border-t border-slate-200">
              <td className="py-2 font-semibold text-slate-900">Cash flow</td>
              {(["monthly", "quarterly", "annual"] as const).map((period) => (
                <td
                  key={period}
                  className={`py-2 text-right font-semibold tabular-nums ${
                    data.cash_flow[period] >= 0 ? "text-emerald-700" : "text-rose-700"
                  }`}
                >
                  {data.cash_flow[period] >= 0 ? "+" : ""}
                  {formatCurrency(data.cash_flow[period])}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Assets / Liabilities breakdown */}
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
            <div className="text-sm text-slate-500">No debt on file.</div>
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

function CategoryRow({ cs, colorIdx }: { cs: CategorySummary; colorIdx: number }) {
  const textColor = CAT_COLORS[colorIdx % CAT_COLORS.length];
  const dotColor = CAT_DOT_COLORS[colorIdx % CAT_DOT_COLORS.length];
  return (
    <tr className="border-t border-slate-50">
      <td className="py-2 pl-6">
        <span className="flex items-center gap-1.5">
          <span className={`inline-block h-2 w-2 rounded-full ${dotColor}`} />
          <span className="text-xs text-slate-600">
            {cs.label}
            <span className="ml-1 text-slate-400">({cs.transaction_count})</span>
          </span>
        </span>
      </td>
      <td className={`py-2 text-right tabular-nums ${textColor}`}>
        {formatCurrency(cs.projection.monthly)}
      </td>
      <td className={`py-2 text-right tabular-nums ${textColor}`}>
        {formatCurrency(cs.projection.quarterly)}
      </td>
      <td className={`py-2 text-right tabular-nums ${textColor}`}>
        {formatCurrency(cs.projection.annual)}
      </td>
    </tr>
  );
}

function ProjectionRow({
  label,
  icon,
  proj,
  tone,
  prefix,
}: {
  label: string;
  icon: React.ReactNode;
  proj: PeriodProjection;
  tone: string;
  prefix?: string;
}) {
  const fmt = (v: number) => `${prefix ?? ""}${formatCurrency(v)}`;
  return (
    <tr className="border-t border-slate-50">
      <td className="py-2">
        <span className="flex items-center gap-1.5">
          {icon}
          <span className="font-medium text-slate-700">{label}</span>
        </span>
      </td>
      <td className={`py-2 text-right tabular-nums ${tone}`}>{fmt(proj.monthly)}</td>
      <td className={`py-2 text-right tabular-nums ${tone}`}>{fmt(proj.quarterly)}</td>
      <td className={`py-2 text-right tabular-nums ${tone}`}>{fmt(proj.annual)}</td>
    </tr>
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
