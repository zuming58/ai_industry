# 调研：可借鉴的开源项目 + CODESYS MCP 能否直接用（2026-08-27）

> 背景：镇江比赛放弃，方向不变——AI 赋能自动化（PLC 自动编程 + 故障诊断）。本篇回答两个问题：①现成的开源轮子有哪些 ②报告里说的 CODESYS MCP Server 能不能直接调用。

## 一、CODESYS MCP Server 能不能直接调用？——能，免费开源，但要分清两条路

| 路径 | 是什么 | 费用 |
|------|--------|------|
| **官方 AI-Supported Engineering** | CODESYS Professional Developer Edition 里的付费订阅功能 | 付费（CODESYS 开发环境订阅约2000美元/年量级） |
| **社区开源 MCP 工具包** | GitHub 上的开源项目，把 CODESYS IDE 的脚本引擎包装成 MCP Server | **零费用，MIT 协议，只付模型 token** |

### 可直接用的开源项目（都是社区版，全部免费）

| 项目 | GitHub | 特点 |
|------|--------|------|
| **codesys-mcp-toolkit**（Johannes Pettersson） | github.com/johannesPettersson80/codesys-mcp-toolkit | 教程最多，实测在 V3.5 SP22 Patch 1 跑通，配合 Claude Code 从建POU到编译读错全流程 |
| **Codesys-MCP-Server**（PhilipLykov） | github.com/PhilipLykov/Codesys-MCP-Server | MIT 协议，npm 安装（codesys-mcp-sp21-plus），支持 SP21+ |
| **Codesys-MCP**（luke-harriman） | github.com/luke-harriman/Codesys-MCP | 最全：41个工具+3资源，SP19/SP20 带界面持久模式，可在线读写 PLC 变量（read_variable / connect_to_device），SP21+ 走无头模式 |

### 直接调用的前提（缺一不可）

1. 本机装 **CODESYS V3.5**（SP19~SP22，各项目支持版本不同；个人学习用可免费下载）
2. **Node.js 18+**
3. 任意 MCP 客户端：Claude Desktop / Claude Code / Cursor / Codex CLI / Gemini CLI 都行
4. 原理：MCP Server 通过 CODESYS 自带的 **Script Engine（IronPython 脚本引擎）** 操控 IDE——建工程、建POU、写变量声明、写ST实现、触发编译、读回错误、AI自动修复，甚至登录 PLC 在线读写变量

**结论：不用自己写 MCP Server，clone 下来配个 .mcp.json 就能跑。这部分是"直接调用"，不是"借鉴"。**

## 二、关键坑：汇川 InoProShop ≠ 标准 CODESYS，MCP 大概率不能直接接

调研确认的事实：

1. InoProShop 是基于 **CODESYS Automation Platform 深度定制**的 IDE——内核是 CODESYS Runtime，但硬件驱动、EtherCAT 协议栈、汇川运动控制库全锁在自己 IDE 里
2. 地址映射机制被汇川重构过，**原版 CODESYS 工程直接导入编译会报错**
3. 开源 MCP 项目依赖的 Script Engine 接口，InoProShop 是否保留**未验证，大概率不完整**
4. **AutoShop（H5U/Easy系列）根本不是 CODESYS 体系**，跟 MCP 完全无关

### 汇川生态的可行接入路径（按优先级）

1. **PLCopen XML 交换格式**（首选）——IEC 61131-3 标准导出导入格式，CODESYS 系 IDE 都支持。Agent 生成 ST/PLCopen XML → InoProShop 导入 → 编译 → 错误回传 → AI 修复。不依赖脚本引擎，最稳
2. **实测 InoProShop 脚本接口**——装一个看看有没有 scriptengine 入口，有就照标准项目包一层
3. 先在**标准 CODESYS V3.5 上跑通全闭环**（学习成本最低、轮子最全），汇川适配作为第二阶段

## 三、TIA（西门子）生态：开源轮子已经多到用不完

国内工控公众号已汇总 GitHub 上 **28 个 TIA Openness/MCP 项目**，重点：

| 项目 | 特点 |
|------|------|
| **TIA_Portal_Openness_MCP**（linux.do 热帖起源） | 预编译 exe，V20/V21，建项目/写SCL/生成WinCC画面/编译诊断一条龙 |
| **TiaMCP-v2**（spyshow） | Openness API 包装完整，Gemini CLI/Claude/Codex 都能接 |
| **tia-portal-mcp**（Czarnak，MIT） | V21，支持交叉引用诊断、编译诊断、批量安全写入 |
| **tiacommander-mcp** | 16工具166动作，覆盖硬件组态到下载，商业化最完整 |

**含义：西门子生态的"AI写PLC"已经卷成红海，轮子随便捡；但全是通用工具，垂直行业（非标设备工艺知识）层依然是空的——之前 02 号文件的判断不变，反而更成立。**

## 四、故障诊断方向：现成开源项目可直接借鉴

