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

## M3 前置接口

| 领域 | 方法与路径 |
|---|---|
| Adapter 注册表 | GET /api/v1/adapters |
| 只读环境检测 | POST /api/v1/adapters/detect |
| 项目环境快照 | GET /api/v1/projects/{project_id}/adapter-environments |
| 生成物审计 | POST/GET /api/v1/generation-runs/{run_id}/audit |
| 项目自动审核 | POST/GET /api/v1/projects/{project_id}/automated-reviews |
| 自动审核详情 | GET /api/v1/automated-reviews/{review_id} |
| 编译准备 | POST/GET /api/v1/projects/{project_id}/compile-runs、GET /api/v1/compile-runs/{run_id} |
| 外部证据 | POST /api/v1/compile-runs/{run_id}/evidence |
| 参考模拟 | POST/GET /api/v1/projects/{project_id}/simulation-runs、GET /api/v1/simulation-runs/{run_id} |
| Trace | GET /api/v1/simulation-runs/{run_id}/trace |
| 交付候选 | POST/GET /api/v1/projects/{project_id}/release-candidates |
| 候选详情 | GET /api/v1/release-candidates/{candidate_id} |
| 只读监控计划 | POST/GET /api/v1/projects/{project_id}/monitoring-plans |
| 计划详情 | GET /api/v1/monitoring-plans/{plan_id} |
| 离线快照 | POST /api/v1/monitoring-plans/{plan_id}/snapshots |
| 监控证据 | GET /api/v1/monitoring-plans/{plan_id}/evidence |
| 调试任务 | POST /api/v1/monitoring-evidence/{evidence_id}/commissioning-tasks |

Adapter v1 能力固定为 detect_environment、get_capabilities、prepare_workspace_copy、compile、get_diagnostics、start_simulation、get_trace、export_vendor_project。ManualAdapter 对厂商操作只返回 manual_required/unverified，不会启动未知程序；reference 的模拟入口只代表 automatic_reference。

生成物审计绑定生成任务创建时的不可变 ProgramCommit，并再次核验 Control IR、TestSpec、ProgramArtifact 与锁定 MachineSpec 的内容哈希。审计报告按 audit_version + Commit 固定，重复请求复用同一结果；发现包含严重级别、文件/行号、稳定对象 ID、Excel 来源和恢复动作。

项目自动审核在生成 Commit 和内容寻址工件落库后自动触发，默认 repeat_count=20。报告固定包含不可变基线、重复生成、来源追溯、静态审计、参考执行器、变异检测和安全边界七项检查，以及五项 pending_external 外部验证门。POST 请求包含 generation_run_id、repeat_count（2–50）和 expected_generation_revision，并接受 If-Match；过期版本返回 409。

AutomatedReviewRun 以 generation_run_id、review_version 和 input_hash 唯一标识。相同不可变输入复用原报告和 SHA-256 工件，不覆盖历史；生成器版本、重复次数或基线变化会产生不同 input_hash。状态只有 passed 或 blocked，验证等级固定为 automatic。blocked 报告会保留当前生成基线并给出恢复动作，但禁止进入编译准备。

编译准备状态为 manual_required，前置条件是生成任务处于 review_ready、当前不可变 Commit 的项目自动审核存在且状态为 passed。证据上传携带 expected_revision，原件按 SHA-256 去重保存，任何证据均保持 manual_unverified。

参考模拟状态为 review_ready 或 failed，使用版本化 TestSpec DSL（当前 1.0）和受限表达式/赋值语法；不执行任意 Python、ST、Shell 或外部进程。结果绑定 ProgramCommit、TestSpecRevision、Control IR 和引擎版本，并保存不可变周期 Trace 工件。

交付候选创建必须绑定当前 GenerationRun、当前分支 head Commit、passed 自动审核、无 blocker 静态审计和当前 Commit 的 review_ready 参考模拟。分支存在未提交修改时返回 409。候选 ZIP 使用固定时间戳和排序条目生成，MANIFEST.json 记录基线、外部验证门、文件 SHA-256 与大小；相同 project_id + input_hash 只复用原候选。状态固定为 external_validation_required，验证等级固定为 automatic_package。

只读监控计划一对一绑定 ReleaseCandidate，变量白名单来自候选 Control IR，每项访问权限固定为 read_only。target_fingerprint 同时绑定项目、PLC 目标、候选 Manifest 和变量映射哈希。快照提交必须携带匹配指纹和 expected_plan_revision，只接受白名单内的 bool/int/float 离线值；证据固定为 manual_unverified。

CommissioningTask 只能由不可变 MonitoringEvidence 创建。系统从候选 ProgramCommit 派生 engineer/commissioning-* 分支，并复制 Control IR、TestSpec、ProgramArtifact 和 TraceLink 基线到新的 GenerationRun；后续修改形成新 Commit 和自动审核，不覆盖候选或来源历史。

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

## M3 安全与验证等级

- automatic_reference：仅指控谱参考逻辑模拟的自动结果；不等同于 GX Simulator3。
- unverified：厂商 Adapter、编译准备和环境能力尚未由真实工具验证。
- manual_unverified：外部日志、截图和报告已导入但没有集中验证签名。
- automatic：仅指项目级确定性代码审核已运行并满足其检查范围；不包含厂商工具、真实 PLC 或电气工程师确认。
- automatic_package：只表示候选 ZIP 已通过本机确定性打包和哈希门禁；不表示正式发布或厂商通过。
- awaiting_external_read_only_connection：只表示已生成未来只读连接所需的计划与指纹；当前没有在线连接。
- 本机未安装或未配置 GX Works3、GX Simulator3、MX Component 时，API 返回 unavailable 或 manual_required，不猜测版本、不执行任意命令。
- 详见 Adapter 安全与依赖矩阵文档。
