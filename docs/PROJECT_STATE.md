# PROJECT_STATE

## 2026-08-06 Frontend visual redesign (Content Ops)

- ?????????????????? + ????? + ??????????????????Aurora ?????????????Candy AI?????????????? JSX ??????????? CSS ????
- `frontend/src/figma.css` ??????????`:root` ?????????? `--figma-pink`/`--figma-purple` ??????????/??????????????`frontend/src/ui-motion.css` ???????? `main.tsx` ????????????????????????????????????????????????????????????/??????? `prefers-reduced-motion`?`main.tsx` ???? `candy.css`?`ConsoleRoot.tsx` ???? `styles.css` / `console.css`?
- ??? `login-stitch.css` ??????????? Google Fonts ????????????????/?????????????????? ?Candy AI? ?? ?Content Ops / ?????????
- ? `figma.css` ??? `.runtime/figma.css.bak`?????????? `frontend/src/figma.css` ????
- ???`pnpm build` ? `pnpm test`?9 ?????CDP ???? 6 ????? + ????? + ????????????????? `document.getAnimations()` ????????????

## 2026-08-06 AI-assisted layout (render_mode=ai)

- 新增 AI 装配排版：策略配置 `render_mode: deterministic|ai`（默认 deterministic）。`ai` 模式下，render 阶段把文章交给模型，模型按所选主题的组件模板生成完整微信 HTML（封面/编号章节/金句卡/列表/代码/数据表/结语）。
- 模型指令由 `themes.layout_instruction()` 生成（组件模板 + 微信红线），输出经 `validate_gzh_html()` 校验；不合规或调用失败自动回退确定性渲染并记录 `render_fallback` 任务事件，文章不会卡死。
- render 阶段已加入 MODEL_STAGES/SKILL_STAGES，可用 `model_by_stage.render` 或 `skill_by_stage.render` 指定排版模型/Skill；`ai` 模式必须配置 `theme_id`。
- 交付（微信草稿）在 ai 模式下直接使用模型装配的 HTML（`delivery._channel_html` 不再用确定性渲染覆盖）；手动换主题建草稿仍走确定性渲染。
- 预览接口 `/themes/{id}/preview?mode=ai` 支持 AI 装配预览（需要策略配置 render 阶段模型）；前端“审核与发布 → 微信草稿”预览面板新增“AI 排版预览”按钮，显式点击才调模型。
- 后端新增 test_ai_layout.py 覆盖校验/提取/指令生成/render_mode 校验/ai 成功与回退路径。
## 2026-08-06 Componentized theme rendering

- 排版渲染从「markdown-it 标签 + 主题色」升级为「组件化装配」：正文的 h1/h2/h3、引用、列表、代码块、表格、图片、分割线会自动装配成主题组件（封面卡、编号章节标题、金句引用卡、要点列表、数据表、代码块、图片卡、结语区）。
- 6 套内置主题（摸鱼绿/红白色系/石墨极简/留白禅意/摸鱼票据/橄榄手记）各定义了差异化组件模板，设计语言参考 gzh-design-skill 组件库与 iniwap/AIWriteX 模板结构；旧内置主题与自定义主题自动回退到通用组件 + 主题色。
- 组件模板随主题 tokens 存入 `theme_versions.tokens_json.components`；既有内置主题在 `ensure_builtin_themes` 时自动补种组件，无需迁移脚本。
- markdown-it 渲染启用了 table 插件；渲染产物保持微信兼容（全内联、无 class/style/div、装饰空元素带占位）。
## 2026-08-06 Built-in article themes replaced with gzh-design-skill themes

