import { useEffect, useState } from "react";
import { Check, Download, ShieldAlert, X } from "lucide-react";
import {
  decideApproval,
  downloadBulk,
  listApprovals,
} from "../services/api";
import type { ApprovalRecord } from "../types";

export default function PendingApprovalsPanel() {
  const [items, setItems] = useState<ApprovalRecord[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const data = await listApprovals("pending");
      setItems(data);
    } catch {
      // ignore — backend may be reloading
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  if (items.length === 0) return null;

  const handleApprove = async (rec: ApprovalRecord, withDownload: boolean) => {
    setBusy(rec.id);
    try {
      if (withDownload) {
        await downloadBulk(rec.email_ids, true);
      }
      await decideApproval(rec.id, "approved");
      await refresh();
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : "unknown error"}`);
    } finally {
      setBusy(null);
    }
  };

  const handleDeny = async (rec: ApprovalRecord) => {
    setBusy(rec.id);
    try {
      await decideApproval(rec.id, "denied");
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mb-6 rounded-2xl border-2 border-amber-300 bg-amber-50 p-4">
      <div className="mb-3 flex items-center gap-2">
        <ShieldAlert className="h-5 w-5 text-amber-700" />
        <h3 className="font-semibold text-amber-900">
          Pending agent approvals ({items.length})
        </h3>
      </div>

      <div className="space-y-2">
        {items.map((rec) => {
          const isBusy = busy === rec.id;
          return (
            <div
              key={rec.id}
              className="rounded-lg border border-amber-200 bg-white p-3 text-sm"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-medium text-gray-900">{rec.sender || "(unknown sender)"}</span>
                <span className="text-xs text-gray-500">
                  {rec.email_ids.length} email{rec.email_ids.length === 1 ? "" : "s"} · proposes{" "}
                  {rec.suggested_action}
                </span>
              </div>
              {rec.reason && (
                <p className="mt-1 text-xs text-gray-600">{rec.reason}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  onClick={() => handleApprove(rec, true)}
                  disabled={isBusy}
                  className="flex items-center gap-1 rounded-md border border-blue-600 bg-white px-2.5 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-60"
                >
                  <Download className="h-3 w-3" />
                  Download &amp; approve
                </button>
                <button
                  onClick={() => handleApprove(rec, false)}
                  disabled={isBusy}
                  className="flex items-center gap-1 rounded-md bg-green-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-60"
                >
                  <Check className="h-3 w-3" />
                  Approve without download
                </button>
                <button
                  onClick={() => handleDeny(rec)}
                  disabled={isBusy}
                  className="flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-60"
                >
                  <X className="h-3 w-3" />
                  Deny
                </button>
                {isBusy && (
                  <span className="self-center text-xs text-gray-500">Processing…</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
