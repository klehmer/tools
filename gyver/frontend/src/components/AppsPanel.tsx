import { useEffect, useRef, useState } from "react";
import {
  ExternalLink,
  FolderOpen,
  Pencil,
  Play,
  Plus,
  Square,
  Terminal,
  Trash2,
} from "lucide-react";
import type { AppConfig } from "../types";
import {
  getApps,
  createApp,
  updateApp,
  startApp,
  stopApp,
  deleteApp,
} from "../services/api";
import FileBrowserModal from "./FileBrowserModal";

export default function AppsPanel() {
  const [apps, setApps] = useState<AppConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    start_script: "",
    stop_script: "",
    url: "",
    working_dir: "",
  });
  const [browseTarget, setBrowseTarget] = useState<{
    field: "start_script" | "stop_script" | "working_dir";
    mode: "file" | "directory";
  } | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchApps();
    // Poll running status every 5 seconds
    pollRef.current = setInterval(fetchApps, 5000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (adding && nameRef.current) nameRef.current.focus();
  }, [adding]);

  const fetchApps = async () => {
    try {
      const data = await getApps();
      setApps(data);
    } catch {
      // keep existing state on poll failures
    }
    setLoading(false);
  };

  const resetForm = () =>
    setForm({ name: "", start_script: "", stop_script: "", url: "", working_dir: "" });

  const handleCreate = async () => {
    if (!form.name.trim() || !form.start_script.trim()) return;
    const app = await createApp({
      name: form.name.trim(),
      start_script: form.start_script.trim(),
      stop_script: form.stop_script.trim(),
      url: form.url.trim(),
      working_dir: form.working_dir.trim(),
    });
    setApps((prev) => [...prev, app]);
    resetForm();
    setAdding(false);
  };

  const handleSave = async (app: AppConfig) => {
    const updated = await updateApp(app.id, {
      name: form.name.trim() || app.name,
      start_script: form.start_script.trim() || app.start_script,
      stop_script: form.stop_script.trim(),
      url: form.url.trim(),
      working_dir: form.working_dir.trim(),
    });
    setApps((prev) => prev.map((a) => (a.id === app.id ? updated : a)));
    setEditingId(null);
    resetForm();
  };

  const handleStart = async (id: string) => {
    try {
      const updated = await startApp(id);
      setApps((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch {}
  };

  const handleStop = async (id: string) => {
    try {
      const updated = await stopApp(id);
      setApps((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch {}
  };

  const handleDelete = async (id: string) => {
    await deleteApp(id);
    setApps((prev) => prev.filter((a) => a.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const openEdit = (app: AppConfig) => {
    setEditingId(app.id);
    setForm({
      name: app.name,
      start_script: app.start_script,
      stop_script: app.stop_script,
      url: app.url,
      working_dir: app.working_dir,
    });
  };

  if (loading) return <p className="text-slate-500">Loading...</p>;

  const browseButton = (
    field: "start_script" | "stop_script" | "working_dir",
    mode: "file" | "directory",
  ) => (
    <button
      type="button"
      onClick={() => setBrowseTarget({ field, mode })}
      className="px-2.5 py-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-slate-200 border-l-0 rounded-r-lg transition-colors"
      title={mode === "file" ? "Browse for file..." : "Browse for folder..."}
    >
      <FolderOpen size={16} />
    </button>
  );

  const formFields = (
    <div className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Name *</label>
        <input
          ref={adding ? nameRef : undefined}
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="My App"
          className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Start Script *</label>
        <div className="flex">
          <input
            type="text"
            value={form.start_script}
            onChange={(e) => setForm({ ...form, start_script: e.target.value })}
            placeholder="/path/to/start.sh or 'npm run dev'"
            className="flex-1 text-sm font-mono border border-slate-200 rounded-l-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          />
          {browseButton("start_script", "file")}
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Stop Script (optional)</label>
        <div className="flex">
          <input
            type="text"
            value={form.stop_script}
            onChange={(e) => setForm({ ...form, stop_script: e.target.value })}
            placeholder="Leave empty to kill process on stop"
            className="flex-1 text-sm font-mono border border-slate-200 rounded-l-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          />
          {browseButton("stop_script", "file")}
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">URL (optional)</label>
        <input
          type="text"
          value={form.url}
          onChange={(e) => setForm({ ...form, url: e.target.value })}
          placeholder="http://localhost:5173"
          className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1">Working Directory (optional)</label>
        <div className="flex">
          <input
            type="text"
            value={form.working_dir}
            onChange={(e) => setForm({ ...form, working_dir: e.target.value })}
            placeholder="/path/to/app"
            className="flex-1 text-sm font-mono border border-slate-200 rounded-l-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          />
          {browseButton("working_dir", "directory")}
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-800">Apps</h2>
        <button
          onClick={() => { setAdding(true); resetForm(); }}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus size={16} />
          Add App
        </button>
      </div>

      {/* Add form */}
      {adding && (
        <div className="bg-white border-2 border-indigo-300 rounded-xl p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Configure New App</h3>
          {formFields}
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={handleCreate}
              disabled={!form.name.trim() || !form.start_script.trim()}
              className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Add App
            </button>
            <button
              onClick={() => { setAdding(false); resetForm(); }}
              className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {apps.length === 0 && !adding && (
        <div className="text-center py-12 text-slate-400">
          <Terminal size={40} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No apps configured. Add one to get started.</p>
        </div>
      )}

      {/* App cards */}
      <div className="space-y-3">
        {apps.map((app) => {
          const isEditing = editingId === app.id;

          if (isEditing) {
            return (
              <div
                key={app.id}
                className="bg-white border-2 border-indigo-300 rounded-xl p-5 shadow-sm"
              >
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Edit App</h3>
                {formFields}
                <div className="flex items-center gap-2 mt-4">
                  <button
                    onClick={() => handleSave(app)}
                    className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => { setEditingId(null); resetForm(); }}
                    className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            );
          }

          return (
            <div
              key={app.id}
              className="group bg-white border border-slate-200 rounded-xl px-5 py-4 hover:border-slate-300 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {/* Status indicator */}
                  <div
                    className={`w-3 h-3 rounded-full flex-shrink-0 ${
                      app.running
                        ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]"
                        : "bg-slate-300"
                    }`}
                    title={app.running ? "Running" : "Stopped"}
                  />
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">{app.name}</h3>
                    <p className="text-[11px] text-slate-400 font-mono truncate max-w-sm">
                      {app.start_script}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  {/* Start / Stop */}
                  {app.running ? (
                    <button
                      onClick={() => handleStop(app.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100 transition-colors"
                      title="Stop"
                    >
                      <Square size={12} />
                      Stop
                    </button>
                  ) : (
                    <button
                      onClick={() => handleStart(app.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors"
                      title="Start"
                    >
                      <Play size={12} />
                      Start
                    </button>
                  )}

                  {/* Open in browser */}
                  {app.url && (
                    <a
                      href={app.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
                      title="Open in browser"
                    >
                      <ExternalLink size={12} />
                      Open
                    </a>
                  )}

                  {/* Edit */}
                  <button
                    onClick={() => openEdit(app)}
                    className="p-1.5 text-slate-300 hover:text-indigo-600 transition-colors opacity-0 group-hover:opacity-100"
                    title="Edit"
                  >
                    <Pencil size={14} />
                  </button>

                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(app.id)}
                    className="p-1.5 text-slate-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Details row */}
              {(app.working_dir || app.url) && (
                <div className="mt-2 flex items-center gap-4 text-[11px] text-slate-400">
                  {app.working_dir && (
                    <span className="font-mono truncate" title={app.working_dir}>
                      {app.working_dir}
                    </span>
                  )}
                  {app.url && (
                    <span className="truncate">{app.url}</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* File browser modal */}
      {browseTarget && (
        <FileBrowserModal
          initialPath={form[browseTarget.field] || form.working_dir || "~"}
          mode={browseTarget.mode}
          onSelect={(path) => {
            setForm({ ...form, [browseTarget.field]: path });
            setBrowseTarget(null);
          }}
          onClose={() => setBrowseTarget(null)}
        />
      )}
    </div>
  );
}
