import { useEffect, useState } from "react";
import { Play, Plus, Pencil, Trash2, CheckCircle, XCircle, Clock } from "lucide-react";
import type { ScheduledJob } from "../types";
import { deleteJob, getJobs, runJobNow, updateJob } from "../services/api";
import JobFormModal from "./JobFormModal";
import ReportsPanel from "./ReportsPanel";

const SCHEDULE_LABELS: Record<string, string> = {
  hourly: "Every hour",
  daily: "Daily",
  weekdays: "Weekdays",
  weekly: "Weekly",
  monthly: "Monthly",
};

const DAY_LABELS: Record<string, string> = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday",
};

function scheduleDescription(job: ScheduledJob): string {
  const s = job.schedule;
  const time = s.time || "08:00";
  switch (s.type) {
    case "hourly":
      return `Every hour at :${time.split(":")[1]}`;
    case "daily":
      return `Daily at ${time}`;
    case "weekdays":
      return `Weekdays at ${time}`;
    case "weekly":
      return `${DAY_LABELS[s.day_of_week || "mon"] ?? s.day_of_week}s at ${time}`;
    case "monthly":
      return `Monthly on day ${s.day_of_month ?? 1} at ${time}`;
    default:
      return `At ${time}`;
  }
}

function taskSummary(job: ScheduledJob): string {
  return job.tasks
    .map((t) => {
      if (t.type === "email") return `Emails (${t.period})`;
      const dir = t.direction === "future" ? "upcoming" : "previous";
      return `Calendar ${dir} (${t.period})`;
    })
    .join(", ");
}

export default function SchedulePanel() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [editing, setEditing] = useState<ScheduledJob | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [running, setRunning] = useState<Set<string>>(new Set());

  const load = () => getJobs().then(setJobs).catch(() => {});

  useEffect(() => {
    load();
    const interval = setInterval(load, 10_000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async (job: ScheduledJob) => {
    await updateJob(job.id, { enabled: !job.enabled });
    load();
  };

  const handleDelete = async (job: ScheduledJob) => {
    if (!confirm(`Delete "${job.name}"?`)) return;
    await deleteJob(job.id);
    load();
  };

  const handleRunNow = async (job: ScheduledJob) => {
    setRunning((s) => new Set(s).add(job.id));
    try {
      await runJobNow(job.id);
    } catch {}
    // Poll briefly for status update
    setTimeout(() => {
      load();
      setRunning((s) => {
        const n = new Set(s);
        n.delete(job.id);
        return n;
      });
    }, 3000);
  };

  const handleEdit = (job: ScheduledJob) => {
    setEditing(job);
    setShowForm(true);
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditing(null);
    load();
  };

  return (
    <div className="space-y-6">
      {/* Job list */}
      <div className="bg-white rounded-2xl shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Scheduled Jobs</h2>
          <button
            onClick={() => { setEditing(null); setShowForm(true); }}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
          >
            <Plus size={16} /> New Job
          </button>
        </div>

        {jobs.length === 0 ? (
          <p className="text-slate-500 text-sm py-8 text-center">
            No scheduled jobs yet. Create one to automatically generate summaries.
          </p>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className={`border rounded-xl p-4 ${job.enabled ? "border-slate-200" : "border-slate-100 bg-slate-50 opacity-60"}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-sm truncate">{job.name}</h3>
                      {job.last_status === "success" && (
                        <CheckCircle size={14} className="text-green-500 shrink-0" />
                      )}
                      {job.last_status === "error" && (
                        <XCircle size={14} className="text-red-500 shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {scheduleDescription(job)} &middot; {taskSummary(job)}
                    </p>
                    {job.notification.enabled && (
                      <p className="text-xs text-slate-400 mt-0.5">
                        Notification: {job.notification.style}
                      </p>
                    )}
                    {job.last_run && (
                      <p className="text-xs text-slate-400 mt-1">
                        Last run: {new Date(job.last_run).toLocaleString()}
                        {job.last_status === "error" && job.last_message && (
                          <span className="text-red-400"> — {job.last_message}</span>
                        )}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => handleRunNow(job)}
                      disabled={running.has(job.id)}
                      className="p-1.5 text-slate-500 hover:text-indigo-600 disabled:opacity-40"
                      title="Run now"
                    >
                      {running.has(job.id) ? (
                        <Clock size={16} className="animate-spin" />
                      ) : (
                        <Play size={16} />
                      )}
                    </button>
                    <button
                      onClick={() => handleEdit(job)}
                      className="p-1.5 text-slate-500 hover:text-indigo-600"
                      title="Edit"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => handleToggle(job)}
                      className={`px-2 py-1 text-xs rounded-full font-medium ${
                        job.enabled
                          ? "bg-green-100 text-green-700 hover:bg-green-200"
                          : "bg-slate-200 text-slate-500 hover:bg-slate-300"
                      }`}
                    >
                      {job.enabled ? "On" : "Off"}
                    </button>
                    <button
                      onClick={() => handleDelete(job)}
                      className="p-1.5 text-slate-400 hover:text-red-500"
                      title="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent reports */}
      <ReportsPanel />

      {showForm && <JobFormModal job={editing} onClose={handleFormClose} />}
    </div>
  );
}
