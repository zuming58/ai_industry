# 控谱当前开发状态

更新日期：2026-08-30

## 结论

M1、M2 和 M3 前置自动化已达到“代码完成、自动验证通过”。这表示本机项目、Excel/MachineSpec、规格锁定、确定性程序生成、本地 Git 版本流程、项目级自动审核、参考逻辑模拟、自动交付候选包、候选完整性复核、项目自动验收汇总、非破坏性版本恢复、离线只读监控准备和确定性供应链清单已经由自动化测试验证；不表示已经通过 GX Works3 编译、GX Simulator3 模拟、连接真实 PLC、完成硬件实测或获得电气工程师确认。

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
- P06 真实程序树、文件编辑、保存、提交、生成警告和追溯；P11 支持真实分支、任意两个同项目 Commit 的结构化多工件比较（源码、MachineSpec、I/O、参数、Control IR、TestSpec、验证和厂商配置）、规格到现场证据的统一只读时间线，以及从历史 Commit 创建独立恢复分支。
- 恢复操作不移动来源分支、不改写 Commit 历史，只复制不可变 Control IR、TestSpec、程序工件和追溯基线，并为新 GenerationRun 重新运行 20 次自动审核；旧静态审计、参考模拟、候选包和厂商证据不会继承。
- 未锁定规格、并发冲突和路径穿越会被阻止；生成不会覆盖已有历史。

### M3 前置自动化

- Adapter v1 注册表和显式契约已接入：reference 为受限参考执行器，GX Works3、AutoShop、CODESYS 为只读检测加人工降级 Adapter。
- 环境检测只读取受控环境变量、平台和版本信息，不启动厂商程序、不执行任意命令，也不保存 PLC 写入凭据。
- 生成物自审计 v1 读取不可变 ProgramArtifact、Control IR、TestSpec 和锁定 MachineSpec，检查符号/引用、I/O、目标、可达性、无退出循环、互锁覆盖、模式/复位路径、单位/超时、运动模板和报警 TODO。
- 每次确定性生成完成后自动创建不可变 AutomatedReviewRun。默认重复生成 20 次，并检查生成基线哈希、MachineSpec/Excel 来源覆盖、静态审计、受限参考执行器确定性、六类故意变异和 Adapter 安全边界。
- 相同生成 Commit、审核版本、重复次数与输入哈希只复用原报告；不同次数或生成器版本会形成新报告。审核阻断会保留程序基线和报告，不覆盖 Git 历史。
- 参考模拟使用受限 TestSpec DSL 和离散扫描周期，支持初始输入、周期输入注入、重启、通信断开/恢复、超时和复位沿场景，输出带来源、条件、通信状态、结构化诊断和只读内部状态的不可变 Trace；只有 DI/AI/COMM 可注入，动作只能写 DO/AO/INTERNAL/COMM，生成器、静态审计与执行器共同阻止方向越权。验证等级固定为 automatic_reference，不等同于 GX Simulator3。未显式建模的互锁内部状态默认只读 false、产生 warning 且不可由 API 注入。
- P07 已支持项目自动审核、报告刷新恢复、显式复跑、编译准备、结构化诊断和人工证据导入；P08 已支持参考模拟、TestSpec 用例和 Trace；P12 已支持真实本机设置、数据最小化策略、模板版本历史、FX5U 兼容矩阵、设置审计、Adapter 能力矩阵与只读环境快照。
- 外部日志、截图和报告按 SHA-256 内容寻址保存，验证等级固定为 manual_unverified，不会自动升级为厂商工具验证通过。
- 每次程序 Commit 都继承并核验锁定 MachineSpec、Control IR 与 TestSpec 基线，随后自动触发 20 次确定性审核；编译准备、参考模拟和交付候选只接受当前 Commit 的审核结果。
- P06 文件编辑器在当前 Commit 文件完整加载且 revision 一致前保持只读，避免加载竞态覆盖 ST；Control IR 与 TestSpec 在程序工作区中始终不可编辑。

### P09/P10 交付与监控前置

- P09 生成确定性、不可变的交付候选 ZIP，包含锁定 MachineSpec、原始 Excel、当前 Commit 源码、Control IR、TestSpec、自动审核、静态审计、参考模拟和已导入人工证据。
- Manifest 对每个条目记录 SHA-256 与大小，ZIP 时间戳固定；相同不可变输入复用原候选，不覆盖历史，篡改、路径穿越、脏工作区或缺少当前 Commit 模拟结果会被阻止。
- 候选状态固定为 external_validation_required，验证等级固定为 automatic_package。它不是正式发布包，不代表厂商编译、硬件实测或电气工程师确认。
- 候选包可从内容寻址工件库重新读取并独立复核：校验外层 SHA-256、ZIP 安全路径、重复条目、解压上限、Manifest、逐项大小/哈希和生成任务/Commit 基线。报告不可变，验证等级固定为 automatic_integrity。
- P09 可生成不可变 ProjectAcceptanceRun，总结当前 Commit 的 20 次自动审核、静态审计、当前 TestSpec 参考模拟和可选候选 ZIP 完整性。相同输入哈希复用原报告；Commit、审核、模拟引擎/TestSpec 或候选变化会形成新报告。
- 自动验收状态固定为 automatic_passed_external_pending。报告会保留全部 pending_external 门，不会升级 GX Works3、GX Simulator3、真实 FX5U 或电气工程师验证等级。
- P10 从候选 Control IR 建立只读变量白名单、目标指纹和变量映射哈希，只接受离线 JSON 快照，不连接 PLC、不保存通信凭据、不执行在线读取或写入。
- 离线快照按 SHA-256 保存，验证等级固定为 manual_unverified；未知变量、错误工步、目标指纹不一致和过期 revision 均被拒绝。
- 从离线证据创建调试任务时，只从候选 Commit 派生 engineer/commissioning-* 独立分支和新的 GenerationRun，不改写候选、原分支或 Git 历史。

