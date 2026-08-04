import { describe, expect, it } from "vitest";

import { buildChannelTestPath, buildWechatThumbPath } from "../src/contracts";

describe("channel API contracts", () => {
  it("uses a non-ambiguous account test route", () => {
    expect(buildChannelTestPath("account/1")).toBe("/api/v1/channels/accounts/account%2F1/test");
  });

  it("keeps the default thumb upload route when no account is selected", () => {
    expect(buildWechatThumbPath()).toBe("/api/v1/channels/wechat/materials/thumb");
  });

  it("scopes thumb upload to the selected channel account", () => {
    expect(buildWechatThumbPath("公众号 1")).toBe("/api/v1/channels/wechat/materials/thumb?account_id=%E5%85%AC%E4%BC%97%E5%8F%B7%201");
  });
});