| 项目 | 架构 | 借鉴价值 |
|------|------|---------|
| **plc-log-explainer-local**（adityamhaske） | FastAPI + ChromaDB + Ollama(Mistral 7B) + Next.js，全本地，Docker 一键部署 | **跟我们的demo架构几乎一模一样**：报警日志+手册PDF → RAG → 根因/证据/排查步骤/置信度。直接抄架构 |
| **tracefault**（mono0826，中文项目） | Neo4j 故障知识图谱 + LangGraph 多智能体 + Streamlit | 设备手册/故障案例/维修记录建图谱，混合检索（图+向量），前端可视化。第二阶段升级路线 |
| **Manufacturing-ExcH-Agents**（德国硕士论文） | MSRGuard runtime 监控 PLC/OPC UA 信号 + KG Agent vs RAG Agent 对比实验 | 有完整 benchmark 数据，验证了"知识图谱 vs RAG"两条路线的效果差异，写方案时引用 |

## 五、对本项目的结论

1. **诊断 Agent demo：不从零写**——plc-log-explainer-local 的架构直接借鉴（全栈开源、全本地部署、Docker化），把它的通用手册换成汇川故障码手册 + 老王的调试记录
2. **编程 Agent demo：直接用现成 MCP**——装标准 CODESYS V3.5 SP22 + codesys-mcp-toolkit，两天能跑通"自然语言→ST→编译→自动修复"闭环，作为技术验证
3. **汇川落地：走 PLCopen XML 路线**，不要指望脚本引擎
4. **风险提示**：所有开源项目都是 0.x 版本（社区个人维护），demo 没问题，产品化要自己加固；InoProShop 的 PLCopen XML 导入对汇川定制库的兼容性需实测
5. **竞争判断更新**：西门子侧工具已经红海、汇川侧生态空白的判断进一步确认——AM 系列的第三方 MCP 生态确实还是零

## 六、知乎抓取补充（opencli，2026-08-27）

### RealPLC 最新动向（08-22发文）——最重要的竞品情报

产品形态已定：**RealPLC Agent = 云端配对 + 设备侧 Agent Core + TIA/CODESYS 独立 Connector + 一次性验证 Worker**。关键信息：

1. **验证闭环全免费**：ST生成 → 静态检查 → CODESYS编译 → 下载到 **Win V3 x64 软PLC仿真** → 跑 TestSpec → 验证通过/失败。用用户已有软件和许可证（CODESYS SP18 + Win V3 x64），零额外授权成本——**这套"软PLC仿真验证"路线我们可以直接抄**
2. MCP 被定位为**可选的 AI 接口层**，不做内部总线（内部走 Named Pipe + gRPC）——架构判断和开源社区一致
3. 真实 PLC 下载/写变量默认关闭、必须审批——工业安全共识
4. **仍在内部测试，未发布**——时间窗口还在
5. 它做的是通用 Agent 框架，**依然不做垂直行业知识库**——我们的定位不受冲击，反而它发布后可以当我们的底座用

### 108 Bug 研究警示（Hello工控 07-17 引用 STMut 论文）

研究人员往 ST 程序埋 108 个 bug 测 AI：**编译通过远远不等于代码可靠**（`AND` 改 `OR` 照样编译通过但逻辑全变）。结论：AI 生成的 PLC 代码必须过"编译 + 仿真测试 + 安全属性验证"三关，不能靠大模型自审。→ **我们 demo 的验证环节必须包含软PLC仿真，不能只做语法校验**（06 号文件里"语法校验"的设计要升级）。

### 其他实战情报

- **CODESYS MCP 2026年2月大更新**，Claude Code 成为官方贡献者（04-04 报道）——生态在加速
- **国内已有工程师用 WorkBuddy/Codex + CODESYS MCP 修真实产线编译错误**（08-13，多工位印刷线，CODESYS IDE 3.5.22 + MCP Server 1.1.0）——路线已有人跑通，且有完整配置指南可参考
- **冶金电炉大智能体**（08-20）：DeepSeek + WinCC 实时数据 + PLC 交互 + 语音对话诊断炉况，agent 只出策略建议、人工验证执行——诊断 Agent 的分寸感（建议不执行）是行业共识
- 欧姆龙宣布训练自有工业大模型（07-21）——通用大模型不懂真实工厂，安全联锁规则散落在 PLC/驱动器/继电器/规程多处，垂直知识仍是壁垒

## 来源

- controlbyte.tech：CODESYS MCP Server + Claude Code 实测教程（含安装步骤）
- github.com/luke-harriman/Codesys-MCP（41工具清单原文）
- lobehub.com/mcp/philiplykov-codesys-mcp-server（MIT协议、安装方式）
- Hello工控公众号：GitHub 28个 TIA Openness/MCP 项目汇总帖
- openai-hub.net：TIA_Portal_Openness_MCP 深度实测（含坑：上下文漂移、工具缓存）
- tsight.io 两篇：汇川 InoProShop 与 CODESYS 内核关系拆解（兼容性陷阱）
- github.com/adityamhaske/plc-log-explainer-local、mono0826/tracefault、verkal1999/Manufacturing-ExcH-Agents
- 知乎（opencli 抓取）：zhuanlan.zhihu.com/p/2074594310918616352（RealPLC 架构与免费闭环）、p/2061550957503189394（108 Bug 研究）、p/2071274218113742335（CODESYS MCP 配置实战）、p/2023861050387230844（CODESYS MCP 更新）
