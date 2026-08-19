# GitHub Actions + 宝塔部署

## 部署方式

合并到 `main` 后，`CI` 工作流先完成后端和前端验证。验证成功后，`Deploy to Baota` 从 GitHub Runner 打包该次合并的精确提交，通过 SSH 上传到宝塔服务器，再执行 `scripts/deploy-baota.sh`。

服务器不需要访问 GitHub。部署脚本适配当前宝塔运行结构：

- 发布目录：`/opt/content-ops/release`
- Python：`/opt/content-ops/venv/bin/python`
- API 服务：`content-ops-api.service`
- Worker 服务：`content-ops-worker.service`
- Nginx 前端目录：`/opt/content-ops/release/frontend-dist`
- 生产配置：`/opt/content-ops/release/backend/.env`
- SQLite 数据：`/opt/content-ops/release/backend/data`

脚本会先在临时目录解压并安装依赖，保留生产 `.env`、SQLite 数据和存储目录，然后停止 API/Worker，替换发布目录并健康检查。失败时恢复上一份备份；不会执行数据库迁移。

## GitHub 配置

在仓库 Settings → Environments 中创建 `production` 环境，并为该环境设置以下 Secrets：

```text
BAOTA_HOST=114.132.180.230
BAOTA_SSH_PORT=22
BAOTA_SSH_USER=<部署用户>
BAOTA_PROJECT_DIR=/opt/content-ops
BAOTA_SSH_PRIVATE_KEY=<部署用户私钥，整段粘贴>
BAOTA_KNOWN_HOSTS=<服务器 SSH 主机公钥，整行粘贴>
```

不要把私钥、服务器 `.env` 或数据库文件提交到仓库。生产环境建议使用专用部署用户，仅授予执行发布脚本和重启两个 systemd 服务的权限；不要长期使用 root 私钥。

## 触发与回滚

- `push` 到 `main` 不会绕过 CI；只有 CI 成功后才触发部署。
- 也可以在 Actions → Deploy to Baota → Run workflow 手动部署指定 SHA。
- 每次发布会在 `/opt/content-ops/backups/` 保留上一版本。
- 回滚前先停止服务，将当前 `release` 移走，再把目标备份目录恢复为 `release`，然后启动两个 systemd 服务并检查 `/health`。
