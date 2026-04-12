import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api, formatCurrencyCents } from "../services/api";
import type { IncomeSummary, IncomeSource } from "../types";

export function IncomePanel() {
  const [windowDays, setWindowDays] = useState(90);
  const [data, setData] = useState<IncomeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.income(windowDays).then(setData).catch((e) => setError(e.message));
  }, [windowDays]);

  if (error) return <div className="text-rose-600">Error: {error}</div>;
  if (!data) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Monthly income (avg)
            </div>
            <div className="mt-1 text-3xl font-semibold text-slate-900">
              {formatCurrencyCents(data.total_monthly)}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              based on last {data.window_days} days of deposits
            </div>
          </div>
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          >
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
            <option value={180}>180 days</option>
            <option value={365}>365 days</option>
          </select>
        </div>
      </div>

      {data.sources.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
          No income-like deposits detected in this window.
        </div>
      ) : (
        <div className="space-y-3">
          {data.sources.map((s) => (
            <SourceCard key={s.name} source={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceCard({ source }: { source: IncomeSource }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-3 text-left hover:bg-slate-50"
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-slate-400" />
          )}
          <span className="text-sm font-semibold text-slate-900">{source.name}</span>
          <span className="text-xs text-slate-500">
            {source.transaction_count} deposit{source.transaction_count === 1 ? "" : "s"}
          </span>
        </div>
        <span className="text-sm font-semibold tabular-nums text-slate-900">
          {formatCurrencyCents(source.average_monthly)}
          <span className="ml-1 text-xs font-normal text-slate-500">/mo</span>
        </span>
      </button>

      {expanded && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-slate-100 text-xs uppercase tracking-wide text-slate-400">
              <th className="px-5 py-1.5 text-left font-medium">Date</th>
              <th className="px-5 py-1.5 text-left font-medium">Description</th>
              <th className="px-5 py-1.5 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {source.deposits.map((d, i) => (
              <tr key={i} className="border-t border-slate-50">
                <td className="px-5 py-2 tabular-nums text-slate-600">{d.date}</td>
                <td className="px-5 py-2 text-slate-600 truncate max-w-xs">{d.description}</td>
                <td className="px-5 py-2 text-right tabular-nums font-medium text-emerald-700">
                  {formatCurrencyCents(d.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
