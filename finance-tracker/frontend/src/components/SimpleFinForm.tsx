import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { api } from "../services/api";

interface Props {
  onClaimed: () => void;
}

/**
 * SimpleFIN Bridge uses a one-shot setup token (base64-encoded URL) that is
 * exchanged server-side for a long-lived access URL. The user pastes the
 * token here; the backend does the claim and stores the access URL.
 */
export function SimpleFinForm({ onClaimed }: Props) {
  const [token, setToken] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.claimSimpleFin(token.trim(), displayName || undefined);
      onClaimed();
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-slate-600">
        <a
          href="https://beta-bridge.simplefin.org/"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-indigo-600 hover:underline"
        >
          SimpleFIN Bridge <ExternalLink className="h-3 w-3" />
        </a>{" "}
        is a paid aggregator ($1.50/mo) that works with US and Canadian banks. Generate a
        setup token from your bridge account and paste it below — it'll be exchanged
        once for a long-lived access URL.
      </p>

      <Field label="Setup token" hint="Usually a long base64 string. Single-use.">
        <textarea
          required
          value={token}
          onChange={(e) => setToken(e.target.value)}
          rows={4}
          className="input font-mono text-xs"
          placeholder="aHR0cHM6Ly9icmlkZ2Uuc2ltcGxlZmluLm9yZy9zaW1wbGVmaW4vY2xhaW0v…"
          spellCheck={false}
        />
      </Field>

      <Field
        label="Display name"
        hint="Optional — how it'll appear in your accounts list. Defaults to “SimpleFIN”."
      >
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="input"
          placeholder="Chase via SimpleFIN"
        />
      </Field>

      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting || !token.trim()}
        className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {submitting ? "Claiming token…" : "Claim & link"}
      </button>
    </form>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-slate-700">{label}</div>
      {children}
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </label>
  );
}
