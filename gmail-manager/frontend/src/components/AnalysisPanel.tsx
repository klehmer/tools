import { useEffect, useState } from "react";
import {
  Ban,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  MailMinus,
  Square,
  Trash2,
} from "lucide-react";
import type { AnalysisResult, EmailCategory, EmailGroup } from "../types";
import {
  blockSender,
  deleteEmails,
  downloadBulk,
  getMessagesMetadata,
  unsubscribeSender,
  type EmailMeta,
} from "../services/api";
import DownloadModal from "./DownloadModal";

interface Props {
  analysis: AnalysisResult;
}

const TABS: { key: EmailCategory; label: string; icon: React.ReactNode }[] = [
  { key: "delete", label: "Bulk Delete", icon: <Trash2 className="h-4 w-4" /> },
  {
    key: "unsubscribe",
    label: "Unsubscribe",
    icon: <MailMinus className="h-4 w-4" />,
  },
  { key: "block", label: "Block Senders", icon: <Ban className="h-4 w-4" /> },
];

export default function AnalysisPanel({ analysis }: Props) {
  const [activeTab, setActiveTab] = useState<EmailCategory>("delete");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Set<string>>(new Set());
  const [downloadModal, setDownloadModal] = useState<EmailGroup | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const grouped = analysis.email_groups.reduce<
    Record<EmailCategory, EmailGroup[]>
  >(
    (acc, g) => {
      acc[g.category].push(g);
      return acc;
    },
    { delete: [], unsubscribe: [], block: [] }
  );

  const tabGroups = grouped[activeTab].filter(
    (g) => !done.has(groupKey(g))
  );

  const toggleSelect = (g: EmailGroup) => {
    const k = groupKey(g);
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(k) ? next.delete(k) : next.add(k);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(tabGroups.map(groupKey)));
  };

  const clearAll = () => setSelected(new Set());

  const selectedGroups = tabGroups.filter((g) => selected.has(groupKey(g)));

  const executeSelected = async () => {
    if (!selectedGroups.length) return;
    setBusy(true);
    setFeedback(null);
    try {
      if (activeTab === "delete") {
        const ids = selectedGroups.flatMap((g) => g.email_ids);
        const totalMb = selectedGroups.reduce((s, g) => s + g.total_size_mb, 0);
        await deleteEmails(ids);
        setFeedback(`Deleted ${ids.length} emails — freed ~${totalMb.toFixed(1)} MB.`);
      } else if (activeTab === "unsubscribe") {
        for (const g of selectedGroups) {
          const result = await unsubscribeSender(
            g.email_ids[0],
            g.sender,
            g.unsubscribe_link
          );
          if (result.method === "http" && result.url) {
            window.open(result.url, "_blank");
          }
        }
        setFeedback(`Unsubscribed from ${selectedGroups.length} senders.`);
      } else if (activeTab === "block") {
        for (const g of selectedGroups) {
          await blockSender(g.sender.match(/<([^>]+)>/)?.[1] ?? g.sender);
        }
        setFeedback(`Blocked ${selectedGroups.length} senders.`);
      }

      setDone((prev) => {
        const next = new Set(prev);
        selectedGroups.forEach((g) => next.add(groupKey(g)));
        return next;
      });
      setSelected(new Set());
    } catch (e) {
      setFeedback(`Error: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setBusy(false);
    }
  };

  const downloadSelected = async () => {
    const ids = selectedGroups.flatMap((g) => g.email_ids);
    if (!ids.length) return;
    await downloadBulk(ids, true);
  };

  return (
    <div>
      {/* Tabs */}
      <div className="mb-4 flex gap-1 rounded-xl bg-gray-100 p-1">
        {TABS.map((tab) => {
          const count = grouped[tab.key].filter(
            (g) => !done.has(groupKey(g))
          ).length;
          return (
            <button
              key={tab.key}
              onClick={() => {
                setActiveTab(tab.key);
                setSelected(new Set());
              }}
              className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
                activeTab === tab.key
                  ? "bg-white shadow text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.icon}
              {tab.label}
              {count > 0 && (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-xs ${
                    activeTab === tab.key
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-200 text-gray-600"
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Action bar */}
      {tabGroups.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button
            onClick={selected.size === tabGroups.length ? clearAll : selectAll}
            className="flex items-center gap-1 text-sm text-gray-600 hover:text-blue-600"
          >
            {selected.size === tabGroups.length ? (
              <CheckSquare className="h-4 w-4" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            {selected.size === tabGroups.length ? "Deselect all" : "Select all"}
          </button>

          {selectedGroups.length > 0 && (
            <>
              <span className="ml-auto text-sm text-gray-500">
                {selectedGroups.length} selected
              </span>
              {activeTab === "delete" && (
                <button
                  onClick={downloadSelected}
                  className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  <Download className="h-4 w-4" />
                  Download first
                </button>
              )}
              <button
                onClick={executeSelected}
                disabled={busy}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold text-white transition disabled:opacity-60 ${
                  activeTab === "delete"
                    ? "bg-red-600 hover:bg-red-700"
                    : activeTab === "unsubscribe"
                      ? "bg-orange-600 hover:bg-orange-700"
                      : "bg-gray-800 hover:bg-gray-900"
                }`}
              >
                {busy ? "Processing…" : actionLabel(activeTab, selectedGroups)}
              </button>
            </>
          )}
        </div>
      )}

      {feedback && (
        <div className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700">
          {feedback}
        </div>
      )}

      {/* Group cards */}
      <div className="space-y-3">
        {tabGroups.length === 0 ? (
          <p className="py-12 text-center text-sm text-gray-400">
            No recommendations in this category.
          </p>
        ) : (
          tabGroups.map((group) => (
            <GroupCard
              key={groupKey(group)}
              group={group}
              selected={selected.has(groupKey(group))}
              onToggle={() => toggleSelect(group)}
              onDownload={() => setDownloadModal(group)}
            />
          ))
        )}
      </div>

      {downloadModal && (
        <DownloadModal
          group={downloadModal}
          onClose={() => setDownloadModal(null)}
        />
      )}
    </div>
  );
}

