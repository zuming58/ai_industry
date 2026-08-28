# 09 项目总说明（喂给 Codex 的完整上下文文档）

> 本文档自包含，是项目从想法到技术方案的全部上下文。Codex 开发前请通读。
> 来源：2026-08-27 五轮调研 + 产品定义讨论定稿。
> 配套详细方案见 08 号文件，本文是浓缩+输入层新增设计后的最终版。

---

## 1. 项目背景：我们要解决什么问题

**发起人背景**：苏州茗宇智能科技，10 人非标自动化设计工作室，主业是新能源汽车三电（电池/电驱/电控）产线非标设备设计外包。机械工程师出身的创始人（十几年非标现场经验）+ 电气工程师合伙人（汇川生态）。服务过的客户：巨一、先导、烽禾升、柯马、ABB、库卡、均普、中科摩通、科瑞恩等。

**行业痛点**：
- 非标设备外包价格从单站位 5-6 万跌到 2-3 万，行业内卷
- 电气工程师紧缺、招聘难，PLC 程序编写占电气工程师大量工时
- 设备故障后诊断依赖老师傅经验，响应慢
- 大厂平台（卡奥斯/浪潮/羚羊）只服务大客户，**中小非标设备厂没人服务**

**产品愿景**：做一个面向非标设备行业的 AI Agent 桌面工具（双引擎）：

1. **编程引擎**：输入结构化的机电对接表 + 动作时序 + 电气架构 → 自动生成 PLC 程序（ST 语言）→ 自动编译 → 软PLC 仿真验证 → 导出可交付程序
2. **诊断引擎**：现场设备故障码 → RAG 检索汇川手册 + 上下文推理 → 给出处置建议

**核心竞争力不是大模型，是行业知识**：非标行业的 ST 模板库、机电对接编码体系、汇川手册库、测试用例生成逻辑。这些从十几年现场经验来，抄不走。

---

## 2. 输入层设计（产品最关键的差异化，重点开发）

### 2.1 设计哲学

**纯自然语言描述一台设备，大模型理解会非常困难**（设备几十个机构、上百个 IO、严格时序）。所以主输入用结构化表格，自然语言只做辅助。

**核心洞察**：机械工程师本来就要做机电对接表、动作时序图；电气工程师本来就要做电气架构表。我们的产品只是把这些"本来要做的活"从 Excel/图片升级为结构化数据——**对工程师是零额外成本，对 Agent 是精确燃料**。

STEP 3D 模型导入自动识别（点击气缸/伺服标注）暂不做：3D 解析技术栈太重，性价比低，远期再议。

### 2.2 三张输入表（数据模型定义）

#### 表一：机电对接表（机械工程师填）

非标行业编码惯例示例：机构号 4251，其下传感器编号 4251-P1 / 4251-P2。执行器和传感器挂在机构下。

```yaml
# Excel 模板列定义 → 解析为 pydantic 模型
station: "4251"                    # 站位/机构号（唯一键）
station_name: "伺服压装机构"        # 中文名（可选）
components:
  - id: "4251-M1"                  # M=伺服电机
    type: servo
    model: "SV660P"                # 选填，汇川型号
    has_origin_sensor: true        # 原点回归
    sensors: ["4251-P5"]           # 原点传感器
  - id: "4251-CY1"                 # CY=气缸
    type: cylinder
    function: "工件夹紧"
    sensors: ["4251-P1", "4251-P2"]  # P1=伸出到位, P2=缩回到位
  - id: "4251-P3"
    type: photo_sensor             # 光电/光纤传感器
    function: "工件检测"
  - id: "4251-V1"
    type: vacuum                   # 真空吸盘
    sensors: ["4251-P4"]           # 真空压力检测
```

**组件类型枚举（首版）**：servo（伺服轴）、cylinder（气缸）、vacuum（真空）、photo_sensor（光电/光纤）、proximity_sensor（接近开关）、pressure_sensor（压力）、temperature_sensor（温度）、gripper（夹爪）、robot（机器人接口）、safety_door（安全门）、e_stop（急停）。

