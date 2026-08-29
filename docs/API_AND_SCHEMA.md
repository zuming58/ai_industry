# API 与数据契约

## 入口

- OpenAPI UI：http://127.0.0.1:8000/docs
- OpenAPI JSON：http://127.0.0.1:8000/openapi.json
- MachineSpec JSON Schema：GET /api/v1/schemas/machine-spec/v1
- 前端生成类型：kongpu-demo/src/api/schema.d.ts

前端只通过 openapi-fetch 客户端访问后端。接口 ID 为 UUID，时间为 UTC ISO 8601；可变对象带 revision，过期写入返回 HTTP 409。

## M1 接口

| 领域 | 方法与路径 |
|---|---|
| 健康 | GET /api/v1/health |
| 项目 | GET/POST /api/v1/projects |
| 项目详情 | GET/PATCH /api/v1/projects/{project_id} |
| 归档 | POST /api/v1/projects/{project_id}/archive、restore |
| 模板 | GET /api/v1/template-versions/current |
| 模板下载 | POST /api/v1/projects/{project_id}/templates?kind=blank 或 example |
| 导入 | POST /api/v1/projects/{project_id}/imports |
| 导入读取 | GET /api/v1/imports/{import_id}、issues、sheets/{sheet} |
| 修订与校验 | PATCH /api/v1/imports/{import_id}/cells、POST validate |
| 审阅 | GET /api/v1/spec-revisions/{revision_id} |
| 确认/警告 | PUT confirmations/{view}、POST warnings/{issue_id}/accept |
| 锁定 | POST /api/v1/spec-revisions/{revision_id}/lock |
| 工件 | GET /api/v1/artifacts/{artifact_id} |

## M2 接口

| 领域 | 方法与路径 |
|---|---|
| 生成 | POST/GET /api/v1/projects/{project_id}/generation-runs |
| 生成详情 | GET /api/v1/generation-runs/{run_id} |
| 分支 | GET/POST /api/v1/projects/{project_id}/branches |
| 文件 | GET /api/v1/branches/{branch_id}/files |
| 文件内容 | GET/PATCH /api/v1/branches/{branch_id}/files/{path} |
| 提交 | POST /api/v1/branches/{branch_id}/commits |
| 历史 | GET /api/v1/projects/{project_id}/commits |
| Commit | GET /api/v1/commits/{commit_id}、diff |

## MachineSpec v1

顶层字段：schema_version、template_version、generated_at、project、plc_target、components、signals、sequence、interlocks、exceptions。

Excel 工作表：

- 必填：Instructions、Project、Components、Signals、Sequence；
- 选填：Interlocks、Exceptions；
- 隐藏元数据：_meta。

对象使用稳定 ID，显示名称与 ID 分离；跨对象关系只使用 ID；工程数值应携带单位；每个主要对象保存 source.sheet 与 source.row。

## 状态与错误

- 导入：uploaded → parsing → blocked 或 review_ready → reviewing → locked，目标变化后可为 stale。
- 生成：queued → generating → review_ready、blocked 或 failed。
- 问题级别：blocker、warning、suggestion、info。
- 错误响应：code、message、location、action。前端同时显示 message 与可恢复动作 action。

## 不可变与并发

- 上传原件按 SHA-256 内容寻址，页面编辑只创建新 revision。
- 锁定规格生成不可变 JSON 快照和内容哈希。
- 程序生成进入独立分支，保存与提交不覆盖已有 Commit。
- 文件路径经过仓库根目录守卫，拒绝路径穿越。
- expected_revision 或 If-Match 不匹配时返回 409，禁止静默覆盖。
