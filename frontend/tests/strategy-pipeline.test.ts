import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type StrategyConfig } from "../src/api";
import { isReviewFailureStatus } from "../src/ContentFlowPages";
import { dailyTime, mergeCombinationConfig, sanitizeCombinationConfig, scheduleMode, validatedSchedule } from "../src/StrategyPipelinePage";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("strategy combination contracts", () => {
  it("keeps inherited stage mappings while applying a combination override", () => {
    const base: StrategyConfig = {
      model_by_stage: { style: "style-model" },
      skill_by_stage: { review: "review-skill" },
      review_rules: { human_review_required: true },
    };

    expect(mergeCombinationConfig(base, {
      model_by_stage: { writing: "writing-model" },
      skill_by_stage: { writing: "writing-skill" },
    })).toMatchObject({
      model_by_stage: { style: "style-model", writing: "writing-model" },
      skill_by_stage: { review: "review-skill", writing: "writing-skill" },
      review_rules: { human_review_required: true },
    });
  });

  it("keeps retryable generation failures visible in the review queue", () => {
    expect(isReviewFailureStatus("failed_retryable")).toBe(true);
    expect(isReviewFailureStatus("running")).toBe(false);
  });
  it("removes hidden WeChat settings from a local-draft combination", () => {
    expect(sanitizeCombinationConfig({
      delivery_mode: "local_draft",
      channel_account_id: "missing-account",
      wechat_thumb_media_id: "unused-cover",
    })).toEqual({ delivery_mode: "local_draft" });
  });
  it("requires a concrete Beijing-time clock value for daily scheduling", () => {
    expect(scheduleMode("daily@09:30")).toBe("daily");
    expect(dailyTime("daily@09:30")).toBe("09:30");
    expect(validatedSchedule("daily@09:30")).toBe("daily@09:30");
    expect(() => validatedSchedule("daily")).toThrow("每日运行必须设置固定时刻");
  });
  it("sends the selected combination when manually trial-running a pipeline", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "job-1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.runStrategy("strategy/1", "deep-analysis");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/strategies/strategy/1/run",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ combination_id: "deep-analysis" }),
      }),
    );
  });

  it("lets the backend choose the combination for an automatic run", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "job-2" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.runStrategy("strategy-2");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/strategies/strategy-2/run",
      expect.objectContaining({ method: "POST", body: undefined }),
    );
  });
  it("keeps the HTTP status and backend validation detail visible", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: async () => JSON.stringify({ detail: "微信公众号交付模式必须配置默认封面素材 ID" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.updateStrategy("strategy-1", {
      name: "pipeline",
      objective: "draft",
      schedule: "manual",
      automation_level: "L2",
      config: {},
    })).rejects.toThrow("请求失败（HTTP 400）：微信公众号交付模式必须配置默认封面素材 ID");
  });
  it("archives an article through a recoverable delete contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "article-1", status: "archived" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.archiveArticle("article-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/articles/article-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
