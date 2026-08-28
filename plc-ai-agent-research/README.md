# PLC AI Engineering Agent Research

本目录把用户的行业经验、产品设想、独立技术调研和可执行开发路线固化为一套项目基线。结论不是“让大模型直接写一整台设备”，而是建设一个受工程规则、厂商编译器、仿真测试和人工签核约束的 PLC 工程系统。

## 一句话结论

先以汇川 H5U + AutoShop 做有退出条件的适配器可行性验证；产品核心先做厂商无关的 `MachineSpec` 设备规格、确定性代码模板和验收测试，再接入厂商工程软件。若 AutoShop 自动化接口验证失败，第一条可完整闭环的厂商链路转为三菱 FX5U + GX Works3/GX Simulator3/MX Component。故障诊断使用同一份设备模型，第一版只做离线日志和只读采集，不允许 AI 直接修改或下载现场程序。

## 建议阅读顺序

1. [user-vision.md](user-vision.md)：用户背景、现行协作流程、目标与约束。
2. [report-source.md](report-source.md)：完整调研结论、证据与取舍，是本目录的主报告。
3. [machine-specification.md](machine-specification.md)：机电对接表应怎样升级成可生成、可诊断的设备规格。
4. [architecture.md](architecture.md)：系统模块、技术栈、程序生成闭环、诊断闭环和边缘部署。
5. [roadmap.md](roadmap.md)：验证门槛、12–16 周 MVP 和后续试点路线。
6. [historical-review.md](historical-review.md)：对 WorkBuddy 与 Hermes 历史调研的吸收、修正和待验证项。
7. [evidence-ledger.md](evidence-ledger.md)：关键主张、来源、可信度和工程含义。

## 开发文档

调研结论已经转化为第一版开发基线，入口见 [Development Documents](../docs/README.md)。其中包含正式 PRD、P01–P12 逐页 UI 规格、可点击 Demo 到真实 Adapter 的开发路线，以及待与机械/电气工程师共同定稿的 MachineSpec Excel 模板草案。

## 当前产品边界

首版做：

- 通过向导或 Excel 导入结构化设备资料；
- 自动检查 I/O、动作、互锁、节拍、报警和测试条件是否完整、矛盾；
- 生成受模板约束的 ST 程序、变量表、报警表、测试用例和文档；
- 调用厂商编译器，读取错误，进入软件仿真并形成验收报告；
- 根据故障码、设备步骤、时序数据、人工现象和知识库提供有证据的排查建议；
- 所有程序变更以差异包提交，由电气工程师审核、编译、仿真和下载。

首版不做：

- 从 SolidWorks 三维模型直接推断完整控制逻辑；
- 自动生成或修改安全 PLC、急停、门锁、光栅等安全功能；
- 让诊断盒直接向运行中的 PLC 下载程序；
- 把开源软 PLC 的通过结果当成汇川或三菱真机的等价证明；
- 以“编译通过”代替工艺正确、故障可恢复和节拍达标。

## 需要用户准备的真实样本

为了从调研进入开发，最有价值的不是更多泛化资料，而是 1 套已完成并可脱敏的小设备资料：机电对接表、I/O 表、动作/节拍表、电气 BOM、PLC 工程、报警记录和最终验收项。建议选择 1–2 个伺服、2–4 个气缸、20–60 点 I/O 的单工站，避开机器人、安全 PLC 和复杂视觉。
