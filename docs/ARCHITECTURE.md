# Architecture

## Strategy combinations and immutable runs

- `backend/src/content_ops/strategy_combinations.py` validates production-line definitions, merges base configuration with combination overrides, and resolves fixed, round-robin, or manually requested combinations.
- A strategy remains the production-line aggregate. Its `config_json` may contain multiple `strategy_combinations`, a `selection_mode`, and a `default_combination_id`; legacy strategies without combinations continue to run as one implicit combination.
- `create_job` resolves the combination before enqueueing and stores both `resolved_strategy_config` and `runtime_snapshot` in the job payload. Workers execute only this frozen configuration, so later edits to the strategy do not change queued work.
- Manual trial runs may request a `combination_id`. Manual selections do not advance the round-robin sequence; scheduled and automatic runs do.
- Production-line runs execute the fixed workflow through AI material curation, grounded topic selection, writing, AI quality review, rendering, and the configured delivery mode. `local_draft` and `wechat_draft` never publish; `auto_publish` can submit a WeChat publication only after AI quality passes, the account advertises publish capability, and the server-wide `AUTO_PUBLISH_ENABLED` emergency switch is explicitly enabled.
## Material categories and collection boundary

- Information sources are collection inputs only. Foreign content is translated into Chinese before it becomes a material; enabled model calls then assign one persisted `material_category` with confidence, reason, source, and failure state.
- Categories are first-class, reversible resources. Disabling a category never deletes historical materials, and operators can manually correct or clear a material classification.
- Automation combinations select `material_category_ids`, not collection sources. Legacy `source_ids` remain supported as a compatibility filter.
- Job creation freezes category scope in `execution_config`; after AI curation and topic recommendation, `runtime_snapshot.material_selection` freezes the final material IDs and topic so retries cannot silently select different evidence.
- Alembic revision `0008_material_categories` adds the category table and classification state without deleting or rewriting existing source items; existing rows enter `pending` classification.

## Material-first selection and AI topic radar
- Scan jobs collect and normalize source items, then use the production line's frozen writing model to create grounded topic recommendations. Topic scores and dimension scores are stored model results; the UI does not synthesize fallback scores.
- Topic algorithms are a separate library, selected in the Topic Radar rather than on a production-line combination. Each scan freezes the chosen algorithm definition (instructions, recommendation count, and heat/timeliness/reader-value/strategy-fit weights) into its job snapshot; later edits or deletion do not alter that scan.
- A topic can reference multiple source items through `topic_materials`. `topics.source_item_id` remains the primary-material compatibility field for older jobs.
- Retained materials use `selected` or `used` triage states. A manual creation can combine up to 12 retained materials; all linked materials are frozen into the evidence package before writing.
- Candidate topics are the only items shown in the topic radar. Articles requiring a decision are shown in the review queue; approved, drafted, WeChat-draft, and published articles are shown in the approved library.
- Saving an edit creates a new revision and returns the article to `waiting_review`. Removing an approved-library article is a local soft archive (`archived`); it does not delete an existing WeChat draft or published item.
- Skill, model, category scope, theme, delivery mode, channel, and default permanent cover belong to the frozen production-line combination for automatic runs. The approved library can still override theme, cover, and channel during manual delivery.


## 边界

- `backend/src/content_ops/api.py`：HTTP 接口和权限依赖。
- `backend/src/content_ops/models.py`：持久化领域模型。
- `backend/src/content_ops/workflow.py`：固定内容生产流程和幂等步骤。
- `backend/src/content_ops/providers.py`：模型供应商适配器。
- `backend/src/content_ops/skills.py`：Skill 包解析和安全校验。
- `frontend/src/`：浏览器后台。

任务状态以 PostgreSQL 为准，Redis 只负责唤醒 Worker 和发送短期事件。Worker 重启后通过数据库扫描恢复过期租约任务。

## V1 流程

流程步骤固定为 `collect → normalize → deduplicate → topic → evidence → outline → writing → style → rewrite → review → render → draft`。策略可以关闭可选步骤，但不能新增任意代码节点或改变核心顺序。

## 安全边界

Skill 包只允许 YAML、Markdown、示例和测试数据，不允许可执行文件、路径穿越或未知文件。默认写作 Skill 为已发布的 `khazix-writer`，策略显式配置优先。模型密钥加密存储，API 返回脱敏值，日志不得记录完整密钥。

## 复用相邻 MVP

后续可从 `D:\codex-all\wirter` 迁移采集、正文抽取、评分和事实包校验逻辑，但不能把其 SQLite、CLI 或 Playwright 发布器直接作为后台系统边界。


## 微信公众号连接器

`content_ops.wechat.WeChatClient` 通过官方 HTTPS API 处理 access_token、永久封面素材、草稿创建、草稿获取、草稿更新与发布提交。手动接口位于 `/api/v1/channels/wechat/*` 与文章修订版本下；`content_ops.delivery` 为自动化复用相同的账号能力、幂等键和失败状态。绑定到频道的凭证加密存储，接口和日志不返回完整密钥。自动正式发布默认由 `AUTO_PUBLISH_ENABLED=false` 全局阻断，且还要求组合选择 `auto_publish`、AI 质量审核通过、账号声明发布能力和有效永久封面素材 ID。