import { useEffect, useState } from "react";
import { getConfig, saveConfig } from "../services/api";
import type { AIProvider } from "../types";

const PROVIDER_MODELS: Record<AIProvider, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-haiku-4-5", label: "Claude Haiku 4.5" },
    { value: "claude-sonnet-4-5", label: "Claude Sonnet 4.5" },
    { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
    { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
  ],
  "claude-code": [
    { value: "claude-haiku-4-5", label: "Claude Haiku 4.5" },
    { value: "claude-sonnet-4-5", label: "Claude Sonnet 4.5" },
    { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
    { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
  ],
  codex: [
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "o3", label: "o3" },
    { value: "o4-mini", label: "o4-mini" },
  ],
  openai: [
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "o3", label: "o3" },
    { value: "o4-mini", label: "o4-mini" },
  ],
};

const PROVIDER_HINTS: Record<AIProvider, string> = {
  anthropic: "Anthropic API — requires API key",
  "claude-code": "Uses your local Claude Code CLI — no API key needed.",
  codex: "Uses your local Codex CLI — no API key needed.",
  openai: "OpenAI API — requires API key",
};

export default function SettingsModal({ onClose }: { onClose: () => void }) {
  const [fields, setFields] = useState<Record<string, string>>({
    GOOGLE_CLIENT_ID: "",
    GOOGLE_CLIENT_SECRET: "",
    ANTHROPIC_API_KEY: "",
    OPENAI_API_KEY: "",
    AI_PROVIDER: "claude-code",
    AI_MODEL: "",
    DEFAULT_PERIOD: "week",
    DEFAULT_DIRECTION: "past",
    PLANNER_COLUMN_WIDTH: "220",
    DEFAULT_TAB: "planner",
    EMAIL_PROMPT_RULES: "",
    CALENDAR_PROMPT_RULES: "",
    SLACK_WEBHOOK_URL: "",
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
  const provider = (fields.AI_PROVIDER || "claude-code") as AIProvider;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, string> = {};
      Object.entries(fields).forEach(([k, v]) => {
        if (v) payload[k] = v;
      });
      await saveConfig(payload);
      if (fields.DEFAULT_TAB) {
        localStorage.setItem("daybrief_default_tab", fields.DEFAULT_TAB);
      }
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
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center p-6 z-50 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-xl p-6 max-w-lg w-full space-y-5 my-6">
        <h2 className="text-xl font-bold">Configuration</h2>

        {/* AI Provider — shown first so users pick their provider before entering keys */}
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

          <div>
            <label className={labelCls}>Model</label>
            <select value={fields.AI_MODEL} onChange={(e) => set("AI_MODEL", e.target.value)} className={inputCls}>
              {PROVIDER_MODELS[provider]?.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          <p className="text-xs text-slate-500">
            {PROVIDER_HINTS[provider]}
          </p>
        </section>

        <hr className="border-slate-200" />

        {/* Google OAuth */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Google OAuth <span className="text-slate-400 font-normal normal-case">(optional)</span></h3>
          <p className="text-xs text-slate-500">Needed for email/calendar summaries. You can skip this and add it later — the Planner works without it.</p>
          <div>
            <label className={labelCls}>Client ID</label>
            <input type="text" value={fields.GOOGLE_CLIENT_ID} onChange={(e) => set("GOOGLE_CLIENT_ID", e.target.value)} className={inputCls} />
          </div>
          {secretInput("GOOGLE_CLIENT_SECRET", "Client Secret")}
        </section>

        <hr className="border-slate-200" />

        {/* Defaults */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Defaults</h3>
          <div>
            <label className={labelCls}>Default View</label>
            <select value={fields.DEFAULT_TAB || "planner"} onChange={(e) => set("DEFAULT_TAB", e.target.value)} className={inputCls}>
              <option value="summary-emails">Summary - Emails</option>
              <option value="summary-calendar">Summary - Calendar</option>
              <option value="planner">Planner</option>
              <option value="reports">Reports</option>
              <option value="schedule">Scheduled Jobs</option>
              <option value="analytics">Analytics</option>
            </select>
          </div>
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
                <option value="current">Current</option>
                <option value="future">Upcoming</option>
              </select>
            </div>
          </div>
        </section>

        <hr className="border-slate-200" />

        {/* Prompt Rules */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Summary Rules</h3>
          <p className="text-xs text-slate-500">
            Custom instructions for the AI when generating summaries. Use these to filter, prioritize, or shape the output.
          </p>
          <div>
            <label className={labelCls}>Email Summary Rules</label>
            <textarea
              value={fields.EMAIL_PROMPT_RULES}
              onChange={(e) => set("EMAIL_PROMPT_RULES", e.target.value)}
              className={inputCls + " resize-y"}
              rows={3}
              placeholder="e.g. Ignore all emails from github.com and noreply senders. Prioritize emails from my manager (jane@company.com)."
            />
          </div>
          <div>
            <label className={labelCls}>Calendar Summary Rules</label>
            <textarea
              value={fields.CALENDAR_PROMPT_RULES}
              onChange={(e) => set("CALENDAR_PROMPT_RULES", e.target.value)}
              className={inputCls + " resize-y"}
              rows={3}
              placeholder="e.g. Ignore recurring standup meetings. Focus on meetings with external attendees. Flag any meetings longer than 1 hour."
            />
          </div>
        </section>

        <hr className="border-slate-200" />

        {/* Planner */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Planner</h3>
          <div>
            <label className={labelCls}>Column Width: {fields.PLANNER_COLUMN_WIDTH || 220}px</label>
            <input
              type="range"
              min={160}
              max={400}
              step={10}
              value={fields.PLANNER_COLUMN_WIDTH || "220"}
              onChange={(e) => set("PLANNER_COLUMN_WIDTH", e.target.value)}
              className="w-full accent-indigo-600"
            />
            <div className="flex justify-between text-xs text-slate-400">
              <span>Compact</span>
              <span>Wide</span>
            </div>
          </div>
        </section>

        <hr className="border-slate-200" />

        {/* Integrations */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Integrations</h3>
          {secretInput("SLACK_WEBHOOK_URL", "Slack Webhook URL")}
          <p className="text-xs text-slate-500">
            Create an Incoming Webhook at your Slack app's settings page.
            The target channel or DM is set when you create the webhook.
          </p>
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
