# 开源与外部资料审计

核对日期：2026-08-29

## 使用原则

开源项目只用于可行性调研、隔离实验或前置检查候选。没有经过源码、许可证、版本、失败模式和目标厂商差异审计前，不进入生产依赖。开放编译器或软 PLC 的通过结果不能证明 FX5U/GX Works3 行为。

## 候选项目

| 项目 | 许可证/维护状态 | 可借鉴范围 | 限制与当前状态 |
|---|---|---|---|
| IEC Checker | LGPL-3.0；仓库未归档；2026-04 有更新 | IEC 61131-3/ST 与 PLCopen XML 的前置静态检查思路 | 方言和规则覆盖有限；未集成、未本机运行 |
| Beremiz | GPL-3.0；仓库未归档；2026-08 有更新 | 开放 IEC 工程、运行时和自动化 IDE 架构参考 | GPL 传播义务需法律审查；不等价于 FX5U；未集成 |
| MatIEC | GPL-3.0；仓库未归档；2026-08 有更新 | IEC 文本语言解析与转译参考 | 三菱 ST 方言、库和扫描语义不同；未集成 |
| OpenPLC Runtime v3 | GPL-3.0；仓库已归档 | 软 PLC、测试夹具和运行时接口的历史参考 | 已归档且不能代替厂商工具或硬件；不作为新底座 |
| Codesys-MCP | MIT；仓库未归档；2026-05 有更新 | Agent 工具契约、编译诊断和变量读取的实验参考 | 面向 CODESYS，不是 GX Works3；自动保存和在线写入必须隔离；未集成 |

许可证和维护数据来自对应 GitHub 仓库官方元数据。任何后续引入都必须固定 Commit、保存 LICENSE/NOTICE、生成 SBOM，并运行供应链和恶意行为审计。

## 官方与标准资料

- PLCopen IEC 61131-3：确认 ST 等语言定位。
- PLCopen XML 与 IEC 61131-10：用于交换格式参考，不保证厂商扩展无损互操作。
- GX Works3 官方产品页：确认目标工程环境，不证明存在完整第三方自动生成 API。
- MX Component v5 手册：为未来 GX Simulator3 与变量通信验证提供官方路径。

完整原始链接、主张、证据等级和未决项见 plc-ai-agent-research/evidence-ledger.md。

## 当前实现的来源边界

M1/M2 的解析器、规则、版本模型、Control IR 和 FX5U ST 骨架均为本仓库自主实现，没有复制上述 GPL/LGPL 项目代码。当前运行依赖的 Python/npm 包由清单管理；进入可发布安装包前仍需生成完整第三方许可证清单。

M3 前置的 Adapter 注册表、Manual/Reference Adapter 契约、生成物 Audit v1 和受限 TestSpec 参考模拟器同样为本仓库自主实现。参考模拟只使用 Python 标准库 ast 对白名单节点做解释，不加载或执行外部 ST/Python 代码；没有复制 Beremiz、MatIEC、OpenPLC 或其他 GPL/LGPL 实现。

当前没有新增运行时厂商依赖。GX Works3、GX Simulator3、MX Component、AutoShop 和 CODESYS 只作为未来人工验证目标，不被本机代码自动下载、启动或控制。任何未来引入的 Adapter 或开源库必须固定 Commit、保留 LICENSE/NOTICE、生成 SBOM，并通过权限、网络、文件写入、超时和回滚审计。

## 后续自主审计步骤

1. 为 IEC Checker 建立隔离 spike，固定版本并比较其结果与本项目规则；不通过则不集成。
2. 使用人工构造的公开 ST 夹具评估 MatIEC/Beremiz 语法覆盖，只作为前置反馈。
3. 对任何 Vendor Adapter 候选做源码完整性、预编译二进制、权限、网络、文件写入和回滚审计。
4. 将适用结果转成自动化回归测试；不能自动关闭的差异进入集中厂商验证包。
