import type {
  AgentReport,
  AnalysisResult,
  AppConfig,
  ApprovalRecord,
  CleanupRules,
  UserProfile,
} from "../types";

const SESSION_KEY = "gmail_manager_session";

export function getSessionToken(): string | null {
  return localStorage.getItem(SESSION_KEY);
}

export function setSessionToken(token: string): void {
  localStorage.setItem(SESSION_KEY, token);
}

export function clearSessionToken(): void {
  localStorage.removeItem(SESSION_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
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

// ------------------------------------------------------------------ //
// Config (no session required)                                         //
// ------------------------------------------------------------------ //

export async function getConfigStatus(): Promise<{ configured: boolean }> {
  const res = await fetch("/config/status");
  return res.json();
}

export async function getConfig(): Promise<AppConfig> {
  return request<AppConfig>("/config");
}

export async function saveConfig(
  values: Partial<Record<string, string>>
): Promise<{ ok: boolean; configured: boolean }> {
  const res = await fetch("/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  if (!res.ok) throw new Error("Failed to save config");
  return res.json();
}

// ------------------------------------------------------------------ //
// Auth                                                                 //
// ------------------------------------------------------------------ //

export async function getAuthUrl(): Promise<string> {
  const data = await request<{ url: string }>("/auth/url");
  return data.url;
}

export async function getMe(): Promise<UserProfile> {
  return request<UserProfile>("/auth/me");
}

export async function logout(): Promise<void> {
  await request("/auth/logout", { method: "POST" });
  clearSessionToken();
}

// ------------------------------------------------------------------ //
// Analysis                                                             //
// ------------------------------------------------------------------ //

export async function analyzeInbox(): Promise<AnalysisResult> {
  return request<AnalysisResult>("/agent/analyze", { method: "POST" });
}

// ------------------------------------------------------------------ //
// Actions                                                              //
// ------------------------------------------------------------------ //

export async function deleteEmails(emailIds: string[]): Promise<void> {
  await request("/actions/delete", {
    method: "POST",
    headers: { "X-Approved": "1" },
    body: JSON.stringify({ email_ids: emailIds }),
  });
}

// ------------------------------------------------------------------ //
// Rules                                                                //
// ------------------------------------------------------------------ //

export async function getRules(): Promise<CleanupRules> {
  return request<CleanupRules>("/rules");
}

export async function saveRules(rules: Partial<CleanupRules>): Promise<CleanupRules> {
  return request<CleanupRules>("/rules", {
    method: "POST",
    body: JSON.stringify(rules),
  });
}

// ------------------------------------------------------------------ //
// Per-message metadata                                                 //
// ------------------------------------------------------------------ //

export interface EmailMeta {
  id: string;
  sender: string;
  subject: string;
  date: string;
  size_bytes: number;
}

export async function searchEmailIds(query: string, limit = 500): Promise<string[]> {
  const data = await request<{ emails: { id: string }[] }>(
    `/gmail/search?query=${encodeURIComponent(query)}&limit=${limit}`
  );
  return (data.emails ?? []).map((e) => e.id);
}

export async function findUnsubscribeLink(senderEmail: string): Promise<{ id: string; link: string | null } | null> {
  const data = await request<{
    emails: { id: string; unsubscribe_link?: string | null; has_unsubscribe?: boolean }[];
  }>(`/gmail/search?query=${encodeURIComponent(`from:${senderEmail}`)}&limit=5`);
  const emails = data.emails ?? [];
  if (emails.length === 0) return null;
  const withLink = emails.find((e) => e.unsubscribe_link) ?? emails[0];
  return { id: withLink.id, link: withLink.unsubscribe_link ?? null };
}

export async function getMessagesMetadata(emailIds: string[]): Promise<EmailMeta[]> {
  const data = await request<{ messages: EmailMeta[] }>("/gmail/messages", {
    method: "POST",
    body: JSON.stringify({ email_ids: emailIds }),
  });
  return data.messages;
}

// ------------------------------------------------------------------ //
// Approvals                                                            //
// ------------------------------------------------------------------ //

export async function listApprovals(status?: "pending" | "approved" | "denied"): Promise<ApprovalRecord[]> {
  const qs = status ? `?status=${status}` : "";
  const data = await request<{ approvals: ApprovalRecord[] }>(`/approvals${qs}`);
  return data.approvals;
}

export async function decideApproval(
  id: string,
  status: "approved" | "denied"
): Promise<ApprovalRecord> {
  return request<ApprovalRecord>(`/approvals/${id}/decide`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

// ------------------------------------------------------------------ //
// Agent live report                                                    //
// ------------------------------------------------------------------ //

export async function getAgentReport(): Promise<AgentReport | null> {
  return request<AgentReport | null>("/agent/report");
}

export async function clearAgentReport(): Promise<void> {
  await request("/agent/report", { method: "DELETE" });
}

export async function markReportAction(
  key: string,
  deletedCount = 0,
  freedMb = 0
): Promise<AgentReport> {
  return request<AgentReport>("/agent/report/action", {
    method: "POST",
    body: JSON.stringify({ key, deleted_count: deletedCount, freed_mb: freedMb }),
  });
}

export async function listUnsubscribedSenders(): Promise<string[]> {
  const data = await request<{ senders: string[] }>("/agent/unsubscribed");
  return data.senders;
}

export async function addUnsubscribedSender(senderEmail: string): Promise<void> {
  await request("/agent/unsubscribed", {
    method: "POST",
    body: JSON.stringify({ sender_email: senderEmail }),
  });
}

export async function getAgentLogs(lines = 200): Promise<string[]> {
  const data = await request<{ lines: string[] }>(`/agent/logs?lines=${lines}`);
  return data.lines;
}

export async function clearAgentLogs(): Promise<void> {
  await request("/agent/logs", { method: "DELETE" });
}

export interface AgentProcess {
  pid: string;
  etime: string;
  command: string;
}

export async function listAgentProcesses(): Promise<AgentProcess[]> {
  const d = await request<{ processes: AgentProcess[] }>("/agent/processes");
  return d.processes;
}

export async function killAllAgents(): Promise<void> {
  await request("/agent/kill-all", { method: "POST" });
}

export async function startAgent(runner: "codex" | "claude-code"): Promise<void> {
  await request("/agent/start", {
    method: "POST",
    body: JSON.stringify({ runner }),
  });
}

export async function installCleanupFiles(
  prompt: string,
  runner: "codex" | "claude-code"
): Promise<{ prompt_path: string; script_path: string }> {
  return request<{ ok: boolean; prompt_path: string; script_path: string }>(
    "/agent/install-files",
    { method: "POST", body: JSON.stringify({ prompt, runner }) }
  );
}

export async function unsubscribeSender(
  emailId: string,
  senderEmail: string,
  unsubscribeLink?: string | null
): Promise<{ method: string; url?: string; success?: boolean }> {
  return request("/actions/unsubscribe", {
    method: "POST",
    body: JSON.stringify({
      email_id: emailId,
      sender_email: senderEmail,
      unsubscribe_link: unsubscribeLink,
    }),
  });
}

export async function blockSender(senderEmail: string): Promise<void> {
  await request("/actions/block", {
    method: "POST",
    headers: { "X-Approved": "1" },
    body: JSON.stringify({ sender_email: senderEmail }),
  });
}

// ------------------------------------------------------------------ //
// Download                                                             //
// ------------------------------------------------------------------ //

export async function downloadBulk(
  emailIds: string[],
  includeAttachments = true,
  filename?: string
): Promise<void> {
  const token = getSessionToken();
  const res = await fetch("/emails/download-bulk", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Session-Token": token } : {}),
    },
    body: JSON.stringify({
      email_ids: emailIds,
      include_attachments: includeAttachments,
      filename,
    }),
  });

  if (!res.ok) throw new Error("Download failed");

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename ?? "emails.zip";
  a.click();
  URL.revokeObjectURL(url);
}
