import { useEffect, useState } from "react";
import LoginPage from "./components/LoginPage";
import Dashboard from "./components/Dashboard";
import SettingsModal from "./components/SettingsModal";
import {
  clearSessionToken,
  getConfig,
  getConfigStatus,
  getMe,
  getSessionToken,
  setSessionToken,
} from "./services/api";
import type { UserProfile } from "./types";

type State = "loading" | "setup" | "login" | "app";

export default function App() {
  const [state, setState] = useState<State>("loading");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [googleConfigured, setGoogleConfigured] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("session_token");
    const error = params.get("error");
    const detail = params.get("detail");
    if (token) {
      setSessionToken(token);
      window.history.replaceState({}, "", "/");
    } else if (error) {
      setAuthError(`Auth failed: ${detail ?? error}`);
      window.history.replaceState({}, "", "/");
    }
    bootstrap();
  }, []);

  const bootstrap = async () => {
    try {
      const status = await getConfigStatus();
      if (!status.configured) {
        setState("setup");
        return;
      }
      setGoogleConfigured(status.google_configured);

      // Sync DEFAULT_TAB to localStorage
      getConfig().then((cfg) => {
        const tab = cfg.DEFAULT_TAB?.value;
        if (tab) localStorage.setItem("daybrief_default_tab", tab);
      }).catch(() => {});

      // If Google isn't configured, skip login and go straight to dashboard
      // (only planner will be available)
      if (!status.google_configured) {
        setState("app");
        return;
      }

      if (!getSessionToken()) {
        setState("login");
        return;
      }
      try {
        const p = await getMe();
        setProfile(p);
        setState("app");
      } catch {
        clearSessionToken();
        setState("login");
      }
    } catch (e) {
      setState("setup");
    }
  };

  if (state === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500">
        Loading...
      </div>
    );
  }

  if (state === "setup") {
    return <SettingsModal onClose={bootstrap} />;
  }

  if (state === "login") {
    return <LoginPage error={authError} />;
  }

  return <Dashboard profile={profile} googleConfigured={googleConfigured} onSettingsChanged={bootstrap} />;
}
