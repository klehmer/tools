import { useEffect, useState, useCallback } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api, formatCurrencyCents } from "../services/api";
import type { SpendingBreakdown, SpendingBucket, SpendingCategory, SpendingFrequency, SpendingTransaction } from "../types";

const CATEGORIES: { value: SpendingCategory; label: string }[] = [
  { value: "subscription", label: "Subscription" },
  { value: "bill", label: "Bill" },
  { value: "work_expense", label: "Work expense" },
  { value: "food", label: "Food" },
  { value: "vacation", label: "Vacation & recreation" },
  { value: "other", label: "Other" },
];

const FREQUENCIES: { value: SpendingFrequency; label: string }[] = [
  { value: "one_time", label: "One time" },
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Biweekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "annual", label: "Annual" },
];

const BUCKET_META: {
  key: keyof Pick<SpendingBreakdown, "subscriptions" | "bills" | "work_expenses" | "food" | "vacation" | "other">;
  title: string;
  color: string;
  headerBg: string;
  defaultCollapsed?: boolean;
  showFrequency?: boolean;
}[] = [
  { key: "subscriptions", title: "Subscriptions", color: "border-indigo-100", headerBg: "hover:bg-indigo-50", showFrequency: true },
  { key: "bills", title: "Recurring bills", color: "border-amber-100", headerBg: "hover:bg-amber-50", showFrequency: true },
  { key: "work_expenses", title: "Work expenses", color: "border-emerald-100", headerBg: "hover:bg-emerald-50" },
  { key: "food", title: "Food", color: "border-orange-100", headerBg: "hover:bg-orange-50" },
  { key: "vacation", title: "Vacation & recreation", color: "border-cyan-100", headerBg: "hover:bg-cyan-50" },
  { key: "other", title: "Other spending", color: "border-slate-200", headerBg: "hover:bg-slate-50", defaultCollapsed: true },
];

export function SpendingPanel() {
  const [windowDays, setWindowDays] = useState(30);
  const [data, setData] = useState<SpendingBreakdown | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.spending(windowDays).then(setData).catch((e) => setError(e.message));
  }, [windowDays]);

  useEffect(() => {
    setData(null);
    load();
  }, [load]);

  const handleCategorize = async (merchantKey: string, category: SpendingCategory) => {
    await api.categorize(merchantKey, category);
    load();
  };

  const handleFrequency = async (merchantKey: string, frequency: SpendingFrequency) => {
    await api.setFrequency(merchantKey, frequency);
    load();
  };

  if (error) return <div className="text-rose-600">Error: {error}</div>;
  if (!data) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Total spending
            </div>
            <div className="mt-1 text-3xl font-semibold text-slate-900">
              {formatCurrencyCents(data.total)}
            </div>
            <div className="mt-1 text-xs text-slate-500">last {data.window_days} days</div>
          </div>
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          >
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-6 gap-3">
        {BUCKET_META.map((b) => {
          const bucket = data[b.key];
          return (
            <MiniCard
              key={b.key}
              label={b.title}
              total={bucket.total}
              count={bucket.transactions.length}
              monthlyEquiv={bucket.monthly_equivalent}
              annualEquiv={bucket.annual_equivalent}
            />
          );
        })}
      </div>

      {BUCKET_META.map((b) => {
        const bucket = data[b.key];
        if (bucket.transactions.length === 0) return null;
        return (
          <BucketCard
            key={b.key}
            title={b.title}
            bucket={bucket}
            borderColor={b.color}
            headerBg={b.headerBg}
            defaultCollapsed={b.defaultCollapsed}
            showFrequency={b.showFrequency}
            onCategorize={handleCategorize}
            onFrequency={handleFrequency}
          />
        );
      })}
    </div>
  );
}

function MiniCard({
  label,
  total,
  count,
  monthlyEquiv,
  annualEquiv,
}: {
  label: string;
  total: number;
  count: number;
  monthlyEquiv?: number;
  annualEquiv?: number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-900 tabular-nums">
        {formatCurrencyCents(total)}
      </div>
      <div className="mt-0.5 text-[10px] text-slate-500">
        {count} txn{count === 1 ? "" : "s"}
      </div>
      {monthlyEquiv != null && monthlyEquiv > 0 && (
        <div className="mt-1 border-t border-slate-100 pt-1 text-[10px] text-slate-500">
          <div>{formatCurrencyCents(monthlyEquiv)}/mo</div>
          <div>{formatCurrencyCents(annualEquiv ?? 0)}/yr</div>
        </div>
      )}
    </div>
  );
}