**编码规范（固化为软件校验规则）**：`{机构号}-{组件代号}{序号}`，组件代号：M=伺服、CY=气缸、V=真空、G=夹爪、P=传感器（原点位序号）、RB=机器人。软件内置校验：编号唯一、传感器必须归属组件或独立 IO。

#### 表二：动作时序流程表（机械工程师填）

本质是 SFC（顺序功能图）的表格化。非标行业本来就有"动作时序表"惯例（行=机构，列=步骤）。

```yaml
process:
  name: "压装流程"
  mode: "auto"                     # auto / manual / homing（回零流程单独一份）
  steps:
    - no: 1
      name: "等待工件到位"
      wait_conditions: ["4251-P3 == ON"]        # 等待信号
      actions: []                                 # 无输出
    - no: 2
      name: "夹紧工件"
      actions:
        - component: "4251-CY1"
          command: "extend"                       # extend/retract
      wait_conditions: ["4251-P1 == ON"]          # 等伸出到位
      timeout_sec: 3                              # 超时报警
    - no: 3
      name: "伺服压装"
      actions:
        - component: "4251-M1"
          command: "move_abs"                     # move_abs/move_rel/jog/home
          params: {position: 120.5, speed: 50.0}  # 单位 mm / mm/s
      wait_conditions: ["4251-M1.done == true"]
    - no: 4
      name: "松开返回"
      actions:
        - component: "4251-CY1"
          command: "retract"
      wait_conditions: ["4251-P2 == ON"]
  alarms:                          # 步骤超时/异常 → 报警定义
    - id: "AL4251-01"
      trigger: "step2.timeout"
      message: "4251 夹紧超时，检查气源压力"
```

**同设备多流程**：auto（自动流程）、homing（回零流程）、manual（手动/点动）各一份，程序生成时分别生成程序组织单元（POU）。

#### 表三：电气架构表（电气工程师填）

```yaml
electrical:
  plc: {brand: "汇川", model: "AM402", code_sys: true}   # 或标准 CODESYS 系
  io_modules:
    - {slot: 1, type: "DI32", addressing: "%IX0.0-%IX3.7"}
    - {slot: 2, type: "DO32", addressing: "%QX0.0-%QX3.7"}
    - {slot: 3, type: "AXIS-4", note: "EtherCAT 总线轴"}
  fieldbus: {type: "EtherCAT", slaves: ["4251-M1 驱动器"]}
  safety: {type: "安全继电器+急停回路", note: "硬件安全回路，程序只做状态读取"}
```

### 2.3 输入形态的演进路线

| 版本 | 形态 | 说明 |
|------|------|------|
| V1（MVP） | **Excel/CSV 模板导入** | 我们提供三张标准模板（带示例行+下拉校验），工程师照旧用 Excel 填，软件解析。零学习成本，最快落地 |
| V2 | **内置表单编辑器** | React+Antd 表格界面，组件类型下拉选择、编号自动校验、传感器自动关联提示。边做边选，比 Excel 智能 |
| V3（远期） | 图形化流程编辑器 | 蚂蚁 X6 / bpmn.js 拖拽画流程图，导出同 schema；STEP 3D 导入辅助标注再评估 |

### 2.4 自然语言辅助（定位：辅助，不是主输入）

对话窗口两个用途：
1. **填表助手**：工程师用口语说"第二步夹紧气缸伸出，等 P1 到位"，LLM 转成结构化步骤 JSON，展示给工程师确认后入表
2. **补充描述**：对流程的例外情况、特殊联锁做自然语言补充，Agent 追问澄清后结构化

### 2.5 长期记忆：设备模板库（数据飞轮）

同一类非标机构（上料、压装、拧紧、搬运模组、转台、检测）的动作模式高度相似。每次交付的流程沉淀为**机构级模板**（如"伺服压装机构标准流程"）。新项目时：选相似模板 → 改参数（位置/速度/点位映射）→ 完成。**做得越多模板越全，这是第二个护城河。**

模板库 schema 与三张输入表同构，外加字段：`template_type`（机构类型）、`applicable_stations`、`usage_count`。

