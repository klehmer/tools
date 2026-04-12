import { useState } from "react";
import { Upload } from "lucide-react";
import { api } from "../services/api";
import type { Account, CsvImportResult } from "../types";
import { Modal } from "./Modal";

interface Props {
  open: boolean;
  account: Account | null;
  onClose: () => void;
  onImported: () => void;
}

export function CsvImportModal({ open, account, onClose, onImported }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [signConvention, setSignConvention] = useState<"auto" | "outflow_positive" | "inflow_positive">(
    "auto"
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CsvImportResult | null>(null);

  const reset = () => {
    setFile(null);
    setSignConvention("auto");
    setError(null);
    setResult(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !account) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.importCsv(account.account_id, file, signConvention);
      setResult(r);
      onImported();
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title="Import CSV"
      subtitle={account ? `Into ${account.name}` : undefined}
    >
      {result ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            <div className="font-semibold">Imported {result.imported} transactions.</div>
            <div className="mt-1 text-xs">
              {result.row_count} rows parsed · {result.skipped} skipped (duplicates or
              unparseable).
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600">
            <div className="mb-2 font-semibold text-slate-700">Detected columns</div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(result.detected_columns).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="font-mono">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
          {result.errors.length > 0 && (
            <details className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              <summary className="cursor-pointer font-semibold">
                {result.errors.length} row warning{result.errors.length === 1 ? "" : "s"}
              </summary>
              <ul className="mt-2 space-y-1">
                {result.errors.map((err, i) => (
                  <li key={i} className="font-mono">
                    {err}
                  </li>
                ))}
              </ul>
            </details>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={reset}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Upload another
            </button>
            <button
              type="button"
              onClick={close}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              Done
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <p className="text-sm text-slate-600">
            Upload a CSV export from your bank. We'll auto-detect the column layout and
            skip duplicates. Amounts are interpreted as outflow-positive (matching Plaid)
            — use <em>Outflow positive</em> or <em>Inflow positive</em> to force a
            convention if auto-detection guesses wrong.
          </p>

          <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center hover:border-indigo-400 hover:bg-indigo-50">
            <Upload className="mb-2 h-6 w-6 text-slate-400" />
            <span className="text-sm font-medium text-slate-700">
              {file ? file.name : "Click to choose a CSV"}
            </span>
            {file && (
              <span className="mt-1 text-xs text-slate-500">
                {(file.size / 1024).toFixed(1)} KB
              </span>
            )}
            <input
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <div>
            <div className="mb-1 text-xs font-semibold text-slate-700">Sign convention</div>
            <div className="flex gap-2">
              {(
                [
                  { value: "auto", label: "Auto" },
                  { value: "outflow_positive", label: "Outflow +" },
                  { value: "inflow_positive", label: "Inflow +" },
                ] as const
              ).map((opt) => (
                <button
                  type="button"
                  key={opt.value}
                  onClick={() => setSignConvention(opt.value)}
                  className={`flex-1 rounded-md border px-3 py-2 text-xs font-medium transition ${
                    signConvention === opt.value
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                      : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !file}
            className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {submitting ? "Importing…" : "Import CSV"}
          </button>
        </form>
      )}
    </Modal>
  );
}