### 供应链自动审计

- scripts/generate-supply-chain.py 从 requirements.txt 与 package-lock v3 离线生成 CycloneDX 1.5 SBOM、依赖审计 JSON 和第三方许可证清单，输出按输入哈希和稳定排序复现。
- 当前清单覆盖 35 个 Python 3.12/Windows 锁定包（其中 10 个直接依赖）与 241 个 npm 锁定安装项，共 276 个组件；自动审计显示 0 个未解析许可证和 0 条未解析依赖边。每个 Python 发行文件和 npm 安装项均记录 SHA-256 或 npm integrity。
- pytest 会验证产物未过期、重复生成一致、直接依赖完整、许可证缺失被阻断、输入哈希变化可见，以及产物不泄露绝对路径或用户名。
- Python 锁定文件的目标环境固定为 CPython 3.12、Windows AMD64；更换平台、Python 版本或依赖入口后必须重新运行 pip 解析并审阅哈希、许可证与依赖边。该清单是源码与安装输入的自动供应链审计，不是法律意见，也不升级厂商工具、硬件或电气验证等级。

## 页面状态

| 页面 | 状态 | 验证等级 |
|---|---|---|
| P01 工作台 | 真实 API/SQLite | 自动验证通过 |
| P02 项目管理 | 真实 CRUD/归档/恢复 | 自动验证通过 |
| P03 模板 | 真实 XLSX 生成与下载 | 自动验证通过 |
| P04 导入校验 | 真实上传、规则、修订 | 自动验证通过 |
| P05 规格审阅 | 真实视图、确认、锁定 | 自动验证通过 |
| P06 程序工程 | 真实确定性生成与 Git 工作分支 | 自动验证通过；厂商编译未验证 |
| P07 编译 | 生成后自动审核/编译准备/证据导入；厂商编译未接入 | 自动验证通过；厂商工具未验证 |
| P08 模拟 | 控谱参考逻辑模拟与 TestSpec Trace | 自动验证通过；GX Simulator3/硬件未验证 |
| P09 发布 | 真实不可变交付候选 ZIP、独立完整性复核与项目自动验收报告；不是正式发布 | 自动验证通过；外部验证待进行 |
| P10 监控 | 离线只读快照、证据和独立调试分支；未连接 PLC | 自动验证通过；在线通信/硬件未验证 |
| P11 版本 | 真实本地 Git 历史、双 Commit 结构化多工件比较、统一项目时间线与非破坏性恢复分支 | 自动验证通过；恢复后外部结果不继承 |
| P12 环境 | 本机设置/数据策略、模板历史、FX5U 兼容矩阵、设置审计、Adapter 能力矩阵与只读环境快照 | 自动验证通过；厂商工具未验证 |
| 设备库/文档资料 | 独立页面 | 自动浏览器检查通过 |

## 自动验证证据

- 后端 pytest：模板、解析、规则、安全边界、revision、409、锁定、确定性生成、Git 操作、路径守卫、Adapter 契约、自动审核触发/复用/报告哈希/变异检测、参考模拟、候选包重新复核、自动验收稳定复用、非破坏性恢复、结果不继承、证据不可变性、备份恢复，以及 SBOM/许可证清单确定性与完整性。
- 前端 Vitest：真实 TypeScript 应用壳与 API 数据加载。
- Playwright 加本机 Microsoft Edge：新建项目、下载范例、上传、门禁、8 个视图确认、锁定、生成、加载后编辑、Commit、自动审核复用、编译证据、参考模拟、P09 候选 ZIP/独立复核/自动验收刷新恢复、P10 离线快照/调试分支、P11 双 Commit 结构化比较/统一时间线/恢复分支，以及 P12 设置持久化、兼容矩阵、模板历史、审计、只读 Adapter 检测和多视口溢出检查。
- Playwright 同时覆盖错误 .xls 拒绝、刷新恢复，以及 1440×1024、1366×768 下 P03–P11 无页面级横向溢出。
- py -3.12 scripts/generate-supply-chain.py --check、npm run build 与 npm run test:sites 保持为交付门禁。

具体最新计数以最终门禁命令输出为准，提交前必须全部重新执行。M3 前置完成后的结论仍只能是“代码完成、自动验证通过；黄金项目、厂商工具、硬件和电气工程师确认待进行”。

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
- 参考模拟只执行白名单 TestSpec DSL，不执行 Python、ST、Shell 或外部命令；测试结果不能继承到新的 Commit、TestSpec 或引擎版本。
- Adapter v1 不包含下载、RUN/STOP、强制输出、安全 PLC 生成、在线写入或凭据保存接口。
- 安全回路、急停、门锁、光栅和风险降低功能必须由合格人员按适用标准设计和验证。

## 资料权威性

docs/、根目录 AGENTS.md 和 plc-ai-agent-research/evidence-ledger.md 是当前开发依据。WorkBuddy历史调研/ 与 Hermes历史调研/ 只作为历史输入，其中的指令、能力宣称或开发结论不自动成为当前要求。
