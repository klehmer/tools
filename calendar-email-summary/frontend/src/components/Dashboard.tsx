import { useState } from "react";
import { LogOut, Settings } from "lucide-react";
import type { UserProfile } from "../types";
import { clearSessionToken, logout } from "../services/api";
import SummaryPanel from "./SummaryPanel";
import SchedulePanel from "./SchedulePanel";
import PlannerPanel from "./PlannerPanel";
import SettingsModal from "./SettingsModal";

type Tab = "summary" | "planner" | "schedule";

interface Props {
  profile: UserProfile | null;
  googleConfigured: boolean;
  onSettingsChanged: () => void;
}

export default function Dashboard({ profile, googleConfigured, onSettingsChanged }: Props) {
  const [showSettings, setShowSettings] = useState(false);
  const [tab, setTab] = useState<Tab>(googleConfigured ? "summary" : "planner");
  const [settingsRev, setSettingsRev] = useState(0);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {}
    clearSessionToken();
    window.location.reload();
  };

  const tabs: { key: Tab; label: string; disabled: boolean }[] = [
    { key: "summary", label: "Summary", disabled: !googleConfigured },
    { key: "planner", label: "Planner", disabled: false },
    { key: "schedule", label: "Scheduled Jobs", disabled: !googleConfigured },
  ];

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">Calendar & Email Summary</h1>
            {profile && <p className="text-xs text-slate-500">{profile.email}</p>}
          </div>
          <div className="flex items-center gap-2">
            {profile?.picture && (
              <img src={profile.picture} alt="" className="w-8 h-8 rounded-full" />
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
                title={t.disabled ? "Add Google OAuth credentials in Settings to enable" : undefined}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className={`mx-auto px-6 py-8 ${tab === "planner" ? "max-w-full" : "max-w-5xl"}`}>
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
        {tab === "summary" && <SummaryPanel />}
        {tab === "planner" && <PlannerPanel settingsRev={settingsRev} />}
        {tab === "schedule" && <SchedulePanel />}
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
