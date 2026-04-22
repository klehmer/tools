import { useEffect, useState } from "react";
import { Archive, BarChart3, Check, ChevronDown, Loader2, Trash2 } from "lucide-react";
import type { AnalyticsResult, Report, SavedAnalyticsReport } from "../types";
import {
  deleteAnalyticsReport,
  generateAnalytics,
  getAnalyticsReports,
  getReports,
  saveAnalyticsReport,
} from "../services/api";

export default function AnalyticsPanel() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<AnalyticsResult | null>(null);
  const [resultSourceIds, setResultSourceIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Save state
  const [saveName, setSaveName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Saved analytics reports
  const [savedReports, setSavedReports] = useState<SavedAnalyticsReport[]>([]);
  const [viewingReport, setViewingReport] = useState<SavedAnalyticsReport | null>(null);
  const [savedOpen, setSavedOpen] = useState(false);

  useEffect(() => {
    Promise.all([getReports(undefined, 200), getAnalyticsReports()])
      .then(([r, ar]) => {
        setReports(r);
        setSavedReports(ar);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const selectAll = () => {
    if (selected.size === reports.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(reports.map((r) => r.id)));
    }
  };

  const run = async () => {
    if (selected.size === 0) return;
    setGenerating(true);
    setError(null);
    setResult(null);
    setViewingReport(null);
    setSaved(false);
    setSaveName("");
    const ids = Array.from(selected);
    try {
      const r = await generateAnalytics(ids);
      setResult(r);
      setResultSourceIds(ids);
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!result || !saveName.trim()) return;
    setSaving(true);
    try {
      const report = await saveAnalyticsReport(saveName.trim(), result, resultSourceIds);
      setSavedReports((prev) => [report, ...prev]);
      setSaved(true);
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteAnalyticsReport(id);
      setSavedReports((prev) => prev.filter((r) => r.id !== id));
      if (viewingReport?.id === id) {
        setViewingReport(null);
        setResult(null);
      }
    } catch {}
  };

  const viewSaved = (report: SavedAnalyticsReport) => {
    setViewingReport(report);
    setResult(report.analytics);
    setSaved(true);
    setSaveName(report.name);
    setError(null);
  };

  const fmtDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  const badges = (r: Report) => {
    const b: string[] = [];
    if (r.results.email) b.push("Email");
    if (r.results.calendar) b.push("Calendar");
    return b;
  };

  const maxOf = (arr: { hours?: number; count?: number; pct?: number }[], key: "hours" | "count" | "pct") =>
    Math.max(...arr.map((a) => (a as any)[key] ?? 0), 1);

  // The active result to display (from generation or viewing a saved report)
  const displayResult = result;

  return (
    <div className="space-y-6">
      {/* Saved analytics reports */}
      {savedReports.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm p-6">
          <button
            onClick={() => setSavedOpen(!savedOpen)}
            className="flex items-center gap-2 w-full text-left"
          >
            <ChevronDown
              size={16}
              className={`text-slate-400 transition-transform ${savedOpen ? "" : "-rotate-90"}`}
            />
            <h3 className="font-semibold text-slate-900">Saved Analytics Reports</h3>
            <span className="text-xs text-slate-400 ml-1">({savedReports.length})</span>
          </button>
          {savedOpen && (
            <div className="mt-3 border border-slate-200 rounded-lg divide-y divide-slate-100 max-h-48 overflow-y-auto">
              {savedReports.map((r) => (
                <div
                  key={r.id}
                  className={`flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors ${
                    viewingReport?.id === r.id ? "bg-indigo-50" : ""
                  }`}
                >
                  <button
                    onClick={() => viewSaved(r)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="text-sm font-medium text-slate-800 truncate">{r.name}</div>
                    <div className="text-xs text-slate-400">
                      {fmtDate(r.created_at)} &middot; {r.source_report_ids.length} source reports
                    </div>
                  </button>
                  <button
                    onClick={() => handleDelete(r.id)}
                    className="p-1 text-slate-300 hover:text-red-500 transition-colors flex-shrink-0"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Report selector */}
      <div className="bg-white rounded-2xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">Select Reports for Analysis</h3>
          <div className="flex items-center gap-3">
            <button
              onClick={selectAll}
              className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
            >
              {selected.size === reports.length ? "Deselect All" : "Select All"}
            </button>
            <button
              onClick={run}
              disabled={generating || selected.size === 0}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-50"
            >
              {generating ? (
                <><Loader2 size={16} className="animate-spin" /> Analyzing...</>
              ) : (
                <><BarChart3 size={16} /> Generate Analytics ({selected.size})</>
              )}
            </button>
          </div>
        </div>

        {loading ? (
          <p className="text-slate-500 text-sm">Loading reports...</p>
        ) : reports.length === 0 ? (
          <p className="text-slate-500 text-sm">
            No reports yet. Generate summaries and save them, or set up scheduled jobs.
          </p>
        ) : (
          <div className="max-h-64 overflow-y-auto border border-slate-200 rounded-lg divide-y divide-slate-100">
            {reports.map((r) => (
              <label
                key={r.id}
                className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-slate-50 transition-colors ${
                  selected.has(r.id) ? "bg-indigo-50" : ""
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(r.id)}
                  onChange={() => toggle(r.id)}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-800 truncate">{r.job_name}</div>
                  <div className="text-xs text-slate-400">{fmtDate(r.created_at)}</div>
                </div>
                <div className="flex gap-1.5 flex-shrink-0">
                  {badges(r).map((b) => (
                    <span
                      key={b}
                      className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                        b === "Email"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {b}
                    </span>
                  ))}
                  {r.job_id === "adhoc" && (
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                      Ad-hoc
                    </span>
                  )}
                </div>
              </label>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {displayResult && (
        <div className="space-y-5">
          {/* Save bar */}
          {!viewingReport && (
            <div className="bg-white rounded-2xl shadow-sm p-4 flex items-center gap-3">
              <input
                type="text"
                value={saveName}
                onChange={(e) => { setSaveName(e.target.value); setSaved(false); }}
                placeholder="Name this analytics report..."
                className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
              />
              <button
                onClick={handleSave}
                disabled={saving || saved || !saveName.trim()}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  saved
                    ? "bg-green-100 text-green-700"
                    : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                } disabled:opacity-60`}
              >
                {saved ? (
                  <><Check size={15} /> Saved</>
                ) : saving ? (
                  <><Loader2 size={15} className="animate-spin" /> Saving...</>
                ) : (
                  <><Archive size={15} /> Save</>
                )}
              </button>
            </div>
          )}

          {/* Viewing saved report indicator */}
          {viewingReport && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-indigo-800">{viewingReport.name}</div>
                <div className="text-xs text-indigo-500">{fmtDate(viewingReport.created_at)}</div>
              </div>
              <button
                onClick={() => { setViewingReport(null); setResult(null); setSaved(false); setSaveName(""); }}
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
              >
                Close
              </button>
            </div>
          )}

          {/* Overall summary */}
          <div className="bg-white rounded-2xl shadow-sm p-6">
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">Overall Summary</div>
            <p className="text-slate-800 leading-relaxed">{displayResult.overall_summary}</p>
          </div>

          {/* Calendar Analytics */}
          {displayResult.calendar_analytics && (
            <div className="bg-white rounded-2xl shadow-sm p-6 space-y-5">
              <h3 className="font-semibold text-slate-900">Calendar Analytics</h3>
              <p className="text-sm text-slate-600">{displayResult.calendar_analytics.summary}</p>

              {displayResult.calendar_analytics.meeting_load && (
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: "Total Events", value: displayResult.calendar_analytics.meeting_load.total_events },
                    { label: "Total Hours", value: displayResult.calendar_analytics.meeting_load.total_hours },
                    { label: "Avg / Day", value: displayResult.calendar_analytics.meeting_load.avg_per_day },
                  ].map((s) => (
                    <div key={s.label} className="bg-indigo-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-indigo-700">{s.value}</div>
                      <div className="text-xs text-indigo-500">{s.label}</div>
                    </div>
                  ))}
                </div>
              )}

              {displayResult.calendar_analytics.hours_by_category?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Hours by Category</h4>
                  <div className="space-y-2">
                    {displayResult.calendar_analytics.hours_by_category.map((c) => (
                      <div key={c.category} className="flex items-center gap-3">
                        <span className="text-sm text-slate-600 w-32 truncate flex-shrink-0">{c.category}</span>
                        <div className="flex-1 bg-slate-100 rounded-full h-5 overflow-hidden">
                          <div
                            className="bg-indigo-500 h-full rounded-full transition-all"
                            style={{
                              width: `${(c.hours / maxOf(displayResult.calendar_analytics!.hours_by_category, "hours")) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-sm font-medium text-slate-700 w-12 text-right">{c.hours}h</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {displayResult.calendar_analytics.busiest_days?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Busiest Days</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                    {displayResult.calendar_analytics.busiest_days.map((d) => (
                      <div key={d.day} className="bg-slate-50 rounded-lg p-2.5 text-center">
                        <div className="text-sm font-medium text-slate-800">{d.day}</div>
                        <div className="text-xs text-slate-500">{d.event_count} events &middot; {d.hours}h</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {displayResult.calendar_analytics.top_attendees?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Top Collaborators</h4>
                  <div className="flex flex-wrap gap-2">
                    {displayResult.calendar_analytics.top_attendees.map((a) => (
                      <span
                        key={a.name}
                        className="bg-violet-50 text-violet-700 text-xs px-2.5 py-1 rounded-full"
                      >
                        {a.name} ({a.meeting_count})
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {displayResult.calendar_analytics.recurring_patterns?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Recurring Patterns</h4>
                  <ul className="list-disc pl-5 space-y-1 text-sm text-slate-600">
                    {displayResult.calendar_analytics.recurring_patterns.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Email Analytics */}
          {displayResult.email_analytics && (
            <div className="bg-white rounded-2xl shadow-sm p-6 space-y-5">
              <h3 className="font-semibold text-slate-900">Email Analytics</h3>
              <p className="text-sm text-slate-600">{displayResult.email_analytics.summary}</p>

              {displayResult.email_analytics.categories?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Email Categories</h4>
                  <div className="space-y-2">
                    {displayResult.email_analytics.categories.map((c) => (
                      <div key={c.category} className="flex items-center gap-3">
                        <span className="text-sm text-slate-600 w-40 truncate flex-shrink-0">{c.category}</span>
                        <div className="flex-1 bg-slate-100 rounded-full h-5 overflow-hidden">
                          <div
                            className="bg-blue-500 h-full rounded-full transition-all"
                            style={{ width: `${c.pct}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-slate-700 w-12 text-right">{c.pct}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {displayResult.email_analytics.top_senders?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Top Senders</h4>
                  <div className="space-y-2">
                    {displayResult.email_analytics.top_senders.slice(0, 10).map((s) => (
                      <div key={s.sender} className="flex items-center gap-3">
                        <span className="text-sm text-slate-600 flex-1 truncate">{s.sender}</span>
                        <div className="w-24 bg-slate-100 rounded-full h-4 overflow-hidden">
                          <div
                            className="bg-blue-400 h-full rounded-full"
                            style={{
                              width: `${(s.count / maxOf(displayResult.email_analytics!.top_senders, "count")) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs font-medium text-slate-500 w-8 text-right">{s.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {displayResult.email_analytics.volume_trend?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Volume Trend</h4>
                  <div className="flex items-end gap-1 h-24">
                    {displayResult.email_analytics.volume_trend.map((v, i) => {
                      const max = maxOf(displayResult.email_analytics!.volume_trend, "count");
                      return (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1">
                          <span className="text-[10px] text-slate-500">{v.count}</span>
                          <div
                            className="w-full bg-blue-400 rounded-t min-h-[2px]"
                            style={{ height: `${(v.count / max) * 60}px` }}
                          />
                          <span className="text-[9px] text-slate-400 truncate w-full text-center">{v.period}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {displayResult.email_analytics.response_needed?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Needs Response</h4>
                  <ul className="list-disc pl-5 space-y-1 text-sm text-slate-600">
                    {displayResult.email_analytics.response_needed.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Cross-insights */}
          {displayResult.cross_insights?.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm p-6">
              <h3 className="font-semibold text-slate-900 mb-3">Cross-Cutting Insights</h3>
              <ul className="space-y-2">
                {displayResult.cross_insights.map((insight, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="text-indigo-500 mt-0.5 flex-shrink-0">&#x2022;</span>
                    {insight}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
