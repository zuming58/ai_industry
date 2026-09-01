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
| 校验报告 | GET /api/v1/imports/{import_id}/validation-report?kind=json、markdown 或 xlsx |
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
| Commit 比较 | GET /api/v1/commits/{base_commit_id}/diff/{target_commit_id} |
| 项目时间线 | GET /api/v1/projects/{project_id}/timeline |
| 恢复分支 | POST /api/v1/commits/{commit_id}/restore-branches |

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
| 本机就绪度预检 | GET /api/v1/projects/{project_id}/readiness?generation_run_id=... |
| 候选详情 | GET /api/v1/release-candidates/{candidate_id} |
| 候选验证材料 | GET /api/v1/release-candidates/{candidate_id}/validation-material?kind=json 或 checklist |
| 候选完整性复核 | POST /api/v1/release-candidates/{candidate_id}/verify |
| 项目自动验收 | POST/GET /api/v1/projects/{project_id}/acceptance-runs |
| 自动验收详情 | GET /api/v1/acceptance-runs/{acceptance_id} |
| 只读监控计划 | POST/GET /api/v1/projects/{project_id}/monitoring-plans |
| 计划详情 | GET /api/v1/monitoring-plans/{plan_id} |
| 离线快照 | POST /api/v1/monitoring-plans/{plan_id}/snapshots |
| 监控证据 | GET /api/v1/monitoring-plans/{plan_id}/evidence |
| 调试任务 | POST /api/v1/monitoring-evidence/{evidence_id}/commissioning-tasks |

## P12 本机设置与兼容性接口

| 领域 | 方法与路径 |
|---|---|
| 本机设置 | GET/PATCH /api/v1/settings |
| 设置审计 | GET /api/v1/settings/audit |
| 模板版本历史 | GET /api/v1/template-versions |
| FX5U 兼容矩阵 | GET /api/v1/compatibility-matrix |

`PATCH /api/v1/settings` 必须携带当前 `expected_revision`，只接受模型端点、模型名称和三项数据最小化开关。模型端点必须为不含凭据、查询参数或片段的 `http`/`https` 基础地址；未知字段（包括 `api_key`）被拒绝。设置冲突返回 HTTP 409，空变更返回 422。

设置数据库只保存非敏感配置；模型密钥没有对应字段，不会落库、返回、写日志或进入工件。模型状态 `configured_unverified` 只表示端点已填写，不表示模型服务、回答质量或任何工程验证已通过。设置审计仅保存 changed keys，不保存设置值。

兼容矩阵固定区分 `automatic`、`automatic_reference`、`unverified`、`pending_external` 和 `excluded`。FX5U Structured Text 生成和控谱参考逻辑模拟仍不等同于 GX Works3/GX Simulator3；真实工具、FX5U 硬件和电气工程师确认继续属于集中外部验证。

Adapter v1 能力固定为 detect_environment、get_capabilities、prepare_workspace_copy、compile、get_diagnostics、start_simulation、get_trace、export_vendor_project。ManualAdapter 对厂商操作只返回 manual_required/unverified，不会启动未知程序；reference 的模拟入口只代表 automatic_reference。

生成物审计 v2 绑定生成任务创建时的不可变 ProgramCommit，并再次核验 Control IR、TestSpec、ProgramArtifact 与锁定 MachineSpec 的内容哈希。IEC/ST 标识符按不区分大小写的语义比较，但诊断保留原始拼写；审计 `input_hash` 显式包含 `audit_version`、生成器版本和全部不可变输入，版本变化不会复用旧报告。发现包含严重级别、文件/行号、稳定对象 ID、Excel 来源和恢复动作。

项目自动审核在生成 Commit 和内容寻址工件落库后自动触发，默认 repeat_count=20。报告固定包含不可变基线、重复生成、来源追溯、静态审计、参考执行器、变异检测和安全边界七项检查，以及五项 pending_external 外部验证门；变异检测覆盖断引用、断流程、危险操作、互锁删除、条件翻转行为、缺反馈和任意代码注入，来源 ID 按 IEC/ST 不区分大小写比较。POST 请求包含 generation_run_id、repeat_count（2–50）和 expected_generation_revision，并接受 If-Match；过期版本返回 409。

