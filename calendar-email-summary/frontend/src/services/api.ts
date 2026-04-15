import type { AppConfig, ChecklistItem, Direction, Period, Report, ScheduledJob, SummaryResult, UserProfile } from "../types";

const SESSION_KEY = "ces_session";

export function getSessionToken(): string | null {
  return localStorage.getItem(SESSION_KEY);
}
export function setSessionToken(token: string) {
  localStorage.setItem(SESSION_KEY, token);
}
export function clearSessionToken() {
  localStorage.removeItem(SESSION_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getSessionToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Session-Token": token } : {}),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const getConfigStatus = () => request<{ configured: boolean; google_configured: boolean; ai_configured: boolean }>("/config/status");
export const getConfig = () => request<AppConfig>("/config");
export const saveConfig = (data: Record<string, string>) =>
  request<{ ok: boolean }>("/config", { method: "POST", body: JSON.stringify(data) });

export const getDefaults = () =>
  request<{ period: string; direction: string; provider: string }>("/config/defaults");
export const getAuthUrl = () => request<{ url: string }>("/auth/url");
export const getMe = () => request<UserProfile>("/auth/me");
export const logout = () => request<{ ok: boolean }>("/auth/logout", { method: "POST" });

export const summarizeEmails = (period: Period) =>
  request<SummaryResult>(`/summary/emails?period=${period}`);
export const summarizeCalendar = (period: Period, direction: Direction) =>
  request<SummaryResult>(`/summary/calendar?period=${period}&direction=${direction}`);

// --- Scheduled Jobs ---
export const getJobs = () => request<ScheduledJob[]>("/jobs");
export const createJob = (data: Record<string, unknown>) =>
  request<ScheduledJob>("/jobs", { method: "POST", body: JSON.stringify(data) });
export const updateJob = (id: string, data: Record<string, unknown>) =>
  request<ScheduledJob>(`/jobs/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteJob = (id: string) =>
  request<{ ok: boolean }>(`/jobs/${id}`, { method: "DELETE" });
export const runJobNow = (id: string) =>
  request<{ ok: boolean; message: string }>(`/jobs/${id}/run`, { method: "POST" });

// --- Reports ---
export const getReports = (jobId?: string, limit = 50) => {
  const params = new URLSearchParams();
  if (jobId) params.set("job_id", jobId);
  params.set("limit", String(limit));
  return request<Report[]>(`/reports?${params}`);
};
export const getReport = (id: string) => request<Report>(`/reports/${id}`);
export const deleteReport = (id: string) =>
  request<{ ok: boolean }>(`/reports/${id}`, { method: "DELETE" });

// --- Checklist / Planner ---
export const getChecklist = (dateFrom?: string, dateTo?: string, done?: boolean) => {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (done !== undefined) params.set("done", String(done));
  return request<ChecklistItem[]>(`/checklist?${params}`);
};
export const createChecklistItem = (text: string, date: string, sort_order = 0, priority = false) =>
  request<ChecklistItem>("/checklist", {
    method: "POST",
    body: JSON.stringify({ text, date, sort_order, priority }),
  });
export const updateChecklistItem = (id: string, data: Partial<Pick<ChecklistItem, "text" | "date" | "done" | "sort_order" | "priority">>) =>
  request<ChecklistItem>(`/checklist/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
export const reorderChecklist = (itemIds: string[]) =>
  request<ChecklistItem[]>("/checklist/reorder", {
    method: "POST",
    body: JSON.stringify({ item_ids: itemIds }),
  });
export const deleteChecklistItem = (id: string) =>
  request<{ ok: boolean }>(`/checklist/${id}`, { method: "DELETE" });
