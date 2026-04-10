import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { Direction, JobNotification, JobSchedule, JobTask, NotifyStyle, Period, ScheduleType, ScheduledJob } from "../types";
import { createJob, getSessionToken, updateJob } from "../services/api";

const SCHEDULE_TYPES: { value: ScheduleType; label: string }[] = [
  { value: "hourly", label: "Every hour" },
  { value: "daily", label: "Daily" },
  { value: "weekdays", label: "Weekdays (Mon-Fri)" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
];

const DAYS_OF_WEEK: { value: string; label: string }[] = [
  { value: "mon", label: "Monday" },
  { value: "tue", label: "Tuesday" },
  { value: "wed", label: "Wednesday" },
  { value: "thu", label: "Thursday" },
  { value: "fri", label: "Friday" },
  { value: "sat", label: "Saturday" },
  { value: "sun", label: "Sunday" },
];

interface Props {
  job: ScheduledJob | null;
  onClose: () => void;
}

export default function JobFormModal({ job, onClose }: Props) {
  const [name, setName] = useState(job?.name ?? "");
  const [schedule, setSchedule] = useState<JobSchedule>(
    job?.schedule ?? { type: "daily", time: "08:00" }
  );
  const [tasks, setTasks] = useState<JobTask[]>(
    job?.tasks?.length ? job.tasks : [{ type: "email", period: "day" }]
  );
  const [notification, setNotification] = useState<JobNotification>(
    job?.notification ?? { enabled: true, style: "banner" }
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateSchedule = <K extends keyof JobSchedule>(key: K, val: JobSchedule[K]) =>
    setSchedule((s) => ({ ...s, [key]: val }));

  const updateTask = (idx: number, patch: Partial<JobTask>) =>
    setTasks((ts) => ts.map((t, i) => (i === idx ? { ...t, ...patch } : t)));

  const removeTask = (idx: number) => setTasks((ts) => ts.filter((_, i) => i !== idx));

  const addTask = () =>
    setTasks((ts) => [...ts, { type: "email", period: "week" }]);

  const handleSave = async () => {
    if (!name.trim()) {
      setError("Job name is required");
      return;
    }
    if (tasks.length === 0) {
      setError("Add at least one task");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: name.trim(),
        schedule,
        tasks,
        notification,
        session_token: getSessionToken() ?? "",
      };
      if (job) {
        await updateJob(job.id, payload);
      } else {
        await createJob(payload);
      }
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save job");
      setSaving(false);
    }
  };

  const inputCls = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm";
  const labelCls = "block text-sm font-medium mb-1";
  const sectionCls = "space-y-3";

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50 overflow-auto">
      <div className="bg-white rounded-2xl shadow-xl p-6 max-w-lg w-full space-y-5 my-6">
        <h2 className="text-xl font-bold">{job ? "Edit Job" : "New Scheduled Job"}</h2>

        {/* Name */}
        <div>
          <label className={labelCls}>Job Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputCls}
            placeholder="e.g. Morning Email Digest"
          />
        </div>

        <hr className="border-slate-200" />

        {/* Schedule */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Schedule</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Frequency</label>
              <select
                value={schedule.type}
                onChange={(e) => updateSchedule("type", e.target.value as ScheduleType)}
                className={inputCls}
              >
                {SCHEDULE_TYPES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls}>Time</label>
              <input
                type="time"
                value={schedule.time}
                onChange={(e) => updateSchedule("time", e.target.value)}
                className={inputCls}
              />
            </div>
          </div>

          {schedule.type === "weekly" && (
            <div>
              <label className={labelCls}>Day of Week</label>
              <select
                value={schedule.day_of_week ?? "mon"}
                onChange={(e) => updateSchedule("day_of_week", e.target.value)}
                className={inputCls}
              >
                {DAYS_OF_WEEK.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
          )}

          {schedule.type === "monthly" && (
            <div>
              <label className={labelCls}>Day of Month</label>
              <input
                type="number"
                min={1}
                max={28}
                value={schedule.day_of_month ?? 1}
                onChange={(e) => updateSchedule("day_of_month", Number(e.target.value))}
                className={inputCls}
              />
            </div>
          )}
        </section>

        <hr className="border-slate-200" />

        {/* Tasks */}
        <section className={sectionCls}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Tasks</h3>
            <button
              onClick={addTask}
              className="text-indigo-600 hover:text-indigo-700 text-sm font-medium flex items-center gap-1"
            >
              <Plus size={14} /> Add Task
            </button>
          </div>

          {tasks.map((task, idx) => (
            <div key={idx} className="border border-slate-200 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">Task {idx + 1}</span>
                {tasks.length > 1 && (
                  <button
                    onClick={() => removeTask(idx)}
                    className="text-slate-400 hover:text-red-500"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-slate-500">Type</label>
                  <select
                    value={task.type}
                    onChange={(e) => updateTask(idx, { type: e.target.value as "email" | "calendar" })}
                    className={inputCls}
                  >
                    <option value="email">Emails</option>
                    <option value="calendar">Calendar</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Period</label>
                  <select
                    value={task.period}
                    onChange={(e) => updateTask(idx, { period: e.target.value as Period })}
                    className={inputCls}
                  >
                    <option value="day">Day</option>
                    <option value="week">Week</option>
                    <option value="month">Month</option>
                    <option value="quarter">Quarter</option>
                  </select>
                </div>
              </div>
              {task.type === "calendar" && (
                <div>
                  <label className="text-xs text-slate-500">Direction</label>
                  <select
                    value={task.direction ?? "future"}
                    onChange={(e) => updateTask(idx, { direction: e.target.value as Direction })}
                    className={inputCls}
                  >
                    <option value="past">Previous</option>
                    <option value="future">Upcoming</option>
                  </select>
                </div>
              )}
            </div>
          ))}
        </section>

        <hr className="border-slate-200" />

        {/* Notification */}
        <section className={sectionCls}>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">macOS Notification</h3>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={notification.enabled}
              onChange={(e) => setNotification((n) => ({ ...n, enabled: e.target.checked }))}
              className="rounded"
            />
            Show notification when report is ready
          </label>
          {notification.enabled && (
            <div>
              <label className={labelCls}>Style</label>
              <select
                value={notification.style}
                onChange={(e) => setNotification((n) => ({ ...n, style: e.target.value as NotifyStyle }))}
                className={inputCls}
              >
                <option value="banner">Banner (brief notification)</option>
                <option value="popup">Popup dialog (stays until dismissed)</option>
              </select>
            </div>
          )}
        </section>

        {/* Actions */}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-4 py-2 text-slate-600 text-sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
          >
            {saving ? "Saving..." : job ? "Update Job" : "Create Job"}
          </button>
        </div>
      </div>
    </div>
  );
}
