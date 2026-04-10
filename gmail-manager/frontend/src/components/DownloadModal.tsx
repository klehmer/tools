import { useState } from "react";
import { Download, X } from "lucide-react";
import type { EmailGroup } from "../types";
import { downloadBulk } from "../services/api";

interface Props {
  group: EmailGroup;
  onClose: () => void;
}

export default function DownloadModal({ group, onClose }: Props) {
  const [includeAttachments, setIncludeAttachments] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      await downloadBulk(group.email_ids, includeAttachments);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div className="flex items-center gap-2 font-semibold">
            <Download className="h-5 w-5 text-blue-600" />
            Download Emails
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6">
          <div className="mb-4 rounded-lg bg-gray-50 p-3 text-sm">
            <p className="font-medium text-gray-800">
              {group.sender_name || group.sender}
            </p>
            <p className="text-gray-500">
              {group.email_ids.length} emails · {group.total_size_mb.toFixed(1)} MB
            </p>
          </div>

          <p className="mb-4 text-sm text-gray-600">
            Emails will be downloaded as <strong>.eml</strong> files inside a{" "}
            <strong>ZIP archive</strong>. You can open them with any email
            client after downloading.
          </p>

          <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-200 p-3">
            <input
              type="checkbox"
              checked={includeAttachments}
              onChange={(e) => setIncludeAttachments(e.target.checked)}
              className="h-4 w-4 accent-blue-600"
            />
            <div>
              <p className="text-sm font-medium text-gray-800">
                Include attachments
              </p>
              <p className="text-xs text-gray-500">
                Saves attachment files in a separate folder inside the ZIP
              </p>
            </div>
          </label>

          {error && (
            <p className="mt-3 text-sm text-red-600">{error}</p>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {downloading ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Downloading…
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Download ZIP
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
