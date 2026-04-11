import { useEffect, useState } from "react";
import { api, formatCurrencyCents } from "../services/api";
import type { Subscription } from "../types";

export function SubscriptionsPanel() {
  const [subs, setSubs] = useState<Subscription[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.subscriptions().then(setSubs).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="text-rose-600">Error: {error}</div>;
  if (!subs) return <div className="text-slate-500">Analyzing transactions…</div>;

  if (subs.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
        No recurring charges detected yet. Link accounts and sync at least 3 months of transactions
        to surface subscriptions.
      </div>
    );
  }

  const active = subs.filter((s) => s.status === "active");
  const inactive = subs.filter((s) => s.status === "inactive");
  const monthlyTotal = active.reduce((sum, s) => sum + s.annualized_cost / 12, 0);
  const annualTotal = active.reduce((sum, s) => sum + s.annualized_cost, 0);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Total active subscriptions
            </div>
            <div className="mt-1 text-3xl font-semibold text-slate-900">
              {formatCurrencyCents(monthlyTotal)}
              <span className="ml-1 text-base font-normal text-slate-500">/mo</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Annual</div>
            <div className="mt-1 text-xl font-semibold text-slate-700">
              {formatCurrencyCents(annualTotal)}
            </div>
          </div>
        </div>
      </div>

      <SubTable title={`Active (${active.length})`} subs={active} />
      {inactive.length > 0 && <SubTable title={`Inactive (${inactive.length})`} subs={inactive} muted />}
    </div>
  );
}

function SubTable({ title, subs, muted }: { title: string; subs: Subscription[]; muted?: boolean }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-700">
        {title}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-slate-500">
            <th className="px-5 py-2 text-left font-medium">Merchant</th>
            <th className="px-5 py-2 text-left font-medium">Cadence</th>
            <th className="px-5 py-2 text-left font-medium">Last charged</th>
            <th className="px-5 py-2 text-right font-medium">Amount</th>
            <th className="px-5 py-2 text-right font-medium">Annualized</th>
          </tr>
        </thead>
        <tbody className={muted ? "text-slate-500" : ""}>
          {subs.map((s) => (
            <tr key={s.id} className="border-t border-slate-100">
              <td className="px-5 py-2 font-medium">{s.merchant}</td>
              <td className="px-5 py-2 capitalize">{s.frequency}</td>
              <td className="px-5 py-2">{s.last_charge_date}</td>
              <td className="px-5 py-2 text-right tabular-nums">
                {formatCurrencyCents(s.average_amount)}
              </td>
              <td className="px-5 py-2 text-right font-semibold tabular-nums">
                {formatCurrencyCents(s.annualized_cost)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
