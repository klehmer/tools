import { useEffect, useState, useCallback } from "react";
import { ChevronDown, ChevronRight, Plus, Pencil, Trash2, X, Check } from "lucide-react";
import { api, formatCurrencyCents } from "../services/api";
import type {
  SpendingBreakdown,
  SpendingBucket,
  SpendingCategoryDef,
  SpendingFrequency,
  SpendingTransaction,
} from "../types";

const FREQUENCIES: { value: SpendingFrequency; label: string }[] = [
  { value: "one_time", label: "One time" },
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Biweekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "annual", label: "Annual" },
];

const PALETTE = [
  { border: "border-indigo-100", headerBg: "hover:bg-indigo-50" },
  { border: "border-amber-100", headerBg: "hover:bg-amber-50" },
  { border: "border-emerald-100", headerBg: "hover:bg-emerald-50" },
  { border: "border-orange-100", headerBg: "hover:bg-orange-50" },
  { border: "border-cyan-100", headerBg: "hover:bg-cyan-50" },
  { border: "border-slate-200", headerBg: "hover:bg-slate-50" },
  { border: "border-rose-100", headerBg: "hover:bg-rose-50" },
  { border: "border-purple-100", headerBg: "hover:bg-purple-50" },
  { border: "border-teal-100", headerBg: "hover:bg-teal-50" },
  { border: "border-pink-100", headerBg: "hover:bg-pink-50" },
  { border: "border-lime-100", headerBg: "hover:bg-lime-50" },
  { border: "border-sky-100", headerBg: "hover:bg-sky-50" },
];

export function SpendingPanel() {
  const [windowDays, setWindowDays] = useState(30);
  const [data, setData] = useState<SpendingBreakdown | null>(null);
  const [categories, setCategories] = useState<SpendingCategoryDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showCatManager, setShowCatManager] = useState(false);

  const load = useCallback(() => {
    Promise.all([api.spending(windowDays), api.listSpendingCategories()])
      .then(([spending, cats]) => {
        setData(spending);
        setCategories(cats);
      })
      .catch((e) => setError(e.message));
  }, [windowDays]);

  useEffect(() => {
    setData(null);
    load();
  }, [load]);

  const handleCategorize = async (merchantKey: string, category: string) => {
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
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCatManager((v) => !v)}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              {showCatManager ? "Done" : "Manage categories"}
            </button>
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
      </div>

      {showCatManager && (
        <CategoryManager categories={categories} onUpdate={(cats) => { setCategories(cats); load(); }} />
      )}

      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: `repeat(${Math.min(data.categories.length, 6)}, minmax(0, 1fr))` }}
      >
        {data.categories.map((b) => (
          <MiniCard
            key={b.key}
            label={b.label}
            total={b.total}
            count={b.transactions.length}
            monthlyEquiv={b.monthly_equivalent}
            annualEquiv={b.annual_equivalent}
          />
        ))}
      </div>

      {data.categories.map((bucket, i) => {
        if (bucket.transactions.length === 0) return null;
        const colors = PALETTE[i % PALETTE.length];
        return (
          <BucketCard
            key={bucket.key}
            bucket={bucket}
            borderColor={colors.border}
            headerBg={colors.headerBg}
            allCategories={categories}
            onCategorize={handleCategorize}
            onFrequency={handleFrequency}
          />
        );
      })}
    </div>
  );
}

/* ── Category Manager ────────────────────────────────────────────── */