function GroupCard({
  group,
  selected,
  onToggle,
  onDownload,
}: {
  group: EmailGroup;
  selected: boolean;
  onToggle: () => void;
  onDownload: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<EmailMeta[] | null>(null);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [perEmailSelected, setPerEmailSelected] = useState<Set<string>>(new Set());
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (expanded && messages === null && !loadingMsgs) {
      setLoadingMsgs(true);
      getMessagesMetadata(group.email_ids)
        .then(setMessages)
        .catch(() => setMessages([]))
        .finally(() => setLoadingMsgs(false));
    }
  }, [expanded, messages, loadingMsgs, group.email_ids]);

  const toggleEmail = (id: string) => {
    setPerEmailSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAllEmails = () => {
    if (!messages) return;
    setPerEmailSelected(new Set(messages.map((m) => m.id)));
  };

  const clearEmails = () => setPerEmailSelected(new Set());

  const downloadChecked = async () => {
    if (!perEmailSelected.size) return;
    setDownloading(true);
    try {
      await downloadBulk(Array.from(perEmailSelected), true);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      className={`rounded-xl border transition ${
        selected
          ? "border-blue-300 bg-blue-50"
          : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="flex items-start gap-3 p-4">
        <button onClick={onToggle} className="mt-0.5 shrink-0 text-gray-400">
          {selected ? (
            <CheckSquare className="h-5 w-5 text-blue-600" />
          ) : (
            <Square className="h-5 w-5" />
          )}
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="truncate font-medium text-gray-900">
              {group.sender_name || parseName(group.sender)}
            </span>
            <span className="truncate text-xs text-gray-400">{group.sender}</span>
          </div>

          <p className="mt-1 text-sm text-gray-600">{group.suggestion_reason}</p>

          <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
            <Chip>{group.count} emails</Chip>
            <Chip>{group.total_size_mb.toFixed(1)} MB</Chip>
            <Chip>
              {shortDate(group.oldest_date)} – {shortDate(group.newest_date)}
            </Chip>
          </div>

          {group.unsubscribe_link && (
            <a
              href={group.unsubscribe_link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
            >
              Unsubscribe link <ExternalLink className="h-3 w-3" />
            </a>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="inline-flex items-center gap-1 text-blue-600 hover:underline"
            >
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              {expanded ? "Hide emails" : "Pick emails to download"}
            </button>
          </div>
        </div>

        <button
          onClick={onDownload}
          title="Download all in this group (with attachments)"
          className="shrink-0 rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          <Download className="h-4 w-4" />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-gray-200 bg-white px-4 py-3">
          {loadingMsgs && (
            <div className="text-xs text-gray-500">Loading email subjects…</div>
          )}
          {!loadingMsgs && messages && messages.length === 0 && (
            <div className="text-xs text-gray-500">No emails to show.</div>
          )}
          {!loadingMsgs && messages && messages.length > 0 && (
            <>
              <div className="mb-2 flex items-center gap-3 text-xs">
                <button onClick={selectAllEmails} className="text-blue-600 hover:underline">
                  Select all
                </button>
                <button onClick={clearEmails} className="text-blue-600 hover:underline">
                  Clear
                </button>
                <span className="ml-auto text-gray-500">
                  {perEmailSelected.size} of {messages.length} selected
                </span>
                <button
                  onClick={downloadChecked}
                  disabled={!perEmailSelected.size || downloading}
                  className="flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white shadow hover:bg-blue-700 disabled:opacity-60"
                >
                  <Download className="h-3 w-3" />
                  {downloading ? "Downloading…" : `Download ${perEmailSelected.size}`}
                </button>
              </div>

              <ul className="max-h-72 space-y-1 overflow-y-auto rounded border border-gray-100 p-2">
                {messages.map((m) => {
                  const checked = perEmailSelected.has(m.id);
                  return (
                    <li
                      key={m.id}
                      onClick={() => toggleEmail(m.id)}
                      className={`flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs ${
                        checked ? "bg-blue-50" : "hover:bg-gray-50"
                      }`}
                    >
                      {checked ? (
                        <CheckSquare className="h-4 w-4 shrink-0 text-blue-600" />
                      ) : (
                        <Square className="h-4 w-4 shrink-0 text-gray-400" />
                      )}
                      <span className="min-w-0 flex-1 truncate text-gray-800">
                        {m.subject}
                      </span>
                      <span className="shrink-0 text-gray-400">
                        {shortDate(m.date)}
                      </span>
                      <span className="shrink-0 text-gray-400">
                        {(m.size_bytes / 1024).toFixed(0)} KB
                      </span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-md bg-gray-100 px-2 py-0.5">{children}</span>
  );
}

function groupKey(g: EmailGroup) {
  return `${g.category}:${g.sender}`;
}

function parseName(sender: string) {
  const m = sender.match(/^"?([^"<]+)"?\s*</);
  return m ? m[1].trim() : sender;
}

function shortDate(dateStr: string) {
  if (!dateStr) return "?";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr.slice(0, 10);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short" });
}

function actionLabel(tab: EmailCategory, groups: EmailGroup[]) {
  const totalEmails = groups.reduce((s, g) => s + g.email_ids.length, 0);
  if (tab === "delete") return `Delete ${totalEmails} emails`;
  if (tab === "unsubscribe") return `Unsubscribe from ${groups.length}`;
  return `Block ${groups.length} senders`;
}
