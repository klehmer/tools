import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { Link2 } from "lucide-react";
import { api } from "../services/api";

interface Props {
  onLinked: () => void;
  disabled?: boolean;
}

/**
 * Outer wrapper: fetches a Plaid link token first, then mounts the inner
 * component that actually calls `usePlaidLink`. This matters because
 * react-plaid-link@3 throws if it's initialised with a null/undefined token.
 */
export function LinkAccountButton({ onLinked, disabled }: Props) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (disabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .createLinkToken()
      .then((r) => {
        if (!cancelled) setLinkToken(r.link_token);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [disabled]);

  if (error) {
    return (
      <button
        type="button"
        disabled
        title={error}
        className="inline-flex items-center gap-2 rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-500"
      >
        <Link2 className="h-4 w-4" />
        Link unavailable
      </button>
    );
  }

  if (loading || disabled || !linkToken) {
    return (
      <button
        type="button"
        disabled
        className="inline-flex items-center gap-2 rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-500"
      >
        <Link2 className="h-4 w-4" />
        {disabled ? "Link an account" : "Preparing…"}
      </button>
    );
  }

  return <LinkInner token={linkToken} onLinked={onLinked} />;
}

function LinkInner({ token, onLinked }: { token: string; onLinked: () => void }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSuccess = useCallback(
    async (public_token: string, metadata: any) => {
      setSubmitting(true);
      try {
        await api.exchangePublicToken(
          public_token,
          metadata?.institution?.name,
          metadata?.institution?.institution_id
        );
        onLinked();
      } catch (e: any) {
        setError(e.message);
      } finally {
        setSubmitting(false);
      }
    },
    [onLinked]
  );

  const { open, ready } = usePlaidLink({ token, onSuccess });

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        disabled={!ready || submitting}
        onClick={() => open()}
        className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        <Link2 className="h-4 w-4" />
        {submitting ? "Linking…" : "Link an account"}
      </button>
      {error && <span className="max-w-xs text-right text-xs text-rose-600">{error}</span>}
    </div>
  );
}
