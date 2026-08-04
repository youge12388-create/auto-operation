# AI 自动内容运营系统(没写完还在更新)

V1 是单租户、内部使用的可配置 AI 内容运营后台，首个闭环为：

```text
信息源 → 选题 → 事实包 → 文章 → 审核 → 排版 → 微信公众号草稿
```

## 技术栈

- 后端：Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、PostgreSQL、Redis。
- 前端：React、TypeScript、Vite、Ant Design、TanStack Query、Vitest。
- AI：Fake Provider、OpenAI-compatible、Anthropic；Skill 只允许 YAML/Markdown/测试数据。
- 部署：Docker Compose，包含 API、Worker、PostgreSQL、Redis 和 Nginx 前端。

## 本地启动

1. 准备 Python 3.11、Node.js 20+、pnpm 和 Docker。
2. 复制 `.env.example` 到项目根目录 `.env`（供 Compose 使用），如需直接运行后端再准备 `backend/.env`；填写本地数据库、模型和微信公众号配置，不要提交真实密钥。
3. 启动基础服务：

```powershell
docker compose up -d
```

4. 后端直接开发启动：

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m content_ops.main
```

5. 前端：

```powershell
cd frontend
pnpm install
pnpm dev
```

默认地址：API `http://localhost:8000`，前端 `http://localhost:5173`。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m compileall -q src alembic

cd ..\frontend
pnpm test
pnpm lint
pnpm build
```

## 微信公众号边界

系统使用官方接口创建和更新草稿，凭证可通过环境变量或后台绑定账号提供。V1 默认进入草稿箱，人工确认后发布；接口超时或重复点击时使用“文章修订版本 + 频道账号 + 操作”幂等键避免重复草稿。

真实公众号联调、真实模型请求和 Docker 容器验收必须在具备对应外部权限的环境执行。本机若没有 Docker 或有效凭证，只能完成 Mock、静态和隔离数据库测试，不能把测试结果描述为真实发布成功。

更多当前状态见 [docs/PROJECT_STATE.md](D:/codex-all/wirter-agents/docs/PROJECT_STATE.md)。