function CategoryManager({
  categories,
  onUpdate,
}: {
  categories: SpendingCategoryDef[];
  onUpdate: (cats: SpendingCategoryDef[]) => void;
}) {
  const [newKey, setNewKey] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newShowFreq, setNewShowFreq] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editShowFreq, setEditShowFreq] = useState(false);

  const handleAdd = async () => {
    const key = newKey.trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
    if (!key || !newLabel.trim()) return;
    const cats = await api.createSpendingCategory({
      key,
      label: newLabel.trim(),
      show_frequency: newShowFreq,
      collapsed: false,
      position: categories.length,
    });
    onUpdate(cats);
    setNewKey("");
    setNewLabel("");
    setNewShowFreq(false);
  };

  const handleSaveEdit = async (key: string) => {
    const existing = categories.find((c) => c.key === key);
    if (!existing) return;
    const cats = await api.updateSpendingCategory(key, {
      ...existing,
      label: editLabel.trim() || existing.label,
      show_frequency: editShowFreq,
    });
    onUpdate(cats);
    setEditingKey(null);
  };

  const handleDelete = async (key: string) => {
    const cats = await api.deleteSpendingCategory(key);
    onUpdate(cats);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Spending categories
      </div>
      <div className="space-y-1">
        {categories.map((c) => (
          <div key={c.key} className="flex items-center gap-2 text-sm">
            {editingKey === c.key ? (
              <>
                <input
                  value={editLabel}
                  onChange={(e) => setEditLabel(e.target.value)}
                  className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
                  onKeyDown={(e) => e.key === "Enter" && handleSaveEdit(c.key)}
                />
                <label className="flex items-center gap-1 text-xs text-slate-500">
                  <input
                    type="checkbox"
                    checked={editShowFreq}
                    onChange={(e) => setEditShowFreq(e.target.checked)}
                  />
                  Frequency
                </label>
                <button onClick={() => handleSaveEdit(c.key)} className="text-emerald-600 hover:text-emerald-800">
                  <Check className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => setEditingKey(null)} className="text-slate-400 hover:text-slate-600">
                  <X className="h-3.5 w-3.5" />
                </button>
              </>
            ) : (
              <>
                <span className="flex-1 text-slate-700">
                  {c.label}
                  {c.show_frequency && (
                    <span className="ml-1 text-[10px] text-slate-400">(frequency)</span>
                  )}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">{c.key}</span>
                <button
                  onClick={() => { setEditingKey(c.key); setEditLabel(c.label); setEditShowFreq(c.show_frequency); }}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <Pencil className="h-3 w-3" />
                </button>
                <button onClick={() => handleDelete(c.key)} className="text-slate-400 hover:text-rose-600">
                  <Trash2 className="h-3 w-3" />
                </button>
              </>
            )}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 border-t border-slate-100 pt-2">
        <input
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          placeholder="key"
          className="w-24 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
        />
        <input
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          placeholder="Label"
          className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
        />
        <label className="flex items-center gap-1 text-xs text-slate-500">
          <input
            type="checkbox"
            checked={newShowFreq}
            onChange={(e) => setNewShowFreq(e.target.checked)}
          />
          Freq
        </label>
        <button
          onClick={handleAdd}
          disabled={!newKey.trim() || !newLabel.trim()}
          className="rounded bg-slate-800 px-2 py-1 text-xs text-white hover:bg-slate-700 disabled:opacity-40"
        >
          <Plus className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

/* ── Mini Card ───────────────────────────────────────────────────── */

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

/* ── Bucket Card ─────────────────────────────────────────────────── */

function BucketCard({
  bucket,
  borderColor,
  headerBg,
  allCategories,
  onCategorize,
  onFrequency,
}: {
  bucket: SpendingBucket;
  borderColor: string;
  headerBg: string;
  allCategories: SpendingCategoryDef[];
  onCategorize: (merchantKey: string, category: string) => void;
  onFrequency: (merchantKey: string, frequency: SpendingFrequency) => void;
}) {
  const [expanded, setExpanded] = useState(!bucket.collapsed);

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
          <span className="text-sm font-semibold text-slate-900">{bucket.label}</span>
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
              {bucket.show_frequency && <th className="px-5 py-1.5 text-right font-medium">Frequency</th>}
              <th className="px-5 py-1.5 text-right font-medium">Category</th>
            </tr>
          </thead>
          <tbody>
            {bucket.transactions.map((t, i) => (
              <TransactionRow
                key={i}
                t={t}
                showFrequency={bucket.show_frequency}
                allCategories={allCategories}
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

/* ── Transaction Row ─────────────────────────────────────────────── */

function TransactionRow({
  t,
  showFrequency,
  allCategories,
  onCategorize,
  onFrequency,
}: {
  t: SpendingTransaction;
  showFrequency?: boolean;
  allCategories: SpendingCategoryDef[];
  onCategorize: (merchantKey: string, category: string) => void;
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
            onCategorize(t.merchant_key, e.target.value)
          }
          className="rounded border border-slate-200 bg-slate-50 px-1.5 py-1 text-xs text-slate-600 hover:border-slate-300"
        >
          {allCategories.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
      </td>
    </tr>
  );
}
