import { describe, expect, it } from "vitest";

import type { Job, JobEvent } from "../src/api";
import {
  FIXED_JOB_STAGES,
  JOB_STAGE_LABELS,
  JOB_STATUS_META,
  formatJobDate,
  formatJobDuration,
  getJobEventLabel,
  getJobEventStatusLabel,
  getJobEventTone,
  getJobStageLabel,
  getJobStatusMeta,
  getOperatorSafeJobError,
  isActiveJob,
  isCancelableJob,
  isFailureJob,
  isRetryableJob,
} from "../src/jobPresentation";

function job(status: string, lastError: string | null = null): Pick<Job, "status" | "last_error"> {
  return { status, last_error: lastError };
}

function event(eventType: string, status: string | null, payload: Record<string, unknown> = {}): Pick<JobEvent, "event_type" | "status" | "payload"> {
  return { event_type: eventType, status, payload };
}

describe("job presentation", () => {
  it("keeps metadata for all eight persisted job statuses", () => {
    expect(Object.keys(JOB_STATUS_META)).toHaveLength(8);
    expect(getJobStatusMeta("waiting_topic")).toEqual({ label: "等待选题", tone: "purple" });
    expect(getJobStatusMeta("missing")).toEqual({ label: "missing", tone: "neutral" });
    expect(getJobStatusMeta(null)).toEqual({ label: "未知状态", tone: "neutral" });
  });

  it("labels every fixed workflow stage and safely handles a missing stage", () => {
    expect(FIXED_JOB_STAGES).toHaveLength(12);
    expect(FIXED_JOB_STAGES.map((stage) => JOB_STAGE_LABELS[stage])).not.toContain("");
    expect(getJobStageLabel("draft")).toBe("创建草稿");
    expect(getJobStageLabel(null)).toBe("等待调度");
  });

  it("uses the strict job status filters required by the operations center", () => {
    expect(isActiveJob(job("queued"))).toBe(true);
    expect(isActiveJob(job("running"))).toBe(true);
    expect(isActiveJob(job("waiting_review"))).toBe(false);
    expect(isActiveJob(job("failed_retryable"))).toBe(false);

    expect(isFailureJob(job("failed_retryable"))).toBe(true);
    expect(isFailureJob(job("failed_terminal"))).toBe(true);
    expect(isFailureJob(job("canceled"))).toBe(false);

    expect(isCancelableJob(job("queued"))).toBe(true);
    expect(isCancelableJob(job("running"))).toBe(true);
    expect(isCancelableJob(job("failed_retryable"))).toBe(true);
    expect(isCancelableJob(job("waiting_review"))).toBe(false);
    expect(isCancelableJob(job("failed_terminal"))).toBe(false);

    expect(isRetryableJob(job("failed_retryable"))).toBe(true);
    expect(isRetryableJob(job("failed_terminal"))).toBe(true);
    expect(isRetryableJob(job("running"))).toBe(false);
  });

  it("formats duration and timestamps deterministically for the Beijing workbench", () => {
    expect(formatJobDuration(null)).toBe("—");
    expect(formatJobDuration(65_000)).toBe("01:05");
    expect(formatJobDuration(3_661_000)).toBe("01:01:01");
    expect(formatJobDate(null)).toBe("—");
    expect(formatJobDate("not-a-date")).toBe("—");
    expect(formatJobDate("2026-08-23T01:30:00.000Z")).toBe("2026-08-23 09:30");
  });

  it("maps known and fallback event labels and tones", () => {
    expect(getJobEventLabel(event("step_failed", "failed"))).toBe("步骤失败");
    expect(getJobEventTone(event("step_failed", "failed"))).toBe("red");
    expect(getJobEventLabel(event("custom_event", "warning"))).toBe("custom_event");
    expect(getJobEventTone(event("custom_event", "warning"))).toBe("orange");
    expect(getJobEventStatusLabel("failed")).toBe("执行失败");
    expect(getJobEventStatusLabel(null)).toBe("已记录任务事件");
  });

  it("prefers the newest event error, truncates it, and never reads runtime snapshots", () => {
    const longEventError = `事件失败：${"x".repeat(400)}`;
    const result = getOperatorSafeJobError(
      job("failed_terminal", "任务上的旧错误"),
      [
        event("step_failed", "failed", { error: "较早的错误" }),
        event("step_failed", "failed", { error: longEventError, runtime_snapshot: "不得展示" }),
      ],
    );

    expect(result).toHaveLength(320);
    expect(result).toMatch(/^事件失败：/);
    expect(result).toMatch(/…$/);
    expect(result).not.toContain("不得展示");
    expect(getOperatorSafeJobError(job("failed_terminal", "  后备\n错误  "))).toBe("后备 错误");
  });

  it("redacts credentials returned by an older backend before displaying an error", () => {
    const secret = "legacy-secret-value-123456";
    const result = getOperatorSafeJobError(
      job("failed_terminal", `任务错误：Bearer ${secret}`),
      [event("step_failed", "failed", { error: `上游错误：api_key=${secret}; access_token=${secret}` })],
    );

    expect(result).toContain("[redacted]");
    expect(result).not.toContain(secret);
  });
});