AutomatedReviewRun 以 generation_run_id、review_version 和 input_hash 唯一标识。相同不可变输入复用原报告和 SHA-256 工件，不覆盖历史；生成器版本、重复次数或基线变化会产生不同 input_hash。状态只有 passed 或 blocked，验证等级固定为 automatic。blocked 报告会保留当前生成基线并给出恢复动作，但禁止进入编译准备。

编译准备状态为 manual_required，前置条件是生成任务处于 review_ready、当前不可变 Commit 的项目自动审核存在且状态为 passed。证据上传携带 expected_revision，原件按 SHA-256 去重保存，任何证据均保持 manual_unverified。

参考模拟在进入执行前会拒绝重复或仅大小写不同的信号 ID/名称、工步 ID 和异常 ID，避免这些标识符在内部映射中被静默覆盖。

参考模拟状态为 review_ready 或 failed，使用 `kongpu-reference-v2`、版本化 TestSpec DSL（当前 1.0）和受限表达式/赋值语法；不执行任意 Python、ST、Shell 或外部进程。信号、工步、互锁和 TestSpec 引用遵循 IEC/ST 不区分大小写语义；仅大小写不同的歧义定义或重复输入会被确定性拒绝。请求可携带 `input_overrides`、按周期的 `input_schedule`、`restart_cycles`、`disconnect_cycles`、`max_cycles` 和 `cycle_time_ms`。只有 DI、AI 和 COMM 可作为外部输入；动作只能写入 DO、AO、INTERNAL 和 COMM，TestSpec 生成与静态审计使用同一方向门禁。未知字段、未知信号、方向不匹配、非有限数值、越界周期及同周期重启/断线均被拒绝。结果绑定 ProgramCommit、TestSpecRevision、Control IR 和引擎版本，并保存不可变周期 Trace 工件；引擎版本变化不能继承旧结果。Trace 分离动作执行前的外部信号 `inputs`、本周期 `outputs` 和只读 `internal_state`，同时记录入口/完成条件、Excel 来源、通信状态、事件与结构化诊断；历史仅含事件数组的记录仍可读取。未显式建模的互锁内部状态只在参考执行器中按只读 `false` 处理并产生 warning，不能通过 API 注入，也不代表现场状态。

交付候选创建必须绑定当前 GenerationRun、当前分支 head Commit、passed 自动审核、无 blocker 静态审计和当前 Commit 的 review_ready 参考模拟。分支存在未提交修改时返回 409。候选 ZIP 使用固定时间戳和排序条目生成，MANIFEST.json 记录基线、外部验证门、文件 SHA-256 与大小；同时包含 `validation/EXTERNAL_VALIDATION_PACKAGE.json` 和 `validation/EXTERNAL_VALIDATION_CHECKLIST.md`，两者绑定当前 PLC Profile、锁定规格哈希、Program Commit、生成器、TestSpec 和外部验证门。相同 project_id + input_hash 只复用原候选。状态固定为 external_validation_required，验证等级固定为 automatic_package；验证包中的 `manual_unverified` 不会被 ZIP 生成或证据上传自动升级。

候选级外部证据使用 `GET/POST /api/v1/release-candidates/{candidate_id}/evidence`。上传字段为 `file`、固定枚举 `evidence_kind`、可选 `note` 与 `expected_candidate_revision`，并接受 `If-Match`；上限 20 MB。原件进入 SHA-256 内容寻址工件库，同一候选、同一类型、同一源工件重复上传时复用原记录。证据类型固定为 `environment`、`vendor_import`、`vendor_compile`、`vendor_simulation`、`hardware_test`、`electrical_signoff` 和 `other`。所有上传结果固定为 `manual_unverified`，只进入候选证据台账和项目时间线，不修改不可变候选 ZIP/Manifest，不改变 `external_validation_required` 状态，也不升级厂商工具、硬件或电气验证等级。

候选证据台账可通过 `GET /api/v1/release-candidates/{candidate_id}/evidence-ledger?kind=json|markdown` 导出。导出为只读操作，JSON 使用 `kongpu-release-evidence-ledger/v1` 契约，Markdown 适合打印或集中验证时填写；两种格式均绑定候选版本、Manifest/ZIP SHA-256、GenerationRun、Program Commit、Git SHA、MachineSpec/Control IR/TestSpec 哈希、生成器版本、外部验证门和全部候选级证据原件哈希。台账的 `as_of` 取候选及证据更新时间，内容按稳定顺序生成并通过 ETag 返回；导出不会创建版本、改变候选 revision 或升级任何验证等级。

