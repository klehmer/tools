import { useState } from "react";
import { api } from "../services/api";
import type { Account, ManualAccountInput } from "../types";

interface Props {
  onCreated: (account: Account) => void;
}

const TYPES: { value: ManualAccountInput["type"]; label: string }[] = [
  { value: "depository", label: "Checking / Savings" },
  { value: "investment", label: "Investment" },
  { value: "brokerage", label: "Brokerage" },
  { value: "credit", label: "Credit card" },
  { value: "loan", label: "Loan / Mortgage" },
  { value: "other", label: "Other" },
];

export function ManualAccountForm({ onCreated }: Props) {
  const [form, setForm] = useState<ManualAccountInput>({
    name: "",
    type: "depository",
    subtype: "",
    current_balance: 0,
    iso_currency_code: "USD",
    institution_name: "",
    mask: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const account = await api.createManualAccount({
        ...form,
        subtype: form.subtype || null,
        institution_name: form.institution_name || null,
        mask: form.mask || null,
      });
      onCreated(account);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-slate-600">
        Add an account by hand. You can update the balance any time, and upload a CSV of
        transactions from the accounts page later.
      </p>

      <Field label="Account name">
        <input
          required
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="input"
          placeholder="Vanguard Roth IRA"
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Type">
          <select
            value={form.type}
            onChange={(e) =>
              setForm({ ...form, type: e.target.value as ManualAccountInput["type"] })
            }
            className="input"
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Subtype" hint="Optional free-text, e.g. “roth ira”, “mortgage”.">
          <input
            value={form.subtype || ""}
            onChange={(e) => setForm({ ...form, subtype: e.target.value })}
            className="input"
            placeholder="roth ira"
          />
        </Field>
      </div>

      <Field
        label="Current balance"
        hint="Enter a positive number — we'll treat loan/credit accounts as liabilities automatically."
      >
        <input
          required
          type="number"
          step="0.01"
          value={form.current_balance}
          onChange={(e) =>
            setForm({ ...form, current_balance: parseFloat(e.target.value) || 0 })
          }
          className="input tabular-nums"
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Institution" hint="Optional — shown in the accounts list.">
          <input
            value={form.institution_name || ""}
            onChange={(e) => setForm({ ...form, institution_name: e.target.value })}
            className="input"
            placeholder="Vanguard"
          />
        </Field>
        <Field label="Last 4" hint="Optional.">
          <input
            value={form.mask || ""}
            onChange={(e) => setForm({ ...form, mask: e.target.value })}
            className="input font-mono"
            placeholder="1234"
            maxLength={4}
          />
        </Field>
      </div>

      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting || !form.name}
        className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {submitting ? "Creating…" : "Create account"}
      </button>
    </form>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-slate-700">{label}</div>
      {children}
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </label>
  );
}
