import { useState } from "react";
import { Link2, KeyRound, CheckCircle2 } from "lucide-react";
import { Modal } from "./Modal";
import { SetupPanel } from "./SetupPanel";
import { SimpleFinForm } from "./SimpleFinForm";
import type { StatusResponse } from "../types";

type Tab = "plaid" | "simplefin";

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  status: StatusResponse | null;
  initialTab?: Tab;
}

/**
 * Single place to configure aggregator credentials. Plaid stores a client_id
 * + secret; SimpleFIN exchanges a one-shot setup token for an access URL.
 * Both show a "configured" badge once set up so the user can tell at a glance.
 */
export function SettingsModal({ open, onClose, onSaved, status, initialTab = "plaid" }: Props) {
  const [tab, setTab] = useState<Tab>(initialTab);

  const plaidConfigured = !!status?.configured;
  const simplefinCount = status?.source_counts_by_kind?.simplefin ?? 0;
  const simplefinConfigured = simplefinCount > 0;

  const handleSaved = () => {
    onSaved();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Settings"
      subtitle="Configure aggregator credentials. Both Plaid and SimpleFIN are optional — you can use whichever you prefer, or both."
      widthClass="max-w-2xl"
    >
      <div className="mb-5 flex gap-2 rounded-lg border border-slate-200 bg-slate-50 p-1">
        <TabButton
          active={tab === "plaid"}
          onClick={() => setTab("plaid")}
          icon={<Link2 className="h-4 w-4" />}
          label="Plaid"
          configured={plaidConfigured}
          detail={plaidConfigured ? status?.env : undefined}
        />
        <TabButton
          active={tab === "simplefin"}
          onClick={() => setTab("simplefin")}
          icon={<KeyRound className="h-4 w-4" />}
          label="SimpleFIN"
          configured={simplefinConfigured}
          detail={simplefinConfigured ? `${simplefinCount} linked` : undefined}
        />
      </div>

      {tab === "plaid" && (
        <SetupPanel
          onConfigured={handleSaved}
          currentEnv={status?.env}
          currentClientIdMasked={plaidConfigured ? "(existing credentials)" : null}
        />
      )}
      {tab === "simplefin" && (
        <div className="space-y-4">
          {simplefinConfigured && (
            <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div>
                <div className="font-semibold">
                  {simplefinCount} SimpleFIN bridge{simplefinCount === 1 ? "" : "s"} already linked.
                </div>
                <div className="mt-0.5 text-xs">
                  Claim another setup token below to add a new bridge, or remove existing ones
                  from the Accounts tab.
                </div>
              </div>
            </div>
          )}
          <SimpleFinForm onClaimed={handleSaved} />
        </div>
      )}
    </Modal>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
  configured,
  detail,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  configured: boolean;
  detail?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
        active
          ? "bg-white text-indigo-700 shadow-sm ring-1 ring-slate-200"
          : "text-slate-600 hover:text-slate-900"
      }`}
    >
      {icon}
      <span>{label}</span>
      {configured && (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-700 ring-1 ring-emerald-200">
          <CheckCircle2 className="h-2.5 w-2.5" />
          {detail || "on"}
        </span>
      )}
    </button>
  );
}