function BucketCard({
  title,
  bucket,
  borderColor,
  headerBg,
  defaultCollapsed,
  showFrequency,
  onCategorize,
  onFrequency,
}: {
  title: string;
  bucket: SpendingBucket;
  borderColor: string;
  headerBg: string;
  defaultCollapsed?: boolean;
  showFrequency?: boolean;
  onCategorize: (merchantKey: string, category: SpendingCategory) => void;
  onFrequency: (merchantKey: string, frequency: SpendingFrequency) => void;
}) {
  const [expanded, setExpanded] = useState(!defaultCollapsed);

  return (
    <div className={`overflow-hidden rounded-xl border ${borderColor} bg-white shadow-sm`}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={`flex w-full items-center justify-between px-5 py-3 text-left ${headerBg}`}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-slate-400" />
          )}
          <span className="text-sm font-semibold text-slate-900">{title}</span>
          <span className="text-xs text-slate-500">
            {bucket.transactions.length} transaction
            {bucket.transactions.length === 1 ? "" : "s"}
          </span>
        </div>
        <div className="flex items-center gap-4">
          {bucket.monthly_equivalent != null && bucket.monthly_equivalent > 0 && (
            <span className="text-xs text-slate-500 tabular-nums">
              {formatCurrencyCents(bucket.monthly_equivalent)}/mo &middot; {formatCurrencyCents(bucket.annual_equivalent ?? 0)}/yr
            </span>
          )}
          <span className="text-sm font-semibold tabular-nums text-slate-900">
            {formatCurrencyCents(bucket.total)}
          </span>
        </div>
      </button>

      {expanded && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-slate-100 text-xs uppercase tracking-wide text-slate-400">
              <th className="px-5 py-1.5 text-left font-medium">Date</th>
              <th className="px-5 py-1.5 text-left font-medium">Description</th>
              <th className="px-5 py-1.5 text-left font-medium">Account</th>
              <th className="px-5 py-1.5 text-right font-medium">Amount</th>
              {showFrequency && <th className="px-5 py-1.5 text-right font-medium">Frequency</th>}
              <th className="px-5 py-1.5 text-right font-medium">Category</th>
            </tr>
          </thead>
          <tbody>
            {bucket.transactions.map((t, i) => (
              <TransactionRow
                key={i}
                t={t}
                showFrequency={showFrequency}
                onCategorize={onCategorize}
                onFrequency={onFrequency}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TransactionRow({
  t,
  showFrequency,
  onCategorize,
  onFrequency,
}: {
  t: SpendingTransaction;
  showFrequency?: boolean;
  onCategorize: (merchantKey: string, category: SpendingCategory) => void;
  onFrequency: (merchantKey: string, frequency: SpendingFrequency) => void;
}) {
  const isCheck = !!t.check_number;
  return (
    <tr className="border-t border-slate-50">
      <td className="px-5 py-2 tabular-nums text-slate-600">{t.date}</td>
      <td className="px-5 py-2 text-slate-700 max-w-xs">
        <div className="truncate">{t.name}</div>
        {isCheck && (
          <div className="text-[10px] text-slate-400">Check #{t.check_number}</div>
        )}
      </td>
      <td className="px-5 py-2 text-xs text-slate-500 max-w-[180px] truncate">
        {t.account_name}
      </td>
      <td className="px-5 py-2 text-right tabular-nums font-medium text-slate-900">
        {formatCurrencyCents(t.amount)}
      </td>
      {showFrequency && (
        <td className="px-5 py-1.5 text-right">
          <select
            value={t.frequency || ""}
            onChange={(e) => {
              if (e.target.value) {
                onFrequency(t.merchant_key, e.target.value as SpendingFrequency);
              }
            }}
            className="rounded border border-slate-200 bg-slate-50 px-1.5 py-1 text-xs text-slate-600 hover:border-slate-300"
          >
            <option value="">—</option>
            {FREQUENCIES.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </td>
      )}
      <td className="px-5 py-1.5 text-right">
        <select
          value={t.category}
          onChange={(e) =>
            onCategorize(t.merchant_key, e.target.value as SpendingCategory)
          }
          className="rounded border border-slate-200 bg-slate-50 px-1.5 py-1 text-xs text-slate-600 hover:border-slate-300"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </td>
    </tr>
  );
}
