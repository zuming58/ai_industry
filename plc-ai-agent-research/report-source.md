# AI-assisted PLC Engineering and Fault Diagnosis

## Independent Feasibility and Technical Stack Research

**研究日期：** 2026-08-27  
**目标市场：** 苏州及周边非标自动化设备企业  
**首选对象：** 汇川 H5U/AutoShop；三菱 FX5U/GX Works3 作为闭环备选  
**结论性质：** 产品与技术决策基线；未通过本地测试的厂商接口均明确标记为假设

## Executive Summary

这个方向现实可行，但可行的产品不是“把设备描述给大模型，大模型一次性写完整 PLC 程序并直接下发”。可行形态是一个工程编排与验证系统：机械和电气工程师共同形成结构化设备规格，确定性模板生成大部分控制骨架，LLM 负责自然语言转结构、歧义发现、文档检索和有限修复，目标厂商编译器与模拟器负责闭环验证，电气工程师保留批准和下载权限。

PLC 编程与故障诊断应共享同一份设备数字规格。设计阶段定义的元件、信号、步骤、互锁、报警、时序和恢复策略，正是运行阶段判断“命令发了没有、反馈为什么没到、当前卡在哪一步、哪些原因更可能”的上下文。故障码只能说明某个设备报告了什么，通常不能单独回答整机为什么停机。

