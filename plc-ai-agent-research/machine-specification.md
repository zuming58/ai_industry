# MachineSpec: Structured Machine Specification

## 1. 为什么不能只靠截图和自然语言

截图适合人理解机构，自然语言适合补充意图，但二者都难以可靠回答以下工程问题：每个输出由谁驱动、在哪些模式可动、启动前必须满足什么、动作完成看哪个反馈、超时多久、失败进入什么状态、如何复位、哪些信号属于安全回路、验收时怎样证明逻辑正确。

因此，输入层应保留用户熟悉的 Excel/向导界面，同时在系统内部归一化成有版本的 `MachineSpec` JSON。Excel 是编辑载体，JSON Schema 是机器契约，图片和三维截图是附件证据，不是逻辑真源。

## 2. 建议的 Excel 工作簿

首版建议使用 9 个工作表。每一行都必须有稳定 ID，显示名称可改，ID 不随描述变化。

### 2.1 Project

| 字段 | 示例 | 说明 |
|---|---|---|
| `project_id` | `CELL_A01` | 项目唯一 ID |
| `machine_name` | 托盘举升检测站 | 人类可读名称 |
| `spec_version` | `0.3.0` | 规格版本 |
| `target_vendor` | `INOVANCE_AUTOSHOP` | 目标平台 |
| `target_cpu` | `H5U-1614MTD-A8` | 精确 CPU/固件需后补 |
| `cycle_time_target_ms` | `12000` | 整机目标节拍 |
| `units_profile` | `SI_MM_MS` | 单位约定 |
| `safety_boundary` | `EXTERNAL_SAFETY_CIRCUIT` | 安全功能边界 |

### 2.2 Components

记录机构层级和执行元件，不把 PLC 地址写死在机械命名中。

| 字段 | 示例 |
|---|---|
| `component_id` | `LIFT_CYL_01` |
| `station_id` | `ST10` |
| `type` | `DOUBLE_ACTING_CYLINDER` |
| `display_name` | 举升气缸 |
| `template_id` | `CYLINDER_2POS_V1` |
| `parent_id` | `LIFT_MODULE_01` |
| `mechanical_ref` | 图纸页/截图/三维对象链接 |
| `failure_reaction` | `STOP_SEQUENCE_HOLD_PRESSURE` |

### 2.3 Signals

这是机械、电气和 PLC 共用的 I/O 接口表。

| 字段 | 示例 | 规则 |
|---|---|---|
| `signal_id` | `LIFT_UP_FB` | 全项目唯一 |
| `component_id` | `LIFT_CYL_01` | 必须引用已存在元件 |
| `direction` | `DI` | DI/DO/AI/AO/INTERNAL/COMM |
| `meaning` | `CYLINDER_UP_POSITION` | 采用受控枚举或词表 |
| `normal_state` | `FALSE` | 用于断线/常闭判断 |
| `address` | `%IX0.1` | 允许在硬件设计后补齐 |
| `debounce_ms` | `30` | 去抖参数 |
| `required_for` | `STEP_LIFT_UP` | 可反向检查引用 |
| `safety_related` | `false` | true 时禁止自动生成控制逻辑 |

### 2.4 Hardware

记录 PLC、I/O 模块、伺服、变频器、通信拓扑、设备站号、对象字典/PDO 映射和工程软件版本。这里由电气工程师主责，机械工程师不必预先填写所有细节。

关键字段包括 `device_id`、`vendor`、`model`、`firmware`、`protocol`、`station_address`、`eds_esi_ref`、`io_mapping_ref`、`engineering_tool_version`、`library_versions`。

### 2.5 Sequences

一行描述一个步骤，不用一大段文字隐藏多个动作。

| 字段 | 示例 |
|---|---|
| `sequence_id` | `AUTO_MAIN` |
| `step_id` | `S030_LIFT_UP` |
| `order_hint` | `30` |
| `entry_condition` | `PALLET_PRESENT && CLAMP_HOME` |
| `actions` | `LIFT_CYL_01.UP := TRUE` |
| `completion_condition` | `LIFT_UP_FB == TRUE` |
| `timeout_ms` | `1800` |
| `on_timeout_alarm` | `ALM_LIFT_UP_TIMEOUT` |
| `next_step` | `S040_CLAMP` |
| `estimated_duration_ms` | `900` |
| `manual_behavior` | `HOLD_TO_RUN` |
| `restart_policy` | `REQUIRE_HOME` |

条件不能长期使用任意自由文本。界面可以接收自然语言，但保存前必须转成可解析的表达式，并让用户确认引用的信号和参数。

### 2.6 Interlocks

区分四类概念，避免统一写成“互锁”：

- `permissive`：允许启动前必须成立；
- `interlock`：运行中失效会阻止或中断动作；
- `inhibit`：特定模式或维护时抑制动作/报警；
- `safety_constraint`：安全设计输入，只可引用、显示和检查，不由 AI 自动实现。

