# PROJECT_STATE

## 2026-07-31 Strategy-combination automation

- One production line can contain multiple enabled strategy combinations. Each combination can override sources, stage models, stage Skills, theme, humanization, and review rules while inheriting the line's base configuration.
- Selection supports a fixed default, round-robin rotation, and a manually specified combination for trial runs. Manual trial runs do not consume the automatic rotation position.
- Job creation freezes the selected combination, strategy identity/version, and final execution configuration. Workers and article audit snapshots use that frozen state even if the production line is edited before execution.
- Scheduled runs and production-line trial runs now execute the complete content workflow instead of stopping after collection. The material-first manual flow still uses scan jobs and stops at `waiting_topic`.
- Topic algorithms are managed from Topic Radar, not the automation editor. A scan selects one enabled algorithm and freezes its complete definition in the job snapshot. Manual material entry bypasses source collection and enters the retained material pool directly.
- Automatic formal publication is still out of scope. With the review gate enabled, jobs pause for review; with it disabled, they finish as local drafts. WeChat draft creation and publication keep their existing explicit safety boundary.

## 项目目标

建立单租户、内部使用的 AI 自动内容运营后台，完成“信息源 → 选题 → 事实包 → 文章 → 审核 → 排版 → 微信公众号草稿”的可恢复闭环。

## 当前实现

- FastAPI + SQLAlchemy 2 + Pydantic v2 后端，React + TypeScript + Vite + Ant Design 前端。
- PostgreSQL/Redis/Docker Compose 部署配置，Alembic bootstrap migration 和后续增量 migration。
- HttpOnly Cookie、Argon2id、角色权限：管理员、运营人员、审核人员。
- 来源采集、正文提取、URL/内容去重、来源分组、来源立即采集、来源更新和停用。
- 内容策略不可变版本、手动/小时/每日调度、固定工作流和数据库状态机；可按阶段选择模型和 Skill，并关闭可选步骤。
- 选题评分、人工接受/拒绝/合并、事实包、来源快照、事实声明和任务事件。
- Fake Provider、OpenAI-compatible Provider、Anthropic Provider，模型密钥加密存储和模型调用审计日志。
- Skill ZIP 安全校验、版本历史、发布、停用和回滚；禁止可执行文件、路径穿越和符号链接。 已导入并发布 `khazix-writer 1.0.0`，未指定 Writing Skill 时默认使用它。
- 文章修订、审核门、历史版本、三套内置排版主题、主题预览和手机友好的 HTML 预览。
- 文章及任务保存策略、模型、Skill、来源、主题和审核规则运行时快照。
- Redis 任务唤醒 + PostgreSQL 任务领取、租约、重试、取消和 Worker 恢复；记录开始、完成和耗时信息。
- 微信官方接口：环境凭证/账号绑定、连接测试、JPG 封面永久素材、草稿创建、草稿更新、草稿查询和账号级幂等键；选定排版主题后以主题 HTML 创建草稿。
- 前端工作台：来源、策略、模型、Skill、选题、文章、事实包、任务、内容日历、公众号频道和管理员用户管理。

## 关键边界

- V1 默认只创建微信公众号草稿，不自动发布；没有发布权限时不能显示“已发布”。
- 频道和模型凭证只保存密文，API 响应和日志只返回是否配置，不返回完整密钥。
- 删除来源、模型、频道和 Skill 使用停用/软删除，保留运行历史和审计记录。
- Skill 只允许 YAML、Markdown、示例和测试数据，不执行用户脚本。
- 旧 SQLite `create_all` 仅用于直接开发兼容；容器启动执行 `alembic upgrade head`。

## 测试与验证

- 后端：69 项 pytest 通过，Ruff check 通过，Python/Alembic 编译检查通过。
- 前端：Vitest 7 项通过，TypeScript 检查通过，Vite 生产构建通过；390、768、1280 px 核心页面无页面级横向溢出。
- Docker Compose 配置已完成；当前机器没有 Docker CLI，未执行 `docker compose config` 和容器验收。
- 前端构建仍有约 618 KB 单包警告，属于性能优化项，不影响构建成功。

## 尚未完成的外部验收

- 当前机器没有 Docker CLI，未执行真实 PostgreSQL/Redis 容器启动、健康检查和镜像构建。
- 未调用真实微信公众号接口创建草稿；接口行为使用 HTTP MockTransport 和本地幂等测试验证。
- 未执行真实 OpenAI-compatible/Anthropic 请求和真实 RSS/网页网络采集验收。
- `backend/.env` 属于本机敏感配置，不应提交或打印；此前在截图/聊天中暴露的公众号 AppSecret 应重新生成。

## 下一步

