# 本机开发与运行

## 环境

- Windows 10/11
- Python 3.12
- Node.js 与 npm
- Git
- Microsoft Edge（Playwright E2E 使用本机 Edge，不要求另行下载 Chromium）

## 首次安装

在 F:\Codex\ai_industry 执行：

    py -3.12 -m pip install -r requirements.txt
    Set-Location kongpu-demo
    npm ci
    Set-Location ..

.env.example 是配置样例。真实 .env、.private/ 和 .local-data/ 不进入 Git。

## 启动

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1

默认地址：

- Web：http://127.0.0.1:5173/
- API：http://127.0.0.1:8000
- OpenAPI：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

启动脚本执行 Alembic 迁移并分别启动 Web/API。日志与 PID 保存到 .local-data/。脚本只启动未运行的服务，不删除现有数据。

## 演示种子

    py -3.12 scripts/seed-demo.py

种子会通过真实 API 与业务逻辑建立 FX5U 示例、锁定规格并生成程序工作区。它不表示厂商编译、模拟或硬件通过。

## 质量门禁

    py -3.12 -m pytest
    Set-Location kongpu-demo
    npm run typecheck
    npm run test
    npm run build
    npm run test:sites
    npm run test:e2e
    Set-Location ..
    git diff --check

Playwright 启动独立的 8010 API、5174 Web 和临时 SQLite 数据目录，不修改正式 .local-data。

## 备份与恢复

创建一致性备份：

    py -3.12 scripts/backup-local.py F:\Backups\kongpu-backup.zip

恢复前停止服务，并恢复到明确目录：

    py -3.12 scripts/restore-local.py F:\Backups\kongpu-backup.zip --data-dir F:\Codex\ai_industry\.local-data --confirm-overwrite

恢复脚本逐个覆盖 ZIP 中明确列出的数据库、工件和仓库文件，不删除目录或无关文件。建议先恢复到单独临时目录并检查项目数、Alembic 版本和关键工件。

## 私有黄金项目

黄金资料只放入 .private/golden-project/，建议包含：

- 原机电对接表、I/O 表、动作/节拍表；
- 已完成的 FX5U 工程副本；
- GX Works3 精确版本、库版本和目标 CPU/模块清单；
- 预期动作、异常和验收记录。

原件不得提交 GitHub。测试中需要的公开夹具必须重新脱敏或人工构造。
