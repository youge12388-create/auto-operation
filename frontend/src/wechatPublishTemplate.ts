import type { StrategyConfig } from "./api";

/**
 * Adapted from the publish configuration template in
 * aiworkskills/wechat-article-skills (Apache-2.0).
 * Source: https://github.com/aiworkskills/wechat-article-skills
 *
 * The target account and permanent cover media ID intentionally remain unset:
 * they are account-specific release credentials and must be selected by an operator.
 */
export function applyWechatAutoPublishTemplate(config: StrategyConfig): StrategyConfig {
  return {
    ...config,
    delivery_mode: "auto_publish",
    review_rules: {
      ...(config.review_rules ?? {}),
      human_review_required: false,
    },
    need_open_comment: true,
    only_fans_can_comment: false,
  };
}
