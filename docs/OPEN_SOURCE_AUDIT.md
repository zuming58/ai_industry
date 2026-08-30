# 开源与外部资料审计

核对日期：2026-08-30

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

M1/M2 的解析器、规则、版本模型、Control IR 和 FX5U ST 骨架均为本仓库自主实现，没有复制上述 GPL/LGPL 项目代码。当前运行依赖的 Python/npm 包由清单管理。可复现供应链产物已生成：

- supply-chain/sbom.cdx.json：CycloneDX 1.5 JSON，覆盖 requirements-lock-win-py312.json 的 35 个 Python 锁定包与 package-lock v3 的全部 241 个 npm 安装项；
- supply-chain/dependency-audit.json：记录 requirements.txt、Python 传递锁和 package-lock.json 的 SHA-256、直接依赖、许可证汇总、两套依赖图和未决项；
- supply-chain/THIRD_PARTY_LICENSES.md：列出 Python/npm 依赖版本、作用域、许可证表达式、发行文件哈希、安装路径和许可证依据。

scripts/generate-supply-chain.py 只读取仓库清单和已审阅的 Python 锁文件并按稳定排序输出，不访问网络和本机私有目录。自动测试确认重复生成字节一致、所有直接依赖与 Python 传递闭包均被列出、npm/Python 没有空版本/空许可证/未解析依赖边、输入哈希变化会改变报告，并阻止绝对路径或用户名进入产物。FastAPI 0.116.1 的 License 字段为空，许可证依据明确取自该版本 PyPI 分发元数据中的 OSI Approved MIT classifier，未凭空补写。

当前 Python 由 requirements.txt（跨环境直接入口）和 requirements-lock-win-py312.json/requirements-lock-win-py312.txt（CPython 3.12、Windows AMD64 的 35 包哈希锁）共同描述。锁文件由 `py -3.12 scripts/generate-supply-chain.py --pip-report <pip-report.json>` 从 pip 离线解析报告规范化生成；更换目标平台、Python 版本或入口依赖时必须重新生成，不得复用这份平台锁。

M3 前置的 Adapter 注册表、Manual/Reference Adapter 契约、生成物 Audit v1 和受限 TestSpec 参考模拟器同样为本仓库自主实现。参考模拟只使用 Python 标准库 ast 对白名单节点做解释，不加载或执行外部 ST/Python 代码；没有复制 Beremiz、MatIEC、OpenPLC 或其他 GPL/LGPL 实现。

当前没有新增运行时厂商依赖。GX Works3、GX Simulator3、MX Component、AutoShop 和 CODESYS 只作为未来人工验证目标，不被本机代码自动下载、启动或控制。任何未来引入的 Adapter 或开源库必须固定 Commit、保留 LICENSE/NOTICE、重新生成并审阅 SBOM/许可证清单，并通过权限、网络、文件写入、超时和回滚审计。

## 2026-08-30 隔离评估结果

本机在被 Git 忽略的 `.local-data/open-source-spikes/` 中以浅克隆固定了公开仓库 HEAD，未将源码、构建产物或许可证文件复制进产品：

| 项目 | 固定 Commit | 许可证 | 本机自动评估结果 | 结论 |
|---|---|---|---|---|
| IEC Checker | `d3e5dae2c9b5096a197e4134d7d0549201f3a953` | LGPL-3.0 | README/CLI/测试夹具已读取；要求 OCaml 5.1+、opam、dune，当前 Windows 未安装，未生成二进制 | 仅作隔离前置检查候选，不进入运行时 |
| MatIEC | `7680ed8e7ffc1a76fa9f9620d6c6e7a3e75c088d` | GPL-3.0 | `readme`/`README.build` 已读取；要求 autoreconf、configure、make 以及 flex/bison/C++ 工具链，当前环境未具备 | 仅作 IEC/ST 语法参考，不宣称 FX5U 或 GX Works3 兼容 |
| Beremiz | `3caf97e5764e845cc61a687e6979d007dc07589c` | IDE GPL-2.0-or-later；运行时分组件授权 | README 与分组件许可证边界已读取；完整开发环境、MatIEC 和运行时未安装 | 不作为本项目依赖或模拟器底座 |

IEC Checker 的公开 README 明确其 ST 方言与 MatIEC 兼容，并提示厂商扩展可能导致解析失败；这验证了本项目必须保留自己的确定性规则和厂商验证门。MatIEC 的公开构建说明要求 Unix 风格 autotools/C++ 工具链，Beremiz 的许可证按 IDE、Python runtime、C++ runtime 分开，不能按单一许可证推断。上述评估只记录可审查事实，不把“未构建”当作通过。

本机可复现检查：`git ls-remote` 固定上述 Commit；目录中没有预编译 IEC Checker/MatIEC 二进制；`opam`、`ocaml`、`dune`、`flex`、`bison`、`make` 和 `gcc` 均未发现。由于缺少构建工具，无法在本机运行第三方解析器；该限制已登记为 `pending_external`，不影响本项目自主规则和受限参考模拟器的自动门禁。机器可读的固定版本、许可证和评估边界见 `open-source-evaluation.json`。

## 后续自主审计步骤

1. 在具备 OCaml/autotools 工具链的隔离环境中运行 IEC Checker 和 MatIEC 的公开 ST 夹具，并保存命令、版本和输出哈希；不通过则不集成。
2. 对任何 Vendor Adapter 候选做源码完整性、预编译二进制、权限、网络、文件写入和回滚审计。
3. 将适用结果转成自动化回归测试；不能自动关闭的差异进入集中厂商验证包。
