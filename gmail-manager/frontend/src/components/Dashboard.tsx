import { useState } from "react";
import { Bot, HardDrive, LogOut, Mail, RefreshCw, Settings, Shield, Terminal } from "lucide-react";
import type { AnalysisResult, UserProfile } from "../types";
import { analyzeInbox } from "../services/api";
import AnalysisPanel from "./AnalysisPanel";
import AgentLogsPanel from "./AgentLogsPanel";
import AgentReportPanel from "./AgentReportPanel";
import AgentRunnerModal from "./AgentRunnerModal";
import PendingApprovalsPanel from "./PendingApprovalsPanel";
import RulesModal from "./RulesModal";

type Runner = "builtin" | "claude-code" | "codex";

interface Props {
  user: UserProfile;
  analysis: AnalysisResult | null;
  onAnalysisComplete: (result: AnalysisResult) => void;
  onLogout: () => void;
  onOpenSettings: () => void;
}

export default function Dashboard({
  user,
  analysis,
  onAnalysisComplete,
  onLogout,
  onOpenSettings,
}: Props) {
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runner, setRunner] = useState<Runner>("builtin");
  const [showRunnerModal, setShowRunnerModal] = useState(false);
  const [showRulesModal, setShowRulesModal] = useState(false);

  const runAnalysis = async () => {
    if (runner !== "builtin") {
      setShowRunnerModal(true);
      return;
    }
    setAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeInbox();
      onAnalysisComplete(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2 font-semibold text-gray-900">
            <Mail className="h-5 w-5 text-blue-600" />
            Gmail Manager
          </div>
          <div className="flex items-center gap-3">
            {user.picture && (
              <img
                src={user.picture}
                alt="avatar"
                className="h-8 w-8 rounded-full"
              />
            )}
            <div className="hidden text-sm sm:block">
              <p className="font-medium">{user.name || user.email}</p>
              {user.name && (
                <p className="text-xs text-gray-500">{user.email}</p>
              )}
            </div>
            <button
              onClick={() => setShowRulesModal(true)}
              title="Cleanup rules"
              className="rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            >
              <Shield className="h-4 w-4" />
            </button>
            <button
              onClick={onOpenSettings}
              title="Settings"
              className="rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            >
              <Settings className="h-4 w-4" />
            </button>
            <button
              onClick={onLogout}
              className="ml-1 flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-500 hover:bg-gray-100"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <AgentReportPanel />
        <PendingApprovalsPanel />

        {/* Stats bar */}
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            label="Total messages"
            value={user.total_messages.toLocaleString()}
            icon={<Mail className="h-5 w-5 text-blue-500" />}
          />
          {user.storage_used_bytes != null && (
            <StatCard
              label="Storage used"
              value={
                user.storage_limit_bytes
                  ? `${formatBytes(user.storage_used_bytes)} / ${formatBytes(user.storage_limit_bytes)}`
                  : formatBytes(user.storage_used_bytes)
              }
              icon={<HardDrive className="h-5 w-5 text-purple-500" />}
            />
          )}
          {analysis && (
            <StatCard
              label="Estimated space to free"
              value={`${analysis.estimated_storage_freed_mb.toFixed(0)} MB`}
              icon={<Bot className="h-5 w-5 text-green-500" />}
              highlight
            />
          )}
        </div>

        {/* Analyse button */}
        {!analysis && (
          <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-blue-200 bg-white py-16 text-center">
            <Bot className="mb-4 h-16 w-16 text-blue-400" />
            <h2 className="mb-2 text-xl font-semibold text-gray-800">
              Analyse Your Inbox
            </h2>
            <p className="mb-6 max-w-md text-sm text-gray-500">
              Pick how to run the analysis. The built-in agent gives you a
              suggestion list to review. Claude Code or Codex will run as a
              long-lived agent and clean your inbox autonomously over several
              minutes.
            </p>

            <div className="mb-6 flex flex-wrap items-center justify-center gap-2">
              <RunnerOption
                value="builtin"
                current={runner}
                onChange={setRunner}
                label="Built-in agent"
                hint="Quick scan, you approve actions"
              />
              <RunnerOption
                value="claude-code"
                current={runner}
                onChange={setRunner}
                label="Claude Code"
                hint="Long-lived autonomous cleanup"
              />
              <RunnerOption
                value="codex"
                current={runner}
                onChange={setRunner}
                label="Codex"
                hint="Long-lived autonomous cleanup"
              />
            </div>

            <button
              onClick={runAnalysis}
              disabled={analyzing}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow transition hover:bg-blue-700 disabled:opacity-60"
            >
              {analyzing ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Analysing inbox… (this may take up to 90s)
                </>
              ) : runner === "builtin" ? (
                <>
                  <Bot className="h-4 w-4" />
                  Start AI Analysis
                </>
              ) : (
                <>
                  <Terminal className="h-4 w-4" />
                  Get {runner === "claude-code" ? "Claude Code" : "Codex"} prompt
                </>
              )}
            </button>
          </div>
        )}

        {/* Re-analyse */}
        {analysis && !analyzing && (
          <div className="mb-4 flex justify-end">
            <button
              onClick={runAnalysis}
              className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100"
            >
              <RefreshCw className="h-4 w-4" />
              Re-analyse
            </button>
          </div>
        )}

        {analyzing && analysis && (
          <div className="mb-4 flex items-center gap-2 text-sm text-blue-600">
            <RefreshCw className="h-4 w-4 animate-spin" />
            Re-analysing inbox…
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {analysis && !analyzing && (
          <>
            {/* Summary */}
            <div className="mb-6 rounded-xl bg-blue-50 p-4 text-sm text-blue-800">
              <strong>Summary:</strong> {analysis.analysis_summary}
            </div>
            <AnalysisPanel analysis={analysis} />
          </>
        )}

        <AgentLogsPanel />
      </main>

      {showRunnerModal && runner !== "builtin" && (
        <AgentRunnerModal
          runner={runner}
          totalMessages={user.total_messages}
          onClose={() => setShowRunnerModal(false)}
        />
      )}

      {showRulesModal && <RulesModal onClose={() => setShowRulesModal(false)} />}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`;
}

function RunnerOption({
  value,
  current,
  onChange,
  label,
  hint,
}: {
  value: Runner;
  current: Runner;
  onChange: (r: Runner) => void;
  label: string;
  hint: string;
}) {
  const selected = current === value;
  return (
    <button
      onClick={() => onChange(value)}
      className={`w-44 rounded-lg border px-3 py-2 text-left text-xs transition ${
        selected
          ? "border-blue-600 bg-blue-50 ring-2 ring-blue-200"
          : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="font-semibold text-gray-900">{label}</div>
      <div className="text-gray-500">{hint}</div>
    </button>
  );
}

function StatCard({
  label,
  value,
  icon,
  highlight,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-4 rounded-xl border p-4 ${highlight ? "border-green-200 bg-green-50" : "border-gray-200 bg-white"}`}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-sm">
        {icon}
      </div>
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-lg font-semibold text-gray-900">{value}</p>
      </div>
    </div>
  );
}
