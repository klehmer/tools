import { useEffect, useState } from "react";
import { Eye, EyeOff, Save, Settings, X } from "lucide-react";
import type { AppConfig } from "../types";
import { getConfig, saveConfig } from "../services/api";

interface Props {
  /** When undefined the component renders as a full-page setup screen */
  onClose?: () => void;
  /** Called after a successful save so the parent can react */
  onSaved?: (configured: boolean) => void;
}

interface FieldState {
  value: string;
  /** True when the backend has a value already set (used for secrets) */
  isSet: boolean;
  /** True when the user has typed a new value into the field */
  dirty: boolean;
}

type Fields = Record<keyof AppConfig, FieldState>;

const FIELD_META: {
  key: keyof AppConfig;
  label: string;
  secret: boolean;
  placeholder: string;
  hint?: string;
}[] = [
  {
    key: "GOOGLE_CLIENT_ID",
    label: "Google OAuth Client ID",
    secret: false,
    placeholder: "xxxxxxxxxx.apps.googleusercontent.com",
    hint: "From Google Cloud Console → APIs & Services → Credentials",
  },
  {
    key: "GOOGLE_CLIENT_SECRET",
    label: "Google OAuth Client Secret",
    secret: true,
    placeholder: "GOCSPX-…",
  },
  {
    key: "ANTHROPIC_API_KEY",
    label: "Anthropic API Key",
    secret: true,
    placeholder: "sk-ant-…",
    hint: "From console.anthropic.com",
  },
  {
    key: "BACKEND_URL",
    label: "Backend URL",
    secret: false,
    placeholder: "http://localhost:8000",
  },
  {
    key: "FRONTEND_URL",
    label: "Frontend URL",
    secret: false,
    placeholder: "http://localhost:5173",
  },
];

const SECTIONS = [
  {
    title: "Google OAuth",
    keys: ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"] as (keyof AppConfig)[],
    description:
      "Create an OAuth 2.0 Web client in Google Cloud Console and add http://localhost:8000/auth/callback as an authorised redirect URI.",
  },
  {
    title: "AI / Anthropic",
    keys: ["ANTHROPIC_API_KEY"] as (keyof AppConfig)[],
    description: "Required for the inbox analysis agent.",
  },
  {
    title: "Server URLs",
    keys: ["BACKEND_URL", "FRONTEND_URL"] as (keyof AppConfig)[],
    description: "Change only if running on non-default ports.",
  },
];

function emptyFields(): Fields {
  return Object.fromEntries(
    FIELD_META.map(({ key }) => [
      key,
      { value: "", isSet: false, dirty: false },
    ])
  ) as Fields;
}

export default function SettingsModal({ onClose, onSaved }: Props) {
  const [fields, setFields] = useState<Fields>(emptyFields());
  const [reveal, setReveal] = useState<Set<keyof AppConfig>>(new Set());
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getConfig()
      .then((cfg) => {
        setFields(
          Object.fromEntries(
            FIELD_META.map(({ key }) => [
              key,
              {
                value: cfg[key].value,
                isSet: cfg[key].is_set,
                dirty: false,
              },
            ])
          ) as Fields
        );
      })
      .catch(() => setLoadError("Could not load current configuration."));
  }, []);

  const handleChange = (key: keyof AppConfig, value: string) => {
    setFields((prev) => ({
      ...prev,
      [key]: { ...prev[key], value, dirty: true },
    }));
    setSaved(false);
  };

  const toggleReveal = (key: keyof AppConfig) => {
    setReveal((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const payload: Record<string, string> = {};
      for (const { key, secret } of FIELD_META) {
        const f = fields[key];
        if (secret) {
          // Only send if the user actually typed something
          if (f.dirty && f.value) payload[key] = f.value;
        } else {
          if (f.value) payload[key] = f.value;
        }
      }
      const result = await saveConfig(payload);
      setSaved(true);
      onSaved?.(result.configured);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const isModal = onClose !== undefined;

  const content = (
    <div
      className={
        isModal
          ? "w-full max-w-2xl rounded-2xl bg-white shadow-2xl"
          : "mx-auto w-full max-w-2xl"
      }
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-2 font-semibold text-gray-900">
          <Settings className="h-5 w-5 text-blue-600" />
          {isModal ? "Settings" : "Setup — Gmail Manager"}
        </div>
        {isModal && onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Body */}
      <div className="max-h-[70vh] overflow-y-auto px-6 py-4">
        {!isModal && (
          <p className="mb-6 text-sm text-gray-500">
            Fill in the credentials below to get started. Values are stored in{" "}
            <code className="rounded bg-gray-100 px-1 py-0.5 text-xs">
              backend/.env
            </code>
            .
          </p>
        )}

        {loadError && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {loadError}
          </div>
        )}

        <div className="space-y-6">
          {SECTIONS.map((section) => (
            <section key={section.title}>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
                {section.title}
              </h3>
              <p className="mb-3 text-xs text-gray-400">{section.description}</p>
              <div className="space-y-3">
                {section.keys.map((key) => {
                  const meta = FIELD_META.find((m) => m.key === key)!;
                  const f = fields[key];
                  const isRevealed = reveal.has(key);
                  const showSet = meta.secret && f.isSet && !f.dirty;

                  return (
                    <div key={key}>
                      <label className="mb-1 block text-sm font-medium text-gray-700">
                        {meta.label}
                        {["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ANTHROPIC_API_KEY"].includes(
                          key
                        ) && (
                          <span className="ml-1 text-red-500">*</span>
                        )}
                      </label>
                      <div className="relative">
                        <input
                          type={
                            meta.secret && !isRevealed ? "password" : "text"
                          }
                          value={showSet ? "" : f.value}
                          onChange={(e) => handleChange(key, e.target.value)}
                          placeholder={
                            showSet ? "••••••••  (already set)" : meta.placeholder
                          }
                          className={`w-full rounded-lg border px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-blue-500 ${
                            showSet
                              ? "border-green-200 bg-green-50 placeholder-green-600"
                              : "border-gray-300 bg-white"
                          } ${meta.secret ? "pr-10" : ""}`}
                        />
                        {meta.secret && (
                          <button
                            type="button"
                            onClick={() => toggleReveal(key)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                            tabIndex={-1}
                          >
                            {isRevealed ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        )}
                      </div>
                      {meta.hint && (
                        <p className="mt-1 text-xs text-gray-400">{meta.hint}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t px-6 py-4">
        <div className="text-sm">
          {saved && (
            <span className="text-green-600">✓ Configuration saved</span>
          )}
          {saveError && <span className="text-red-600">{saveError}</span>}
          {!saved && !saveError && (
            <span className="text-xs text-gray-400">
              * Required fields
            </span>
          )}
        </div>
        <div className="flex gap-3">
          {isModal && onClose && (
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Saving…
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                Save
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  if (isModal) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        {content}
      </div>
    );
  }

  // Full-page setup screen
  return (
    <div className="flex min-h-screen items-start justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-6 pt-12">
      {content}
    </div>
  );
}