### 2.6 输入层 → 编程引擎的数据流

```
三张表（Excel导入/表单录入） → pydantic 校验（编号唯一性/引用完整性/时序逻辑检查）
  → 设备数字孪生模型（DeviceModel：全部组件+IO映射+流程）
  → 编程引擎消费：组件→变量表生成；流程→主程序POU（SFC/ST）；
    组件类型→调用模板库（气缸标准FB、伺服轴标准FB、真空标准FB）
  → 同时自动生成仿真测试用例（每个 wait_condition 就是一条断言；
    每个 timeout 就是一条异常测试）——需求和测试同源，这是验证闭环的燃料
```

---

## 3. 编程引擎设计（引擎 A）

### 3.1 闭环流程

```
DeviceModel（来自输入层）
  → [1] 变量表/IO 映射生成（纯规则，不用 LLM）
  → [2] 每个组件实例化标准 FB（模板库，纯规则）
  → [3] 流程步骤 → ST 主程序（LLM 生成 + 模板约束，这是 LLM 唯一介入的生成环节）
  → [4] 三关验证：
       ①静态检查（命名/双线圈/未使用变量——纯规则）
       ②CODESYS 编译（MCP 调用用户本机 IDE，回读错误）
       ③软PLC 仿真测试（下载到 CODESYS Control Win V3，
         模拟 IO 翻转，跑自动生成的测试用例）
  → [5] 失败 → 错误回传 LLM 修复（循环上限 5 次）
  → [6] 输出：ST 源码 + PLCopen XML + IO 表 + 测试报告
```

### 3.2 为什么 LLM 只在第 3 步介入

- 变量表、FB 实例化是确定性工作，规则生成 100% 可靠，不浪费 token 也不引入幻觉
- LLM 只做它擅长的：把流程逻辑翻译成 ST 控制流
- 三关验证兜底：行业研究（108 个人工埋 bug 实验）证明"AND 改 OR 照样编译通过"——编译通过≠可靠，必须仿真测试。我们的测试用例从输入层的 wait_condition/timeout 自动生成，**需求与测试同源**

### 3.3 核心资产：非标行业 ST 模板库（app/templates/）

首版必做模板：气缸标准 FB（伸出/缩回/到位检测/超时报警）、伺服轴管理 FB（使能/点动/绝对定位/相对定位/回零/报警复位）、真空 FB、自动流程主程序骨架（步进逻辑+跳转+超时框架）、回零流程、报警管理 FB、安全状态监控 FB。**每个模板对应输入层一个组件类型，一一映射。**

---

## 4. 诊断引擎设计（引擎 B）

```
现场设备（汇川 PLC + SV660 伺服）
  → EtherCAT 总线读 0x6041（状态字）/0x603F（故障码）/PLC 报警区（不加接线）
  → [边缘盒 RK3588，~900元：采集/脱敏/缓存/断网续传，不跑大模型]
  → MQTT 上行 → 诊断 Agent
  → 第一级：故障码精确匹配（汇川手册 RAG 检索）→ 原因+处理步骤
  → 第二级：匹配不上 → 结合上下文（前后 5 秒变量轨迹）LLM 推理
  → 输出：处置建议 + 关联历史案例（案例库积累=数据飞轮）
```

RAG 架构直接参考开源项目 plc-log-explainer-local（FastAPI+ChromaDB 全本地）。第二阶段引入知识图谱（参考 tracefault 项目）。

---

## 5. 调研过程与关键结论（五轮，已交叉验证）

