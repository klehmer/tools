import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import type { Direction, Period, SummaryResult } from "../types";
import { getDefaults, summarizeCalendar, summarizeEmails } from "../services/api";

type Mode = "emails" | "calendar";

export default function SummaryPanel() {
  const [mode, setMode] = useState<Mode>("emails");
  const [period, setPeriod] = useState<Period>("week");
  const [direction, setDirection] = useState<Direction>("past");
  const [provider, setProvider] = useState<string>("anthropic");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SummaryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDefaults()
      .then((d) => {
        if (d.period) setPeriod(d.period as Period);
        if (d.direction) setDirection(d.direction as Direction);
        if (d.provider) setProvider(d.provider);
      })
      .catch(() => {});
  }, []);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r =
        mode === "emails"
          ? await summarizeEmails(period)
          : await summarizeCalendar(period, direction);
      setResult(r);
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setLoading(false);
    }
  };

  const providerLabel: Record<string, string> = {
    anthropic: "Anthropic API",
    "claude-code": "Claude Code CLI",
    codex: "Codex CLI",
    openai: "OpenAI API",
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl shadow-sm p-6 space-y-4">
        <div className="flex flex-wrap gap-3">
          <div className="flex bg-slate-100 rounded-lg p-1">
            {(["emails", "calendar"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-4 py-2 rounded-md text-sm font-medium capitalize ${
                  mode === m ? "bg-white shadow text-indigo-600" : "text-slate-600"
                }`}
              >
                {m}
              </button>
            ))}
          </div>

          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as Period)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="day">Day</option>
            <option value="week">Week</option>
            <option value="month">Month</option>
            <option value="quarter">Quarter</option>
          </select>

          {mode === "calendar" && (
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value as Direction)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
            >
              <option value="past">Previous</option>
              <option value="future">Upcoming</option>
            </select>
          )}

          <button
            onClick={run}
            disabled={loading}
            className="ml-auto bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {loading ? "Summarizing..." : "Generate Summary"}
          </button>
        </div>
        <div className="flex items-center gap-4 text-sm text-slate-500">
          <span>
            {mode === "emails"
              ? `Summarize inbox emails from the previous ${period}.`
              : `Summarize ${direction === "past" ? "previous" : "upcoming"} ${period} of calendar events.`}
          </span>
          <span className="ml-auto text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
            {providerLabel[provider] ?? provider}
          </span>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="bg-white rounded-2xl shadow-sm p-6 space-y-5">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
              Summary {result.count !== undefined && `\u00b7 ${result.count} items`}
            </div>
            <p className="text-slate-800 leading-relaxed">{result.summary}</p>
          </div>

          {result.highlights && result.highlights.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-900 mb-2">Highlights</h3>
              <ul className="space-y-2">
                {result.highlights.map((h, i) => (
                  <li key={i} className="border-l-2 border-indigo-400 pl-3 py-1">
                    <div className="font-medium text-sm">{h.title}</div>
                    {h.subject && <div className="text-xs text-slate-500">{h.subject}</div>}
                    {h.from && <div className="text-xs text-slate-500">From: {h.from}</div>}
                    {h.when && <div className="text-xs text-slate-500">{h.when}</div>}
                    {h.why && <div className="text-xs text-slate-600 mt-1">{h.why}</div>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.themes && result.themes.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-900 mb-2">Themes</h3>
              <div className="flex flex-wrap gap-2">
                {result.themes.map((t, i) => (
                  <span key={i} className="bg-slate-100 text-slate-700 text-xs px-2 py-1 rounded">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {result.action_items && result.action_items.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-900 mb-2">Action Items</h3>
              <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                {result.action_items.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
