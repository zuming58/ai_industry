# Adapter 安全与依赖矩阵

更新日期：2026-08-29

## 范围和结论

M3 前置阶段只完成本机只读环境快照、确定性审计、受限参考模拟和厂商人工降级路径。当前不执行厂商命令，因此命令超时、进程沙箱和日志脱敏属于后续接入真实 Connector 前的强制门禁，不得因为文档存在而暗示已经具备厂商编译能力。

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

- 当前厂商检测只读取 KONGPU_GXWORKS3_PATH、KONGPU_AUTOSHOP_PATH、KONGPU_CODESYS_PATH 指向的存在性；不解析路径中的命令，不拼接 Shell 字符串，不启动程序。
- 工件目录、SQLite 数据库和项目 Git 仓库位于 .local-data/，原始工程、验证材料和黄金项目位于 .private/，两者均被 Git 忽略。
- 未来 Connector 必须为每个任务建立独立工作目录，使用显式允许根目录和 resolve() 后的路径守卫；拒绝 ..、UNC 未授权路径、符号链接逃逸和输出覆盖。
- 未来执行外部程序必须使用参数数组而非 Shell，设置固定命令超时、最大输出大小、退出码白名单和可回收临时目录；超时保留原日志并将任务置为 failed，不得自动重试危险操作。
- 当前不保存任何 PLC、厂商 IDE 或通信凭据；未来凭据必须由操作系统安全存储管理，不能进入 SQLite、日志、工件或前端响应。

## 日志、证据与供应链

- 外部日志、截图、报告以 SHA-256 内容寻址保存，原件不可覆盖；导入后验证等级为 manual_unverified，必须在集中验证包中由人工签名升级。
- 日志展示前应脱敏路径中的用户名、令牌、密码、IP 和序列号；原始证据只放 .private/validation/，不进 GitHub。
- 每个 Adapter 固定 adapter_id、契约版本和能力矩阵；环境快照记录平台、工具版本、目标型号、Adapter 版本、Commit、MachineSpec/Control IR/TestSpec 哈希和时间。
- 当前运行依赖见根目录 requirements.txt 与 kongpu-demo/package.json；M3 未增加新的第三方运行时依赖。后续发布前生成 SBOM、许可证清单和锁文件审计报告。

## 安全测试门

必须自动覆盖：环境变量命令注入、路径穿越、符号链接逃逸、超大文件、超时、恶意文件名、日志脱敏、工件哈希不一致、旧 Commit/旧 TestSpec 结果复用和并发 409。任何失败都只能阻断任务并保留证据，不能静默修复或覆盖基线。

## 当前未验证事项

本机未检测到 GX Works3、GX Simulator3、MX Component、FX5U 硬件和电气工程师签字。相关能力只能显示“未验证/待集中验证”，不能宣称可下载 PLC、可用于生产或已完成安全确认。
