# Development Documents

本目录是 PLC Engineering Agent 的开发文档入口。

- [PRD-001](prd/PRD-001.md)：第一版完整产品需求，包含用户旅程、用户故事、异常路径、验收标准和核心线框图。
- [UI Page Specification](UI_PAGE_SPECIFICATION.md)：逐页说明页面目的、内容、操作、状态和跳转关系。
- [Development Roadmap](DEVELOPMENT_ROADMAP.md)：可点击 Demo 到真实 Adapter、模拟器和在线监控的开发顺序。
- [MachineSpec Template Draft](MACHINE_SPEC_TEMPLATE_DRAFT.md)：Excel 工程模板的初始结构和待共同确认事项。
- [PRD Registry](PRD_REGISTRY.md)：项目 PRD 台账。
- [Current Status](CURRENT_STATUS.md)：M1/M2/M3 前置、P09 自动交付候选、P10 离线只读监控准备、验证等级和未决边界。
- [Local Development](LOCAL_DEVELOPMENT.md)：安装、启动、测试、备份与恢复。
- [API and Schema](API_AND_SCHEMA.md)：公开 API、MachineSpec v1 与并发契约。
- [Open Source Audit](OPEN_SOURCE_AUDIT.md)：官方资料、开源许可证、维护状态和复用边界。
- [Electrical Validation Package](ELECTRICAL_VALIDATION_PACKAGE.md)：集中 1–2 天完成的黄金项目、厂商工具与硬件验证。
- [Adapter Security and Dependencies](ADAPTER_SECURITY_AND_DEPENDENCIES.md)：Adapter v1 权限、路径、进程、证据、SBOM 和未验证边界。
- [CycloneDX SBOM](supply-chain/sbom.cdx.json)：由固定依赖清单离线生成的机器可读供应链清单。
- [Dependency Audit](supply-chain/dependency-audit.json)：输入哈希、Python/npm 完整锁定覆盖范围和依赖门禁。
- [Third-party Licenses](supply-chain/THIRD_PARTY_LICENSES.md)：Python 传递锁与 npm 锁定安装项的许可证清单。
- [Python 3.12 Windows lock](../requirements-lock-win-py312.json)：目标开发环境的发行文件哈希和依赖图锁。

历史调研与技术证据保存在 [plc-ai-agent-research](../plc-ai-agent-research/README.md)。
