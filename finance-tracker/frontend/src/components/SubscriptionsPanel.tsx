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

  const activeSubs = subs.filter((s) => s.status === "active" && s.kind === "subscription");
  const inactiveSubs = subs.filter((s) => s.status === "inactive" && s.kind === "subscription");
  const activeBills = subs.filter((s) => s.status === "active" && s.kind === "bill");
  const inactiveBills = subs.filter((s) => s.status === "inactive" && s.kind === "bill");

  const subsMonthly = activeSubs.reduce((sum, s) => sum + s.annualized_cost / 12, 0);
  const billsMonthly = activeBills.reduce((sum, s) => sum + s.annualized_cost / 12, 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <SummaryCard label="Subscriptions" monthly={subsMonthly} count={activeSubs.length} />
        <SummaryCard label="Recurring bills" monthly={billsMonthly} count={activeBills.length} />
      </div>

      {activeSubs.length > 0 && (
        <SubTable title={`Subscriptions (${activeSubs.length})`} subs={activeSubs} />
      )}
      {inactiveSubs.length > 0 && (
        <SubTable title={`Inactive subscriptions (${inactiveSubs.length})`} subs={inactiveSubs} muted />
      )}
      {activeBills.length > 0 && (
        <SubTable title={`Recurring bills (${activeBills.length})`} subs={activeBills} />
      )}
      {inactiveBills.length > 0 && (
        <SubTable title={`Inactive bills (${inactiveBills.length})`} subs={inactiveBills} muted />
      )}
    </div>
  );
}

function SummaryCard({ label, monthly, count }: { label: string; monthly: number; count: number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-3xl font-semibold text-slate-900">
        {formatCurrencyCents(monthly)}
        <span className="ml-1 text-base font-normal text-slate-500">/mo</span>
      </div>
      <div className="mt-1 text-xs text-slate-500">{count} active</div>
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
