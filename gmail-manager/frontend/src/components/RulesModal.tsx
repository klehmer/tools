import { useEffect, useState } from "react";
import { X, Shield } from "lucide-react";
import { getRules, saveRules } from "../services/api";
import type { CleanupRules } from "../types";

interface Props {
  onClose: () => void;
  onSaved?: (rules: CleanupRules) => void;
}

const EMPTY: CleanupRules = {
  require_approval: true,
  download_before_delete: false,
  protected_senders: [],
  protected_keywords: [],
  custom_instructions: "",
};

export default function RulesModal({ onClose, onSaved }: Props) {
  const [rules, setRules] = useState<CleanupRules>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sendersText, setSendersText] = useState("");
  const [keywordsText, setKeywordsText] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await getRules();
        setRules(r);
        setSendersText(r.protected_senders.join("\n"));
        setKeywordsText(r.protected_keywords.join("\n"));
      } catch {
        // keep defaults
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const splitLines = (s: string) =>
    s
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);

  const handleSave = async () => {
    setSaving(true);
    try {
      const next: CleanupRules = {
        ...rules,
        protected_senders: splitLines(sendersText),
        protected_keywords: splitLines(keywordsText),
      };
      const saved = await saveRules(next);
      onSaved?.(saved);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-white border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900">Cleanup Rules</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-6">
          {/* Approval */}
          <Toggle
            label="Require my approval before deleting"
            hint="Server-enforced. Agents (Claude Code / Codex / built-in) cannot delete without you clicking an explicit approve button in this UI."
            value={rules.require_approval}
            onChange={(v) => setRules({ ...rules, require_approval: v })}
          />

          {/* Download before delete */}
          <Toggle
            label="Download emails before deleting"
            hint="Built-in agent: triggers the Download dialog. External agents: instructed in the prompt to download bulk before delete."
            value={rules.download_before_delete}
            onChange={(v) => setRules({ ...rules, download_before_delete: v })}
          />

          {/* Protected senders */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Protected senders
            </label>
            <p className="mb-2 text-xs text-gray-500">
              One per line. Use a full address (<code>boss@company.com</code>) or a domain prefix (<code>@company.com</code>) to protect everyone at a domain. The block endpoint will reject any matching sender server-side.
            </p>
            <textarea
              value={sendersText}
              onChange={(e) => setSendersText(e.target.value)}
              rows={4}
              placeholder="boss@company.com&#10;@bank.com&#10;mom@gmail.com"
              className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Protected keywords */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Protected subject keywords
            </label>
            <p className="mb-2 text-xs text-gray-500">
              One per line. Agents will be instructed to never delete emails whose subject contains any of these.
            </p>
            <textarea
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
              rows={3}
              placeholder="invoice&#10;tax&#10;passport"
              className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          {/* Custom instructions */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Custom instructions for agents
            </label>
            <p className="mb-2 text-xs text-gray-500">
              Free-form. Injected into the system prompt for the built-in agent and into the copy-paste prompt for Claude Code / Codex.
            </p>
            <textarea
              value={rules.custom_instructions}
              onChange={(e) => setRules({ ...rules, custom_instructions: e.target.value })}
              rows={4}
              placeholder="Don't touch anything from 2024. Be aggressive with category:promotions. Always block LinkedIn newsletters."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t px-6 py-3">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 bg-white px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white shadow hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? "Saving…" : "Save rules"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Toggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <div className="text-sm font-medium text-gray-800">{label}</div>
        <div className="text-xs text-gray-500">{hint}</div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${value ? "bg-blue-600" : "bg-gray-300"}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${value ? "left-5" : "left-0.5"}`}
        />
      </button>
    </div>
  );
}