- 内置排版主题由原来的 6 套自创模板（swiss-blue-grid、night-flight、warm-reading、neon-lab、you-sir-column、briefing-paper）替换为来自 [crossoverJie/gzh-design-skill](https://github.com/crossoverJie/gzh-design-skill) 的 6 套精选主题：摸鱼绿（moyu-green）、红白色系（red-white）、石墨极简（graphite-minimal）、留白禅意（zen-whitespace）、摸鱼票据（moyu-ticket）、橄榄手记（olive-journal）。
- 样式按其 references/theme-*.md 组件库提炼为标签级内联样式（article、h1-h3、p、blockquote、code/pre、a、img、hr、strong、列表、表格），微信兼容策略（禁 style/class，全内联）不变。
- 原仓库为 AGPL-3.0，署名保留在 backend/src/content_ops/themes.py 顶部注释；后续若继续借鉴该仓库需保持署名。
- 既有开发库中的旧主题记录不会被删除（仍可手动停用），全新数据库直接内置新 6 套。

## 2026-08-05 Material-category migration applied locally

- After an exact SQLite backup, local revision `0008_material_categories` was applied successfully. The backup is `backend/data/content_ops.before-0008.20260805-110114.db`.
- The existing development database had no Alembic version record and already contained a partial `material_categories` table. Revision `0008` is therefore repair-safe: it preserves existing records, adds only missing `source_items` category fields and indexes, and seeds only missing built-in categories.
- Migration verification found 217 source records preserved, all six required category fields present, and five built-in categories available. The Material Pool API is available again.

## 2026-08-05 AI HOT source and material-pool closed loop

- New `aihot_api` source type pulls AI HOT `/api/v1/items` (selected mode, default 24h window, up to 100 entries, optional category filter). Entries are stored as summaries with original and AI HOT links, official categories map to local material categories, and classification is recorded as AI-sourced without extra model calls. Collection stays deduplicated by canonical URL and keeps translation and retry behavior.
- The material pool “采集设置” is now a source picker: check sources, confirm, then “立即采集” runs only the checked sources. Adding, editing, and disabling sources stays in “设置 → 信息源”.
- Material cards are selectable in every pool tab, and a sticky selection bar provides the next step “创建选题并写作”, which creates a topic from the checked materials and starts writing, closing the pool → topic → review loop.
## 2026-08-06 Collection isolation and generation reliability

- Collection is now isolated per source: a failing source records a `source_failed` event and its error on the source, while the rest of the sources and the whole job continue. The collect step output reports `succeeded_sources` and `failed_sources`.
- Writing/style/rewrite stages strip a trailing model self-check report (e.g. khazix-writer's “质检报告” section) from the article body instead of failing the stage; only a body that is still too short after stripping is rejected.
- Job retry now retries a SQLite `database is locked` commit up to three times instead of failing silently.
## 2026-08-05 Explicit writing-skill control

- An unconfigured writing stage no longer falls back to khazix-writer. A Skill is only applied when the strategy configures one or the current creation explicitly selects one; otherwise writing runs with the generic editor instruction.
- `POST /api/v1/topics/{id}/start-writing` accepts `{ writing_skill_id?, disable_writing_skill? }` and freezes the override into the job execution config at creation time.
- The material-pool “创建选题并写作” dialog exposes a writing-skill selector (follow pipeline / generic writing without Skill / a specific published Skill), and a one-off selection overrides the pipeline for that run.
- The automation pipeline page now has an “导入 Skill（ZIP）” entry; imported Skills can be published and then selected per combination.
- New pipelines no longer auto-attach the first published Skill; the choice stays explicit.
## 2026-08-04 Material-category automation and guarded delivery

- Collection sources now end at the material-pool boundary. Foreign content is translated to Chinese before storage, then an enabled model assigns a persisted material category; failed classification keeps the material visible with a retryable error, and operators can correct it manually.
- Material categories support create, edit, disable, restore, counts, and filtering. Source settings support edit, disable, and restore; ignored materials remain recoverable.
- Automatic combinations now select material-pool categories. Each run performs model-backed curation and topic recommendation, then freezes the category scope, selected material IDs, and chosen topic in the job/article runtime snapshot. Legacy `source_ids` configurations still run.
- Manual creation exposes queued/running/failed progress in the review page. Model quality review is persisted; a failed quality review always pauses at `waiting_review` and cannot reach delivery.
- Delivery modes are `local_draft`, `wechat_draft`, and `auto_publish`. Existing and new unconfigured strategies remain `local_draft`. Automatic publication requires an explicit combination mode, a publish-capable account, a permanent cover media ID, an AI review pass at or above the configured score threshold (75 by default), all mandatory checks, a successful Tavily-backed fact-verification report, and the server-wide `AUTO_PUBLISH_ENABLED` switch. Failed, unavailable, or incomplete verification enters human review and creates no automated WeChat draft. With the switch off, a verified `auto_publish` run stops safely after a successful WeChat draft.

## Production prerequisites

- Terminate TLS before the application and keep `COOKIE_SECURE=true`.
- Start the dedicated Worker service; API requests only enqueue work.
- Set `TAVILY_API_KEY` to enable online fact verification. Without it, automatic publication fails closed into human review.
- WeChat draft retries and updates use revision/account idempotency keys. The approved library calls the update endpoint for an existing WeChat draft instead of creating a duplicate draft.
- Alembic revision `0008_material_categories` is additive and reversible. It was applied to the local development database on 2026-08-05 after backup.
## 2026-07-31 Strategy-combination automation

- One production line can contain multiple enabled strategy combinations. Each combination can override sources, stage models, stage Skills, theme, humanization, and review rules while inheriting the line's base configuration.
- Selection supports a fixed default, round-robin rotation, and a manually specified combination for trial runs. Manual trial runs do not consume the automatic rotation position.
- Job creation freezes the selected combination, strategy identity/version, and final execution configuration. Workers and article audit snapshots use that frozen state even if the production line is edited before execution.
- Scheduled runs and production-line trial runs now execute the complete content workflow instead of stopping after collection. The material-first manual flow still uses scan jobs and stops at `waiting_topic`.
- Topic algorithms are managed from Topic Radar, not the automation editor. A scan selects one enabled algorithm and freezes its complete definition in the job snapshot. Manual material entry bypasses source collection and enters the retained material pool directly.
- This section is historical. The 2026-08-04 guarded delivery design supersedes its local-draft-only limit while keeping safe defaults and explicit publication gates.

## 项目目标

建立单租户、内部使用的 AI 自动内容运营后台，完成“采集并翻译 → 素材分类与精选 → 自动选题 → 事实包 → 写作与质量审核 → 排版 → 微信草稿/受控自动发布”的可恢复闭环。

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

- 默认交付为本地成稿；选择微信草稿时不会正式发布。自动正式发布必须同时通过策略、AI 质量审核、账号能力和全局紧急开关四层保护；微信未确认成功时不能显示“已发布”。
- 频道和模型凭证只保存密文，API 响应和日志只返回是否配置，不返回完整密钥。
- 删除来源、模型、频道和 Skill 使用停用/软删除，保留运行历史和审计记录。
- Skill 只允许 YAML、Markdown、示例和测试数据，不执行用户脚本。
- 旧 SQLite `create_all` 仅用于直接开发兼容；容器启动执行 `alembic upgrade head`。

## 测试与验证

- 后端：93 项 pytest 通过；本轮新增模块与迁移 Ruff check 通过；Python/Alembic 编译检查通过。
- 前端：Vitest 9 项通过；TypeScript 检查通过；Vite 生产构建通过；390、768、1280 px 核心页面无页面级横向溢出。
- Docker Compose 配置已完成；当前机器没有 Docker CLI，未执行 `docker compose config` 和容器验收。
- 前端构建仍有约 648 KB 单包警告，属于性能优化项，不影响构建成功。

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