| 轮次 | 调研内容 | 结论 | 对方案的影响 |
|------|---------|------|-------------|
| 1 | 镇江 AI 大赛要求 | 评委重落地性；钱少重点是入储备库 | 大赛已放弃（8/31 赶不上），方向保留为长期项目 |
| 2 | AI 写 PLC 现状 | AI 写 ST 文本准确率远超梯形图（汇川披露 92%）；汇川等大厂只做通用平台，**非标垂直层空白** | 路线定为"AI 生成 ST"，我们做行业垂直层 |
| 3 | 故障诊断方案 | EtherCAT 伺服故障码（0x6041/0x603F）总线直读；汇川故障手册 PDF 是现成 RAG 素材 | 诊断引擎两级架构；盒子定位=数据关口 |
| 4 | 开源项目与 MCP | CODESYS MCP Server 社区版 MIT 开源可直接用（codesys-mcp-toolkit 等 3 个）；**汇川 InoProShop 深度定制大概率接不上 MCP，AutoShop 完全非 CODESYS**；TIA 生态已 28+ 开源轮子（红海，反而验证我们站汇川/非标垂直是对的） | 编程闭环用标准 CODESYS 跑通；汇川走 PLCopen XML 导入路线（待实测） |
| 5 | 知乎实战抓取 | RealPLC（国内团队，8/22 文章）验证闭环全免费方案：生成ST→编译→**Win V3 软PLC 仿真跑 TestSpec**，仍在内测未发布、不做垂直行业；108-bug 研究证明编译通过≠可靠；已有工程师用 CODESYS MCP 修真实产线错误 | 仿真验证环节直接抄 RealPLC 架构；验证升级为三关（编译+仿真+安全逻辑） |

## 6. 授权与合规红线（已核实）

- **CODESYS IDE**：永久免费，但 EULA 禁止第三方再分发安装包 → 产品走**调用式集成**：用户自装 IDE，Agent 经 MCP 驱动。我们的产品不包含 CODESYS 任何文件
- **软PLC（CODESYS Control Win V3）**：免费 demo 模式每次启动 2 小时后自动停机 → 对分钟级自动测试无影响，测试完重启即可；7×24 运行才需付费授权（MVP 不涉及）
- **开源 MCP Server**：MIT 协议，保留版权声明即可商用，可改可集成
- **InoProShop**：汇川生态内免费，闭源 → 走 XML 导入，兼容性待合伙人实测（5 项测试清单见 08 文件第五节）
- **安全红线**：生成的代码必须工程师确认后才允许下载实机，仿真通过≠允许直连实机（写进产品逻辑）

---

## 7. 技术栈与架构（Codex 开发依据）

### 7.1 分层架构

```
L1 交互层：Tauri 桌面壳 + React 18 + Vite + Ant Design
L2 Agent 编排层：LangGraph 状态机（意图路由→引擎分发→生成/验证/修复循环）
L3 工具层（MCP + 本地函数）：
    - codesys-tools：IDE 操控（建POU/写ST/编译/读错误/下载软PLC/读写变量）
    - input-parser：三张输入表 Excel/CSV → DeviceModel（pydantic）
    - static-check：ST 静态检查规则引擎
    - xml-export：ST/工程 → PLCopen XML
    - diag-tools：故障码读取/RAG 检索/案例检索
L4 知识层：ChromaDB 向量库（手册/案例）+ SQLite（用户/项目/模板库）
L5 模型层：DeepSeek API（OpenAI 兼容接口，端点可配置，支持切本地 Ollama）
```

### 7.2 选型清单

| 项 | 选型 | 版本 |
|----|------|------|
| 语言 | Python | 3.11+ |
| Agent 编排 | LangGraph | 0.2+ |
| LLM SDK | openai（DeepSeek 兼容） | ≥1.40 |
| MCP | 官方 mcp python SDK（我们是 Host） | 最新 |
| IDE 操控 | 改造 codesys-mcp-toolkit（MIT） | - |
| 向量库 | ChromaDB（嵌入式） | 0.5+ |
| Embedding | BAAI/bge-m3（本地优先，客户数据不出厂） | - |
| PDF 解析 | PyMuPDF | 1.24+ |
| 工业通讯 | asyncua、pymodbus | - |
| 后端 | FastAPI | 0.110+ |
| 前端 | React + Vite + Ant Design | 18 |
| 桌面壳 | Tauri | - |
| 数据库 | SQLite | - |
| 配置 | pydantic-settings | - |
| 打包 | PyInstaller + Tauri bundler | - |
| 测试 | pytest | - |

### 7.3 目录结构