就绪度预检为只读接口，按当前生成任务的锁定规格、分支 head Commit、自动审核、静态审计、参考模拟、候选 ZIP 和候选完整性复核逐项返回 `ready`/`remaining`。响应还按当前 PLC Profile 返回 `prerequisites.software`、`prerequisites.hardware` 和 `prerequisites.validation_scope`，供 P09 直接生成集中验证准备清单。全部本机门满足时状态为 `ready_for_external_validation`，但 `external_validation_gates` 仍保持 `pending_external`；预检不创建工件、不修改版本，也不升级厂商、硬件或电气验证等级。

候选完整性复核会重新读取内容寻址 ZIP，并核对外层工件 SHA-256、路径穿越、重复条目、条目数与解压体积上限、包内 Manifest、逐项 SHA-256/大小，以及 GenerationRun/ProgramCommit 基线。相同候选内容只复用原 ReleaseCandidateVerification；验证等级 automatic_integrity 只表示 ZIP 完整性自动验证通过。

ProjectAcceptanceRun 绑定 GenerationRun、当前 ProgramCommit、AutomatedReviewRun、GenerationAudit、SimulationRun，以及可选的 ReleaseCandidateVerification。输入记录包含生成器、审核、审计、参考模拟引擎、TestSpec 和报告工件哈希；相同 project_id + input_hash 复用原报告。状态固定为 automatic_passed_external_pending，所有厂商工具、真实 PLC、安全回路和电气工程师门继续保持 pending_external。

只读监控计划一对一绑定 ReleaseCandidate，变量白名单来自候选 Control IR，每项访问权限固定为 read_only；变量与工步定位遵循 IEC/ST 不区分大小写语义，仅大小写不同的重复变量、未知变量和非有限值会被确定性拒绝。target_fingerprint 同时绑定项目、PLC 目标、候选 Manifest 和变量映射哈希。快照提交必须携带匹配指纹和 expected_plan_revision，只接受白名单内的 bool/int/float 离线值；证据固定为 manual_unverified。

CommissioningTask 只能由不可变 MonitoringEvidence 创建。系统从候选 ProgramCommit 派生 engineer/commissioning-* 分支，并复制 Control IR、TestSpec、ProgramArtifact 和 TraceLink 基线到新的 GenerationRun；后续修改形成新 Commit 和自动审核，不覆盖候选或来源历史。

