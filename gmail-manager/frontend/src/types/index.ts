export interface ConfigField {
  value: string;
  is_set: boolean;
}

export interface AppConfig {
  GOOGLE_CLIENT_ID: ConfigField;
  GOOGLE_CLIENT_SECRET: ConfigField;
  ANTHROPIC_API_KEY: ConfigField;
  BACKEND_URL: ConfigField;
  FRONTEND_URL: ConfigField;
}

export interface UserProfile {
  email: string;
  name?: string;
  picture?: string;
  total_messages: number;
  storage_used_bytes?: number | null;
  storage_limit_bytes?: number | null;
}

export type EmailCategory = "delete" | "unsubscribe" | "block";

export interface EmailGroup {
  sender: string;
  sender_name: string;
  count: number;
  total_size_mb: number;
  oldest_date: string;
  newest_date: string;
  email_ids: string[];
  category: EmailCategory;
  suggestion_reason: string;
  unsubscribe_link?: string | null;
}

export interface AnalysisResult {
  analysis_summary: string;
  email_groups: EmailGroup[];
  total_emails_to_process: number;
  estimated_storage_freed_mb: number;
}

export interface CleanupRules {
  require_approval: boolean;
  download_before_delete: boolean;
  protected_senders: string[];
  protected_keywords: string[];
  custom_instructions: string;
}

export interface ReportGroup {
  sender: string;
  count: number;
  estimated_size_mb?: number | null;
  suggested_action: "delete" | "block" | "unsubscribe" | "keep" | string;
  reason: string;
  query?: string | null;
  email_ids?: string[] | null;
  unsubscribe_link?: string | null;
}

export interface AgentReport {
  runner: string;
  status: "running" | "done" | string;
  summary: string;
  starting_total?: number | null;
  current_total?: number | null;
  deleted_so_far: number;
  groups: ReportGroup[];
  actioned_keys?: string[];
  updated_at?: number;
}

export interface ApprovalRecord {
  id: string;
  email_ids: string[];
  sender: string;
  reason: string;
  suggested_action: string;
  status: "pending" | "approved" | "denied";
  created_at: number;
  decided_at: number | null;
}
