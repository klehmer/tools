import { useState } from "react";
import { Link2, KeyRound, Pencil, Upload } from "lucide-react";
import { Modal } from "./Modal";
import { LinkAccountButton } from "./LinkAccountButton";
import { ManualAccountForm } from "./ManualAccountForm";
import { SimpleFinForm } from "./SimpleFinForm";
import type { StatusResponse } from "../types";

type Tab = "plaid" | "simplefin" | "manual";

interface Props {
  open: boolean;
  onClose: () => void;
  onSourceAdded: () => void;
  onOpenSettings: () => void;
  status: StatusResponse | null;
}

const TABS: { id: Tab; label: string; icon: React.ReactNode; blurb: string }[] = [
  {
    id: "plaid",
    label: "Plaid",
    icon: <Link2 className="h-4 w-4" />,
    blurb: "OAuth-style linking. Best for US banks, credit cards, and investment accounts.",
  },
  {
    id: "simplefin",
    label: "SimpleFIN",
    icon: <KeyRound className="h-4 w-4" />,
    blurb: "Paid ($1.50/mo). Good fallback when an institution isn't on Plaid.",
  },
  {
    id: "manual",
    label: "Manual / CSV",
    icon: <Pencil className="h-4 w-4" />,
    blurb: "Type balances in by hand, then optionally upload a CSV of transactions.",
  },
];

export function AddSourceModal({
  open,
  onClose,
  onSourceAdded,
  onOpenSettings,
  status,
}: Props) {
  const [tab, setTab] = useState<Tab>("plaid");

  const handleLinked = () => {
    onSourceAdded();
    onClose();
  };

  return (
    <Modal open={open} onClose={onClose} title="Add an account source" widthClass="max-w-2xl">
      <div className="mb-5 flex gap-2 rounded-lg border border-slate-200 bg-slate-50 p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`flex-1 inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
              tab === t.id
                ? "bg-white text-indigo-700 shadow-sm ring-1 ring-slate-200"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      <p className="mb-4 text-sm text-slate-600">{TABS.find((t) => t.id === tab)?.blurb}</p>

      {tab === "plaid" && (
        <PlaidTab
          configured={!!status?.configured}
          onLinked={handleLinked}
          onOpenSettings={onOpenSettings}
        />
      )}
      {tab === "simplefin" && <SimpleFinForm onClaimed={handleLinked} />}
      {tab === "manual" && <ManualAccountForm onCreated={handleLinked} />}
    </Modal>
  );
}

function PlaidTab({
  configured,
  onLinked,
  onOpenSettings,
}: {
  configured: boolean;
  onLinked: () => void;
  onOpenSettings: () => void;
}) {
  if (!configured) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          You haven't configured Plaid credentials yet. Plaid needs a{" "}
          <code className="font-mono">client_id</code> and secret from{" "}
          <a
            href="https://dashboard.plaid.com/signup"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            dashboard.plaid.com
          </a>{" "}
          before you can link accounts through it.
        </div>
        <button
          type="button"
          onClick={onOpenSettings}
          className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
        >
          Set up Plaid credentials
        </button>
        <p className="text-center text-xs text-slate-500">
          Prefer not to? Use <strong>SimpleFIN</strong> or <strong>Manual / CSV</strong>{" "}
          instead — they don't need Plaid.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Click below to open the Plaid link flow. You'll pick your institution and log in
        with your bank credentials — those credentials go to Plaid directly, never to
        this app.
      </p>
      <div className="flex justify-center py-2">
        <LinkAccountButton onLinked={onLinked} />
      </div>
      <div className="flex justify-center">
        <button
          type="button"
          onClick={onOpenSettings}
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 hover:underline"
        >
          <Upload className="h-3 w-3" />
          Update Plaid credentials
        </button>
      </div>
    </div>
  );
}
