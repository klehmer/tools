import { useEffect, useState } from "react";
import { Building2, Trash2 } from "lucide-react";
import { api, formatCurrencyCents } from "../services/api";
import type { Account, LinkedItem } from "../types";

export function AccountsPanel({ reloadKey }: { reloadKey: number }) {
  const [items, setItems] = useState<LinkedItem[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    Promise.all([api.listItems(), api.accounts()])
      .then(([i, a]) => {
        setItems(i);
        setAccounts(a);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(load, [reloadKey]);

  const unlink = async (itemId: string, name?: string | null) => {
    if (!confirm(`Unlink ${name || itemId}? This removes the token and cached data.`)) return;
    setBusy(true);
    try {
      await api.deleteItem(itemId);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const sync = async (itemId: string) => {
    setBusy(true);
    try {
      await api.syncItem(itemId);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (error) return <div className="text-rose-600">Error: {error}</div>;
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
        No institutions linked yet. Click <em>Link an account</em> to connect Robinhood, PNC,
        Vanguard, Fidelity, or another institution.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {items.map((item) => {
        const its = accounts.filter((a) => a.item_id === item.item_id);
        return (
          <div key={item.item_id} className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-slate-500" />
                <div>
                  <div className="font-semibold text-slate-800">
                    {item.institution_name || "Unknown institution"}
                  </div>
                  <div className="text-xs text-slate-500">
                    Linked {new Date(item.linked_at).toLocaleDateString()} ·{" "}
                    {item.last_synced_at
                      ? `synced ${new Date(item.last_synced_at).toLocaleString()}`
                      : "never synced"}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => sync(item.item_id)}
                  disabled={busy}
                  className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Sync
                </button>
                <button
                  onClick={() => unlink(item.item_id, item.institution_name)}
                  disabled={busy}
                  className="rounded-md border border-rose-200 px-3 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                >
                  <Trash2 className="inline h-3 w-3" /> Unlink
                </button>
              </div>
            </div>
            {item.error && (
              <div className="border-b border-rose-100 bg-rose-50 px-5 py-2 text-xs text-rose-600">
                {item.error}
              </div>
            )}
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-2 text-left font-medium">Account</th>
                  <th className="px-5 py-2 text-left font-medium">Type</th>
                  <th className="px-5 py-2 text-right font-medium">Balance</th>
                </tr>
              </thead>
              <tbody>
                {its.map((a) => (
                  <tr key={a.account_id} className="border-t border-slate-100">
                    <td className="px-5 py-2">
                      <div className="font-medium text-slate-800">{a.name}</div>
                      {a.mask && <div className="text-xs text-slate-500">••{a.mask}</div>}
                    </td>
                    <td className="px-5 py-2 text-slate-600">
                      {a.type}
                      {a.subtype ? ` · ${a.subtype}` : ""}
                    </td>
                    <td className="px-5 py-2 text-right font-medium tabular-nums text-slate-800">
                      {formatCurrencyCents(a.current_balance, a.iso_currency_code || "USD")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
