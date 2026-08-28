# Evidence Ledger

## 1. 证据等级

- **A**：标准组织、厂商官方文档或官方产品页面；
- **B**：可审查的开源仓库、同行评审/公开研究、官方合作研究；
- **C**：第三方教程、社区项目、论坛或未完全公开实现；
- **U**：尚未找到足够证据，必须实测。

## 2. 关键主张台账

| 主张 | 等级 | 状态 | 工程含义 | 来源 |
|---|---:|---|---|---|
| IEC 61131-3 包含 ST、LD、FBD、SFC 等语言 | A | 已确认 | 内部 IR 可面向不同语言，但首版应缩窄到 ST/模板 | [PLCopen IEC 61131-3](https://www.plcopen.org/standards/logic/iec-61131-3/) |
| PLCopen XML 支持 IEC 工程信息交换，但厂商扩展和导入器行为仍影响互操作 | A | 已确认 | XML 不是“跨厂商语义完全相同”的保证 | [PLCopen XML](https://www.plcopen.org/standards/xml-echange/)、[IEC 61131-10 说明](https://www.plcopen.org/standards/logic/iec-61131-10/) |
| CODESYS 官方 MCP 可读取/修改 ST POU、编译并获取错误 | A | 已确认，受版本/许可限制 | 可作为 Agent 工具接口标杆，不代表汇川工具同样开放 | [CODESYS MCP release](https://www.codesys.com/ecosystem/release-lifecycle/releases-updates/development-system-mcp-server/)、[AI-supported engineering](https://www.codesys.com/products/engineering/ai-supported-engineering/) |
| CODESYS Scripting 可通过命令行运行脚本 | A | 已确认 | 适合建立可重复的参考后端 CI | [Starting scripts via command line](https://content.helpme-codesys.com/en/CODESYS%20Scripting/_cds_starting_script_via_command_line.html) |
| 社区 CODESYS MCP 具备较多工程工具，但不同 CODESYS 版本行为不同 | B/C | 已确认其仓库声明，未做本地验证 | 只能做实验依赖，需隔离自动保存/无撤销风险 | [Codesys-MCP repository](https://github.com/luke-harriman/Codesys-MCP) |
| 汇川 H5U 支持 EtherCAT、功能块和多种通信 | A | 已确认 | 适合作为目标控制器，但不等于工程软件可自动化 | [H5U User Guide](https://portal-file.inovance.com/owfile/ProdDoc/SC/19011517-SC/A02/19011517-SC_A02%E3%80%8AH5U%20Series%20Programmable%20Logic%20Controller%20User%20Guide%E3%80%8B-EN.pdf) |
| 汇川运动文档包含 `0x603F` 故障码与 `0x6041` 状态字对象 | A | 已确认，具体轴/映射需核对 | 可作为驱动诊断证据，但需要 PLC 暴露和正确 PDO/SDO 映射 | [Inovance Motion Control Guide](https://portal-file.inovance.com/owfile/ProdDoc/SC/19012378-SC/A00/19012378-SCY_A00%20Medium-sized%20PLC%20Programming%20Guide%20%28Motion%20Control%29-EN.pdf) |
| AutoShop 存在官方公开稳定 CLI/COM/LSP | U | 未确认 | 不得作为架构硬依赖，必须做本地技术验证 |
| InoProShop 支持完整项目 PLCopen XML 自动往返 | U/C | 未确认；仅见第三方功能块库导入线索 | 不承诺跨工具自动导入，按精确版本实测 | [第三方 InoProShop PLCopen XML 教程](https://fashionstar.com.hk/wiki/industrial/plc/inovance-inoproshop/) |
| `AutoShopAgentInterface` 可导出/应用 H5U 工作区 JSON，并通过 UI 自动化编译等 | C | 仓库声明已确认，真实可靠性未验证 | 可加速适配器 spike；预编译二进制、源码完整性和许可需审计 | [Repository](https://github.com/xianruiyang/AutoShopAgentInterface)、[Skill description](https://github.com/xianruiyang/AutoShopAgentInterface/blob/main/SKILL.md) |
| OpenCLI 在 Gitee 找到 InoProShop EtherCAT 从站模拟项目 | C | 发现但未验证 | 可能辅助特定设备仿真，不纳入首版底座 | [ECatSim](https://gitee.com/openwcs/ecat-sim) |
| OpenCLI 在 Gitee 找到 PLC Agent 技能知识库 | C | 发现但未验证 | 可参考知识组织，不证明代码生成或闭环可靠性 | [plc-skills](https://gitee.com/plccode/plc-skills) |
| GX Works3 有官方模拟器，MX Component 可与 GX Simulator3 连接并读写数据 | A | 已确认 | 三菱是更清晰的测试闭环备选 | [GX Works3](https://www.mitsubishielectric.com/fa/products/cnt/plcf/pmerit/concept/gx_works3.html)、[FX5 simulation FAQ](https://fa-faq.mitsubishielectric.com/faq/show/22327)、[MX Component v5 manual](https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh082395eng/sh082395engh.pdf) |
| GX Works3 有面向第三方的完整工程自动生成/编译 API | U | 未确认 | 可先接受人工导入，自动化能力另做验证 |
| Siemens TIA Openness 有官方编译服务，PLCSIM Advanced 提供仿真 API | A | 已确认 | 证明行业可形成官方闭环，是架构参照，不是首期厂商 | [TIA Openness](https://support.industry.siemens.com/cs/attachments/109773802/TIAPortalOpenness_en-US.pdf)、[PLCSIM Advanced API](https://developer.siemens.com/s7-plcsim-advanced/overview.html) |
| AutomationML 面向机械、电气、控制跨域工程交换 | A | 已确认 | 适合未来交换层，首版内部 Schema 保持轻量 | [AutomationML domain model](https://www.automationml.org/industrial-application/domain-model/)、[What is AutomationML](https://www.automationml.org/about-automationml/automationml/) |
| PackML 提供设备状态、模式和标签规范 | A | 已确认 | 可统一顶层状态，但不能代替具体工艺顺序 | [ISA TR88 preview](https://www.isa.org/getmedia/300dbd50-d549-41ac-b372-a5e52f32fc97/tr_880002_preview.pdf)、[OMAC PackML](https://www.omac.org/packml?v=1731570962) |
| IEC Checker 可检查部分 ST/PLCopen 规则 | B | 仓库能力已确认 | 适合作为前置静态检查，受方言与规则覆盖限制 | [IEC Checker](https://github.com/iec-checker/iec-checker) |
| Beremiz/MatIEC 可把部分 IEC 语言转为 C 并运行 | B | 已确认 | 可做参考仿真，不证明商业厂商行为 | [Beremiz overview](https://beremiz.readthedocs.io/en/latest/overview.html) |
| 商业 ST 方言/语义存在差异，开放实现也可能有语义缺陷 | B | 研究支持 | 最终验证必须使用目标厂商工具与真机层级 | [K-ST research](https://arxiv.org/abs/2202.04076) |
| LLM + 在线编译器反馈能改善 ST 生成 | B | 研究支持，非生产保证 | 编译反馈应进入循环，但不能替代测试 | [Online compiler feedback study](https://arxiv.org/abs/2410.22159) |
| RAG、多 Agent 和厂商上下文有助于 PLC 代码生成 | B | 研究原型支持 | 使用受控检索与分工，但不照搬研究原型作安全承诺 | [AutoPLC](https://arxiv.org/abs/2412.02410) |
| 变异测试可评估 PLC 测试是否真正捕获逻辑错误 | B | 研究支持 | MVP 应加入条件翻转/互锁删除等变异用例 | [STMutants](https://arxiv.org/abs/2606.05499) |
| 故障问答/视觉语言研究显示 LLM 可辅助工业诊断 | B | 研究阶段 | 只能作为候选生成与解释层，必须用现场数据集验证 | [FaultGPT](https://arxiv.org/abs/2502.15481)、[Industrial machine consultation](https://arxiv.org/abs/2410.03223) |
| CiA 402 状态/实际量可经 PDO 暴露，但实现子集会影响互换 | A | 已确认 | 必须绑定厂商、对象和映射版本 | [CiA 402 overview](https://www.can-cia.org/can-knowledge/cia-402-series-canopen-device-profile-for-drives-and-motion-control) |
| EtherCAT 被动诊断通常需要专用 TAP/监测硬件 | A | 已确认 | 普通交换机镜像不是默认方案，EtherCAT 抓包后置 | [Beckhoff ET2000](https://www.beckhoff.com/en-en/products/i-o/ethercat-development-products/elxxxx-etxxxx-fbxxxx-hardware/et2000.html)、[ETG mirror TAP listing](https://www.ethercat.org/en/products/C08A14A0872A46B28DA3F90CE45C74A8.htm) |
| OPC UA 提供认证、加密、签名、审计与角色控制 | A | 已确认 | 首选只读语义采集接口之一，仍需正确配置 | [OPC UA overview](https://opcfoundation.org/about/opc-technologies/opc-ua/)、[Role permissions](https://reference.opcfoundation.org/specs/OPC-30142/6.7) |
| 开源 Neuron 主要是 Modbus/MQTT，多种工业驱动属于商业版 | B | 仓库说明已确认 | 不把 Neuron 当作免费全协议网关 | [Neuron repository](https://github.com/emqx/neuron)、[Neuron dashboard note](https://github.com/emqx/neuron-dashboard/blob/master/README.md) |
| OT 网络应分区、最小化数据流并默认拒绝 | A | 已确认 | 边缘部署需走 OT/IT 安全评审，采集与下载分权 | [NIST SP 800-82 Rev.3](https://csrc.nist.gov/pubs/sp/800/82/r3/final) |
| 机械安全相关控制必须按专门标准设计与验证 | A | 已确认 | Agent 首版不得生成或修改安全功能 | [ISO 13849-1:2023](https://www.iso.org/standard/73481.html)、[ISO 13849-2](https://www.iso.org/standard/53640.html)、[IEC 62061:2021](https://webstore.iec.ch/en/publication/59927) |

## 3. 必须通过本地实测关闭的缺口

1. AutoShop 精确版本是否能稳定自动读写、编译、模拟和监控；
2. `AutoShopAgentInterface` 的完整源码、二进制来源、权限行为、许可与可重复性；
3. InoProShop 的 PLCopen XML/脚本/工程导入能力边界；
4. GX Works3 的项目自动生成或导入能力，以及可接受的人工门位置；
5. 用户现有机电对接表到 MachineSpec 的字段映射和缺失率；
6. 汇川/三菱真实项目中的 ST 方言、运动库和错误诊断格式；
7. 工厂现场可用的只读协议、变量采样频率、时间同步与网络策略；
8. 本地模型在真实规格补全、错误修复、手册问答和诊断案例上的通过率。