```
ai-automation-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── orchestrator/          # L2
│   │   │   ├── graph.py
│   │   │   └── engines/
│   │   │       ├── coding.py      # 编程闭环状态机
│   │   │       └── diag.py        # 诊断两级流程
│   │   ├── tools/                 # L3
│   │   │   ├── codesys_mcp.py
│   │   │   ├── input_parser.py    # 三张表 → DeviceModel（新增，核心）
│   │   │   ├── device_model.py    # pydantic：组件/流程/电气架构模型（新增，核心）
│   │   │   ├── static_check.py
│   │   │   ├── xml_export.py
│   │   │   ├── test_gen.py        # DeviceModel → 仿真测试用例（新增，核心）
│   │   │   └── regs_reader.py
│   │   ├── rag/
│   │   ├── templates/             # 非标 ST 模板库（核心资产，与组件类型一一对应）
│   │   └── models/
│   ├── tests/
│   └── pyproject.toml
├── frontend/                      # 含三张表编辑器（V1 Excel导入界面 + 解析报错）
├── templates_xlsx/                # 三张输入表的标准 Excel 模板（带示例+校验）
└── docs/
```

### 7.4 环境前置

- Windows 10/11 64 位
- 本机安装 CODESYS V3.5 SP19+（免费，store.codesys.com，安装勾选 Control Win V3 软PLC）
- Node.js 18+（跑 codesys-mcp-server）
- 环境变量：`DEEPSEEK_API_KEY`、`CODESYS_PROJECT_DIR`；模型端点可配置（有自建端点备用）

---

## 8. 开发计划（四周 MVP，已含输入层）

| 周 | 交付 | 验收标准 |
|----|------|----------|
| W1 | **DeviceModel + 输入层**：pydantic 数据模型、三张 Excel 模板、input_parser 解析器、校验规则（编号唯一/引用完整/时序逻辑） | 填好示例设备（1 个伺服+2 气缸+4 传感器+8 步流程）的模板表，导入输出正确 DeviceModel；错误表（重复编号/悬空引用）全部被拦截 |
| W2 | **诊断引擎**（RAG）：手册 PDF 入库 + 检索 + 两级诊断流程 | 输入汇川故障码如 E604.0，输出原因+处理步骤，检索命中率>90% |
| W3 | **编程引擎闭环**：模板库首批 FB + LLM 生成主程序 + 编译 + 软PLC 仿真 + 自动测试用例 | W1 的示例设备全自动：导入→生成→编译→仿真测试通过，无人工干预 |
| W4 | **桌面壳集成 + 修复循环 + 报告** | 编译错误自动修复成功率>60%；一键导出（ST/XML/IO表/测试报告） |

W1-W3 不依赖任何硬件、不依赖合伙人输入，Codex 可立即开工。汇川 InoProShop 兼容性由合伙人并行实测，结果只影响 W4 的 XML 导出环节，不阻塞主线。

---

## 9. 风险与对策

| 风险 | 对策 |
|------|------|
| InoProShop 连 XML 都导不进 | 编程引擎先服务标准 CODESYS 客户（WAGO/倍福/施耐德等）；对汇川用户输出可复制 ST 源码（体验打折但可用） |
| LLM 生成流程逻辑不可靠 | LLM 只碰流程转 ST 环节；变量表/FB 实例化纯规则；三关验证+需求测试同源 |
| 工程师不习惯新输入方式 | V1 就是 Excel 模板，跟现在工作方式几乎一样，零学习成本 |
| CODESYS 升级破坏脚本接口 | MCP 层做版本适配隔离 |
| RealPLC 等先行者发布 | 他们做通用框架不做垂直行业；模板库+汇川手册库抄不走，必要时可当底座 |

---

## 10. 配套文档索引

- 00_README.md：总索引
- 02-05：四轮专项调研详情
- 07：开源项目清单与 MCP 可用性详情
- 08：完整技术方案（本文的展开版，含 InoProShop 实测清单）

**给 Codex 的开工指令**：从 W1 开始——先实现 `device_model.py`（pydantic）+ 三张 Excel 模板 + `input_parser.py`，测试驱动，验收标准见第 8 节。