厂商选择上，业务上应优先汇川，技术上必须设置退出条件。汇川官方资料确认 H5U、EtherCAT、功能块和运动控制能力，也能从运动文档中找到诸如 `0x603F` 故障码与 `0x6041` 状态字等诊断对象；但公开官方资料没有证实 AutoShop 存在稳定通用的 CLI、COM 或 LSP，也没有证实 InoProShop 可以无损完成任意工程的 PLCopen XML 往返。[汇川 H5U 用户指南](https://portal-file.inovance.com/owfile/ProdDoc/SC/19011517-SC/A02/19011517-SC_A02%E3%80%8AH5U%20Series%20Programmable%20Logic%20Controller%20User%20Guide%E3%80%8B-EN.pdf) 与[汇川运动控制编程指南](https://portal-file.inovance.com/owfile/ProdDoc/SC/19012378-SC/A00/19012378-SCY_A00%20Medium-sized%20PLC%20Programming%20Guide%20%28Motion%20Control%29-EN.pdf)支持控制与诊断能力判断，却不能证明工程软件自动化接口。

公开的 [AutoShopAgentInterface](https://github.com/xianruiyang/AutoShopAgentInterface) 是重要线索：仓库声明可以导出/应用 H5U 工作区 JSON、处理 ST、设备配置，并通过 Windows UI 自动化进行编译、下载、监控等操作。然而该项目规模小、包含预编译代理，完整源码、二进制来源、AutoShop 版本兼容、失败回滚、许可和真机可靠性都要审计。因此建议先投入两周做隔离环境技术验证，而不是立即把整个产品押在它上面。

如果 AutoShop 闭环不稳定，第一条可验证的厂商链路转为三菱。GX Works3 有官方模拟能力，MX Component 官方手册提供与 GX Simulator3 的连接路径，可由测试程序读写模拟 PLC 数据；即使首版需要人工导入一次代码，也能保留“程序—模拟输入—输出/状态—测试报告”的可信闭环。[GX Works3 产品资料](https://www.mitsubishielectric.com/fa/products/cnt/plcf/pmerit/concept/gx_works3.html)、[FX5 仿真 FAQ](https://fa-faq.mitsubishielectric.com/faq/show/22327)和 [MX Component v5 手册](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh082395eng/sh082395engh.pdf)构成了比传闻更可靠的验证基础。

边缘硬件可以形成产品壁垒，但不是第一阶段。车间小盒应是可靠的只读数据网关：采集、时间戳、缓冲、规则、签名和安全传输。大模型可以运行在企业内网的工作站或服务器，不需要把高性能台式机搬到机台边。采集盒不应同时持有 PLC 下载权限；生成的代码差异进入工程工作站，经工程师审批、厂商编译、模拟和受控下载。首版甚至不需要硬件盒，先用模拟器、导出的 Trace/CSV 和手工日志证明诊断价值。

## 1. 为什么这个方向值得做

### 1.1 用户拥有难以复制的工程上下文

通用软件团队通常缺少非标设备的机构模式、机电交接方式、节拍经验、调试失败和恢复知识。用户与电气伙伴恰好覆盖机械—电气—控制—现场之间的真实断点。这种跨岗位知识比单纯“会调用模型 API”更接近商业壁垒。

### 1.2 PLC 工程具有机器可验证反馈

PLC 程序至少可以接受语法/类型检查、目标厂商编译、模拟执行、时序断言和真机 FAT/SAT。研究已经开始探索用在线编译反馈改善 ST 生成，也有 RAG 和多 Agent 的 PLC 代码生成原型，但这些结果只说明反馈闭环有价值，不能直接推出生产现场的自主部署。[在线编译反馈研究](https://arxiv.org/abs/2410.22159)与 [AutoPLC](https://arxiv.org/abs/2412.02410)都更支持“检索 + 工具反馈 + 迭代”的路线，而不是一次性自由生成。

### 1.3 同一设备模型能贯通设计与运维

如果设计阶段只生成 ST 文本，价值在代码交付时结束。如果建立可追踪的设备规格，则运行时故障数据可以反向关联到执行元件、步骤、互锁、报警、手册和验收测试；调试中发现的问题又能回填为模板和案例。长期资产是跨项目复用的机构控制模块与验证证据。

## 2. 产品应解决什么问题

首要问题不是替 PLC 工程师“按一下按钮写完整程序”，而是减少非标项目中重复且容易遗漏的工程劳动：

1. 把机械交接资料中的隐性含义变成完整、无冲突的控制规格；
2. 自动生成重复性强的 I/O 映射、机构功能块、顺序骨架、报警和 HMI 接口；
3. 把需求同时变成测试，而不是写完程序后才临时想怎样试；
4. 在厂商环境反复编译、模拟、收集证据并形成可审计报告；
5. 故障发生时把设备上下文和时序证据组织成工程师可执行的排查树；
6. 把每次调试修复沉淀为有版本、有适用范围的企业资产。

目标用户不是被替代的 PLC 工程师，而是机械、电气和调试团队。早期销售价值应表述为“缩短交接、基础编程、测试和排障时间，同时提高一致性”，而不是无人化编程。

## 3. 正确的输入：从机电对接表到 MachineSpec

PLCopen 对 IEC 61131-3 语言和 XML 交换已有标准化工作；AutomationML 面向机械、电气和控制跨域交换，PackML 则适合统一设备顶层状态与模式。[PLCopen IEC 61131-3](https://www.plcopen.org/standards/logic/iec-61131-3/)、[PLCopen XML](https://www.plcopen.org/standards/xml-echange/)、[AutomationML domain model](https://www.automationml.org/industrial-application/domain-model/)和 [ISA TR88/PackML 预览](https://www.isa.org/getmedia/300dbd50-d549-41ac-b372-a5e52f32fc97/tr_880002_preview.pdf)可作为未来互操作参照。

但 MVP 不应一开始实现庞大的标准全量模型。建议用九张用户可理解的工作表：Project、Components、Signals、Hardware、Sequences、Interlocks、Alarms、ParametersAndTiming、AcceptanceTests，再归一化为版本化 JSON Schema。它比原先“三张表”多出来的互锁、报警和验收测试，恰好决定程序是否能安全恢复、诊断是否有上下文、测试是否能证明工艺正确。

每个步骤必须至少说明：进入条件、输出动作、完成反馈、超时、报警、下一步、预计时间、手动行为和重启策略。每个报警必须说明：触发、反应、锁存、复位条件、操作员文本和应保存的证据信号。安全相关项只记录为不可变约束和外部接口，绝不让普通 Agent 自动实现。

PLCopen XML 很有用，但不能当成“写一次就能在所有厂商无损运行”的承诺。IEC 61131-10/PLCopen XML 允许供应商扩展，导入工具要选择和解释这些信息，厂商库、任务模型、图形布局和语义差异依然存在。[IEC 61131-10 说明](https://www.plcopen.org/standards/logic/iec-61131-10/)明确了交换格式定位。因此内部 MachineSpec 和厂商适配器仍然必要。

## 4. 代码生成：模板和状态机是骨架，LLM 是助手

首版生成对象应严格受限：标准双位气缸、简单伺服定位轴、变频器、工站顺序、手自动模式、报警管理、I/O 映射和 HMI 接口。每种机构对应经过电气工程师评审的功能块模板、参数约束和测试包。

LLM 可以：

- 把口述动作转成候选结构字段；
- 发现“只有动作，没有完成反馈”“有报警，没有复位条件”等歧义；
- 从对应版本手册中寻找指令和报警解释；
- 根据编译错误提出最小范围修复；
- 解释生成差异和测试失败。

LLM 不应：

- 绕过 Schema 直接生成完整自由文本工程；
- 发明不存在的地址、库、运动指令或安全逻辑；
- 自动改变安全功能；
- 直接控制工程软件下载到生产 PLC；
- 把自己的解释当作验证证据。

研究显示商业 ST 方言和执行语义存在差异，开放实现本身也可能有缺陷；K-ST 的工作在数百个程序上探索 ST 语义并发现开放实现中的问题，这正说明通用解析器和软 PLC 不能替代目标厂商验证。[K-ST](https://arxiv.org/abs/2202.04076)提供了很好的反例证据。

## 5. 验证：编译通过只是中间站

可信闭环至少有九层：数据完整性、工程规则、静态检查、厂商编译、正常仿真、异常注入、变异测试、工程师评审、FAT/SAT。

IEC Checker 可对 ST 和 PLCopen XML 执行一部分编程规范检查；Beremiz/MatIEC 可用于开放环境的早期语义检查和快速运行。[IEC Checker](https://github.com/iec-checker/iec-checker)和 [Beremiz 概览](https://beremiz.readthedocs.io/en/latest/overview.html)适合作为前置工具，但不能证明汇川或三菱的运动库与扫描行为。

测试必须由规格同时生成。正常测试之外，要覆盖传感器始终不来、两个互斥反馈同时到、通信断开、动作超时、手自动切换、报警复位、掉电重启和保持变量等。还要做变异测试：有意翻转一个条件、删掉一个互锁或改变一个比较符，确认现有测试能失败。新的 [STMutants](https://arxiv.org/abs/2606.05499)研究说明 PLC 测试生成本身也需要用变异来衡量，而不是只看测试是否跑完。

## 6. 汇川路线的现实判断

### 6.1 已确认

H5U 是适合中小型机器和运动控制的目标，官方资料支持 EtherCAT、功能块、通信与 PLCopen 风格的运动能力。伺服/运动资料也能提供状态字、错误码和 PDO/SDO 对象，为未来诊断提供真实数据基础。[H5U-INT flyer](https://portal-file.inovance.com/owfile/ProdDoc/CY/19120525-CY/A00/19120525-CY_A00%E3%80%8AH5U-INT%20Series%20PLC%20Flyer-EN%E3%80%8B20241230_Web.pdf)与 [SV660 brochure](https://portal-file.inovance.com/owfile/ProdDoc/CY/19120119-CY/A01/19120119-CY_A01%E3%80%8ASV660%20Series%20Servo%20Drives_EN%E3%80%8B20220602_Web.pdf)进一步支持这一点。

### 6.2 未确认

没有找到汇川官方公开资料证明 AutoShop 拥有稳定、受支持、可用于商业产品的 CLI/COM/LSP；也没有找到 InoProShop 对完整项目 PLCopen XML 往返的官方承诺。第三方资料提到在 InoProShop 中用 PLCopen XML 导入功能块库，只能证明特定使用方式，不能外推为完整工程可移植。[第三方 PLCopen XML 教程](https://fashionstar.com.hk/wiki/industrial/plc/inovance-inoproshop/)应保持 C 级证据。

### 6.3 OpenCLI 补充发现

通过 OpenCLI 对 Gitee、Brave、Google 和 arXiv 做了补充检索。它发现了 [ECatSim](https://gitee.com/openwcs/ecat-sim) 这一面向 InoProShop 的软件 EtherCAT 从站项目，以及 [plc-skills](https://gitee.com/plccode/plc-skills) 这一 PLC Agent 技能知识库。两者都规模很小、尚未完成本地复现，只能进入“可参考实验项目”清单，不能提升为产品依赖。OpenCLI 的 AutoShop Web 结果大多是软件下载站和教程，没有补出官方自动化 API 证据；这进一步强化了“接口必须本地验证”的结论，而不是证明接口不存在。

### 6.4 决策

因为汇川与用户市场最匹配，先做它；因为接口证据不足，只给两周和十项验证门。业务优先不等于忽略工程风险。

## 7. 三菱与 CODESYS 的角色

三菱作为第一备用平台。官方资料表明 GX Works3 支持 IEC 风格语言和模拟；MX Component 可与 GX Simulator3 通信，为外部测试驱动提供官方路径。尚未确认的是完整工程自动生成接口，因此产品可以暂时接受一次人工导入，再自动完成测试。这样仍然比完全依赖未证实接口更可信。

CODESYS 是参考实现和实验后端。官方 MCP 目前支持读取工程、修改 ST POU、编译和错误反馈，但要求 CODESYS V3.5 SP22+ 与 Professional Developer Edition；官方 Scripting 也能从命令行执行脚本。[CODESYS AI-supported engineering](https://www.codesys.com/products/engineering/ai-supported-engineering/)、[MCP release lifecycle](https://www.codesys.com/ecosystem/release-lifecycle/releases-updates/development-system-mcp-server/)和[命令行脚本文档](https://content.helpme-codesys.com/en/CODESYS%20Scripting/_cds_starting_script_via_command_line.html)说明行业正在形成 Agent 化工程接口。但这不能外推为所有 CODESYS 定制平台都有同等能力。

[社区 Codesys-MCP](https://github.com/luke-harriman/Codesys-MCP)提供大量工具，是快速实验的材料；其不同 CODESYS 版本采用不同模式，且存在自动保存、无撤销等高风险行为，必须在副本工程和隔离环境使用。

## 8. 故障诊断：为什么必须喂工艺和时序

仅凭故障码，系统通常只能回答“这个驱动报告了过流/编码器/通信等类别”。要回答“为什么本工站在举升步骤失败”，还要知道：PLC 是否发出命令、使能是否存在、到位反馈是否变化、气压或机械负载是否正常、上一步是否释放互锁、报警出现前几秒哪些信号变化、最近是否换过电机/参数/程序。

CiA 402 规范把驱动状态和实际量映射到 PDO，但设备支持的子集和厂商实现会影响互换性。[CiA 402 overview](https://www.can-cia.org/can-knowledge/cia-402-series-canopen-device-profile-for-drives-and-motion-control)支持“状态字是证据，不是根因”的判断。

建议每次诊断自动形成证据包：设备与程序版本、当前模式/步骤、5–30 秒时序、报警/状态字、命令/反馈、通信质量、操作员现象、最近变更、已做检查和手册版本。诊断输出固定为：

1. 已知事实与来源；
2. 缺失证据；
3. 候选原因及支持/反对证据；
4. 优先级最高且低风险的区分性检查；
5. 需要停机、上锁挂牌或专业人员参与的风险提示；
6. 若涉及代码，生成离线差异和回归测试。

FaultGPT 和工业设备故障咨询等研究显示语言/视觉模型在工业问答上有潜力，但仍是研究系统，不能代替企业自己的标注案例和安全流程。[FaultGPT](https://arxiv.org/abs/2502.15481)与[工业设备故障咨询研究](https://arxiv.org/abs/2410.03223)适合证明“值得验证”，不适合证明“已经可靠”。

## 9. 边缘盒：什么该放在盒子里

### 9.1 盒子承担

- OPC UA、Modbus TCP 或经批准的厂商协议只读采集；
- 高精度时间戳、质量码、断线缓存和循环存储；
- 简单状态规则、数据压缩、证据包签名；
- 设备/程序版本绑定；
- 到企业内网服务的白名单通信；
- 本地健康监控和可恢复升级。

OPC UA 本身提供认证、加密、签名、审计和角色机制，适合作为优先接口之一，但仍要由 PLC 项目显式暴露诊断变量并配置只读权限。[OPC UA overview](https://opcfoundation.org/about/opc-technologies/opc-ua/)与[角色权限规范](https://reference.opcfoundation.org/specs/OPC-30142/6.7)支持这一架构。

### 9.2 盒子不承担

- 不持有生产 PLC 下载凭据；
- 不自动修改或写入控制逻辑；
- 不默认运行大型模型；
- 不用普通网口假装完成 EtherCAT 无侵入抓包；
- 不在安全回路中承担控制职责。

被动 EtherCAT 分析通常要把专用 TAP/监测设备插入链路，并掌握网络描述和 PDO 映射。Beckhoff ET2000 和 EtherCAT Technology Group 的 mirror TAP 产品都体现了专用硬件路径。[Beckhoff ET2000](https://www.beckhoff.com/en-en/products/i-o/ethercat-development-products/elxxxx-etxxxx-fbxxxx-hardware/et2000.html)、[ETG mirror TAP](https://www.ethercat.org/en/products/C08A14A0872A46B28DA3F90CE45C74A8.htm)。因此它应属于高级诊断选件。

开源 [Neuron](https://github.com/emqx/neuron)可作协议网关候选，但当前开源范围主要集中在 Modbus/MQTT，多种工业驱动在商业产品中；不能沿用历史调研中“开源版覆盖所有主流协议”的假设。[Neuron dashboard README](https://github.com/emqx/neuron-dashboard/blob/master/README.md)也明确提示了开源功能和维护状态。

### 9.3 模型部署

企业数据不出厂时，大模型可运行在厂内工作站或服务器，通过 OpenAI-compatible gateway 统一接入。车间盒只把经过授权的数据送到内网服务。具体模型和 GPU 不应在调研阶段拍脑袋固定：先用真实任务集测规格补全、代码补丁、手册问答、诊断 Top-3、拒答、延迟和显存，再决定采用多大模型和是否量化。

## 10. 安全、责任与商业边界

机械安全控制必须遵循组织的风险评估、设计和验证流程。ISO 13849-1:2023、ISO 13849-2 与 IEC 62061:2021分别涉及安全相关控制系统设计和验证。Agent 首版不得生成、修改或旁路急停、门锁、光栅、安全速度/位置等功能；它只能记录安全约束、检查普通逻辑是否越界，并把事项交给具备资格的责任人。[ISO 13849-1](https://www.iso.org/standard/73481.html)、[ISO 13849-2](https://www.iso.org/standard/53640.html)、[IEC 62061](https://webstore.iec.ch/en/publication/59927)。

网络上应把生成服务、工程工作站、采集网关与控制网络分区，采用默认拒绝、按需允许、最小权限和可审计数据流。NIST SP 800-82 Rev.3 是适合参考的 OT 安全框架。[NIST SP 800-82 Rev.3](https://csrc.nist.gov/pubs/sp/800/82/r3/final)。

商业化还需要处理：厂商 EULA 是否允许自动化控制 IDE、第三方二进制能否再分发、GPL/LGPL 与闭源产品的组合方式、客户工程数据的归属、模型供应商的数据保留政策、诊断建议责任和安全免责声明。所有这些必须在试点合同前明确。

## 11. 建议的首版技术栈

- 前端：React + TypeScript；
- 本地/服务器 API：Python 3.12 + FastAPI；
- 模型与校验：Pydantic v2 + JSON Schema；
- 项目/审计数据库：PostgreSQL，单机原型可用 SQLite；
- 文件与大产物：哈希目录或 MinIO；
- 时序：MVP 用 Parquet/SQLite，规模化再上 TimescaleDB；
- 检索：PostgreSQL 全文 + 可选 pgvector，优先型号/版本/章节过滤；
- 生成：类型化 IR + 版本化功能块/状态机模板；
- 测试：pytest 风格测试定义 + 厂商模拟器适配器 + 时序断言；
- LLM：统一兼容网关，可切换云端与本地，不把模型名称写死在业务层；
- Windows 厂商工具：官方 API/CLI 优先，UI 自动化封装成独立、可替换、锁版本的适配器；
- 边缘：容器化只读采集服务，硬件规格在现场数据验证后确定。

不建议 MVP 同时引入复杂 Agent 框架、多个向量库、大型时序平台和自研硬件。流程首先是一个清晰的有限状态工程工作流：Draft → Validated → Generated → Compiled → Simulated → Reviewed → Released。可审计状态比“多个 Agent 自由协商”更重要。

## 12. 时间、团队与现实预期

四周可以做出展示，但不能完成生产可信的双功能产品。更现实的安排是：

- 2 周：黄金项目与 AutoShop/三菱适配器验证；
- 4–6 周：MachineSpec、检查器和确定性生成；
- 4–6 周：首厂商编译/仿真/报告闭环；
- 约 4 周：离线故障诊断 MVP；
- 8–12 周：在前面有效后进行只读现场试点与私有化。

核心小团队至少需要：用户负责机械/工艺与客户场景，电气伙伴负责 PLC 模板、测试和签核，一名全栈/自动化开发负责产品与厂商适配；安全与 OT 网络由合作企业相应负责人参与。模型训练不是最早的关键岗位，真实样本整理和闭环测试更关键。

## 13. 最终建议

1. 将项目定位为“非标自动化设备规格、PLC 生成验证与证据化诊断平台”，而不是通用 PLC 聊天机器人；
2. 先拿一套小而完整的真实设备做黄金项目；
3. 汇川先行，但用十项技术验证门决定是否继续；
4. 三菱建立平行备用闭环；CODESYS只作接口标杆和实验后端；
5. 先实现 MachineSpec、模板、测试和厂商编译器闭环，再加入更多 Agent；
6. 故障诊断先做离线日志与手册证据，不先做自动修复和预测维护；
7. 第一版不买/不造 AI 盒子，现场价值确认后做只读采集网关；
8. 采集权与程序下载权永久分离，安全功能永久在自动生成边界之外；
9. 用“节省工程时间、减少遗漏、测试缺陷发现率、诊断定位时间”衡量价值；
10. 长期把真实机构模板、测试、故障与恢复案例沉淀为企业数据资产。

这条路线比“直接让大模型写 PLC”慢半步，却更可能成为制造企业愿意长期购买和信任的工程产品。

