import { useEffect, useState } from "react";
import { getConfig, saveConfig } from "../services/api";
import type { AIProvider } from "../types";

const MODEL_HINTS: Record<AIProvider, string> = {
  anthropic: "e.g. claude-haiku-4-5, claude-sonnet-4-5",
  "claude-code": "Uses your local Claude Code CLI",
  codex: "Uses your local Codex CLI",
  openai: "e.g. gpt-4o-mini, gpt-4o, o3",
};

export default function SettingsModal({ onClose }: { onClose: () => void }) {
  const [fields, setFields] = useState<Record<string, string>>({
    GOOGLE_CLIENT_ID: "",
    GOOGLE_CLIENT_SECRET: "",
    ANTHROPIC_API_KEY: "",
    OPENAI_API_KEY: "",
    AI_PROVIDER: "anthropic",
    AI_MODEL: "",
    DEFAULT_PERIOD: "week",
    DEFAULT_DIRECTION: "past",
    BACKEND_URL: "http://localhost:8001",
    FRONTEND_URL: "http://localhost:5174",
  });
  const [configuredSecrets, setConfiguredSecrets] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getConfig().then((cfg) => {
      const next: Record<string, string> = {};
      const secrets = new Set<string>();
      Object.entries(cfg).forEach(([k, v]) => {
        if (v.value === "***") {
          next[k] = "";
          if (v.configured) secrets.add(k);
        } else {
          next[k] = v.value;
        }
      });
      setConfiguredSecrets(secrets);
      setFields((f) => ({ ...f, ...next }));
    });
  }, []);

  const set = (k: string, v: string) => setFields((f) => ({ ...f, [k]: v }));
  const provider = (fields.AI_PROVIDER || "anthropic") as AIProvider;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, string> = {};
      Object.entries(fields).forEach(([k, v]) => {
        if (v) payload[k] = v;
      });
      await saveConfig(payload);
      setSaving(false);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save configuration");
      setSaving(false);
    }
  };

  const inputCls = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm";
  const labelCls = "block text-sm font-medium mb-1";
  const sectionCls = "space-y-3";

  const secretInput = (field: string, label: string) => (
    <div>
      <label className={labelCls}>{label}</label>
      <input
        type="password"
        value={fields[field]}
        onChange={(e) => {
          set(field, e.target.value);
          if (!e.target.value) setConfiguredSecrets((s) => { const n = new Set(s); n.delete(field); return n; });
        }}
        className={inputCls}
        placeholder={configuredSecrets.has(field) && !fields[field] ? "Already configured (leave blank to keep)" : ""}
      />
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50 overflow-auto">
      <div className="bg-white rounded-2xl shadow-xl p-6 max-w-lg w-full space-y-5 my-6">
        <h2 className="text-xl font-bold">Configuration</h2>

        {/* Google OAuth */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Google OAuth</h3>
          <div>
            <label className={labelCls}>Client ID</label>
            <input type="text" value={fields.GOOGLE_CLIENT_ID} onChange={(e) => set("GOOGLE_CLIENT_ID", e.target.value)} className={inputCls} />
          </div>
          {secretInput("GOOGLE_CLIENT_SECRET", "Client Secret")}
        </section>

        <hr className="border-slate-200" />

        {/* AI Provider */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">AI Provider</h3>
          <div>
            <label className={labelCls}>Provider</label>
            <select value={provider} onChange={(e) => set("AI_PROVIDER", e.target.value)} className={inputCls}>
              <option value="anthropic">Anthropic API</option>
              <option value="claude-code">Claude Code CLI</option>
              <option value="codex">Codex CLI</option>
              <option value="openai">OpenAI API</option>
            </select>
          </div>

          {provider === "anthropic" && secretInput("ANTHROPIC_API_KEY", "Anthropic API Key")}

          {provider === "openai" && secretInput("OPENAI_API_KEY", "OpenAI API Key")}

          {provider !== "claude-code" && provider !== "codex" && (
            <div>
              <label className={labelCls}>Model</label>
              <input type="text" value={fields.AI_MODEL} onChange={(e) => set("AI_MODEL", e.target.value)} className={inputCls} placeholder={MODEL_HINTS[provider]} />
            </div>
          )}

          <p className="text-xs text-slate-500">{MODEL_HINTS[provider]}</p>
        </section>

        <hr className="border-slate-200" />

        {/* Summary Defaults */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Summary Defaults</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Default Period</label>
              <select value={fields.DEFAULT_PERIOD || "week"} onChange={(e) => set("DEFAULT_PERIOD", e.target.value)} className={inputCls}>
                <option value="day">Day</option>
                <option value="week">Week</option>
                <option value="month">Month</option>
                <option value="quarter">Quarter</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Calendar Direction</label>
              <select value={fields.DEFAULT_DIRECTION || "past"} onChange={(e) => set("DEFAULT_DIRECTION", e.target.value)} className={inputCls}>
                <option value="past">Previous</option>
                <option value="future">Upcoming</option>
              </select>
            </div>
          </div>
        </section>

        <hr className="border-slate-200" />

        {/* URLs */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">URLs</h3>
          <div>
            <label className={labelCls}>Backend URL</label>
            <input type="text" value={fields.BACKEND_URL} onChange={(e) => set("BACKEND_URL", e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Frontend URL</label>
            <input type="text" value={fields.FRONTEND_URL} onChange={(e) => set("FRONTEND_URL", e.target.value)} className={inputCls} />
          </div>
        </section>

        {/* Actions */}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-4 py-2 text-slate-600 text-sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
