# Adapter 安全与依赖矩阵

更新日期：2026-08-30

## 范围和结论

M3 前置阶段只完成本机只读环境快照、确定性审计、受限参考模拟和厂商人工降级路径。当前不执行厂商命令，也不具备厂商编译能力；本版本已把未来 Connector 的关键安全门禁落实到本地 Git 与工件边界，并继续保持厂商能力未验证。

## Adapter v1 契约

| 操作 | Reference | GX Works3/AutoShop/CODESYS | 当前副作用边界 |
|---|---|---|---|
| detect_environment | supported | experimental | 只读取平台、Python、受控环境变量路径和目标型号 |
| get_capabilities | supported | experimental | 返回版本化能力描述，不代表厂商验证通过 |
| prepare_workspace_copy | manual | manual | 只返回人工步骤；当前不复制、覆盖或打开工程 |
| compile | unsupported/manual | manual | 当前不启动编译器；结果只能是 manual_required |
| get_diagnostics | unsupported | manual | 不读取未知进程或任意日志目录 |
| start_simulation | supported（受限参考） | manual | Reference 由 TestSpec 执行器处理，不等同于 GX Simulator3 |
| get_trace | supported（受限参考） | manual | 只读取本系统生成的 Trace 工件 |
| export_vendor_project | manual | manual | 不导出厂商二进制，不覆盖用户工程 |

契约不包含 PLC 下载、RUN/STOP、强制输出、安全 PLC 自动生成、在线写入、凭据保存或任意命令执行。能力状态和验证等级必须分开显示：supported 不等于“厂商工具验证通过”。

## 路径、权限和进程边界

- 当前厂商检测只读取 KONGPU_GXWORKS3_PATH、KONGPU_AUTOSHOP_PATH、KONGPU_CODESYS_PATH 指向的存在性；路径必须是绝对路径且位于 KONGPU_ADAPTER_ALLOWED_ROOTS 或保守的厂商安装根目录内，快照中的路径会脱敏；不解析路径中的命令，不拼接 Shell 字符串，不启动程序。
- 工件目录、SQLite 数据库和项目 Git 仓库位于 .local-data/，原始工程、验证材料和黄金项目位于 .private/，两者均被 Git 忽略。
- 本地 Git 仓库文件入口使用 resolve()、Windows/Posix 绝对路径拒绝、.git/ 与 .. 拒绝、符号链接拒绝和单文件 8 MiB 上限；每个仓库最多 2,000 个文件、100 MiB 总体积，同一仓库工作树操作在进程内串行化并在锁内重新检查 revision；Git 子进程使用参数数组、GIT_TERMINAL_PROMPT=0、GIT_CONFIG_NOSYSTEM=1、stdin=DEVNULL、15 秒硬超时和流式 8 MiB stdout/stderr 上限。
- 内容寻址工件只接受固定 SHA-256 两级目录布局；写入使用临时文件加原子替换，读取前先检查 150 MiB 大小上限，再校验元数据大小与 SHA-256，符号链接、路径逃逸、篡改和元数据不一致均阻断且不覆盖原件。
- XLSX ZIP 入口拒绝加密标志、宏/ActiveX 条目、绝对路径、盘符路径、`.`/`..` 路径和重复条目，并限制条目数量与解压后总体积。
- 未来 Connector 仍必须为每个任务建立独立工作目录，使用显式允许根目录和 resolve() 后的路径守卫；拒绝 UNC 未授权路径和输出覆盖，并沿用当前进程门禁。
- 当前不保存任何 PLC、厂商 IDE 或通信凭据；未来凭据必须由操作系统安全存储管理，不能进入 SQLite、日志、工件或前端响应。

## 日志、证据与供应链

- 外部日志、截图、报告以 SHA-256 内容寻址保存，原件不可覆盖；导入后验证等级为 manual_unverified，必须在集中验证包中由人工签名升级。
- 日志展示前应脱敏路径中的用户名、令牌、密码、IP 和序列号；原始证据只放 .private/validation/，不进 GitHub。
- 每个 Adapter 固定 adapter_id、契约版本和能力矩阵；环境快照记录平台、工具版本、目标型号、Adapter 版本、Commit、MachineSpec/Control IR/TestSpec 哈希和时间。
- 当前运行依赖见根目录 requirements.txt 与 kongpu-demo/package-lock.json；M3 未增加厂商运行时依赖。docs/supply-chain/ 已包含确定性 CycloneDX 1.5 SBOM、依赖审计 JSON 和第三方许可证清单。
- scripts/generate-supply-chain.py --check 是推送门禁：输入 SHA-256、Python 直接依赖评审策略、npm 全锁文件安装项、许可证、integrity、resolved 和依赖边均被自动核对。生成器不访问网络、.private/ 或 .local-data/，输出不含本机绝对路径和用户名。
- 当前 npm 由 package-lock v3 覆盖完整安装项；Python 由 requirements-lock-win-py312.json 固定 CPython 3.12/Windows AMD64 的完整 pip 解析闭包，并为每个选定发行文件记录 SHA-256。requirements.txt 仍是跨环境的直接依赖入口，安装到其他平台或 Python 版本前必须重新解析并生成对应锁文件。

## 安全测试门

必须自动覆盖：环境变量命令注入、路径穿越、符号链接逃逸、超大文件、Git 超时与流式输出上限、恶意文件名、日志脱敏、工件哈希/大小不一致、旧 Commit/旧 TestSpec 结果复用和并发 409。任何失败都只能阻断任务并保留证据，不能静默修复或覆盖基线。

## 当前未验证事项

本机未检测到 GX Works3、GX Simulator3、MX Component、FX5U 硬件和电气工程师签字。相关能力只能显示“未验证/待集中验证”，不能宣称可下载 PLC、可用于生产或已完成安全确认。