Commit 比较只能在同一 ProgramWorkspace 中执行，使用两个明确 Git SHA 直接读取仓库对象，不依赖当前工作树。响应遵循 `kongpu-version-comparison/v1`，除兼容保留的 unified `diff` 外，按源码、MachineSpec、I/O 映射、组件/工程参数、Control IR、TestSpec、生成配置、自动验证摘要和厂商配置摘要返回 added/removed/changed 对象、字段 before/after、Excel 来源和稳定 `comparison_hash`。厂商配置节固定标记 `unverified`，不代表 GX Works3 或硬件验证。恢复接口从历史 Commit 创建 restore/* 独立分支、新 GenerationRun 和分支内 ProgramCommit；来源分支 head 不移动，旧审计、模拟、候选和外部证据均不继承，新基线只自动生成独立 AutomatedReviewRun。

项目时间线遵循 `kongpu-project-timeline/v1`，只读聚合 AuditEvent、MachineSpecRevision、GenerationRun、ProgramCommit、AutomatedReviewRun、GenerationAudit、CompileRun、SimulationRun、ReleaseCandidate、ProjectAcceptanceRun、AdapterEnvironment 和现场/外部证据。每条事件包含 UTC 时间、作者、触发请求、工具、结果、验证等级、实体定位和原始摘要；事件按时间倒序稳定排列，并严格按 project_id 隔离。时间线不创建或升级任何验证结论，厂商工具、真实 PLC、硬件和电气工程师状态仍保持未验证。

时间线可通过 `GET /api/v1/projects/{project_id}/timeline/export?kind=json|markdown` 导出。JSON 保留完整 `kongpu-project-timeline/v1` 结构；Markdown 按 UTC 时间和事件类型稳定排序，适合外部验证包打印归档。导出是只读操作，响应通过 ETag 标识内容哈希，不修改项目、审计或版本记录。

## PLC Profile v1

项目目标由版本化 Profile 校验，当前自动验证范围包含：

| Profile | 目标 | Adapter | 自动能力 | 厂商/硬件未验证边界 |
|---|---|---|---|---|
| `mitsubishi-fx5u-st-v1` | 三菱电机 MELSEC iQ-F：FX5U/FX5UC | `gxworks3` | MachineSpec、保守 IEC ST、静态审计、控谱参考模拟 | GX Works3/GX Simulator3、FX5U 硬件和电气确认 |
| `inovance-h5u-st-v1` | 汇川技术 H5U：H5U-1614MTD-A8、H5U-3232MTD-A8 | `autoshop` | MachineSpec、保守 IEC ST、静态审计、控谱参考模拟 | AutoShop 直接地址绑定/编译/模拟、H5U 硬件和电气确认 |

每个 Profile 还公开结构化验证前置条件：`required_software`（需要安装并由工程师确认版本的软件）、`hardware_prerequisites`（CPU、模块、电源和受控负载等硬件清单）以及 `external_validation_scope`（必须在厂商工具或台架上执行的验证项）。这些字段会随 P09 候选包写入 `prerequisites`，便于集中验证时直接使用；它们是待验证清单，不代表本机已安装或已通过验证。

汇川 Profile 首批只接受 `X/Y/M` 逻辑地址格式。生成器不会为 H5U 写入未经公开资料和实机验证的 `AT` 地址绑定，而是在 ST 变量注释和 Control IR 中保留逻辑地址；因此本机结果是“自动验证通过”，不是 AutoShop 编译通过。

## MachineSpec v1

导入版本读取响应同时返回 `source_artifact_id`，P04 可通过通用工件接口下载原始 Excel；该下载只读并校验 SHA-256，原件永不覆盖。导入校验报告可通过 `GET /api/v1/imports/{import_id}/validation-report?kind=json|markdown|xlsx` 导出。JSON 使用 `kongpu-validation-report/v1` 契约，绑定项目与 PLC 目标、ImportVersion、原始 Excel 工件 SHA-256、模板/Schema、当前 MachineSpec revision 及内容哈希，并按 blocker、warning、suggestion、info 汇总完整问题定位。问题按等级、工作表、行、列、code 和 ID 稳定排序；响应使用 ETag 标识内容哈希。`xlsx` 是从不可变原件派生的标记副本，在问题单元格添加等级颜色和批注，并新增 `ValidationReport` 汇总工作表；它不会覆盖原始 Excel。三种报告导出均为只读操作，不创建持久化工件、不修改 import/revision/status/确认/锁定状态，也不升级厂商工具、硬件或电气验证等级。

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
- 工件读取先检查数据库元数据、磁盘大小和 SHA-256，再加载内容；单个工件默认上限 150 MiB，异常会返回 `ARTIFACT_TOO_LARGE`、`ARTIFACT_SIZE_MISMATCH` 或 `ARTIFACT_HASH_MISMATCH`。
- XLSX 只接受未加密 `.xlsx`：拒绝绝对路径、盘符路径、`.`/`..` 内部路径、重复 ZIP 条目、宏/ActiveX 内容和超限解压体积。
- 每个项目 Git 工作树在进程内按仓库串行化；可变请求取得锁后重新读取 revision，文件写入先整体校验并采用临时文件原子替换。仓库限制为最多 2,000 个文件、100 MiB 总体积、单文件 8 MiB。

## M3 安全与验证等级

- automatic_reference：仅指控谱参考逻辑模拟的自动结果；不等同于 GX Simulator3。
- unverified：厂商 Adapter、编译准备和环境能力尚未由真实工具验证。
- manual_unverified：外部日志、截图和报告已导入但没有集中验证签名。
- automatic：仅指项目级确定性代码审核已运行并满足其检查范围；不包含厂商工具、真实 PLC 或电气工程师确认。
- automatic_package：只表示候选 ZIP 已通过本机确定性打包和哈希门禁；不表示正式发布或厂商通过。
- automatic_integrity：只表示已存候选 ZIP 重新读取后通过结构、Manifest、内容哈希与基线复核；不表示厂商或硬件通过。
- automatic_passed_external_pending：只表示项目自动门已汇总通过且外部门仍明确待验证；不是最终验收通过。
- awaiting_external_read_only_connection：只表示已生成未来只读连接所需的计划与指纹；当前没有在线连接。
- 本机未安装或未配置 GX Works3、GX Simulator3、MX Component 时，API 返回 unavailable 或 manual_required，不猜测版本、不执行任意命令。
- 详见 Adapter 安全与依赖矩阵文档。
