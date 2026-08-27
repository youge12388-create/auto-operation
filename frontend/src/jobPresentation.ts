import type { Job, JobEvent } from "./api";

export type JobPresentationTone = "blue" | "green" | "orange" | "purple" | "red" | "neutral";

export type JobStatus =
  | "queued"
  | "running"
  | "waiting_topic"
  | "waiting_review"
  | "succeeded"
  | "failed_retryable"
  | "failed_terminal"
  | "canceled";

export type JobPresentationMeta = {
  label: string;
  tone: JobPresentationTone;
};

export const JOB_STATUS_META: Readonly<Record<JobStatus, JobPresentationMeta>> = {
  queued: { label: "等待调度", tone: "orange" },
  running: { label: "运行中", tone: "blue" },
  waiting_topic: { label: "等待选题", tone: "purple" },
  waiting_review: { label: "等待审核", tone: "orange" },
  succeeded: { label: "已完成", tone: "green" },
  failed_retryable: { label: "失败，等待重试", tone: "red" },
  failed_terminal: { label: "失败，需人工处理", tone: "red" },
  canceled: { label: "已取消", tone: "neutral" },
};

export const FIXED_JOB_STAGES = [
  "collect",
  "normalize",
  "deduplicate",
  "topic",
  "evidence",
  "outline",
  "writing",
  "style",
  "rewrite",
  "review",
  "render",
  "draft",
] as const;

export type FixedJobStage = (typeof FIXED_JOB_STAGES)[number];

export const JOB_STAGE_LABELS: Readonly<Record<FixedJobStage, string>> = {
  collect: "采集信息源",
  normalize: "清洗与规范化",
  deduplicate: "去重",
  topic: "生成选题",
  evidence: "整理事实依据",
  outline: "生成写作大纲",
  writing: "撰写正文",
  style: "统一写作风格",
  rewrite: "修订优化",
  review: "质量审核",
  render: "排版渲染",
  draft: "创建草稿",
};

const UNKNOWN_STATUS_META: JobPresentationMeta = { label: "未知状态", tone: "neutral" };
const UNKNOWN_EVENT_META: JobPresentationMeta = { label: "任务事件", tone: "neutral" };
const OPERATOR_ERROR_MAX_LENGTH = 320;
const OPERATOR_SECRET_VALUE_RE = /((?:x[-_ ]?api[-_ ]?key|api[-_ ]?key|access[-_ ]?token|app[-_ ]?secret|client[-_ ]?secret|secret[-_ ]?key|password|secret)[\"']?\s*(?:=|:)\s*)(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;)&}\]]+)/gi;
const OPERATOR_BEARER_TOKEN_RE = /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi;

const JOB_EVENT_META: Readonly<Record<string, JobPresentationMeta>> = {
  step_started: { label: "开始执行", tone: "blue" },
  step_succeeded: { label: "步骤完成", tone: "green" },
  step_failed: { label: "步骤失败", tone: "red" },
  step_skipped: { label: "已跳过", tone: "neutral" },
  job_canceled: { label: "任务已取消", tone: "neutral" },
  job_waiting_topic: { label: "等待人工选题", tone: "purple" },
  source_failed: { label: "信息源采集失败", tone: "red" },
  advisory_review_unavailable: { label: "辅助审核不可用", tone: "orange" },
  render_fallback: { label: "排版已降级处理", tone: "orange" },
  auto_publish_blocked: { label: "自动发布已拦截", tone: "orange" },
};

const EVENT_STATUS_TONES: Readonly<Record<string, JobPresentationTone>> = {
  running: "blue",
  succeeded: "green",
  failed: "red",
  warning: "orange",
  skipped: "neutral",
  canceled: "neutral",
  waiting_topic: "purple",
  waiting_review: "orange",
};

const EVENT_STATUS_LABELS: Readonly<Record<string, string>> = {
  running: "正在执行",
  succeeded: "执行完成",
  failed: "执行失败",
  warning: "需要关注",
  skipped: "已跳过",
  canceled: "已取消",
  waiting_topic: "等待选题确认",
  waiting_review: "等待审核确认",
};

function jobStatus(job: Pick<Job, "status">): string {
  return job.status;
}

function isKnownJobStatus(status: string): status is JobStatus {
  return status in JOB_STATUS_META;
}

function isKnownJobStage(stage: string): stage is FixedJobStage {
  return stage in JOB_STAGE_LABELS;
}

function safeErrorText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value
    .replace(/\s+/g, " ")
    .replace(OPERATOR_SECRET_VALUE_RE, "$1[redacted]")
    .replace(OPERATOR_BEARER_TOKEN_RE, "Bearer [redacted]")
    .trim();
  if (!normalized) return null;
  return normalized.length > OPERATOR_ERROR_MAX_LENGTH
    ? `${normalized.slice(0, OPERATOR_ERROR_MAX_LENGTH - 1)}…`
    : normalized;
}

export function getJobStatusMeta(status: string | null | undefined): JobPresentationMeta {
  if (status && isKnownJobStatus(status)) return JOB_STATUS_META[status];
  return status ? { label: status, tone: UNKNOWN_STATUS_META.tone } : UNKNOWN_STATUS_META;
}

export function getJobStageLabel(stage: string | null | undefined): string {
  if (stage && isKnownJobStage(stage)) return JOB_STAGE_LABELS[stage];
  return stage || "等待调度";
}

export function isActiveJob(job: Pick<Job, "status">): boolean {
  return ["queued", "running"].includes(jobStatus(job));
}

export function isFailureJob(job: Pick<Job, "status">): boolean {
  return ["failed_retryable", "failed_terminal"].includes(jobStatus(job));
}

export function isCancelableJob(job: Pick<Job, "status">): boolean {
  return ["queued", "running", "failed_retryable"].includes(jobStatus(job));
}

export function isRetryableJob(job: Pick<Job, "status">): boolean {
  return isFailureJob(job);
}

export function formatJobDuration(durationMs: number | null | undefined): string {
  if (!Number.isFinite(durationMs) || !durationMs || durationMs < 0) return "—";
  const totalSeconds = Math.floor(durationMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const minuteSecond = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return hours ? `${String(hours).padStart(2, "0")}:${minuteSecond}` : minuteSecond;
}

export function formatJobDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value;
  return `${part("year")}-${part("month")}-${part("day")} ${part("hour")}:${part("minute")}`;
}

export function getJobEventMeta(event: Pick<JobEvent, "event_type" | "status">): JobPresentationMeta {
  const meta = JOB_EVENT_META[event.event_type];
  if (meta) return meta;
  const tone = event.status ? EVENT_STATUS_TONES[event.status] : undefined;
  return event.event_type
    ? { label: event.event_type, tone: tone ?? UNKNOWN_EVENT_META.tone }
    : UNKNOWN_EVENT_META;
}

export function getJobEventLabel(event: Pick<JobEvent, "event_type" | "status">): string {
  return getJobEventMeta(event).label;
}

export function getJobEventTone(event: Pick<JobEvent, "event_type" | "status">): JobPresentationTone {
  return getJobEventMeta(event).tone;
}

export function getJobEventStatusLabel(status: string | null | undefined): string {
  if (!status) return "已记录任务事件";
  return EVENT_STATUS_LABELS[status] ?? status;
}

export function getOperatorSafeJobError(
  job: Pick<Job, "last_error">,
  events: readonly Pick<JobEvent, "payload">[] = [],
): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const eventError = safeErrorText(events[index].payload.error);
    if (eventError) return eventError;
  }
  return safeErrorText(job.last_error);
}
