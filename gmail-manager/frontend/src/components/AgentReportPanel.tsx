import { useEffect, useRef, useState } from "react";
import {
  Ban,
  Bot,
  Check,
  Download,
  MailMinus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import {
  addUnsubscribedSender,
  blockSender,
  clearAgentReport,
  deleteEmails,
  downloadBulk,
  findUnsubscribeLink,
  getAgentReport,
  getMessagesMetadata,
  markReportAction,
  searchEmailIds,
  unsubscribeSender,
} from "../services/api";
import type { AgentReport, ReportGroup } from "../types";

type JobState = "queued" | "running";
type Job = { key: string; label: string; run: () => Promise<void> };

export default function AgentReportPanel() {
  const [report, setReport] = useState<AgentReport | null>(null);
  const [pending, setPending] = useState<Record<string, JobState>>({});
  const [feedback, setFeedback] = useState<string | null>(null);
  const queueRef = useRef<Job[]>([]);
  const activeWorkers = useRef(0);
  const MAX_CONCURRENT = 4;

  const done = new Set<string>(report?.actioned_keys ?? []);
  const queueDepth = Object.values(pending).filter((s) => s === "queued").length;
  const runningCount = Object.values(pending).filter((s) => s === "running").length;

  const setKeyState = (key: string, state: JobState | null) => {
    setPending((prev) => {
      const next = { ...prev };
      if (state === null) delete next[key];
      else next[key] = state;
      return next;
    });
  };

  const enqueue = (job: Job) => {
    // Reject duplicate enqueues for the same key — synchronous via ref check.
    if (queueRef.current.some((j) => j.key === job.key)) return;
    if (pending[job.key]) return;
    queueRef.current.push(job);
    setKeyState(job.key, "queued");
    pumpWorkers();
  };

  const pumpWorkers = () => {
    // Spin up workers up to MAX_CONCURRENT. Each worker drains jobs from the
    // shared queue until it's empty, then exits.
    while (activeWorkers.current < MAX_CONCURRENT && queueRef.current.length > 0) {
      activeWorkers.current += 1;
      void (async () => {
        try {
          while (queueRef.current.length > 0) {
            const job = queueRef.current.shift()!;
            setKeyState(job.key, "running");
            try {
              await job.run();
            } catch (e) {
              setFeedback(`Error: ${e instanceof Error ? e.message : "unknown"}`);
            } finally {
              setKeyState(job.key, null);
            }
          }
        } finally {
          activeWorkers.current -= 1;
        }
      })();
    }
  };

  const refresh = async () => {
    try {
      const r = await getAgentReport();
      setReport(r);
    } catch {
      // ignore
    }
  };

  const markActioned = async (key: string, deletedCount = 0, freedMb = 0) => {
    try {
      const r = await markReportAction(key, deletedCount, freedMb);
      setReport(r);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  if (!report) return null;

  const resolveIds = async (g: ReportGroup): Promise<string[]> => {
    if (g.email_ids && g.email_ids.length > 0) return g.email_ids;
    if (g.query) return await searchEmailIds(g.query, 500);
    if (g.sender) {
      // Strip "Display Name <addr>" → "addr". Gmail rejects `from:Name <x>` as
      // an invalid query and returns zero results, which made plain Delete
      // appear broken on agent groups.
      const m = g.sender.match(/<([^>]+)>/);
      const bare = (m ? m[1] : g.sender).trim();
      return await searchEmailIds(`from:${bare}`, 500);
    }
    return [];
  };

  const groupKey = (g: ReportGroup, _i: number) => {
    // Stable key — must match across re-posts of the same group from different
    // agent runs so actioned_keys correctly hides it everywhere.
    const m = g.sender.match(/<([^>]+)>/);
    const bare = (m ? m[1] : g.sender).toLowerCase().trim();
    return `${bare}:${g.suggested_action}`;
  };

  const handleDelete = (g: ReportGroup, i: number, withDownload: boolean) => {
    const key = groupKey(g, i);
    enqueue({
      key,
      label: withDownload ? "Download & delete" : "Delete",
      run: async () => {
        const ids = await resolveIds(g);
        if (!ids.length) {
          setFeedback(`No emails found for ${g.sender}`);
          return;
        }
        if (withDownload) {
          const filename = await buildDownloadFilename(g, ids);
          await downloadBulk(ids, true, filename);
        }
        await deleteEmails(ids);
        await markActioned(key, ids.length, g.estimated_size_mb ?? 0);
        const sz = g.estimated_size_mb != null ? ` — freed ~${g.estimated_size_mb.toFixed(1)} MB` : "";
        setFeedback(`Deleted ${ids.length} emails from ${g.sender}${sz}`);
      },
    });
  };

  const handleBlock = (g: ReportGroup, i: number) => {
    const key = groupKey(g, i);
    enqueue({
      key,
      label: "Block",
      run: async () => {
        const sender = g.sender.match(/<([^>]+)>/)?.[1] ?? g.sender;
        await blockSender(sender);
        await markActioned(key);
        setFeedback(`Blocked ${sender}`);
      },
    });
  };

  const handleUnsubscribe = (g: ReportGroup, i: number) => {
    const key = groupKey(g, i);
    enqueue({
      key,
      label: "Unsubscribe",
      run: async () => {
        const senderEmail = g.sender.match(/<([^>]+)>/)?.[1] ?? g.sender;
        let link: string | null = g.unsubscribe_link ?? null;
        let emailId: string | null = null;
        if (!link || !emailId) {
          const found = await findUnsubscribeLink(senderEmail);
          if (found) {
            emailId = found.id;
            link = link ?? found.link;
          }
        }
        if (!emailId) {
          setFeedback(`No emails found for ${senderEmail}`);
          return;
        }
        const result = await unsubscribeSender(emailId, senderEmail, link);
        if (result.method === "http" && result.url) {
          window.open(result.url, "_blank", "noopener,noreferrer");
          setFeedback(`Opened unsubscribe page for ${senderEmail}`);
        } else if (result.method === "email") {
          setFeedback(
            result.success
              ? `Sent unsubscribe email for ${senderEmail}`
              : `Failed to send unsubscribe email for ${senderEmail}`
          );
        } else {
          setFeedback(`Unsubscribe fallback ran for ${senderEmail}`);
        }
        // NOTE: deliberately do NOT mark this group as actioned — the user
        // may still want to delete the remaining emails after unsubscribing.
        try {
          await addUnsubscribedSender(senderEmail);
        } catch {
          // ignore
        }
      },
    });
  };

  const dismiss = async () => {
    await clearAgentReport();
    setReport(null);
  };

  const bulkKeepAll = async () => {
    if (!report) return;
    const keepGroups = report.groups.filter(
      (g, i) => g.suggested_action === "keep" && !done.has(groupKey(g, i))
    );
    if (keepGroups.length === 0) {
      setFeedback("No 'keep' recommendations to dismiss");
      return;
    }
    setFeedback(`Dismissing ${keepGroups.length} keep recommendations…`);
    for (const g of keepGroups) {
      const key = groupKey(g, 0);
      try {
        await markReportAction(key, 0, 0);
      } catch {
        // ignore individual failures
      }
    }
    await refresh();
    setFeedback(`Dismissed ${keepGroups.length} keep recommendations`);
  };

  const keepCount = report?.groups.filter(
    (g, i) => g.suggested_action === "keep" && !done.has(groupKey(g, i))
  ).length ?? 0;

  const visibleGroups = report.groups.filter((g, i) => !done.has(groupKey(g, i)));

  return (
    <div className="mb-6 rounded-2xl border-2 border-blue-300 bg-blue-50 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-blue-700" />
          <h3 className="font-semibold text-blue-900">
            Agent report ({report.runner})
          </h3>
          {report.status === "running" && (
            <RefreshCw className="h-3 w-3 animate-spin text-blue-600" />
          )}
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              report.status === "done"
                ? "bg-green-100 text-green-700"
                : "bg-amber-100 text-amber-700"
            }`}
          >
            {report.status}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {keepCount > 0 && (
            <button
              onClick={bulkKeepAll}
              title={`Dismiss all ${keepCount} 'keep' recommendations`}
              className="flex items-center gap-1 rounded-md border border-green-500 bg-white px-2 py-1 text-xs font-semibold text-green-700 hover:bg-green-50"
            >
              <Check className="h-3 w-3" />
              Keep all ({keepCount})
            </button>
          )}
          <button
            onClick={async () => {
              if (!confirm("Clear the entire agent report? This lets the next agent pass re-propose senders.")) return;
              await dismiss();
            }}
            className="flex items-center gap-1 rounded-md border border-red-400 bg-white px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
          >
            Clear report
          </button>
          <button
            onClick={dismiss}
            title="Dismiss report"
            className="rounded-full p-1 text-gray-400 hover:bg-white hover:text-gray-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {report.summary && (
        <p className="mb-3 text-sm text-blue-900">{report.summary}</p>
      )}

      <div className="mb-3 flex flex-wrap gap-3 text-xs text-blue-800">
        {report.starting_total != null && (
          <Stat label="Starting total" value={report.starting_total.toLocaleString()} />
        )}
        {report.current_total != null && (
          <Stat label="Current total" value={report.current_total.toLocaleString()} />
        )}
        <Stat label="Deleted so far" value={report.deleted_so_far.toLocaleString()} />
        <Stat label="Recommendations" value={visibleGroups.length.toString()} />
        {(queueDepth > 0 || runningCount > 0) && (
          <Stat
            label="Queue"
            value={`${runningCount} running${queueDepth ? ` · ${queueDepth} waiting` : ""}`}
          />
        )}
      </div>

      {feedback && (
        <div className="mb-3 rounded-md bg-white p-2 text-xs text-gray-700">
          {feedback}
        </div>
      )}

      {visibleGroups.length === 0 ? (
        <p className="text-xs text-blue-700">
          {report.groups.length === 0
            ? "Agent is still gathering data…"
            : "All recommendations have been actioned."}
        </p>
      ) : (
        <div className="space-y-2">
          {report.groups.map((g, i) => {
            const key = groupKey(g, i);
            if (done.has(key)) return null;
            const state = pending[key]; // "queued" | "running" | undefined
            const isBusy = !!state;
            const btnDisabled = `disabled:cursor-not-allowed disabled:opacity-50 ${isBusy ? "pointer-events-none" : ""}`;
            return (
              <div
                key={key}
                className="rounded-lg border border-blue-200 bg-white p-3 text-sm"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="font-medium text-gray-900">{g.sender}</span>
                  <span className="text-xs text-gray-500">
                    {g.count} email{g.count === 1 ? "" : "s"}
                    {g.estimated_size_mb != null && ` · ${g.estimated_size_mb.toFixed(1)} MB`}
                    {" · proposes "}
                    <strong>{g.suggested_action}</strong>
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-600">{g.reason}</p>

                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    onClick={() => handleDelete(g, i, true)}
                    disabled={isBusy}
                    className={`flex items-center gap-1 rounded-md border border-blue-600 bg-white px-2.5 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 ${btnDisabled}`}
                  >
                    <Download className="h-3 w-3" />
                    Download &amp; delete
                  </button>
                  <button
                    onClick={() => handleDelete(g, i, false)}
                    disabled={isBusy}
                    className={`flex items-center gap-1 rounded-md bg-red-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-700 ${btnDisabled}`}
                  >
                    <Trash2 className="h-3 w-3" />
                    Delete
                  </button>
                  {(g.suggested_action === "unsubscribe" || g.unsubscribe_link) && (
                    <button
                      onClick={() => handleUnsubscribe(g, i)}
                      disabled={isBusy}
                      className={`flex items-center gap-1 rounded-md border border-orange-500 bg-white px-2.5 py-1 text-xs font-semibold text-orange-700 hover:bg-orange-50 ${btnDisabled}`}
                    >
                      <MailMinus className="h-3 w-3" />
                      Unsubscribe
                    </button>
                  )}
                  {(g.suggested_action === "block" || g.sender) && (
                    <button
                      onClick={() => handleBlock(g, i)}
                      disabled={isBusy}
                      className={`flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs font-semibold text-gray-800 hover:bg-gray-50 ${btnDisabled}`}
                    >
                      <Ban className="h-3 w-3" />
                      Block sender
                    </button>
                  )}
                  <button
                    onClick={() => markActioned(key)}
                    disabled={isBusy}
                    className={`flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 ${btnDisabled}`}
                  >
                    <Check className="h-3 w-3" />
                    Skip
                  </button>
                  {state === "queued" && (
                    <span className="flex items-center gap-1 self-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                      Queued
                    </span>
                  )}
                  {state === "running" && (
                    <span className="flex items-center gap-1 self-center rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-700">
                      <RefreshCw className="h-3 w-3 animate-spin" />
                      Working
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/<[^>]+>/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "emails";
}

function fmtDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
}

async function buildDownloadFilename(g: ReportGroup, ids: string[]): Promise<string> {
  const slug = slugify(g.sender);
  const stamp = fmtDate(new Date());
  let dateRange = "";
  try {
    const sample = ids.slice(0, Math.min(ids.length, 25));
    const meta = await getMessagesMetadata(sample);
    const times = meta
      .map((m) => Date.parse(m.date))
      .filter((t) => !Number.isNaN(t));
    if (times.length) {
      const oldest = new Date(Math.min(...times));
      const newest = new Date(Math.max(...times));
      dateRange = `_${fmtDate(oldest)}-${fmtDate(newest)}`;
    }
  } catch {
    // ignore — fallback to just the timestamp
  }
  return `gmail_${slug}_${ids.length}msgs${dateRange}_dl${stamp}.zip`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <span className="text-blue-500">{label}:</span>{" "}
      <strong>{value}</strong>
    </span>
  );
}