1. 在具备 Docker 的环境启动 Compose，执行 Alembic、健康检查和 Worker 恢复验收。
2. 使用重新生成的公众号凭证手动完成一次封面上传、草稿创建、更新和查询。
3. 在真实模型和 RSS/网页来源环境执行端到端验收。
4. 根据运行数据再决定是否拆分前端 bundle 和增加多平台能力。
## 2026-07-28 产品化改造

- 微信草稿默认选择第一个启用的排版主题；内置主题从 3 套扩展到 6 套。
- 微信正文主题输出改为标签级内联样式，禁止把外部 `<style>` 标签直接发送给微信。
- 本地 SQLite、Storage 和 `.env` 路径以 `backend` 项目根目录为基准，API、Worker 和 Alembic 使用同一配置来源。
- 微信发布提交后状态为 `submitted`，后台轮询 `freepublish/get`，只有微信最终返回成功才将文章标记为 `published`。
- 当前公众号账号仍以“创建草稿”为验收目标；自动发布需要账号具备微信官方发布接口权限。
## 2026-07-29 公众号交互修复

- `/api/v1/channels` 会以只读虚拟账号 `env:default` 展示 `.env` 中已配置的公众号，不返回 AppID 或 AppSecret。
- 草稿和封面接口接受 `env:default`，并继续使用应用环境中的加密外部凭证。
- 前端按公众号在 `localStorage` 保存最近一次永久封面 `media_id`；缺少封面时，草稿按钮会引导选择 JPG，不再静默禁用。
- 顶部账号和左侧账号区域可退出登录；通知数字改为真实失败/待审核任务数。
- 2026-07-29 真实连接测试被微信错误 `40164` 阻断，当前出口 IP `116.30.101.94` 需要加入公众号 API 白名单。
## 2026-07-29 Material-first editorial flow

- The material-first manual flow uses scan mode: collect, normalize, and deduplicate, then stop at `waiting_topic`; production-line trial and scheduled runs use automation mode and continue through writing, review, render, and local draft creation.
- Operators triage collected items in the material pool (`inbox`, `selected`, `ignored`, `used`), create a candidate topic from one selected material, accept it, and only then start a writing job.
- Writing jobs carry the selected `topic_id`; the evidence package uses that exact `source_item_id`.
- SQLite development database has the non-destructive `source_items.triage_status` column and index. Production/container deployments must apply Alembic revision `0004_material_triage` before starting the API.

## 2026-08-02 Real model runtime validation

- The earlier pending OpenAI-compatible validation item is now complete: DeepSeek handled the writing, style, and rewrite stages in a real production-line run.
- After human approval, the persistent worker resumed the queued job and produced a local draft. The runtime snapshot identifies the actual model; the credential remains encrypted and is never returned by the API.
- The local SQLite database has the `automation_jobs.priority` column and index from revision `0005_job_priority`; a pre-change database backup remains under the local `backend/data` directory.
- Real Anthropic, RSS/web ingestion, PostgreSQL/Redis, and WeChat draft creation remain externally unverified.

## 2026-08-02 Grounded topic radar and approved library

- Scan mode now invokes the frozen production-line model after collection and creates grounded candidate topics with stored heat, timeliness, reader-value, and strategy-fit scores.
- Topics can reference multiple materials through `topic_materials`; the legacy `source_item_id` remains the primary-material compatibility field. Manual creation accepts 1–12 retained materials, and every linked material becomes an evidence source for writing.
- The frontend core flow is now `retained material pool → AI topic radar → review queue → approved library → WeChat draft`. Skill/model selection stays in production-line configuration, while theme/cover/channel selection happens only after approval.
- Local SQLite revision `0006_topic_materials` was applied non-destructively after a backup and backfilled existing topics.
- A real DeepSeek scan analyzed 152 collected items and created four grounded recommendations. The model call succeeded with 2248 input tokens and 818 output tokens.
- Automatic formal publication remains out of scope; the approved library creates WeChat drafts only.
## 2026-08-02 Editorial controls and approved-article lifecycle

- Every strategy combination can configure custom topic-selection instructions, a 1–8 recommendation limit, and relative weights for heat, timeliness, reader value, and strategy fit. Scan jobs use the frozen combination algorithm, and the backend calculates total scores from the four model dimensions.
- Approving an article now selects it and opens the approved library immediately. Editing a library article creates a new revision, can update its title, and returns it to the review queue before delivery.
- Library deletion is a recoverable local archive. Remote WeChat drafts and published content are explicitly preserved.
- WeChat error 40164 is translated into an actionable IP-whitelist instruction using the IP returned by WeChat; credentials and whitelist settings are not changed automatically.
