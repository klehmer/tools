import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { Link2 } from "lucide-react";
import { api } from "../services/api";

interface Props {
  onLinked: () => void;
  disabled?: boolean;
}

export function LinkAccountButton({ onLinked, disabled }: Props) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .createLinkToken()
      .then((r) => {
        if (!cancelled) setLinkToken(r.link_token);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSuccess = useCallback(
    async (public_token: string, metadata: any) => {
      setLoading(true);
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
        setLoading(false);
      }
    },
    [onLinked]
  );

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
  });

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        disabled={disabled || !ready || !linkToken || loading}
        onClick={() => open()}
        className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        <Link2 className="h-4 w-4" />
        {loading ? "Linking…" : "Link an account"}
      </button>
      {error && <span className="text-xs text-rose-600">{error}</span>}
    </div>
  );
}
