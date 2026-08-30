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
可通过 KONGPU_MAX_UPLOAD_BYTES、KONGPU_MAX_ARTIFACT_BYTES、KONGPU_MAX_XLSX_UNCOMPRESSED_BYTES 和 KONGPU_MAX_XLSX_ENTRIES 调整本机输入上限；默认值分别为 20 MiB、150 MiB、100 MiB 和 2,000 条目。生产资料不应通过放宽限制绕过异常检查。

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

先验证由依赖清单生成的供应链产物没有过期：

    py -3.12 scripts/generate-supply-chain.py --check

依赖发生变化时，先用目标 CPython 3.12/Windows 环境解析并更新锁文件，再重新生成和审阅差异：

    py -3.12 -m pip install --dry-run --ignore-installed --only-binary=:all: --report .local-data/supply-chain-pip-report.json -r requirements.txt
    py -3.12 scripts/generate-supply-chain.py --pip-report .local-data/supply-chain-pip-report.json

    py -3.12 scripts/generate-supply-chain.py

然后运行代码、构建和浏览器门禁：

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

供应链生成器仅读取 requirements.txt、requirements-lock-win-py312.json 和 kongpu-demo/package-lock.json，不访问网络、.private/ 或 .local-data/；`--pip-report` 仅用于将用户已运行的 pip 解析报告规范化为锁文件。它生成 CycloneDX SBOM、依赖审计 JSON、第三方许可证清单和带哈希的 Python 安装锁；任何未固定/未评审的 Python 直接依赖、锁文件过期、发行哈希或许可证缺失、npm 许可证缺失或无法解析的依赖边都会使门禁失败。

## 备份与恢复

创建一致性备份：

    py -3.12 scripts/backup-local.py F:\Backups\kongpu-backup.zip

恢复前停止服务，并恢复到明确目录：

    py -3.12 scripts/restore-local.py F:\Backups\kongpu-backup.zip --data-dir F:\Codex\ai_industry\.local-data --confirm-overwrite

恢复脚本只接受带 `backup-manifest.json` 的 `kongpu-local-backup/v1` 归档。它先完整检查路径、重复条目、符号链接、压缩与解压大小、逐项 SHA-256 和 SQLite `PRAGMA quick_check`；全部通过后，才逐个原子替换 ZIP 中明确列出的数据库、工件和仓库文件。旧的无清单归档会被拒绝，任一预检失败都不会覆盖现有文件，恢复过程也不删除目录或无关文件。建议先恢复到单独临时目录并检查项目数、Alembic 版本和关键工件。

## 私有黄金项目

黄金资料只放入 .private/golden-project/，建议包含：

- 原机电对接表、I/O 表、动作/节拍表；
- 已完成的 FX5U 工程副本；
- GX Works3 精确版本、库版本和目标 CPU/模块清单；
- 预期动作、异常和验收记录。

原件不得提交 GitHub。测试中需要的公开夹具必须重新脱敏或人工构造。
