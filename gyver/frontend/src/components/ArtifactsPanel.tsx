import { useEffect, useState } from "react";
import { ExternalLink, FileText } from "lucide-react";
import type { ArtifactList } from "../types";
import { getArtifacts } from "../services/api";

const GALLERY_URL = "https://claude.ai/code/artifacts";

function formatDate(iso: string): string {
  // Date-only strings parse as UTC; pin to local noon so the day doesn't shift
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function ArtifactsPanel() {
  const [data, setData] = useState<ArtifactList | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getArtifacts()
      .then(setData)
      .catch((e) => setError((e as Error).message));
  }, []);

  if (error) return <p className="text-sm text-red-600">Could not load artifacts: {error}</p>;
  if (!data) return <p className="text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-800">Claude Artifacts</h2>
        <a
          href={GALLERY_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <ExternalLink size={16} />
          Open gallery
        </a>
      </div>

      {/* The list can only be fetched from a Claude Code session, so it is a saved copy */}
      <p className="text-xs text-slate-500">
        {data.refreshed_at ? `Saved list, last refreshed ${formatDate(data.refreshed_at)}. ` : "No list saved yet. "}
        To update it, ask a Claude Code session to refresh the Gyver artifacts list. Artifacts shared from
        another organization are not included; the gallery has everything.
      </p>

      {data.artifacts.length === 0 && (
        <div className="text-center py-12 text-slate-400">
          <FileText size={40} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No artifacts in the saved list.</p>
        </div>
      )}

      <div className="space-y-2">
        {data.artifacts.map((a) => (
          <div
            key={a.url}
            className="flex items-center gap-3 bg-white border border-slate-200 rounded-xl px-4 py-3 hover:border-slate-300 transition-colors"
          >
            <FileText size={16} className="flex-shrink-0 text-slate-400" />
            <div className="flex-1 min-w-0">
              <a
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:underline break-words"
              >
                {a.title}
              </a>
              <p className="text-xs text-slate-400">
                {a.updated ? `Updated ${formatDate(a.updated)}` : "Update date not available"}
              </p>
            </div>
            <span
              className={`shrink-0 px-2 py-0.5 text-[11px] font-medium rounded-full ${
                a.owner === "mine" ? "bg-indigo-50 text-indigo-700" : "bg-amber-50 text-amber-700"
              }`}
            >
              {a.owner === "mine" ? "Mine" : "Shared with me"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
