import { useEffect, useState } from "react";
import { Plus, Trash2, Sparkles } from "lucide-react";
import { api, formatCurrencyCents } from "../services/api";
import type { Goal, PlanResponse } from "../types";

const KIND_LABELS: Record<Goal["kind"], string> = {
  savings: "Savings",
  debt_payoff: "Debt payoff",
  retirement: "Retirement",
  purchase: "Major purchase",
  other: "Other",
};

const EMPTY: Goal = {
  name: "",
  target_amount: 0,
  target_date: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString().slice(0, 10),
  current_amount: 0,
  monthly_contribution: 0,
  kind: "savings",
  notes: "",
};

export function GoalsPanel() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [draft, setDraft] = useState<Goal>(EMPTY);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [rate, setRate] = useState(0.06);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.listGoals().then(setGoals).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.saveGoal(draft);
      setDraft(EMPTY);
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this goal?")) return;
    await api.deleteGoal(id);
    load();
    setPlan(null);
  };

  const runPlan = async () => {
    try {
      const r = await api.runPlan(goals, rate);
      setPlan(r);
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3 space-y-4">
        {error && <div className="rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-700">
            Your goals ({goals.length})
          </div>
          {goals.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">
              No goals yet. Add one to the right to see projections.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {goals.map((g) => (
                <li key={g.id} className="flex items-start justify-between gap-3 px-5 py-3">
                  <div>
                    <div className="font-semibold text-slate-800">{g.name}</div>
                    <div className="text-xs text-slate-500">
                      {KIND_LABELS[g.kind]} · by {g.target_date}
                    </div>
                    <div className="mt-1 text-sm text-slate-600">
                      {formatCurrencyCents(g.current_amount)} saved of{" "}
                      {formatCurrencyCents(g.target_amount)}
                      {g.monthly_contribution ? (
                        <> · {formatCurrencyCents(g.monthly_contribution)}/mo</>
                      ) : null}
                    </div>
                    {g.notes && <div className="mt-1 text-xs text-slate-500">{g.notes}</div>}
                  </div>
                  <button
                    onClick={() => remove(g.id!)}
                    className="rounded-md p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {goals.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="flex items-center gap-2 font-semibold text-slate-700">
                <Sparkles className="h-4 w-4" /> Build financial plan
              </h3>
              <div className="flex items-center gap-2 text-xs">
                <label className="text-slate-600">Assumed return</label>
                <select
                  value={rate}
                  onChange={(e) => setRate(Number(e.target.value))}
                  className="rounded border border-slate-300 bg-white px-2 py-1"
                >
                  <option value={0.02}>2% (cash / bonds)</option>
                  <option value={0.04}>4%</option>
                  <option value={0.06}>6% (balanced)</option>
                  <option value={0.08}>8% (equities)</option>
                </select>
                <button
                  onClick={runPlan}
                  className="rounded-md bg-indigo-600 px-3 py-1 font-medium text-white hover:bg-indigo-500"
                >
                  Run plan
                </button>
              </div>
            </div>

            {plan && (
              <div className="mt-4 space-y-3">
                <div
                  className={`rounded-lg p-3 text-sm ${
                    plan.feasibility === "comfortable"
                      ? "bg-emerald-50 text-emerald-800"
                      : plan.feasibility === "tight"
                      ? "bg-amber-50 text-amber-800"
                      : "bg-rose-50 text-rose-800"
                  }`}
                >
                  <div className="font-semibold capitalize">Feasibility: {plan.feasibility}</div>
                  <div className="mt-1">{plan.summary}</div>
                  <div className="mt-2 text-xs">
                    Required: {formatCurrencyCents(plan.total_required_monthly)}/mo · Available:{" "}
                    {formatCurrencyCents(plan.available_monthly_surplus)}/mo
                  </div>
                </div>

                <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                  {plan.projections.map((p) => (
                    <li key={p.goal.id} className="p-3 text-sm">
                      <div className="flex items-baseline justify-between">
                        <div className="font-semibold text-slate-800">{p.goal.name}</div>
                        <div
                          className={`text-xs font-medium ${
                            p.on_track ? "text-emerald-700" : "text-rose-700"
                          }`}
                        >
                          {p.on_track ? "On track" : `Short ${formatCurrencyCents(p.shortfall)}`}
                        </div>
                      </div>
                      <div className="mt-1 text-xs text-slate-600">
                        {p.months_remaining} months remaining · projects to{" "}
                        {formatCurrencyCents(p.projected_end_amount)} · needs{" "}
                        {formatCurrencyCents(p.required_monthly)}/mo
                      </div>
                      {p.advice.map((a, i) => (
                        <div key={i} className="mt-1 text-xs italic text-slate-500">
                          • {a}
                        </div>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <form
        onSubmit={save}
        className="lg:col-span-2 space-y-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h3 className="flex items-center gap-2 font-semibold text-slate-700">
          <Plus className="h-4 w-4" /> Add a goal
        </h3>
        <Field label="Name">
          <input
            required
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            className="input"
            placeholder="Emergency fund"
          />
        </Field>
        <Field label="Type">
          <select
            value={draft.kind}
            onChange={(e) => setDraft({ ...draft, kind: e.target.value as Goal["kind"] })}
            className="input"
          >
            {Object.entries(KIND_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Target amount">
            <input
              required
              type="number"
              min={0}
              value={draft.target_amount || ""}
              onChange={(e) => setDraft({ ...draft, target_amount: Number(e.target.value) })}
              className="input"
            />
          </Field>
          <Field label="Already saved">
            <input
              type="number"
              min={0}
              value={draft.current_amount || ""}
              onChange={(e) => setDraft({ ...draft, current_amount: Number(e.target.value) })}
              className="input"
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Target date">
            <input
              required
              type="date"
              value={draft.target_date}
              onChange={(e) => setDraft({ ...draft, target_date: e.target.value })}
              className="input"
            />
          </Field>
          <Field label="Monthly contribution">
            <input
              type="number"
              min={0}
              value={draft.monthly_contribution || ""}
              onChange={(e) =>
                setDraft({ ...draft, monthly_contribution: Number(e.target.value) })
              }
              className="input"
            />
          </Field>
        </div>
        <Field label="Notes">
          <textarea
            value={draft.notes || ""}
            onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
            className="input"
            rows={2}
          />
        </Field>
        <button
          type="submit"
          disabled={saving}
          className="w-full rounded-md bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save goal"}
        </button>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs font-medium text-slate-600">
      {label}
      <div className="mt-1">{children}</div>
    </label>
  );
}
