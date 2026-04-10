import { useState } from "react";
import { LogOut, Settings } from "lucide-react";
import type { UserProfile } from "../types";
import { clearSessionToken, logout } from "../services/api";
import SummaryPanel from "./SummaryPanel";
import SchedulePanel from "./SchedulePanel";
import SettingsModal from "./SettingsModal";

type Tab = "summary" | "schedule";

export default function Dashboard({ profile }: { profile: UserProfile }) {
  const [showSettings, setShowSettings] = useState(false);
  const [tab, setTab] = useState<Tab>("summary");

  const handleLogout = async () => {
    try {
      await logout();
    } catch {}
    clearSessionToken();
    window.location.reload();
  };

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">Calendar & Email Summary</h1>
            <p className="text-xs text-slate-500">{profile.email}</p>
          </div>
          <div className="flex items-center gap-2">
            {profile.picture && (
              <img src={profile.picture} alt="" className="w-8 h-8 rounded-full" />
            )}
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 text-slate-600 hover:text-slate-900"
              title="Settings"
            >
              <Settings size={18} />
            </button>
            <button
              onClick={handleLogout}
              className="p-2 text-slate-600 hover:text-slate-900"
              title="Logout"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
        {/* Tabs */}
        <div className="max-w-5xl mx-auto px-6">
          <nav className="flex gap-6 -mb-px">
            {([
              { key: "summary", label: "Summary" },
              { key: "schedule", label: "Scheduled Jobs" },
            ] as { key: Tab; label: string }[]).map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`pb-3 text-sm font-medium border-b-2 ${
                  tab === t.key
                    ? "border-indigo-600 text-indigo-600"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {tab === "summary" && <SummaryPanel />}
        {tab === "schedule" && <SchedulePanel />}
      </main>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  );
}
