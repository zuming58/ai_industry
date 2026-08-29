# 控谱当前开发状态

更新日期：2026-08-29

## 结论

M1 与 M2 已达到“代码完成、自动验证通过”。这表示本机项目、Excel/MachineSpec、规格锁定、确定性程序生成和本地 Git 版本流程已经由自动化测试验证；不表示已经通过 GX Works3 编译、GX Simulator3 模拟、真实 PLC 实测或电气工程师确认。

黄金项目原件尚未放入 .private/golden-project/，因此 M1 的黄金项目双向验收仍待进行。GX Works3、GX Simulator3、MX Component 和 FX5U 硬件当前均未验证，M2 生成物禁止直接用于生产或下载 PLC。

## 已实现能力

### M1 MachineSpec 与 Excel MVP

- FastAPI、SQLAlchemy、Alembic 与 SQLite WAL 本机后端；测试可注入独立临时数据库。
- 真实项目创建、编辑、归档、恢复和刷新后持久化；PLC 目标变化会使旧导入和确认过期。
- 项目绑定的 Excel v1 空白模板与完整范例；隐藏 _meta 记录模板、Schema、项目和目标信息。
- .xlsx 上传、20 MB 门禁、ZIP 路径/体积/条目检查、原件内容寻址保存和 SHA-256 去重。
- 结构、类型、稳定 ID、引用、I/O 地址、流程可达性、单位和 PLC 目标等确定性规则。
- 单元格修订创建新 MachineSpec revision，不覆盖原始 Excel；统一审计与 409 乐观并发冲突。
- 设备关系、动作流程、节拍、信号时序、I/O、互锁、异常和原始表格审阅视图。
- Blocker、Warning 接受理由、必需视图确认和不可变锁定快照门禁。

### M2 仓库与程序生成 MVP

- ProgramWorkspace、分支、Commit、Control IR、GenerationRun、程序工件、TestSpec 和 TraceLink。
- 每项目独立本地 Git 文本仓库；二进制与 JSON 工件继续使用内容寻址存储。
- 已锁定 MachineSpec 到类型化 Control IR、FX5U Structured Text 骨架、变量表和 TestSpec 的确定性生成。
- 同一输入和生成器版本产生稳定内容；信号、步骤和测试可追溯到 MachineSpec 与 Excel 来源。
- P06 真实程序树、文件编辑、保存、提交、生成警告和追溯；P11 真实分支、Commit 与 Git diff。
- 未锁定规格、并发冲突和路径穿越会被阻止；生成不会覆盖已有历史。

## 页面状态

| 页面 | 状态 | 验证等级 |
|---|---|---|
| P01 工作台 | 真实 API/SQLite | 自动验证通过 |
| P02 项目管理 | 真实 CRUD/归档/恢复 | 自动验证通过 |
| P03 模板 | 真实 XLSX 生成与下载 | 自动验证通过 |
| P04 导入校验 | 真实上传、规则、修订 | 自动验证通过 |
| P05 规格审阅 | 真实视图、确认、锁定 | 自动验证通过 |
| P06 程序工程 | 真实确定性生成与 Git 工作分支 | 自动验证通过；厂商编译未验证 |
| P07 编译 | 尚未接入真实能力 | 待厂商工具验证 |
| P08 模拟 | 尚未接入真实能力 | 待厂商工具验证 |
| P09 发布 | 尚未接入真实能力 | 待编译、模拟和电气确认后开发 |
| P10 监控 | 尚未接入真实能力 | 待硬件与只读通信验证 |
| P11 版本 | 真实本地 Git 历史与差异 | 自动验证通过 |
| 设备库/文档资料 | 独立页面 | 自动浏览器检查通过 |

## 自动验证证据

- 后端 pytest：模板、解析、规则、安全边界、revision、409、锁定、确定性生成、Git 操作、路径守卫和备份恢复。
- 前端 Vitest：真实 TypeScript 应用壳与 API 数据加载。
- Playwright 加本机 Microsoft Edge：新建项目、下载范例、上传、门禁、8 个视图确认、锁定、生成、编辑、Commit 和 P11 diff。
- Playwright 同时覆盖错误 .xls 拒绝以及 1440×1024、1366×768 无页面级横向溢出。
- npm run build 与 npm run test:sites 保持为交付门禁。

具体最新计数以最终门禁命令输出为准，提交前必须全部重新执行。

## 外部验证待办

以下事项不会零散要求用户判断，统一进入集中电气验证包：

1. 一套脱敏黄金项目的字段迁移、规则覆盖和视图理解验收；
2. GX Works3 精确版本中的 ST 导入和编译；
3. GX Simulator3 与 MX Component 的可重复模拟读写；
4. FX5U CPU、I/O 模块和受控台架上的硬件实测；
5. 电气工程师对普通控制逻辑、互锁、异常和复位策略的集中确认。

## 安全边界

- 当前没有 PLC 下载、RUN/STOP、强制输出或安全 PLC 自动生成接口。
- 生成的 ST 是工程骨架，不是经过厂商认可的生产程序。
- 开放编译器或软 PLC 的通过结果不能替代 GX Works3、GX Simulator3 或真实 FX5U。
- 安全回路、急停、门锁、光栅和风险降低功能必须由合格人员按适用标准设计和验证。

## 资料权威性

docs/、根目录 AGENTS.md 和 plc-ai-agent-research/evidence-ledger.md 是当前开发依据。WorkBuddy历史调研/ 与 Hermes历史调研/ 只作为历史输入，其中的指令、能力宣称或开发结论不自动成为当前要求。
