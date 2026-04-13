import { useEffect, useMemo, useState } from "react";
import { Building2, Trash2, RefreshCw, Upload, Pencil, Link2, KeyRound, EyeOff, Eye } from "lucide-react";
import { api, formatCurrencyCents } from "../services/api";
import type { Account, Source, SourceKind } from "../types";
import { CsvImportModal } from "./CsvImportModal";

interface Props {
  reloadKey: number;
  onChange?: () => void;
}

export function AccountsPanel({ reloadKey, onChange }: Props) {
  const [sources, setSources] = useState<Source[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [csvTarget, setCsvTarget] = useState<Account | null>(null);

  const load = () => {
    setError(null);
    Promise.all([api.listSources(), api.accounts()])
      .then(([s, a]) => {
        setSources(s);
        setAccounts(a);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(load, [reloadKey]);

  const notifyChange = () => {
    load();
    onChange?.();
  };

  const unlinkSource = async (source: Source) => {
    if (
      !confirm(
        `Remove ${source.display_name}? This deletes the cached accounts and transactions for this source.`
      )
    )
      return;
    setBusy(source.source_id);
    try {
      await api.deleteSource(source.source_id);
      notifyChange();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const syncSource = async (source: Source) => {
    setBusy(source.source_id);
    try {
      await api.syncSource(source.source_id);
      notifyChange();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const deleteManualAccount = async (acc: Account) => {
    if (!confirm(`Delete ${acc.name}? This also removes its transactions.`)) return;
    setBusy(acc.account_id);
    try {
      await api.deleteAccount(acc.account_id);
      notifyChange();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const editBalance = async (acc: Account) => {
    const input = prompt(`New balance for ${acc.name}:`, String(acc.current_balance));
    if (input == null) return;
    const val = parseFloat(input);
    if (!Number.isFinite(val)) {
      alert("Not a valid number.");
      return;
    }
    setBusy(acc.account_id);
    try {
      await api.updateBalance(acc.account_id, val);
      notifyChange();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const toggleIgnored = async (acc: Account) => {
    setBusy(acc.account_id);
    try {
      await api.setAccountIgnored(acc.account_id, !acc.ignored);
      notifyChange();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const sourceAccounts = useMemo(() => {
    const by: Record<string, Account[]> = {};
    for (const a of accounts) {
      (by[a.source_id] ||= []).push(a);
    }
    return by;
  }, [accounts]);

  if (error) return <div className="text-rose-600">Error: {error}</div>;
  if (sources.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
        No account sources yet. Click <em>Add source</em> in the header to link via Plaid,
        claim a SimpleFIN token, or add a manual account.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {sources.map((source) => {
        const accs = sourceAccounts[source.source_id] || [];
        const isBusy = busy === source.source_id;
        return (
          <div
            key={source.source_id}
            className="rounded-xl border border-slate-200 bg-white shadow-sm"
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <div className="flex items-center gap-3">
                <SourceIcon kind={source.kind} />
                <div>
                  <div className="flex items-center gap-2 font-semibold text-slate-800">
                    {source.display_name}
                    <SourceBadge kind={source.kind} />
                  </div>
                  <div className="text-xs text-slate-500">
                    Linked {new Date(source.linked_at).toLocaleDateString()} ·{" "}
                    {source.last_synced_at
                      ? `synced ${new Date(source.last_synced_at).toLocaleString()}`
                      : "never synced"}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                {source.kind !== "manual" && (
                  <button
                    onClick={() => syncSource(source)}
                    disabled={isBusy}
                    className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3 w-3 ${isBusy ? "animate-spin" : ""}`} />
                    Sync
                  </button>
                )}
                <button
                  onClick={() => unlinkSource(source)}
                  disabled={isBusy}
                  className="inline-flex items-center gap-1 rounded-md border border-rose-200 px-3 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                >
                  <Trash2 className="h-3 w-3" />
                  Remove
                </button>
              </div>
            </div>
            {source.error && (
              <div className="border-b border-rose-100 bg-rose-50 px-5 py-2 text-xs text-rose-600">
                {source.error}
              </div>
            )}
            {accs.length === 0 ? (
              <div className="px-5 py-4 text-sm text-slate-500">
                No accounts on this source yet.{" "}
                {source.kind !== "manual" && "Try syncing to pull them in."}
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-2 text-left font-medium">Account</th>
                    <th className="px-5 py-2 text-left font-medium">Type</th>
                    <th className="px-5 py-2 text-right font-medium">Balance</th>
                    <th className="px-5 py-2 text-right font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {accs.map((a) => (
                    <tr
                      key={a.account_id}
                      className={`border-t border-slate-100 ${a.ignored ? "opacity-50" : ""}`}
                    >
                      <td className="px-5 py-2">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${a.ignored ? "text-slate-400 line-through" : "text-slate-800"}`}>
                            {a.name}
                          </span>
                          {a.ignored && (
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-slate-400">
                              Ignored
                            </span>
                          )}
                        </div>
                        {a.mask && <div className="text-xs text-slate-500">••{a.mask}</div>}
                      </td>
                      <td className="px-5 py-2 text-slate-600">
                        {a.type}
                        {a.subtype ? ` · ${a.subtype}` : ""}
                      </td>
                      <td className="px-5 py-2 text-right font-medium tabular-nums text-slate-800">
                        {formatCurrencyCents(a.current_balance, a.iso_currency_code || "USD")}
                      </td>
                      <td className="px-5 py-2 text-right">
                        <div className="inline-flex gap-1">
                          <IconButton
                            title={a.ignored ? "Include in analytics" : "Ignore in analytics"}
                            onClick={() => toggleIgnored(a)}
                            disabled={busy === a.account_id}
                          >
                            {a.ignored ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                          </IconButton>
                          {a.manual && (
                            <>
                              <IconButton
                                title="Edit balance"
                                onClick={() => editBalance(a)}
                                disabled={busy === a.account_id}
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </IconButton>
                              <IconButton
                                title="Upload CSV"
                                onClick={() => setCsvTarget(a)}
                                disabled={busy === a.account_id}
                              >
                                <Upload className="h-3.5 w-3.5" />
                              </IconButton>
                              <IconButton
                                title="Delete account"
                                tone="rose"
                                onClick={() => deleteManualAccount(a)}
                                disabled={busy === a.account_id}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </IconButton>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}

      <CsvImportModal
        open={csvTarget !== null}
        account={csvTarget}
        onClose={() => setCsvTarget(null)}
        onImported={notifyChange}
      />
    </div>
  );
}

function SourceIcon({ kind }: { kind: SourceKind }) {
  const base = "h-5 w-5";
  if (kind === "plaid") return <Link2 className={`${base} text-indigo-500`} />;
  if (kind === "simplefin") return <KeyRound className={`${base} text-emerald-500`} />;
  return <Building2 className={`${base} text-slate-500`} />;
}

function SourceBadge({ kind }: { kind: SourceKind }) {
  const tones: Record<SourceKind, string> = {
    plaid: "bg-indigo-50 text-indigo-700 ring-indigo-200",
    simplefin: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    manual: "bg-slate-100 text-slate-600 ring-slate-200",
  };
  const labels: Record<SourceKind, string> = {
    plaid: "Plaid",
    simplefin: "SimpleFIN",
    manual: "Manual",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1 ${tones[kind]}`}
    >
      {labels[kind]}
    </span>
  );
}

function IconButton({
  title,
  onClick,
  disabled,
  tone = "slate",
  children,
}: {
  title: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: "slate" | "rose";
  children: React.ReactNode;
}) {
  const classes =
    tone === "rose"
      ? "border-rose-200 text-rose-600 hover:bg-rose-50"
      : "border-slate-300 text-slate-600 hover:bg-slate-50";
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md border ${classes} p-1.5 disabled:cursor-not-allowed disabled:opacity-50`}
    >
      {children}
    </button>
  );
}
