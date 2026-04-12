import { useState } from "react";
import { KeyRound, ExternalLink } from "lucide-react";
import { api, type PlaidConfigInput } from "../services/api";

interface Props {
  onConfigured: () => void;
  /** If the user is editing existing creds, prefill env. */
  currentEnv?: string;
  currentClientIdMasked?: string | null;
}

/**
 * Shown when Plaid credentials haven't been set yet (or when the user
 * explicitly wants to re-enter them). POSTs to /config which verifies the
 * creds by trying to create a link token and rolls back on failure, so a
 * successful submit means the creds actually work.
 */
export function SetupPanel({ onConfigured, currentEnv, currentClientIdMasked }: Props) {
  const [form, setForm] = useState<PlaidConfigInput>({
    client_id: "",
    secret: "",
    env: (currentEnv === "production" ? "production" : "sandbox") as PlaidConfigInput["env"],
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.saveConfig(form);
      onConfigured();
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div>
        <div className="mb-4 flex items-start gap-4">
          <div className="rounded-xl bg-indigo-50 p-3 text-indigo-600 ring-1 ring-indigo-200">
            <KeyRound className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm text-slate-600">
              Finance Tracker uses{" "}
              <a
                className="inline-flex items-center gap-1 text-indigo-600 hover:underline"
                href="https://plaid.com"
                target="_blank"
                rel="noreferrer"
              >
                Plaid <ExternalLink className="h-3 w-3" />
              </a>{" "}
              to link your financial accounts in read-only mode. Your credentials live on
              this machine only — they're written to{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">
                backend/data/plaid_config.json
              </code>{" "}
              with 0600 permissions.
            </p>
          </div>
        </div>

        <ol className="mb-6 space-y-1 text-sm text-slate-600">
          <li>
            <span className="font-semibold text-slate-800">1.</span> Sign up at{" "}
            <a
              className="text-indigo-600 hover:underline"
              href="https://dashboard.plaid.com/signup"
              target="_blank"
              rel="noreferrer"
            >
              dashboard.plaid.com/signup
            </a>{" "}
            — free sandbox account, no credit card.
          </li>
          <li>
            <span className="font-semibold text-slate-800">2.</span> Go to{" "}
            <em>Team Settings → Keys</em> and copy your <code>client_id</code> and the
            secret for your chosen environment.
          </li>
          <li>
            <span className="font-semibold text-slate-800">3.</span> Paste them below. In
            sandbox you can link fake institutions with username{" "}
            <code>user_good</code> / password <code>pass_good</code>.
          </li>
        </ol>

        {currentClientIdMasked && (
          <div className="mb-4 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
            Current credentials on file:{" "}
            <code className="font-mono">{currentClientIdMasked}</code>{" "}
            <span className="text-slate-400">· {currentEnv}</span>
          </div>
        )}

        <form onSubmit={submit} className="space-y-4">
          <Field label="Environment" hint="Start with sandbox. Production requires Plaid approval.">
            <div className="flex gap-2">
              {(["sandbox", "production"] as const).map((env) => (
                <button
                  type="button"
                  key={env}
                  onClick={() => setForm({ ...form, env })}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm font-medium capitalize transition ${
                    form.env === env
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                      : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {env}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Plaid client_id">
            <input
              required
              autoComplete="off"
              spellCheck={false}
              value={form.client_id}
              onChange={(e) => setForm({ ...form, client_id: e.target.value })}
              className="input font-mono"
              placeholder="5f9b4d1e2c3a4b6d7e8f9a0b"
            />
          </Field>

          <Field
            label={`Plaid ${form.env} secret`}
            hint="Each environment has its own secret — make sure it matches the one selected above."
          >
            <input
              required
              type="password"
              autoComplete="new-password"
              spellCheck={false}
              value={form.secret}
              onChange={(e) => setForm({ ...form, secret: e.target.value })}
              className="input font-mono"
              placeholder="••••••••••••••••••••••••••••••••"
            />
          </Field>

          {error && (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !form.client_id || !form.secret}
            className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {submitting ? "Verifying with Plaid…" : "Save & verify credentials"}
          </button>
        </form>
      </div>

      <p className="mt-4 text-center text-xs text-slate-500">
        Credentials are verified by attempting to create a Plaid link token. On failure the
        config file is rolled back.
      </p>
    </div>
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
