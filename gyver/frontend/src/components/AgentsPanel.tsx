import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { AlertTriangle, Bot, ChevronDown, ChevronRight, FolderOpen, Info, Pencil, Play, Plus, Square, Trash2, X } from "lucide-react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import type { AgentDef, AgentRun, AgentRuntime, AgentRuntimes } from "../types";
import {
  agentRunSocketUrl,
  createAgent,
  deleteAgent,
  getAgentModels,
  getAgentRuns,
  getAgentRuntimes,
  getAgents,
  reorderAgents,
  killAgentRun,
  launchAgent,
  removeAgentRun,
  updateAgent,
} from "../services/api";
import FileBrowserModal from "./FileBrowserModal";

// Sentinel <option> value that switches the model field to free text
const CUSTOM_MODEL = "__custom__";

const emptyForm = {
  name: "",
  runtime: "claude" as AgentRuntime,
  model: "",
  prompt: "",
  working_dir: "",
  command: "",
};

const inputCls =
  "w-full text-sm border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200";
const labelCls = "block text-xs font-medium text-slate-500 mb-1";

const COLLAPSED_KEY = "gyver_agents_collapsed";

// Only web links: agent output is untrusted, so never open file:, javascript: etc.
function openLink(uri: string) {
  if (/^https?:\/\//i.test(uri)) window.open(uri, "_blank", "noopener,noreferrer");
}

/** One live terminal attached to a run. Stays mounted while hidden so its screen survives tab switches. */
function AgentTerminal({ runId, active }: { runId: string; active: boolean }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);

  const fit = () => {
    // Fitting a hidden terminal would collapse it to a few columns
    if (!hostRef.current?.offsetParent) return;
    try {
      fitRef.current?.fit();
    } catch {}
  };

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const term = new Terminal({
      fontSize: 13,
      fontFamily: "Menlo, Monaco, 'Courier New', monospace",
      cursorBlink: true,
      scrollback: 5000,
      theme: { background: "#0f172a" },
      // Links the agent emits as terminal hyperlinks (OSC 8): open directly, no confirm prompt
      linkHandler: { activate: (_e, uri) => openLink(uri) },
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    // Plain URLs printed in the output
    term.loadAddon(new WebLinksAddon((_e, uri) => openLink(uri)));
    term.open(host);
    termRef.current = term;
    fitRef.current = fitAddon;

    const ws = new WebSocket(agentRunSocketUrl(runId));
    ws.binaryType = "arraybuffer";
    const send = (msg: object) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
    };
    const sendSize = () => send({ type: "resize", cols: term.cols, rows: term.rows });

    ws.onopen = () => {
      fit();
      sendSize();
    };
    ws.onmessage = (e) => {
      if (typeof e.data === "string") {
        const msg = JSON.parse(e.data);
        if (msg.type === "exit") {
          term.write(`\r\n\x1b[90m[agent exited with code ${msg.code}]\x1b[0m\r\n`);
        }
      } else {
        term.write(new Uint8Array(e.data));
      }
    };
    const onData = term.onData((data) => send({ type: "input", data }));
    const onResize = term.onResize(sendSize);
    const observer = new ResizeObserver(fit);
    observer.observe(host);

    return () => {
      observer.disconnect();
      onData.dispose();
      onResize.dispose();
      ws.close();
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, [runId]);

  useEffect(() => {
    if (active) {
      fit();
      termRef.current?.focus();
    }
  }, [active]);

  return (
    <div
      ref={hostRef}
      className="h-full w-full"
      style={{ display: active ? "block" : "none" }}
    />
  );
}

/** Safety check before a destructive action. Cancel is the default; clicking outside cancels too. */
function ConfirmDialog({
  title,
  confirmLabel,
  onConfirm,
  onCancel,
  children,
}: {
  title: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  children: ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-50 text-red-600 rounded-full shrink-0">
            <AlertTriangle size={18} />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-bold text-slate-800">{title}</h2>
            <div className="mt-1 text-sm text-slate-600">{children}</div>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button
            autoFocus
            onClick={onCancel}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AgentsPanel() {
  const [agents, setAgents] = useState<AgentDef[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [runtimes, setRuntimes] = useState<AgentRuntimes | null>(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [browsing, setBrowsing] = useState(false);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<Record<string, string[]>>({});
  const [customModel, setCustomModel] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<AgentDef | null>(null);
  const [confirmKillAll, setConfirmKillAll] = useState(false);
  const [commandExpanded, setCommandExpanded] = useState(false);
  const [dragId, setDragId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const toggleCollapsed = (value: boolean) => {
    setCollapsed(value);
    // Adding/editing happens in the list, so drop any open form when hiding it
    if (value) closeForm();
    try {
      localStorage.setItem(COLLAPSED_KEY, value ? "1" : "0");
    } catch {}
  };
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([getAgents(), getAgentRuntimes()])
      .then(([a, r]) => {
        setAgents(a);
        setRuntimes(r);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    fetchRuns();
    // Poll so the running list reflects agents that exit on their own
    const poll = setInterval(fetchRuns, 2000);
    return () => clearInterval(poll);
  }, []);

  useEffect(() => {
    if (adding && nameRef.current) nameRef.current.focus();
  }, [adding]);

  // Load the model list for whichever runtime the form is showing
  const formOpen = adding || editingId !== null;
  useEffect(() => {
    if (!formOpen || models[form.runtime]) return;
    const runtime = form.runtime;
    getAgentModels(runtime)
      .then((list) => setModels((prev) => ({ ...prev, [runtime]: list })))
      .catch(() => setModels((prev) => ({ ...prev, [runtime]: [] })));
  }, [formOpen, form.runtime]);

  // Keep a valid selection as runs come and go
  useEffect(() => {
    if (runs.length === 0) {
      if (selectedRun) setSelectedRun(null);
    } else if (!runs.some((r) => r.id === selectedRun)) {
      setSelectedRun(runs[runs.length - 1].id);
    }
  }, [runs, selectedRun]);

  const fetchRuns = async () => {
    try {
      setRuns(await getAgentRuns());
    } catch {
      // keep existing state on poll failures
    }
  };

  const closeForm = () => {
    setAdding(false);
    setEditingId(null);
    setForm(emptyForm);
    setCustomModel(false);
  };

  const formPayload = () => ({
    name: form.name.trim(),
    runtime: form.runtime,
    model: form.model.trim(),
    prompt: form.prompt.trim(),
    working_dir: form.working_dir.trim(),
    command: form.command.trim(),
  });

  const formValid = !!form.name.trim() && (form.runtime !== "custom" || !!form.command.trim());

  const handleSave = async () => {
    if (!formValid) return;
    setError(null);
    try {
      if (editingId) {
        const updated = await updateAgent(editingId, formPayload());
        setAgents((prev) => prev.map((a) => (a.id === editingId ? updated : a)));
      } else {
        const created = await createAgent(formPayload());
        setAgents((prev) => [...prev, created]);
      }
      closeForm();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const openEdit = (agent: AgentDef) => {
    setAdding(false);
    setCustomModel(false);
    setEditingId(agent.id);
    setForm({
      name: agent.name,
      runtime: agent.runtime,
      model: agent.model,
      prompt: agent.prompt,
      working_dir: agent.working_dir,
      command: agent.command,
    });
  };

  const handleDelete = async (id: string) => {
    setConfirmDelete(null);
    setError(null);
    try {
      await deleteAgent(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
      if (editingId === id) closeForm();
    } catch (e) {
      setError(`Could not delete: ${(e as Error).message}`);
    }
  };

  const handleLaunch = async (id: string) => {
    setError(null);
    try {
      const run = await launchAgent(id);
      setRuns((prev) => [...prev, run]);
      setSelectedRun(run.id);
    } catch (e) {
      setError(`Could not launch: ${(e as Error).message}`);
    }
  };

  const handleKill = async (runId: string) => {
    try {
      const updated = await killAgentRun(runId);
      setRuns((prev) => prev.map((r) => (r.id === runId ? updated : r)));
    } catch {}
  };

  const handleKillAll = async () => {
    setConfirmKillAll(false);
    // Kill whatever is running right now, not what was running when the dialog opened
    await Promise.all(runs.filter((r) => r.running).map((r) => handleKill(r.id)));
    fetchRuns();
  };

  const handleRemove = async (runId: string) => {
    try {
      await removeAgentRun(runId);
    } catch {}
    setRuns((prev) => prev.filter((r) => r.id !== runId));
  };

  if (loading) return <p className="text-slate-500">Loading...</p>;

  const runtimeLabel = (rt: string) => runtimes?.[rt as AgentRuntime]?.label ?? rt;
  const modelOptions = models[form.runtime];
  // Free-text mode: chosen explicitly, or a saved model the harness no longer lists
  const showCustomModel =
    customModel || (!!form.model && !!modelOptions && !modelOptions.includes(form.model));
  const defaultCommand = runtimes?.[form.runtime]?.command ?? "";
  // ---- Drag to reorder ----
  const onDragStart = (e: DragEvent, id: string) => {
    setDragId(id);
    e.dataTransfer.effectAllowed = "move";
  };

  // Reorder live as the dragged card passes over the others; saved on drag end
  const onDragOverAgent = (e: DragEvent, overId: string) => {
    if (!dragId) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (overId === dragId) return;
    setAgents((prev) => {
      const from = prev.findIndex((a) => a.id === dragId);
      const to = prev.findIndex((a) => a.id === overId);
      if (from < 0 || to < 0) return prev;
      const next = [...prev];
      next.splice(to, 0, ...next.splice(from, 1));
      return next;
    });
  };

  const onDragEnd = async () => {
    if (!dragId) return;
    setDragId(null);
    try {
      await reorderAgents(agents.map((a) => a.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save agent order");
      getAgents().then(setAgents).catch(() => {});
    }
  };

  const runningCount = (agentId: string) =>
    runs.filter((r) => r.agent_id === agentId && r.running).length;
  const runningRuns = runs.filter((r) => r.running);
  const current = runs.find((r) => r.id === selectedRun) ?? null;

  const formCard = (
    <div className="bg-white border-2 border-indigo-300 rounded-xl p-4 shadow-sm space-y-3">
      <h3 className="text-sm font-semibold text-slate-700">
        {editingId ? "Edit Agent" : "Configure New Agent"}
      </h3>
      <div>
        <label className={labelCls}>Name *</label>
        <input
          ref={nameRef}
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="QA"
          className={inputCls}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Runs on</label>
          <select
            value={form.runtime}
            onChange={(e) => {
              // Model ids don't carry over between harnesses
              setForm({ ...form, runtime: e.target.value as AgentRuntime, model: "" });
              setCustomModel(false);
            }}
            className={inputCls}
          >
            {runtimes &&
              (Object.keys(runtimes) as AgentRuntime[]).map((rt) => (
                <option key={rt} value={rt}>
                  {runtimes[rt].label}
                </option>
              ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Model</label>
          <select
            value={showCustomModel ? CUSTOM_MODEL : form.model}
            onChange={(e) => {
              const custom = e.target.value === CUSTOM_MODEL;
              setCustomModel(custom);
              setForm({ ...form, model: custom ? "" : e.target.value });
            }}
            disabled={!modelOptions}
            className={inputCls}
          >
            <option value="">{modelOptions ? "CLI default" : "Loading models..."}</option>
            {(modelOptions ?? []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
            <option value={CUSTOM_MODEL}>Other...</option>
          </select>
        </div>
      </div>
      {showCustomModel && (
        <div>
          <label className={labelCls}>Model id</label>
          <input
            type="text"
            value={form.model}
            onChange={(e) => setForm({ ...form, model: e.target.value })}
            placeholder="Exact model name for this harness"
            className={`${inputCls} font-mono`}
          />
        </div>
      )}
      <div>
        <label className={labelCls}>Working Directory (optional, defaults to home)</label>
        <div className="flex">
          <input
            type="text"
            value={form.working_dir}
            onChange={(e) => setForm({ ...form, working_dir: e.target.value })}
            placeholder="/path/to/repo"
            className="flex-1 text-sm font-mono border border-slate-200 rounded-l-lg px-3 py-2 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
          />
          <button
            type="button"
            onClick={() => setBrowsing(true)}
            className="px-2.5 py-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 border border-slate-200 border-l-0 rounded-r-lg transition-colors"
            title="Browse for folder..."
          >
            <FolderOpen size={16} />
          </button>
        </div>
      </div>
      <div>
        <label className={labelCls}>Starting Prompt</label>
        <textarea
          value={form.prompt}
          onChange={(e) => setForm({ ...form, prompt: e.target.value })}
          placeholder="You are a Quality Assurance engineer who is focused on testing an application..."
          rows={5}
          className={inputCls}
        />
      </div>
      <div>
        <label className={labelCls}>
          Command {form.runtime === "custom" ? "*" : "(optional override)"}
        </label>
        <input
          type="text"
          value={form.command}
          onChange={(e) => setForm({ ...form, command: e.target.value })}
          placeholder={defaultCommand || "my-agent --model {model} {prompt}"}
          className={`${inputCls} font-mono`}
        />
        <p className="mt-1 text-[11px] text-slate-400">
          {"{model}"} and {"{prompt}"} are filled in from the fields above.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={!formValid}
          className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {editingId ? "Save" : "Add Agent"}
        </button>
        <button onClick={closeForm} className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Agent configs */}
      {collapsed ? (
        <button
          onClick={() => toggleCollapsed(false)}
          className="shrink-0 self-start flex lg:flex-col items-center gap-2 px-3 py-2 lg:px-2 lg:py-3 bg-white border border-slate-200 rounded-xl shadow-sm text-slate-500 hover:text-indigo-600 hover:border-indigo-300 transition-colors"
          title="Show agents"
        >
          <ChevronRight size={16} />
          <Bot size={16} />
          <span className="text-xs font-medium">{agents.length}</span>
        </button>
      ) : (
        <div className="lg:w-96 shrink-0 space-y-3">
          <div className="flex items-center justify-between">
            <button
              onClick={() => toggleCollapsed(true)}
              className="flex items-center gap-1 text-xl font-bold text-slate-800 hover:text-indigo-600 transition-colors"
              title="Hide agents"
            >
              <ChevronDown size={18} />
              Agents
            </button>
            <button
              onClick={() => {
                closeForm();
                setAdding(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Plus size={16} />
              Add Agent
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}

          {adding && formCard}

          {agents.length === 0 && !adding && (
            <div className="text-center py-10 text-slate-400">
              <Bot size={40} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">No agents configured. Add one to get started.</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            {agents.map((agent) =>
              editingId === agent.id ? (
                <div key={agent.id} className="col-span-2">
                  {formCard}
                </div>
              ) : (
                <div
                  key={agent.id}
                  draggable
                  onDragStart={(e) => onDragStart(e, agent.id)}
                  onDragOver={(e) => onDragOverAgent(e, agent.id)}
                  onDrop={(e) => e.preventDefault()}
                  onDragEnd={onDragEnd}
                  className={`group min-w-0 bg-white border border-slate-200 rounded-lg p-2 shadow-sm hover:shadow transition-all cursor-grab active:cursor-grabbing ${
                    dragId === agent.id ? "opacity-30 scale-95" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-1">
                    <h3 className="min-w-0 text-[13px] leading-tight font-semibold text-slate-800 break-words">
                      {agent.name}
                    </h3>
                    <button
                      onClick={() => handleLaunch(agent.id)}
                      className="shrink-0 p-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md hover:bg-emerald-100 transition-colors"
                      title="Launch a new instance"
                    >
                      <Play size={12} />
                    </button>
                  </div>
                  <p className="mt-0.5 text-[10px] leading-tight text-slate-500">{runtimeLabel(agent.runtime)}</p>
                  {/* Provider path stripped so the model itself fits; full id on hover */}
                  <p
                    className="text-[11px] leading-tight font-mono text-slate-700 break-all"
                    title={agent.model || undefined}
                  >
                    {agent.model ? agent.model.split("/").pop() : "CLI default"}
                  </p>
                  <div className="mt-1 flex items-center gap-0.5 text-slate-300">
                    {/* The popup is a child of the icon, so it stays open while the pointer is over it */}
                    <div className="relative group/tip p-1 hover:text-indigo-600 cursor-help">
                      <Info size={13} />
                      <div className="hidden group-hover/tip:block absolute left-0 top-full z-50 w-72 max-h-64 overflow-y-auto cursor-auto rounded-lg border border-slate-200 bg-white p-3 text-left shadow-lg">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                          Starting prompt
                        </p>
                        {agent.prompt ? (
                          <p className="mt-1 text-xs text-slate-700 whitespace-pre-wrap break-words">
                            {agent.prompt}
                          </p>
                        ) : (
                          <p className="mt-1 text-xs text-slate-400 italic">None</p>
                        )}
                        <p className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                          Starting directory
                        </p>
                        {agent.working_dir ? (
                          <p className="mt-1 text-[11px] font-mono text-slate-700 break-all">
                            {agent.working_dir}
                          </p>
                        ) : (
                          <p className="mt-1 text-xs text-slate-400 italic">Home folder (default)</p>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => openEdit(agent)}
                      className="p-1 hover:text-indigo-600 transition-colors"
                      title="Edit"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      onClick={() => setConfirmDelete(agent)}
                      className="p-1 hover:text-red-500 transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={13} />
                    </button>
                    {runningCount(agent.id) > 0 && (
                      <span className="ml-auto shrink-0 text-[10px] text-emerald-600 font-medium">
                        {runningCount(agent.id)} running
                      </span>
                    )}
                  </div>
                </div>
              ),
            )}
          </div>
        </div>
      )}

      {/* Running agents window */}
      <div className="flex-1 min-w-0">
        <div className="rounded-xl border border-slate-700 bg-slate-900 overflow-hidden shadow-sm">
          <div className="flex items-end bg-slate-800">
            <div className="flex-1 min-w-0 flex items-center gap-1 px-2 pt-2 overflow-x-auto">
              {runs.length === 0 && (
                <span className="px-2 pb-2 text-xs text-slate-400">No agents running</span>
              )}
              {runs.map((run) => (
                <div
                  key={run.id}
                  onClick={() => setSelectedRun(run.id)}
                  className={`flex items-center gap-2 pl-3 pr-1.5 py-1.5 rounded-t-lg text-xs cursor-pointer whitespace-nowrap ${
                    run.id === selectedRun
                      ? "bg-slate-900 text-white"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${run.running ? "bg-emerald-400" : "bg-slate-500"}`}
                    title={run.running ? "Running" : `Exited (${run.exit_code})`}
                  />
                  {run.name}
                  {run.running ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleKill(run.id);
                      }}
                      className="p-1 text-slate-500 hover:text-red-400"
                      title="Kill agent"
                    >
                      <Square size={11} />
                    </button>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemove(run.id);
                      }}
                      className="p-1 text-slate-500 hover:text-slate-200"
                      title="Close"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            {runningRuns.length > 0 && (
              <button
                onClick={() => setConfirmKillAll(true)}
                className="shrink-0 m-1.5 flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-red-300 border border-red-400/40 rounded-lg hover:bg-red-500/20 transition-colors"
                title="Kill every running agent"
              >
                <Square size={11} />
                Kill all ({runningRuns.length})
              </button>
            )}
          </div>

          {current && (
            <div className="px-3 py-2 border-b border-slate-800 text-xs text-slate-300 space-y-1">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span className={current.running ? "text-emerald-400" : "text-slate-400"}>
                  {current.running ? "Running" : `Exited (${current.exit_code})`}
                </span>
                <span>
                  <span className="text-slate-500">Harness </span>
                  {runtimeLabel(current.runtime)}
                </span>
                <span className="break-all">
                  <span className="text-slate-500">Model </span>
                  <span className="font-mono text-white">{current.model || "CLI default"}</span>
                </span>
                <span className="break-all">
                  <span className="text-slate-500">Dir </span>
                  <span className="font-mono">{current.working_dir}</span>
                </span>
              </div>
              {/* Full command (includes the starting prompt): two lines until clicked */}
              <div
                onClick={() => setCommandExpanded((v) => !v)}
                className={`font-mono text-[11px] text-slate-500 whitespace-pre-wrap break-words cursor-pointer hover:text-slate-400 ${
                  commandExpanded ? "max-h-40 overflow-y-auto" : "line-clamp-2"
                }`}
                title={commandExpanded ? "Click to collapse" : "Click to show the full command"}
              >
                {current.command}
              </div>
            </div>
          )}

          <div className="p-2" style={{ height: "calc(100vh - 130px)", minHeight: 560 }}>
            {runs.length === 0 ? (
              <div className="h-full flex items-center justify-center text-sm text-slate-500">
                Launch an agent to see its terminal here.
              </div>
            ) : (
              runs.map((run) => (
                <AgentTerminal key={run.id} runId={run.id} active={run.id === selectedRun} />
              ))
            )}
          </div>
        </div>
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title="Delete agent configuration?"
          confirmLabel="Delete"
          onConfirm={() => handleDelete(confirmDelete.id)}
          onCancel={() => setConfirmDelete(null)}
        >
          <p>
            Are you sure you want to delete{" "}
            <span className="font-semibold">{confirmDelete.name}</span>? This can't be undone.
          </p>
          {runningCount(confirmDelete.id) > 0 && (
            <p className="mt-2 text-xs text-amber-700">
              {runningCount(confirmDelete.id)} running instance
              {runningCount(confirmDelete.id) !== 1 ? "s" : ""} of this agent will keep running
              until you kill {runningCount(confirmDelete.id) !== 1 ? "them" : "it"}.
            </p>
          )}
        </ConfirmDialog>
      )}

      {confirmKillAll && (
        <ConfirmDialog
          title="Kill all running agents?"
          confirmLabel={`Kill ${runningRuns.length} agent${runningRuns.length !== 1 ? "s" : ""}`}
          onConfirm={handleKillAll}
          onCancel={() => setConfirmKillAll(false)}
        >
          <p>
            This stops every running agent immediately. Anything they are in the middle of is lost.
          </p>
          <p className="mt-2 text-xs text-slate-500">{runningRuns.map((r) => r.name).join(", ")}</p>
        </ConfirmDialog>
      )}

      {browsing && (
        <FileBrowserModal
          initialPath={form.working_dir || "~"}
          mode="directory"
          onSelect={(path) => {
            setForm({ ...form, working_dir: path });
            setBrowsing(false);
          }}
          onClose={() => setBrowsing(false)}
        />
      )}
    </div>
  );
}
