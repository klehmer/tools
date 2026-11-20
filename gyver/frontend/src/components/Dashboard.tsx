import { useState } from "react";
import { AlertTriangle, LogOut, Settings } from "lucide-react";
import type { UserProfile } from "../types";
import { clearSessionToken, logout } from "../services/api";
import AnalyticsPanel from "./AnalyticsPanel";
import ReportsPanel from "./ReportsPanel";
import SummaryPanel from "./SummaryPanel";
import SchedulePanel from "./SchedulePanel";
import PlannerPanel from "./PlannerPanel";
import NotesPanel from "./NotesPanel";
import LinksPanel from "./LinksPanel";
import AppsPanel from "./AppsPanel";
import AgentsPanel from "./AgentsPanel";
import SettingsModal from "./SettingsModal";

type Tab = "summary" | "planner" | "notes" | "links" | "apps" | "agents" | "reports" | "schedule" | "analytics";

interface Props {
  profile: UserProfile | null;
  googleConfigured: boolean;
  googleAuthed: boolean;
  onSignIn: () => void;
  onSettingsChanged: () => void;
}

function getInitialTab(googleEnabled: boolean): { tab: Tab; summaryMode?: "emails" | "calendar" } {
  const saved = localStorage.getItem("gyver_default_tab");
  if (saved === "summary-emails" && googleEnabled) return { tab: "summary", summaryMode: "emails" };
  if (saved === "summary-calendar" && googleEnabled) return { tab: "summary", summaryMode: "calendar" };
  if (saved === "reports" && googleEnabled) return { tab: "reports" };
  if (saved === "schedule" && googleEnabled) return { tab: "schedule" };
  if (saved === "analytics" && googleEnabled) return { tab: "analytics" };
  if (saved === "planner") return { tab: "planner" };
  if (saved === "notes") return { tab: "notes" };
  if (saved === "links") return { tab: "links" };
  if (saved === "apps") return { tab: "apps" };
  if (saved === "agents") return { tab: "agents" };
  if (saved === "summary" && googleEnabled) return { tab: "summary" };
  return { tab: googleEnabled ? "summary" : "planner" };
}

export default function Dashboard({
  profile,
  googleConfigured,
  googleAuthed,
  onSignIn,
  onSettingsChanged,
}: Props) {
  const [showSettings, setShowSettings] = useState(false);
  // Google-backed tabs need both credentials on the server and a signed-in user.
  const googleEnabled = googleConfigured && googleAuthed;
  const notAuthed = googleConfigured && !googleAuthed;
  const initial = getInitialTab(googleEnabled);
  const [tab, setTab] = useState<Tab>(initial.tab);
  const [defaultSummaryMode] = useState(initial.summaryMode);
  const [settingsRev, setSettingsRev] = useState(0);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {}
    clearSessionToken();
    window.location.reload();
  };

  const tabs: { key: Tab; label: string; disabled: boolean }[] = [
    { key: "summary", label: "Summary", disabled: !googleEnabled },
    { key: "planner", label: "Planner", disabled: false },
    { key: "notes", label: "Notes", disabled: false },
    { key: "links", label: "Links", disabled: false },
    { key: "apps", label: "Apps", disabled: false },
    { key: "agents", label: "Agents", disabled: false },
    { key: "reports", label: "Reports", disabled: !googleEnabled },
    { key: "schedule", label: "Scheduled Jobs", disabled: !googleEnabled },
    { key: "analytics", label: "Analytics", disabled: !googleEnabled },
  ];

  const disabledTabTitle = notAuthed
    ? "Not authenticated to Google — sign in to enable email and calendar features"
    : "Add Google OAuth credentials in Settings to enable";

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">Gyver</h1>
            {profile ? (
              <p className="text-xs text-slate-500">{profile.email}</p>
            ) : notAuthed ? (
              <p className="text-xs text-amber-700">Not signed in to Google</p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {notAuthed && (
              <button
                onClick={onSignIn}
                className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
              >
                Sign in with Google
              </button>
            )}
            {profile && (
              profile.picture ? (
                <img
                  src={profile.picture}
                  alt=""
                  className="w-8 h-8 rounded-full"
                  referrerPolicy="no-referrer"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : null
            )}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 text-slate-600 hover:text-slate-900"
              title="Settings"
            >
              <Settings size={18} />
            </button>
            {profile && (
              <button
                onClick={handleLogout}
                className="p-2 text-slate-600 hover:text-slate-900"
                title="Logout"
              >
                <LogOut size={18} />
              </button>
            )}
          </div>
        </div>
        {/* Tabs */}
        <div className="max-w-5xl mx-auto px-6">
          <nav className="flex gap-6 -mb-px">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => !t.disabled && setTab(t.key)}
                disabled={t.disabled}
                className={`pb-3 text-sm font-medium border-b-2 ${
                  t.disabled
                    ? "border-transparent text-slate-300 cursor-not-allowed"
                    : tab === t.key
                    ? "border-indigo-600 text-indigo-600"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
                title={t.disabled ? disabledTabTitle : undefined}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className={`mx-auto px-6 py-8 ${tab === "planner" || tab === "agents" ? "max-w-full" : "max-w-5xl"}`}>
        {notAuthed && (
          <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800 flex items-start gap-2">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            <span>
              You are not authenticated to Google, so email and calendar features
              (Summary, Reports, Scheduled Jobs, Analytics) are disabled. Planner,
              Notes, Links, and Apps work normally.
            </span>
            <button
              onClick={onSignIn}
              className="ml-auto shrink-0 underline font-medium hover:text-amber-900"
            >
              Sign in
            </button>
          </div>
        )}
        {!googleConfigured && tab === "planner" && (
          <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
            Google OAuth is not configured. Only the Planner is available.{" "}
            <button
              onClick={() => setShowSettings(true)}
              className="underline font-medium hover:text-amber-900"
            >
              Open Settings
            </button>{" "}
            to add your Google credentials and enable email/calendar summaries.
          </div>
        )}
        {tab === "summary" && <SummaryPanel defaultMode={defaultSummaryMode} />}
        {tab === "planner" && <PlannerPanel settingsRev={settingsRev} />}
        {tab === "notes" && <NotesPanel />}
        {tab === "links" && <LinksPanel />}
        {tab === "apps" && <AppsPanel />}
        {tab === "agents" && <AgentsPanel />}
        {tab === "reports" && <ReportsPanel />}
        {tab === "schedule" && <SchedulePanel />}
        {tab === "analytics" && <AnalyticsPanel />}
      </main>

      {showSettings && (
        <SettingsModal
          onClose={() => {
            setShowSettings(false);
            setSettingsRev((r) => r + 1);
            onSettingsChanged();
          }}
        />
      )}
    </div>
  );
}