字段包括 `rule_id`、`scope`、`type`、`expression`、`reaction`、`reset_condition`、`rationale`、`owner`、`safety_related`。

### 2.7 Alarms

| 字段 | 示例 |
|---|---|
| `alarm_id` | `ALM_LIFT_UP_TIMEOUT` |
| `trigger_expression` | `S030_ACTIVE && T_STEP > P_LIFT_TIMEOUT` |
| `severity` | `STOPPABLE_FAULT` |
| `latch` | `true` |
| `reaction` | `STOP_SEQUENCE; KEEP_CLAMPED` |
| `reset_condition` | `LIFT_DOWN_FB && OPERATOR_RESET` |
| `operator_text_zh` | 举升气缸上升超时 |
| `evidence_tags` | `LIFT_UP_CMD,LIFT_UP_FB,AIR_PRESSURE_OK` |
| `manual_refs` | 气路图、I/O 页、气缸说明书 |

报警表本身就是未来诊断的第一层知识库，应同时定义要保留哪些前后时序证据。

### 2.8 ParametersAndTiming

记录参数 ID、单位、上下限、默认值、可否在线调整、权限、来源和节拍预算。所有时间、速度、位置都必须带单位，禁止仅写裸数字。

### 2.9 AcceptanceTests

每个步骤和异常分支至少有一个可执行验收测试。

| 字段 | 示例 |
|---|---|
| `test_id` | `T_LIFT_UP_OK` |
| `initial_state` | `AUTO_READY; LIFT_DOWN_FB=1` |
| `stimulus` | `START=1; PALLET_PRESENT=1` |
| `expected_trace` | `LIFT_UP_CMD rises; LIFT_UP_FB within 1800ms` |
| `forbidden_trace` | `LIFT_DOWN_CMD && LIFT_UP_CMD` |
| `expected_final_state` | `S040_CLAMP` |
| `max_duration_ms` | `2000` |
| `test_level` | `SIMULATOR` |
| `evidence_required` | `trace + compiler version + project hash` |

还应有异常测试，例如传感器不来、两端同时来、通信中断、掉电重启、急停后恢复、手自动切换。涉及安全功能的测试要求由安全责任人定义和签核，Agent 不能替代。

## 3. 内部数据模型

建议以 JSON Schema 2020-12 为契约，核心对象如下：

```text
MachineSpec
├── metadata / versions / targetProfile
├── stations[] / components[] / attachments[]
├── signals[] / hardwareTopology[] / mappings[]
├── modes[] / machineStates[] / sequences[] / steps[]
├── interlocks[] / alarms[] / parameters[]
├── timingBudget[] / acceptanceTests[]
├── safetyConstraints[]
└── traceability[]
```

每次生成都绑定以下版本：

- `spec_hash`：设备规格内容哈希；
- `template_pack_version`：功能块与代码模板版本；
- `vendor_adapter_version`：厂商适配器版本；
- `engineering_tool_version`：AutoShop/GX Works3 等版本；
- `library_manifest`：运动控制和公共库版本；
- `knowledge_base_snapshot`：手册和案例知识库快照；
- `model_config`：模型、提示模板和解码参数；
- `generated_artifact_hash`：输出工程和报告哈希。

## 4. 必须在生成前通过的检查

1. 所有引用 ID 存在且类型匹配；
2. 同一物理输出不存在冲突动作；
3. 每个自动步骤都有进入、完成、超时和下一步；
4. 状态图没有不可达步骤和无出口死路；
5. 每个执行元件有手动/自动、复位和掉电重启策略；
6. 每个报警有触发、反应、复位和证据标签；
7. 节拍预算总和、并行动作与整机目标一致；
8. 单位、量程、地址和常开/常闭规则明确；
9. 安全相关信号不进入普通自动生成控制模板；
10. 每个关键需求可追踪到程序单元和验收测试。

## 5. LLM 在输入阶段的正确角色

LLM 可以把“托盘到位后举升，1.8 秒不到位就报警”转成候选步骤、超时和报警字段，也可以追问“气压低时是否允许继续、超时后是否保持夹紧”。但候选结果必须经过 Schema 校验和人机确认。LLM 不应绕过字段约束，直接把长段描述塞进 ST 代码。

## 6. 与行业标准的关系

内部模型首版保持简单，不把产品绑死在大型标准对象模型上。未来可映射到：

- PLCopen XML：交换 IEC 61131-3 程序与部分工程信息；
- AutomationML/IEC 62714：机械、电气和控制跨域交换；
- PackML/ISA TR88：统一设备顶层状态、模式和标签；
- OPC UA 信息模型：运行时语义化数据交换。

这些标准提升互操作，但都不能自动消除厂商扩展、库版本和行为差异，因此不能取代厂商适配器和实测。

