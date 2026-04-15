export type Period = "day" | "week" | "month" | "quarter";
export type Direction = "past" | "future";
export type AIProvider = "anthropic" | "claude-code" | "codex" | "openai";

export interface ConfigField {
  value: string;
  configured: boolean;
}

export interface AppConfig {
  GOOGLE_CLIENT_ID: ConfigField;
  GOOGLE_CLIENT_SECRET: ConfigField;
  ANTHROPIC_API_KEY: ConfigField;
  OPENAI_API_KEY: ConfigField;
  AI_PROVIDER: ConfigField;
  AI_MODEL: ConfigField;
  DEFAULT_PERIOD: ConfigField;
  DEFAULT_DIRECTION: ConfigField;
  PLANNER_COLUMN_WIDTH: ConfigField;
  BACKEND_URL: ConfigField;
  FRONTEND_URL: ConfigField;
}

export interface UserProfile {
  email: string;
  name?: string;
  picture?: string;
}

export interface Highlight {
  title: string;
  why?: string;
  from?: string;
  subject?: string;
  when?: string;
  attendees?: string[];
}

export interface SummaryResult {
  summary: string;
  highlights?: Highlight[];
  themes?: string[];
  action_items?: string[];
  stats?: { total_events?: number; total_hours?: number };
  count?: number;
  period?: string;
  direction?: string;
}

// --- Scheduled Jobs ---

export type ScheduleType = "hourly" | "daily" | "weekdays" | "weekly" | "monthly";
export type NotifyStyle = "banner" | "popup";

export interface JobSchedule {
  type: ScheduleType;
  time: string;            // HH:MM
  day_of_week?: string;    // mon, tue, ...
  day_of_month?: number;   // 1-28
}

export interface JobTask {
  type: "email" | "calendar";
  period: Period;
  direction?: Direction;   // only for calendar
}

export interface JobNotification {
  enabled: boolean;
  style: NotifyStyle;
}

export interface ScheduledJob {
  id: string;
  name: string;
  enabled: boolean;
  schedule: JobSchedule;
  tasks: JobTask[];
  notification: JobNotification;
  session_token: string;
  created_at: string;
  last_run: string | null;
  last_status: "success" | "error" | null;
  last_message: string;
}

export interface Report {
  id: string;
  job_id: string;
  job_name: string;
  created_at: string;
  results: {
    email?: SummaryResult;
    calendar?: SummaryResult;
  };
}

// --- Checklist / Planner ---

export interface ChecklistItem {
  id: string;
  text: string;
  date: string; // YYYY-MM-DD
  done: boolean;
  priority: boolean;
  sort_order: number;
  created_at: string;
}
