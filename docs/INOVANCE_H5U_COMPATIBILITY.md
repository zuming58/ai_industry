# 汇川 H5U 兼容性基线

更新日期：2026-08-30

## 当前结论

`inovance-h5u-st-v1` 已达到“代码完成、自动验证通过”。它覆盖 H5U-1614MTD-A8 和 H5U-3232MTD-A8 的项目目标、Excel 模板、MachineSpec 目标一致性、确定性 Control IR/Structured Text 生成、静态审计、20 次可重复自动审核、控谱参考逻辑模拟、版本与交付追溯。

这不是 AutoShop 编译通过、AutoShop 模拟通过、硬件实测通过或电气工程师确认。当前没有安装或调用 AutoShop，也没有 H5U 硬件。

## 保守实现范围

- 语言：只生成保守 IEC 61131-3 Structured Text 骨架。
- 地址：只接受首批 `X/Y/M` 逻辑地址子集；DI/DO/INTERNAL 分别校验为 X/Y/M 前缀。
- 变量映射：H5U 生成物在 Control IR 和 ST 注释中保留逻辑地址，但不写 `AT` 或任何 AutoShop 专用绑定语法。
- 控制模板：双电控气缸、简单轴/变频握手、自动/手动、互锁、超时、复位及通信断开仅由控谱受限参考模拟器执行。
- Adapter：`autoshop` 只能只读检测允许目录；创建编译任务只会返回 `manual_required/unverified`，不会启动厂商程序、执行命令、下载 PLC、RUN/STOP 或强制输出。

## 调研记录

| 来源 | 类型 | 实际检查 | 结论与限制 |
|---|---|---|---|
| [汇川技术 PLC 产品页](https://www.inovance.com/en/product/industrial-control/plc) | 厂商公开入口 | 2026-08-30 HTTP 200 | 可确认厂商 PLC 产品资料入口；当前公开页未提供可机读、可复现的 H5U AutoShop ST 绑定语法，因此不据此生成方言代码。 |
| IEC 61131-3 | 标准参考 | 未作为运行时依赖 | 仅据此选择通用 ST 骨架；不推断任一厂商方言、库函数、工程格式或下载能力。 |
| 控谱自动回归 | 本仓库测试 | `test_inovance_h5u_profile_template_generation_audit_and_reference_simulation` | 验证模板/导入/锁定/生成/审计/模拟/Adapter 目标绑定的本机闭环；不构成厂商或硬件验证。 |

没有引入汇川 SDK、未固定或复制第三方开源项目代码，也没有新增运行时厂商依赖。

## 集中验证清单

1. 记录 AutoShop 精确版本、H5U CPU/扩展模块、工程格式和授权状态。
2. 在隔离工程副本中导入生成 ST，确认变量声明和 X/Y/M 映射语法。
3. 执行完整编译，保存全部诊断、行号、Commit、MachineSpec 哈希和生成器版本。
4. 在厂商模拟或真实 H5U 台架核对正常循环、缺反馈、超时、互锁禁止、复位、通信断开和重启。
5. 由电气工程师确认互锁、复位、异常、失效状态及安全回路边界。

任何失败都必须保留原工程副本和证据，在新分支修复，并将复现样例加入自动测试；不得修改已锁定规格、既有 Commit 或证据原件。
