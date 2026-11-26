import { useEffect, useState } from "react";
import { ChevronUp, File, Folder, FolderOpen, X } from "lucide-react";
import { browseDirectory, type BrowseResult } from "../services/api";

interface Props {
  /** Starting path to browse from */
  initialPath?: string;
  /** "file" to select files, "directory" to select directories */
  mode: "file" | "directory";
  /** Called with the selected path */
  onSelect: (path: string) => void;
  onClose: () => void;
}

export default function FileBrowserModal({
  initialPath = "~",
  mode,
  onSelect,
  onClose,
}: Props) {
  const [data, setData] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pathInput, setPathInput] = useState(initialPath);
  const [showHidden, setShowHidden] = useState(false);

  useEffect(() => {
    navigate(initialPath);
  }, []);

  const navigate = async (path: string) => {
    setLoading(true);
    setError("");
    try {
      const result = await browseDirectory(path);
      setData(result);
      setPathInput(result.current);
    } catch (e: any) {
      setError(e.message || "Failed to browse directory");
    }
    setLoading(false);
  };

  const handleEntryClick = (entry: BrowseResult["entries"][0]) => {
    if (entry.is_dir) {
      navigate(entry.path);
    } else if (mode === "file") {
      onSelect(entry.path);
    }
  };

  const handleEntryDoubleClick = (entry: BrowseResult["entries"][0]) => {
    if (entry.is_dir && mode === "directory") {
      // Double-click on dir in directory mode selects it
      onSelect(entry.path);
    }
  };

  const handleSelectCurrent = () => {
    if (data) {
      onSelect(data.current);
    }
  };

  const handlePathSubmit = () => {
    navigate(pathInput);
  };

  const filteredEntries = data?.entries.filter((e) => {
    if (showHidden) return true;
    return !e.name.startsWith(".");
  }) ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-800">
            {mode === "file" ? "Select File" : "Select Folder"}
          </h3>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600"
          >
            <X size={18} />
          </button>
        </div>

        {/* Path bar */}
        <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
          <button
            onClick={() => data?.parent && navigate(data.parent)}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded transition-colors"
            title="Go to parent directory"
            disabled={!data || data.current === data.parent}
          >
            <ChevronUp size={16} />
          </button>
          <input
            type="text"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handlePathSubmit();
            }}
            className="flex-1 text-sm font-mono border border-slate-200 rounded-lg px-3 py-1.5 outline-none focus:border-indigo-400"
          />
          <button
            onClick={handlePathSubmit}
            className="px-3 py-1.5 text-xs font-medium bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
          >
            Go
          </button>
          <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer whitespace-nowrap">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => setShowHidden(e.target.checked)}
              className="rounded border-slate-300 text-indigo-600"
            />
            Hidden
          </label>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-y-auto px-2 py-2 min-h-[200px]">
          {loading && (
            <p className="text-sm text-slate-400 text-center py-8">Loading...</p>
          )}
          {error && (
            <p className="text-sm text-red-500 text-center py-8">{error}</p>
          )}
          {!loading && !error && filteredEntries.length === 0 && (
            <p className="text-sm text-slate-400 text-center py-8">Empty directory</p>
          )}
          {!loading &&
            !error &&
            filteredEntries.map((entry) => (
              <button
                key={entry.path}
                onClick={() => handleEntryClick(entry)}
                onDoubleClick={() => handleEntryDoubleClick(entry)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-slate-50 transition-colors ${
                  !entry.is_dir && mode === "directory"
                    ? "opacity-40 cursor-default"
                    : "cursor-pointer"
                }`}
                disabled={!entry.is_dir && mode === "directory"}
              >
                {entry.is_dir ? (
                  <Folder size={16} className="text-amber-500 flex-shrink-0" />
                ) : (
                  <File size={16} className="text-slate-400 flex-shrink-0" />
                )}
                <span className="text-sm text-slate-700 truncate">{entry.name}</span>
              </button>
            ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-200 flex items-center justify-between">
          <span className="text-[11px] text-slate-400 truncate max-w-[60%]" title={data?.current}>
            {data?.current}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
            {mode === "directory" && (
              <button
                onClick={handleSelectCurrent}
                className="px-4 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Select This Folder
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
