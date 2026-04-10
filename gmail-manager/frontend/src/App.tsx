import { useEffect, useState } from "react";
import type { AnalysisResult, UserProfile } from "./types";
import {
  getConfigStatus,
  getMe,
  getSessionToken,
  logout,
  setSessionToken,
} from "./services/api";
import LoginPage from "./components/LoginPage";
import Dashboard from "./components/Dashboard";
import SettingsModal from "./components/SettingsModal";

type AppState = "loading" | "setup" | "login" | "app";

export default function App() {
  const [state, setState] = useState<AppState>("loading");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  // Handle OAuth redirect — extract session_token or error from URL params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("session_token");
    const error = params.get("error");
    const detail = params.get("detail");
    if (token) {
      setSessionToken(token);
      window.history.replaceState({}, "", "/");
    } else if (error) {
      setAuthError(detail ? `Auth failed: ${detail}` : "Authentication failed. Check the backend logs.");
      window.history.replaceState({}, "", "/");
    }
  }, []);

  useEffect(() => {
    (async () => {
      // 1. Check whether credentials are configured
      let configured = false;
      try {
        const status = await getConfigStatus();
        configured = status.configured;
      } catch {
        // Backend unreachable — still show setup
      }

      if (!configured) {
        setState("setup");
        return;
      }

      // 2. Try to restore an existing session
      const token = getSessionToken();
      if (!token) {
        setState("login");
        return;
      }

      try {
        const profile = await getMe();
        setUser(profile);
        setState("app");
      } catch {
        setState("login");
      }
    })();
  }, []);

  // Periodically refresh the user profile so total_messages and storage_used
  // update live as the agent deletes things.
  useEffect(() => {
    if (state !== "app") return;
    const t = setInterval(async () => {
      try {
        const profile = await getMe();
        setUser(profile);
      } catch {
        // ignore transient errors
      }
    }, 15000);
    return () => clearInterval(t);
  }, [state]);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setAnalysis(null);
    setState("login");
  };

  const handleSetupSaved = (configured: boolean) => {
    if (configured) {
      setState("login");
      setShowSettings(false);
    }
  };

  if (state === "loading") {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (state === "setup") {
    return <SettingsModal onSaved={handleSetupSaved} />;
  }

  return (
    <>
      {state === "login" && (
        <LoginPage
          onOpenSettings={() => setShowSettings(true)}
          authError={authError}
        />
      )}

      {state === "app" && user && (
        <Dashboard
          user={user}
          analysis={analysis}
          onAnalysisComplete={setAnalysis}
          onLogout={handleLogout}
          onOpenSettings={() => setShowSettings(true)}
        />
      )}

      {showSettings && (
        <SettingsModal
          onClose={() => setShowSettings(false)}
          onSaved={(configured) => {
            if (configured) setShowSettings(false);
          }}
        />
      )}
    </>
  );
}
