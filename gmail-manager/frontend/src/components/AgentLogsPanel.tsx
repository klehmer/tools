import { useEffect, useRef, useState } from "react";
import { ScrollText, Trash2, Skull, Activity } from "lucide-react";
import { clearAgentLogs, getAgentLogs, killAllAgents, listAgentProcesses, type AgentProcess } from "../services/api";

export default function AgentLogsPanel() {
  const [lines, setLines] = useState<string[]>([]);
  const [open, setOpen] = useState(true);
  const [autoscroll, setAutoscroll] = useState(true);
  const [procs, setProcs] = useState<AgentProcess[] | null>(null);
  const preRef = useRef<HTMLPreElement | null>(null);

  const refresh = async () => {
    try {
      const ls = await getAgentLogs(400);
      setLines(ls);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (autoscroll && preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [lines, autoscroll]);

  const clear = async () => {
    await clearAgentLogs();
    setLines([]);
  };

  return (
    <div className="mb-6 rounded-2xl border border-gray-300 bg-gray-900 text-gray-100">
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-sm font-semibold"
        >
          <ScrollText className="h-4 w-4" />
          Agent log {lines.length > 0 && <span className="text-xs text-gray-400">({lines.length} lines)</span>}
        </button>
        <div className="flex items-center gap-2 text-xs">
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={autoscroll}
              onChange={(e) => setAutoscroll(e.target.checked)}
            />
            autoscroll
          </label>
          <button
            onClick={async () => setProcs(await listAgentProcesses())}
            className="flex items-center gap-1 rounded border border-gray-600 px-2 py-0.5 hover:bg-gray-800"
          >
            <Activity className="h-3 w-3" />
            Show processes
          </button>
          <button
            onClick={async () => {
              if (!confirm("Kill all running cleanup runners and CLI agents (codex/claude)?")) return;
              await killAllAgents();
              await refresh();
            }}
            className="flex items-center gap-1 rounded border border-red-500 bg-red-900/40 px-2 py-0.5 text-red-200 hover:bg-red-900"
          >
            <Skull className="h-3 w-3" />
            Kill all agents
          </button>
          <button
            onClick={clear}
            className="flex items-center gap-1 rounded border border-gray-600 px-2 py-0.5 hover:bg-gray-800"
          >
            <Trash2 className="h-3 w-3" />
            Clear
          </button>
        </div>
      </div>
      {procs && (
        <div className="border-b border-gray-700 px-4 py-2 text-[11px] font-mono">
          <div className="mb-1 flex items-center justify-between text-gray-300">
            <span>{procs.length === 0 ? "No running agent processes." : `${procs.length} running`}</span>
            <button onClick={() => setProcs(null)} className="text-gray-500 hover:text-gray-200">hide</button>
          </div>
          {procs.map((p) => (
            <div key={p.pid} className="truncate text-gray-200">
              <span className="text-amber-400">{p.pid}</span>{" "}
              <span className="text-gray-500">{p.etime}</span>{" "}
              {p.command}
            </div>
          ))}
        </div>
      )}
      {open && (
        <pre
          ref={preRef}
          className="max-h-72 overflow-auto px-4 py-2 font-mono text-[11px] leading-relaxed"
        >
          {lines.length === 0
            ? "No log output yet. The agent will append to /tmp/gmail_manager_agent.log."
            : lines.join("\n")}
        </pre>
      )}
    </div>
  );
}
