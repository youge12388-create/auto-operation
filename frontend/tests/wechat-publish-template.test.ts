import { describe, expect, it } from "vitest";

import { applyWechatAutoPublishTemplate } from "../src/wechatPublishTemplate";

describe("WeChat formal publish template", () => {
  it("enables formal delivery and automatic review without guessing account-specific values", () => {
    expect(applyWechatAutoPublishTemplate({
      channel_account_id: "account-1",
      wechat_thumb_media_id: "thumb-1",
      review_rules: { human_review_required: true },
    })).toEqual({
      channel_account_id: "account-1",
      wechat_thumb_media_id: "thumb-1",
      delivery_mode: "auto_publish",
      review_rules: { human_review_required: false },
      need_open_comment: true,
      only_fans_can_comment: false,
    });
  });
});
