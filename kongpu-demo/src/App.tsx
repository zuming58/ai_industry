import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, Bell, Check, CheckCircle, ClipboardText, Code, Cpu, Cube,
  Database, DownloadSimple, FileCode, FileText, FolderSimple, GearSix,
  GitBranch, HardDrives, Info, ListChecks, MagnifyingGlass, PencilSimple,
  Plus, Pulse, SquaresFour, UploadSimple, WarningCircle, X,
} from "@phosphor-icons/react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, saveBlob } from "./api/client";
import type {
  AdapterDescriptor, AdapterEnvironment, AutomatedReviewRun, CompileRun, GenerationRun,
  MachineSpec, MonitoringEvidence, ProgramBranch, ProgramCommit, ProgramFile,
  Project, ProjectAcceptanceRun, ReleaseCandidate, ReleaseCandidateEvidence,
  ReleaseEvidenceKind, CandidateVerification,
  SimulationRun, SpecRevision, ValidationIssue, VersionComparisonSection, ProjectTimelineEvent,
  LocalSettings, TemplateVersionHistory, CompatibilityMatrix, SettingsAuditEvent,
  SimulationDiagnostic, SimulationScalar,
} from "./domain";

const BRAND_ICON = "/assets/brand/kongpu-app-icon.png";

type ToastState = { message: string; tone?: "success" | "error" } | null;

const rootNavigation = [
  { path: "/", label: "工作台", icon: SquaresFour },
  { path: "/projects", label: "项目管理", icon: FolderSimple },
  { path: "/specs", label: "规格管理", icon: ClipboardText },
  { path: "/program", label: "程序工程", icon: FileCode },
  { path: "/debug", label: "调试工具", icon: Pulse },
  { path: "/devices", label: "设备库", icon: HardDrives },
  { path: "/documents", label: "文档资料", icon: FileText },
  { path: "/versions", label: "版本控制", icon: GitBranch },
];

const workflow = [
  { key: "templates", label: "P03 模板" },
  { key: "imports", label: "P04 导入校验" },
  { key: "review", label: "P05 规格审阅" },
  { key: "program", label: "P06 程序工程" },
  { key: "compile", label: "P07 编译" },
  { key: "simulation", label: "P08 模拟" },
  { key: "release", label: "P09 发布" },
  { key: "monitor", label: "P10 监控" },
  { key: "versions", label: "P11 版本" },
];

const viewLabels: Record<string, string> = {
  device_relationship: "设备关系",
  process_flow: "动作流程",
  cycle_analysis: "节拍分析",
  signal_timing: "信号时序",
  io_mapping: "I/O 映射",
  raw_tables: "原始表格",
  interlock_matrix: "互锁矩阵",
  exceptions: "异常策略",
};

function useProjects(includeArchived = false) {
  return useQuery({ queryKey: ["projects", includeArchived], queryFn: () => api.listProjects(includeArchived) });
}

function formatTime(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "操作失败";
}

function PageHeading({ kicker, title, description, actions }: { kicker: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-heading"><div><div className="page-heading__kicker">{kicker}</div><h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</div>;
}

function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return <div className="real-empty"><Info size={28} weight="duotone" /><strong>{title}</strong><span>{text}</span>{action}</div>;
}

function Status({ value }: { value: string }) {
  const tone = value.includes("锁定") || value.includes("review_ready") || value.includes("clean") ? "green" : value.includes("失败") || value.includes("blocked") ? "violet" : "blue";
  return <span className={"status status--" + tone}>{value}</span>;
}

function AppSidebar() {
  const location = useLocation();
  return <aside className="sidebar"><div className="sidebar__brand"><img src={BRAND_ICON} alt="控谱" /><span>控谱</span></div><nav className="sidebar__nav" aria-label="主导航">{rootNavigation.map((item) => {
    const active = item.path === "/" ? location.pathname === "/" : location.pathname.startsWith(item.path);
    const Icon = item.icon;
    return <Link key={item.path} className={"nav-item " + (active ? "is-active" : "")} to={item.path}><span className="nav-item__icon"><Icon size={23} weight={active ? "duotone" : "regular"} /></span><span>{item.label}</span></Link>;
  })}</nav><div className="sidebar__bottom"><Link className={"nav-item " + (location.pathname === "/settings" ? "is-active" : "")} to="/settings"><span className="nav-item__icon"><GearSix size={23} /></span><span>系统设置</span></Link><div className="sidebar__version">KONGPU · M3 PRE</div></div></aside>;
}

function Topbar() {
  return <header className="topbar"><div className="logo-lockup"><img className="logo-lockup__icon" src={BRAND_ICON} alt="控谱图标" /><div className="logo-lockup__type"><strong>控谱</strong><span>PLC ENGINEERING AGENT</span></div></div><div className="topbar__actions"><span className="runtime-badge"><span />本机 API</span><button className="icon-button" aria-label="通知"><Bell size={20} /></button><div className="user-button"><strong>本机工程师</strong><small>单用户模式</small></div></div></header>;
}

function AppShell({ toast, clearToast }: { toast: ToastState; clearToast: () => void }) {
  return <div className="app-shell"><AppSidebar /><div className="app-frame"><Topbar /><Routes><Route path="/" element={<Dashboard />} /><Route path="/projects" element={<ProjectsPage />} /><Route path="/specs" element={<ProjectChooser destination="review" title="规格管理" />} /><Route path="/program" element={<ProjectChooser destination="program" title="程序工程" />} /><Route path="/versions" element={<ProjectChooser destination="versions" title="版本控制" />} /><Route path="/debug" element={<ProjectChooser destination="compile" title="调试工具" />} /><Route path="/devices" element={<DeviceLibrary />} /><Route path="/documents" element={<DocumentsPage />} /><Route path="/settings" element={<SettingsPage />} /><Route path="/projects/:projectId/templates" element={<TemplatePage />} /><Route path="/projects/:projectId/imports" element={<ImportPage />} /><Route path="/projects/:projectId/review" element={<ReviewPage />} /><Route path="/projects/:projectId/program" element={<ProgramPage />} /><Route path="/projects/:projectId/versions" element={<VersionPage />} /><Route path="/projects/:projectId/:capability" element={<CapabilityPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes><div className="statusbar"><span><Database size={13} /> SQLite WAL · 本机数据</span><span>FX5U / H5U · 自动验证 · 厂商/硬件未验证</span></div></div>{toast && <div className={"toast " + (toast.tone === "error" ? "toast--error" : "")}><CheckCircle size={19} /><span>{toast.message}</span><button onClick={clearToast}><X size={15} /></button></div>}</div>;
}

export function App() {
  const [toast, setToast] = useState<ToastState>(null);
  useEffect(() => {
    const success = (event: Event) => setToast({ message: (event as CustomEvent<string>).detail });
    const failure = (event: Event) => setToast({ message: (event as CustomEvent<string>).detail, tone: "error" });
    window.addEventListener("kongpu:toast", success); window.addEventListener("kongpu:error", failure);
    return () => { window.removeEventListener("kongpu:toast", success); window.removeEventListener("kongpu:error", failure); };
  }, []);
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(null), 4200); return () => window.clearTimeout(timer); }, [toast]);
  return <AppShell toast={toast} clearToast={() => setToast(null)} />;
}

function notify(message: string) { window.dispatchEvent(new CustomEvent("kongpu:toast", { detail: message })); }
function notifyError(error: unknown) { window.dispatchEvent(new CustomEvent("kongpu:error", { detail: errorMessage(error) })); }

function Dashboard() {
  const navigate = useNavigate(); const projects = useProjects(); const items = projects.data || [];
  const active = items[0];
  return <main className="hub-page"><PageHeading kicker="P01 · WORKSPACE" title="工程工作台" description="从真实项目、MachineSpec 与程序版本继续工作。" actions={<button className="button button--primary" onClick={() => navigate("/projects")}><Plus size={16} />新建项目</button>} />
    <section className="hub-metrics"><Metric label="项目总数" value={String(items.length)} note="SQLite 持久化" icon={<FolderSimple />} /><Metric label="待处理" value={String(items.filter((p) => !p.archived && p.status !== "规格锁定").length)} note="需要工程动作" icon={<ListChecks />} /><Metric label="规格锁定" value={String(items.filter((p) => p.status === "规格锁定").length)} note="可进入程序生成" icon={<CheckCircle />} /><Metric label="厂商验证" value="未验证" note="GX Works3 / AutoShop" icon={<WarningCircle />} /></section>
    {projects.isLoading ? <EmptyState title="正在读取项目" text="连接本机 API…" /> : projects.isError ? <EmptyState title="无法连接本机 API" text={errorMessage(projects.error)} /> : active ? <section className="active-card real-active"><div className="project-identity"><div className="project-identity__mark"><Cube size={30} weight="duotone" /></div><div><div className="eyebrow">当前项目</div><h2>{active.name}</h2><p>{active.code} · {active.plc_brand} {active.plc_model}</p></div></div><div><Status value={active.status} /><button className="button button--primary" onClick={() => navigate("/projects/" + active.id + "/templates")}>继续项目 <ArrowRight size={16} /></button></div></section> : <EmptyState title="还没有项目" text="创建首个 FX5U 或汇川 H5U 项目后，数据会保存在本机 SQLite。" action={<button className="button button--primary" onClick={() => navigate("/projects")}><Plus size={16} />创建项目</button>} />}
    <ProjectTable projects={items.slice(0, 8)} onOpen={(project) => navigate("/projects/" + project.id + "/templates")} />
  </main>;
}

function Metric({ label, value, note, icon }: { label: string; value: string; note: string; icon: ReactNode }) {
  return <div className="stat"><span className="stat__icon tone-blue">{icon}</span><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></div>;
}

function ProjectTable({ projects, onOpen, actions }: { projects: Project[]; onOpen: (project: Project) => void; actions?: (project: Project) => ReactNode }) {
  return <section className="panel real-project-table"><div className="panel__header"><div><h3>项目</h3><p>点击项目继续工程流程</p></div></div><div className="table-wrap"><table><thead><tr><th>项目</th><th>PLC 目标</th><th>状态</th><th>最近更新</th><th>操作</th></tr></thead><tbody>{projects.map((project) => <tr key={project.id}><td><strong>{project.name}</strong><small>{project.code}</small></td><td>{project.plc_model}</td><td><Status value={project.archived ? "已归档" : project.status} /></td><td>{formatTime(project.updated_at)}</td><td><div className="row-buttons"><button onClick={() => onOpen(project)}>打开</button>{actions?.(project)}</div></td></tr>)}</tbody></table>{projects.length === 0 && <EmptyState title="没有项目" text="当前筛选条件下没有记录。" />}</div></section>;
}

function ProjectsPage() {
  const queryClient = useQueryClient(); const navigate = useNavigate(); const [showArchived, setShowArchived] = useState(false); const projects = useProjects(true); const [modal, setModal] = useState<Project | "new" | null>(null);
  const visible = (projects.data || []).filter((item) => showArchived || !item.archived);
  const archiveMutation = useMutation({ mutationFn: (project: Project) => project.archived ? api.restore(project.id) : api.archive(project.id), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["projects"] }); notify("项目状态已更新"); }, onError: notifyError });
  return <main className="hub-page"><PageHeading kicker="P02 · PROJECTS" title="项目管理" description="创建、编辑、归档与恢复真实项目，刷新页面后数据仍保留。" actions={<><label className="toggle-label"><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />显示归档</label><button className="button button--primary" onClick={() => setModal("new")}><Plus size={16} />新建项目</button></>} /><ProjectTable projects={visible} onOpen={(project) => navigate("/projects/" + project.id + "/templates")} actions={(project) => <><button onClick={() => setModal(project)}><PencilSimple size={14} />编辑</button><button onClick={() => archiveMutation.mutate(project)}>{project.archived ? "恢复" : "归档"}</button></>} />{modal && <ProjectModal project={modal === "new" ? undefined : modal} onClose={() => setModal(null)} onSaved={() => { setModal(null); queryClient.invalidateQueries({ queryKey: ["projects"] }); }} />}</main>;
}

function ProjectModal({ project, onClose, onSaved }: { project?: Project; onClose: () => void; onSaved: () => void }) {
  const targets = [{ label: "三菱 FX5U", brand: "三菱电机", series: "MELSEC iQ-F", models: ["FX5U-64MT/ES", "FX5U-80MT/ES", "FX5U-32MT/ES"] }, { label: "汇川 H5U", brand: "汇川技术", series: "H5U", models: ["H5U-1614MTD-A8", "H5U-3232MTD-A8"] }];
  const initialTarget = targets.find((item) => item.brand === project?.plc_brand && item.series === project?.plc_series) || targets[0];
  const [name, setName] = useState(project?.name || ""); const [customer, setCustomer] = useState(project?.customer_code || ""); const [targetIndex, setTargetIndex] = useState(targets.indexOf(initialTarget)); const [model, setModel] = useState(project?.plc_model || initialTarget.models[0]); const [saving, setSaving] = useState(false);
  const target = targets[targetIndex];
  const changeTarget = (index: number) => { setTargetIndex(index); setModel(targets[index].models[0]); };
  const submit = async (event: FormEvent) => { event.preventDefault(); setSaving(true); try { const payload = { name, customer_code: customer, plc_brand: target.brand, plc_series: target.series, plc_model: model }; if (project) await api.updateProject(project, payload); else await api.createProject(payload); notify(project ? "项目已保存" : "项目已创建"); onSaved(); } catch (error) { notifyError(error); } finally { setSaving(false); } };
  return <div className="modal-backdrop"><form className="modal" onSubmit={submit}><div className="modal__header"><span className="modal__icon"><FolderSimple size={22} /></span><div><h2>{project ? "编辑项目" : "新建项目"}</h2><p>目标平台决定模板、生成 Profile 和人工验证包；厂商能力保持未验证。</p></div><button type="button" className="icon-button" onClick={onClose}><X /></button></div><div className="modal__body"><label>项目名称<input required minLength={2} value={name} onChange={(event) => setName(event.target.value)} /></label><label>客户编号<input value={customer} onChange={(event) => setCustomer(event.target.value)} /></label><label>PLC 平台<select value={String(targetIndex)} onChange={(event) => changeTarget(Number(event.target.value))}>{targets.map((item, index) => <option value={index} key={item.series}>{item.label}</option>)}</select></label><label>PLC 型号<select value={model} onChange={(event) => setModel(event.target.value)}>{target.models.map((item) => <option key={item}>{item}</option>)}</select></label><div className="modal__notice"><Info size={18} /><span><strong>环境边界</strong>{target.series === "H5U" ? "AutoShop、厂商模拟和 H5U 硬件均未验证。" : "GX Works3、GX Simulator3 和 FX5U 硬件均未验证。"}</span></div></div><div className="modal__footer"><button type="button" className="button button--soft" onClick={onClose}>取消</button><button className="button button--primary" disabled={saving}>{saving ? "保存中…" : "保存项目"}</button></div></form></div>;
}

function ProjectChooser({ destination, title }: { destination: string; title: string }) {
  const navigate = useNavigate(); const projects = useProjects();
  return <main className="hub-page"><PageHeading kicker="PROJECT SELECTOR" title={title} description="先选择一个真实项目，再进入对应工程页面。" /><ProjectTable projects={(projects.data || []).filter((item) => !item.archived)} onOpen={(project) => navigate("/projects/" + project.id + "/" + destination)} /></main>;
}

function useProjectContext() {
  const { projectId = "" } = useParams();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api.getProject(projectId), enabled: Boolean(projectId) });
  return { projectId, project };
}

function WorkflowNav({ projectId }: { projectId: string }) {
  const location = useLocation();
  return <nav className="workflow-nav" aria-label="工程流程">{workflow.map((item) => <Link key={item.key} className={location.pathname.endsWith("/" + item.key) ? "is-active" : ""} to={"/projects/" + projectId + "/" + item.key}>{item.label}</Link>)}</nav>;
}

function ProjectPage({ children, kicker, title, description, actions }: { children: ReactNode; kicker: string; title: string; description: string; actions?: ReactNode }) {
  const { projectId, project } = useProjectContext();
  return <main className="engineering-page"><PageHeading kicker={kicker} title={project.data ? title + " · " + project.data.name : title} description={description} actions={actions} /><WorkflowNav projectId={projectId} />{project.isError ? <EmptyState title="项目读取失败" text={errorMessage(project.error)} /> : children}</main>;
}

function TemplatePage() {
  const { projectId, project } = useProjectContext(); const template = useQuery({ queryKey: ["template-current"], queryFn: api.currentTemplate }); const [downloading, setDownloading] = useState<string | null>(null);
  const download = async (kind: "blank" | "example") => { if (!project.data) return; setDownloading(kind); try { const blob = await api.downloadTemplate(projectId, kind); saveBlob(blob, project.data.code + "_MachineSpec_v1_" + kind + ".xlsx"); notify(kind === "blank" ? "空白模板已下载" : "完整范例已下载"); } catch (error) { notifyError(error); } finally { setDownloading(null); } };
  const target = project.data ? `${project.data.plc_brand} ${project.data.plc_model}` : "当前 PLC";
  const vendorTool = project.data?.plc_series === "H5U" ? "AutoShop" : "GX Works3";
  return <ProjectPage kicker="P03 · TEMPLATE" title="MachineSpec 模板" description="下载与项目 PLC 目标绑定的 Excel v1 模板。"><section className="template-grid"><article className="panel template-card"><span><FileText size={28} /></span><div><h3>空白工程模板</h3><p>包含 Instructions、Project、Components、Signals、Sequence 与选填工作表。</p><small>{target} · Template v{String(template.data?.version || "1.0")} · Schema v{String(template.data?.schema_version || "1.0")}</small></div><button className="button button--primary" onClick={() => download("blank")} disabled={Boolean(downloading)}><DownloadSimple size={16} />{downloading === "blank" ? "下载中…" : "下载空白模板"}</button></article><article className="panel template-card"><span><ClipboardText size={28} /></span><div><h3>完整填写范例</h3><p>与 {target} 绑定的脱敏示例，用于理解稳定 ID、信号、工步、互锁与异常。</p><small>范例不代表 {vendorTool} 编译通过。</small></div><button className="button button--outline" onClick={() => download("example")} disabled={Boolean(downloading)}><DownloadSimple size={16} />{downloading === "example" ? "下载中…" : "下载完整范例"}</button></article></section><section className="panel boundary-panel"><WarningCircle size={20} /><div><strong>模板处理边界</strong><p>仅接受未加密 .xlsx，最大 20 MB；不执行公式、不接受宏、.xls 或损坏压缩包。</p></div></section></ProjectPage>;
}

function ImportPage() {
  const queryClient = useQueryClient(); const { projectId, project } = useProjectContext(); const inputRef = useRef<HTMLInputElement>(null); const [uploading, setUploading] = useState(false); const [selectedIssue, setSelectedIssue] = useState<ValidationIssue | null>(null); const [editValue, setEditValue] = useState("");
  const imported = useQuery({ queryKey: ["import", project.data?.current_import_id], queryFn: () => api.getImport(project.data!.current_import_id!), enabled: Boolean(project.data?.current_import_id) });
  const spec = imported.data?.spec_revision || null;
  useEffect(() => { setSelectedIssue(spec?.issues[0] || null); }, [spec?.id]);
  const upload = async (file?: File) => { if (!file) return; setUploading(true); try { await api.uploadImport(projectId, file); await queryClient.invalidateQueries({ queryKey: ["project", projectId] }); await queryClient.invalidateQueries({ queryKey: ["import"] }); notify("Excel 已上传并完成确定性校验"); } catch (error) { notifyError(error); } finally { setUploading(false); if (inputRef.current) inputRef.current.value = ""; } };
  const patch = async () => { if (!spec || !selectedIssue?.sheet || !selectedIssue.row_number || !selectedIssue.column_name) return; try { await api.patchCells(spec.import_id, spec.revision, [{ sheet: selectedIssue.sheet, row: selectedIssue.row_number, column: selectedIssue.column_name, value: editValue }]); await queryClient.invalidateQueries({ queryKey: ["import"] }); await queryClient.invalidateQueries({ queryKey: ["project", projectId] }); notify("已创建新的 MachineSpec revision，原 Excel 未被覆盖"); } catch (error) { notifyError(error); } };
  const validate = async () => { if (!spec) return; try { await api.validateImport(spec.import_id, imported.data!.revision); await queryClient.invalidateQueries({ queryKey: ["import"] }); notify("已重新执行全部确定性规则"); } catch (error) { notifyError(error); } };
  return <ProjectPage kicker="P04 · IMPORT" title="Excel 导入与校验" description="原文件不可变保存，页面修订会创建新的 MachineSpec revision。" actions={<><input ref={inputRef} type="file" hidden accept=".xlsx" onChange={(event) => upload(event.target.files?.[0])} /><button className="button button--primary" disabled={uploading} onClick={() => inputRef.current?.click()}><UploadSimple size={16} />{uploading ? "校验中…" : "上传 XLSX"}</button></>}>
    {!project.data?.current_import_id ? <EmptyState title="尚未导入工程资料" text="先在 P03 下载模板，填写后上传 .xlsx。" /> : imported.isLoading ? <EmptyState title="正在读取导入版本" text="请稍候…" /> : spec ? <div className="import-layout"><section className="panel issue-list"><div className="panel__header"><div><h3>校验问题</h3><p>Revision {spec.sequence} · {spec.issues.length} 项</p></div><button className="button button--soft" onClick={validate}>重新校验</button></div>{spec.issues.map((issue) => <button key={issue.id} className={selectedIssue?.id === issue.id ? "is-active" : ""} onClick={() => { setSelectedIssue(issue); setEditValue(""); }}><SeverityIcon issue={issue} /><span><strong>{issue.title}</strong><small>{issue.sheet || "全局"} · {issue.code}</small></span><b>{issue.severity}</b></button>)}{spec.issues.length === 0 && <EmptyState title="没有校验问题" text="可以进入 P05 规格审阅。" />}</section><section className="panel issue-detail">{selectedIssue ? <><div className="panel__header"><div><h3>{selectedIssue.title}</h3><p>{selectedIssue.code}</p></div><Status value={selectedIssue.severity} /></div><div className="issue-explanation"><h4>规则说明</h4><p>{selectedIssue.detail}</p><dl><dt>工作表</dt><dd>{selectedIssue.sheet || "-"}</dd><dt>位置</dt><dd>{selectedIssue.row_number ? "第 " + selectedIssue.row_number + " 行 · " + (selectedIssue.column_name || "") : "全局"}</dd><dt>对象 ID</dt><dd>{selectedIssue.entity_id || "-"}</dd></dl>{selectedIssue.sheet && selectedIssue.row_number && selectedIssue.column_name && <label className="inline-editor">修订该单元格<input value={editValue} onChange={(event) => setEditValue(event.target.value)} placeholder="输入修订值" /><button className="button button--primary" onClick={patch} disabled={!editValue}>创建新 revision</button></label>}</div></> : <EmptyState title="选择一个问题" text="右侧将显示来源定位与修订入口。" />}</section><SpecTable spec={spec.data} /></div> : <EmptyState title="导入失败" text={imported.data?.failure_reason || errorMessage(imported.error)} />}
  </ProjectPage>;
}

function SeverityIcon({ issue }: { issue: ValidationIssue }) { return issue.severity === "blocker" ? <WarningCircle size={18} weight="fill" color="#d34d55" /> : issue.severity === "warning" ? <WarningCircle size={18} weight="fill" color="#d49325" /> : <Info size={18} color="#3578b9" />; }

function SpecTable({ spec }: { spec: MachineSpec }) {
  const [sheet, setSheet] = useState<"components" | "signals" | "sequence">("signals"); const rows = spec[sheet] as Array<Record<string, unknown>>;
  const columns = useMemo(() => rows.length ? Object.keys(rows[0]).filter((item) => item !== "source").slice(0, 6) : [], [rows]);
  return <section className="panel spec-table"><div className="panel__header"><div><h3>结构化工作表</h3><p>每行保留源 Excel 定位</p></div><select value={sheet} onChange={(event) => setSheet(event.target.value as typeof sheet)}><option value="components">Components</option><option value="signals">Signals</option><option value="sequence">Sequence</option></select></div><div className="table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row[columns[0]] || index)}>{columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}</tr>)}</tbody></table></div></section>;
}

function ReviewPage() {
  const queryClient = useQueryClient(); const { projectId, project } = useProjectContext(); const revision = useQuery({ queryKey: ["revision", project.data?.current_spec_revision_id], queryFn: () => api.getRevision(project.data!.current_spec_revision_id!), enabled: Boolean(project.data?.current_spec_revision_id) }); const [activeView, setActiveView] = useState("device_relationship"); const spec = revision.data;
  useEffect(() => { if (spec && !spec.required_views.includes(activeView)) setActiveView(spec.required_views[0]); }, [spec?.id]);
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["revision"] }); queryClient.invalidateQueries({ queryKey: ["project", projectId] }); };
  const accept = async (issue: ValidationIssue) => { if (!spec) return; const reason = window.prompt("填写接受该 warning 的工程理由：", "工程师已复核，风险可接受"); if (!reason) return; try { await api.acceptWarning(spec, issue.id, reason); refresh(); notify("Warning 已接受并写入审计记录"); } catch (error) { notifyError(error); } };
  const confirm = async () => { if (!spec) return; try { await api.confirmView(spec, activeView); refresh(); notify(viewLabels[activeView] + "已确认"); } catch (error) { notifyError(error); } };
  const lock = async () => { if (!spec) return; try { await api.lockSpec(spec); refresh(); notify("MachineSpec 已生成不可变锁定快照"); } catch (error) { notifyError(error); } };
  return <ProjectPage kicker="P05 · REVIEW" title="MachineSpec 多视图审阅" description="所有对象可追溯到 Excel 来源；数据修改会使旧确认失效。">
    {!project.data?.current_spec_revision_id ? <EmptyState title="没有可审阅的规格" text="请先在 P04 上传并校验 Excel。" /> : revision.isLoading ? <EmptyState title="正在生成审阅视图" text="请稍候…" /> : spec ? <><div className="review-toolbar"><Status value={spec.status} /><span>Revision {spec.sequence}</span><span>{spec.content_hash.slice(0, 12)}</span><button className="button button--primary" disabled={spec.status === "locked"} onClick={lock}><CheckCircle size={16} />锁定规格</button></div><div className="tab-strip">{spec.required_views.map((view) => { const confirmed = spec.confirmations.some((item) => item.view === view); return <button key={view} className={activeView === view ? "is-active" : ""} onClick={() => setActiveView(view)}>{confirmed && <CheckCircle size={14} weight="fill" />}{viewLabels[view] || view}</button>; })}</div><div className="review-layout"><section className="panel review-canvas"><ReviewView view={activeView} spec={spec} /></section><aside className="panel review-summary"><div className="panel__header"><div><h3>锁定门禁</h3><p>确定性规则与工程确认</p></div></div><Gate label="Blocker" value={spec.issues.filter((item) => item.severity === "blocker" && !item.resolved).length} /><Gate label="未接受 Warning" value={spec.issues.filter((item) => item.severity === "warning" && !item.resolved).length} /><Gate label="未确认视图" value={spec.required_views.filter((view) => !spec.confirmations.some((item) => item.view === view)).length} />{spec.issues.filter((item) => item.severity === "warning" && !item.resolved).map((issue) => <button key={issue.id} className="warning-action" onClick={() => accept(issue)}><WarningCircle size={15} />接受：{issue.title}</button>)}<button className="button button--outline" disabled={spec.confirmations.some((item) => item.view === activeView) || spec.status === "locked"} onClick={confirm}><Check size={15} />确认当前视图</button></aside></div></> : <EmptyState title="规格读取失败" text={errorMessage(revision.error)} />}
  </ProjectPage>;
}

function Gate({ label, value }: { label: string; value: number }) { return <div className="review-check">{value === 0 ? <CheckCircle size={17} weight="fill" /> : <WarningCircle size={17} />}<span>{label}</span><small>{value === 0 ? "通过" : value + " 项"}</small></div>; }

function ReviewView({ view, spec }: { view: string; spec: SpecRevision }) {
  const data = spec.data;
  if (view === "device_relationship") return <div className="device-tree"><strong>{String(data.project.project_name || "项目")}</strong><div>{data.components.map((item) => <button key={String(item.component_id)} title={"来源 " + String((item.source as Record<string, unknown>)?.sheet || "Components") + " 第 " + String((item.source as Record<string, unknown>)?.row || "-") + " 行"}>{String(item.display_name || item.component_id)}</button>)}</div></div>;
  if (view === "process_flow") return <div className="process-flow">{data.sequence.map((item, index) => <button key={String(item.step_id)}><span>{index + 1}</span><strong>{String(item.display_name || item.step_id)}</strong><small>{String(item.completion_condition || "")}</small></button>)}</div>;
  if (view === "io_mapping" || view === "signal_timing") return <div className={view === "signal_timing" ? "timing-chart" : "matrix-view"}>{data.signals.map((item) => <div key={String(item.signal_id)}><strong>{String(item.signal_id)}</strong><span>{String(item.direction)} · {String(item.address || "内部")}</span>{view === "signal_timing" ? <i /> : <span>{String(item.data_type)}</span>}</div>)}</div>;
  if (view === "interlock_matrix") return <div className="matrix-view">{data.interlocks.map((item) => <div key={String(item.interlock_id)}><strong>{String(item.interlock_id)}</strong><span>{String(item.action_id)}</span><span>{String(item.allow_condition)}</span></div>)}</div>;
  if (view === "exceptions") return <div className="matrix-view">{data.exceptions.map((item) => <div key={String(item.exception_id)}><strong>{String(item.exception_id)}</strong><span>{String(item.condition)}</span><span>{String(item.response)}</span></div>)}</div>;
  if (view === "cycle_analysis") return <div className="cycle-grid">{data.sequence.map((item) => <div key={String(item.step_id)}><strong>{String(item.display_name)}</strong><span>{String(item.expected_duration || "-")} {String(item.duration_unit || "")}</span></div>)}</div>;
  return <SpecTable spec={data} />;
}

function ProgramPage() {
  const queryClient = useQueryClient(); const { projectId, project } = useProjectContext(); const branches = useQuery({ queryKey: ["branches", projectId], queryFn: () => api.listBranches(projectId) }); const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => api.listRuns(projectId) }); const [branchId, setBranchId] = useState(""); const activeId = branchId || branches.data?.[0]?.id || ""; const files = useQuery({ queryKey: ["files", activeId], queryFn: () => api.listFiles(activeId), enabled: Boolean(activeId) }); const [path, setPath] = useState(""); const defaultEditablePath = files.data?.files.find((item) => item.path === "src/PRG_AutoCycle.st")?.path || files.data?.files.find((item) => item.path.startsWith("src/") && item.path.endsWith(".st"))?.path || files.data?.files[0]?.path || ""; const selectedPath = path || defaultEditablePath; const immutablePath = selectedPath === "generated/ControlIR.json" || selectedPath === "tests/TestSpec.json"; const file = useQuery({ queryKey: ["file", activeId, selectedPath], queryFn: () => api.getFile(activeId, selectedPath), enabled: Boolean(activeId && selectedPath) }); const fileKey = activeId && selectedPath ? `${activeId}:${selectedPath}` : ""; const [editor, setEditor] = useState({ key: "", content: "" }); const [message, setMessage] = useState("Review generated program");
  useEffect(() => { if (file.data?.path === selectedPath) setEditor({ key: fileKey, content: file.data.content }); }, [file.data?.content, file.data?.path, fileKey, selectedPath]);
  const editorReady = Boolean(fileKey && editor.key === fileKey && file.data?.path === selectedPath && file.data.branch_revision === files.data?.branch.revision);
  const generate = async () => { const specId = project.data?.current_spec_revision_id; if (!specId) return notifyError(new Error("没有已锁定 MachineSpec")); try { await api.generate(projectId, specId, "generated/spec-" + Date.now()); queryClient.invalidateQueries({ queryKey: ["branches", projectId] }); queryClient.invalidateQueries({ queryKey: ["runs", projectId] }); notify("已生成确定性 ST 骨架和 TestSpec；厂商编译未验证"); } catch (error) { notifyError(error); } };
  const save = async () => { if (!files.data?.branch || !selectedPath || immutablePath) return; if (!editorReady || file.data?.path !== selectedPath) return notifyError(new Error("当前文件尚未完整加载，请稍后再保存")); try { const result = await api.saveFile(activeId, selectedPath, editor.content, files.data.branch.revision); await queryClient.invalidateQueries({ queryKey: ["files", activeId] }); queryClient.setQueryData(["file", activeId, selectedPath], { path: selectedPath, content: editor.content, branch_revision: result.branch.revision }); notify("文件已保存到工作分支，尚未提交"); } catch (error) { notifyError(error); } };
  const commit = async () => { if (!files.data?.branch) return; try { await api.commit(files.data.branch, message); await Promise.all([queryClient.invalidateQueries({ queryKey: ["files", activeId] }), queryClient.invalidateQueries({ queryKey: ["branches", projectId] }), queryClient.invalidateQueries({ queryKey: ["runs", projectId] }), queryClient.invalidateQueries({ queryKey: ["automated-reviews", projectId] })]); notify("程序修改已提交到本地 Git 历史"); } catch (error) { notifyError(error); } };
  const latestRun = runs.data?.[0];
  return <ProjectPage kicker="P06 · PROGRAM" title="程序工作区" description={`从已锁定规格生成确定性 ${project.data?.plc_brand || "PLC"} ST；不声明通过厂商 IDE 编译。`} actions={<button className="button button--primary" disabled={project.data?.status !== "规格锁定"} onClick={generate}><Code size={16} />生成程序</button>}>
    {branches.data?.length ? <><div className="program-toolbar"><GitBranch size={15} /><select value={activeId} onChange={(event) => { setBranchId(event.target.value); setPath(""); }}>{branches.data.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select><span><Status value={files.data?.branch.status || "读取中"} /></span><span>生成器 {latestRun?.generator_version || "-"}</span><button disabled={immutablePath || !editorReady} onClick={save}>保存文件</button></div><div className="program-layout"><section className="panel file-tree"><div className="panel__header"><div><h3>程序树</h3><p>{files.data?.files.length || 0} 个文件</p></div></div>{files.data?.files.map((item: ProgramFile) => <button key={item.path} className={selectedPath === item.path ? "is-active" : ""} onClick={() => setPath(item.path)}><FileCode size={15} />{item.path}</button>)}</section><section className="code-panel"><div className="code-panel__header"><span>{selectedPath || "选择文件"}{immutablePath ? " · 不可变基线（只读）" : !editorReady ? " · 正在加载（只读）" : ""}</span><button disabled={immutablePath || !editorReady} onClick={save}>保存</button></div><textarea className="code-editor" value={editorReady ? editor.content : ""} onChange={(event) => editorReady && setEditor({ key: fileKey, content: event.target.value })} readOnly={immutablePath || !editorReady} aria-readonly={immutablePath || !editorReady} aria-busy={!editorReady} placeholder={editorReady ? undefined : "正在读取当前 Commit 文件…"} spellCheck={false} /></section><aside className="panel trace-panel"><div className="panel__header"><div><h3>提交与追溯</h3><p>不改写历史</p></div></div><label className="commit-box">提交说明<input value={message} onChange={(event) => setMessage(event.target.value)} /><button className="button button--primary" disabled={files.data?.branch.status !== "modified"} onClick={commit}>创建 Commit</button></label>{latestRun?.warnings.map((warning) => <div className="trace-item" key={warning.code}><span>{warning.code}</span><strong>{warning.message}</strong></div>)}{latestRun?.trace_links.slice(0, 5).map((link, index) => <div className="trace-item" key={index}><span>{String(link.output_path)}:{String(link.output_line)}</span><strong>{String(link.entity_id)}</strong><small>{String(link.source_sheet)} 第 {String(link.source_row)} 行</small></div>)}</aside></div></> : <EmptyState title="尚未生成程序工作区" text={project.data?.status === "规格锁定" ? "点击“生成程序”创建独立分支、ST、Control IR 与 TestSpec。" : "先在 P05 完成规格锁定，才能生成程序。"} action={project.data?.status === "规格锁定" ? <button className="button button--primary" onClick={generate}>生成程序</button> : undefined} />}
  </ProjectPage>;
}

function comparisonValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function comparisonSource(source?: { sheet?: string | null; row?: number | null; column?: string | null } | null) {
  if (!source?.sheet) return "无 Excel 定位";
  return `${source.sheet}${source.row ? ` 第 ${source.row} 行` : ""}${source.column ? ` · ${source.column}` : ""}`;
}

function VersionSectionDetail({ section, sourceDiff, sameCommit }: { section: VersionComparisonSection; sourceDiff: string; sameCommit: boolean }) {
  if (section.id === "source") {
    return <pre className="source-diff">{sourceDiff || (sameCommit ? "两个选择指向同一 Commit。" : "两个 Commit 的文本源码没有差异。")}</pre>;
  }
  return <div className="structured-diff">
    {section.note && <div className="comparison-note"><WarningCircle size={17} /><span>{section.note}</span></div>}
    {section.items.length === 0 ? <div className="comparison-empty"><CheckCircle size={20} /><span><strong>该工件无变化</strong>两个明确 Commit 的结构化内容一致。</span></div> : section.items.map((item) => <article className={`comparison-item comparison-item--${item.change}`} key={`${item.entity_type}:${item.entity_id}`}>
      <div className="comparison-item__head"><Status value={item.change} /><span><strong>{item.entity_id}</strong><small>{item.entity_type}</small></span><em>{comparisonSource(item.source_after || item.source_before)}</em></div>
      <div className="comparison-fields">{item.fields.map((field) => <div key={field.field}><code>{field.field}</code><span className="comparison-before">{comparisonValue(field.before)}</span><ArrowRight size={13} /><span className="comparison-after">{comparisonValue(field.after)}</span></div>)}</div>
    </article>)}
  </div>;
}

function ProjectTimelineView({ timeline }: { timeline?: { events: ProjectTimelineEvent[]; summary: { total: number; by_type: Record<string, number> }; claim_boundary: string } }) {
  const events = timeline?.events || [];
  return <section className="panel project-timeline"><div className="panel__header"><div><h3>项目时间线</h3><p>规格、代码、审核、编译、模拟、发布与现场证据的只读汇总</p></div><Status value={timeline ? `${timeline.summary.total} 条记录` : "读取中"} /></div>{events.length === 0 ? <EmptyState title="尚无时间线记录" text="完成项目动作后，系统会按 UTC 时间生成可追溯记录。" /> : <div className="project-timeline__list">{events.map((event) => <article className="project-timeline__event" key={event.id}><div className="project-timeline__rail"><span className="project-timeline__dot" /></div><time>{formatTime(event.occurred_at)}</time><div className="project-timeline__body"><div className="project-timeline__title"><strong>{event.title}</strong><Status value={event.status} /></div><p>{event.detail}</p><dl><dt>作者</dt><dd>{event.author}</dd><dt>请求</dt><dd>{event.request}</dd><dt>工具</dt><dd>{event.tool}</dd><dt>验证等级</dt><dd>{event.verification_level}</dd></dl>{Object.keys(event.source).length > 0 && <small>定位：{JSON.stringify(event.source)}</small>}</div></article>)}</div>}<div className="project-timeline__boundary"><Info size={16} /><span>{timeline?.claim_boundary || "时间线仅聚合本机记录；厂商工具、真实 PLC、硬件和电气工程师确认未验证。"}</span></div></section>;
}

function VersionPage() {
  const queryClient = useQueryClient();
  const { projectId } = useProjectContext();
  const branches = useQuery({ queryKey: ["branches", projectId], queryFn: () => api.listBranches(projectId) });
  const commits = useQuery({ queryKey: ["commits", projectId], queryFn: () => api.listCommits(projectId) });
  const [baseId, setBaseId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [restoreName, setRestoreName] = useState("");
  const [sectionId, setSectionId] = useState("source");
  const [timelineVisible, setTimelineVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const commitItems = commits.data || [];
  const resolvedBaseId = baseId || commitItems[1]?.id || commitItems[0]?.id || "";
  const resolvedTargetId = targetId || commitItems[0]?.id || "";
  const baseCommit = commitItems.find((item) => item.id === resolvedBaseId);
  const sourceBranch = branches.data?.find((item) => item.id === baseCommit?.branch_id);
  const comparison = useQuery({ queryKey: ["commit-comparison", resolvedBaseId, resolvedTargetId], queryFn: () => api.compareCommits(resolvedBaseId, resolvedTargetId), enabled: Boolean(resolvedBaseId && resolvedTargetId) });
  const timeline = useQuery({ queryKey: ["project-timeline", projectId], queryFn: () => api.getProjectTimeline(projectId), enabled: timelineVisible });
  const restore = async () => {
    if (!baseCommit || !sourceBranch) return;
    setBusy(true);
    try {
      const result = await api.restoreCommit(baseCommit, sourceBranch, restoreName || undefined);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["branches", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["commits", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["runs", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["automated-reviews", projectId] }),
      ]);
      setRestoreName("");
      notify("已创建恢复分支 " + result.branch.name + "；旧历史和验证结果未改写");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };
  const comparisonTitle = comparison.data ? comparison.data.base.git_sha.slice(0, 12) + " → " + comparison.data.target.git_sha.slice(0, 12) : "选择两个 Commit";
  const sections = comparison.data?.sections || [];
  const activeSection = sections.find((item) => item.id === sectionId) || sections[0];
  return <ProjectPage kicker="P11 · VERSION" title="版本中心" description="比较两个明确 Commit，或查看规格到现场证据的统一只读时间线；恢复不改写历史。"><div className="version-mode"><button className={timelineVisible ? "button button--outline" : "button button--primary"} onClick={() => setTimelineVisible(false)}><GitBranch size={15} />版本比较</button><button className={timelineVisible ? "button button--primary" : "button button--outline"} onClick={() => setTimelineVisible(true)}><Pulse size={15} />项目时间线</button></div>{timelineVisible ? <ProjectTimelineView timeline={timeline.data} /> : <div className="version-layout"><section className="panel"><div className="panel__header"><div><h3>程序分支</h3><p>{branches.data?.length || 0} 条</p></div></div>{branches.data?.map((branch: ProgramBranch) => <div className="branch-row" key={branch.id}><GitBranch size={16} /><span><strong>{branch.name}</strong><small>{branch.head_commit?.slice(0, 12) || "尚无提交"}</small></span><Status value={branch.status} /></div>)}</section><section className="panel"><div className="panel__header"><div><h3>Commit 历史</h3><p>不可变本地 Git 记录</p></div></div>{commitItems.map((commit: ProgramCommit) => <button className={"commit-row " + (resolvedBaseId === commit.id || resolvedTargetId === commit.id ? "is-selected" : "")} key={commit.id} onClick={() => setTargetId(commit.id)}><Code size={16} /><span><strong>{commit.message}</strong><small>{commit.git_sha.slice(0, 12)} · {formatTime(commit.created_at)}</small></span><ArrowRight size={15} /></button>)}</section><section className="code-panel diff-panel"><div className="version-compare-toolbar"><label>基线 Commit<select aria-label="基线 Commit" value={resolvedBaseId} onChange={(event) => setBaseId(event.target.value)}>{commitItems.map((commit) => <option key={commit.id} value={commit.id}>{commit.message} · {commit.git_sha.slice(0, 8)}</option>)}</select></label><label>目标 Commit<select aria-label="目标 Commit" value={resolvedTargetId} onChange={(event) => setTargetId(event.target.value)}>{commitItems.map((commit) => <option key={commit.id} value={commit.id}>{commit.message} · {commit.git_sha.slice(0, 8)}</option>)}</select></label><label>恢复分支名（可选）<input aria-label="恢复分支名" value={restoreName} onChange={(event) => setRestoreName(event.target.value)} placeholder="restore/历史基线" /></label><button className="button button--outline" disabled={busy || !baseCommit || !sourceBranch} onClick={restore}><GitBranch size={15} />{busy ? "创建中…" : "从基线创建恢复分支"}</button></div><div className="version-boundary"><Info size={17} /><span>恢复只复制历史源码基线并重新运行自动审核，不继承旧静态审计、参考模拟、候选包或厂商验证。</span></div><div className="comparison-summary"><span><strong>{comparison.data?.summary.changed_sections || 0}</strong> 变化工件</span><span><strong>{comparison.data?.summary.changed_items || 0}</strong> 变化对象</span><code>{comparison.data?.comparison_hash.slice(0, 16) || "正在计算"}</code></div><div className="comparison-tabs" role="tablist" aria-label="版本比较工件">{sections.map((section) => <button role="tab" aria-selected={activeSection?.id === section.id} className={activeSection?.id === section.id ? "is-active" : ""} key={section.id} onClick={() => setSectionId(section.id)}><span>{section.label}</span><small>{section.summary.added}+ / {section.summary.removed}- / {section.summary.changed}~</small>{section.verification_level === "unverified" && <em>未验证</em>}</button>)}</div><div className="code-panel__header"><span>{comparisonTitle} · {activeSection?.label || "结构化比较"}</span><Status value={activeSection?.status || "读取中"} /></div>{comparison.isLoading ? <div className="comparison-loading">正在读取两个不可变 Commit…</div> : comparison.isError ? <div className="comparison-loading comparison-loading--error">{errorMessage(comparison.error)}</div> : activeSection ? <VersionSectionDetail section={activeSection} sourceDiff={comparison.data?.source_diff || ""} sameCommit={Boolean(comparison.data?.same_commit)} /> : <div className="comparison-loading">尚无可比较 Commit。</div>}<div className="version-claim">{comparison.data?.claim_boundary || "厂商二进制工程、真实编译、真实模拟和硬件结果未验证。"}</div></section></div>}</ProjectPage>;
}

function CapabilityPage() {
  const { capability = "" } = useParams();
  if (capability === "compile") return <CompilePage />;
  if (capability === "simulation") return <SimulationPage />;
  if (capability === "release") return <ReleasePage />;
  if (capability === "monitor") return <MonitoringPage />;
  const labels: Record<string, string> = { release: "P09 发布包", monitor: "P10 在线监控" };
  return <ProjectPage kicker="M4 BOUNDARY" title={labels[capability] || capability} description="该页面尚未接入真实设备能力。"><UnavailableBody detail={capability === "monitor" ? "未实现 PLC 下载、RUN/STOP、强制输出或真实在线连接。" : "发布能力将在真实厂商编译、模拟和安全审查之后接入。"} /></ProjectPage>;
}

function ReleasePage() {
  const queryClient = useQueryClient();
  const { projectId } = useProjectContext();
  const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => api.listRuns(projectId) });
  const reviews = useQuery({ queryKey: ["automated-reviews", projectId], queryFn: () => api.listAutomatedReviews(projectId) });
  const simulations = useQuery({ queryKey: ["simulation-runs", projectId], queryFn: () => api.listSimulationRuns(projectId) });
  const candidates = useQuery({ queryKey: ["release-candidates", projectId], queryFn: () => api.listReleaseCandidates(projectId) });
  const acceptances = useQuery({ queryKey: ["acceptance-runs", projectId], queryFn: () => api.listAcceptanceRuns(projectId) });
  const [runId, setRunId] = useState("");
  const [busy, setBusy] = useState(false);
  const [verification, setVerification] = useState<CandidateVerification | null>(null);
  const [acceptance, setAcceptance] = useState<ProjectAcceptanceRun | null>(null);
  const evidenceInputRef = useRef<HTMLInputElement>(null);
  const [evidenceKind, setEvidenceKind] = useState<ReleaseEvidenceKind>("vendor_compile");
  const [evidenceNote, setEvidenceNote] = useState("");
  const selectedRunId = runId || runs.data?.[0]?.id || "";
  const readiness = useQuery({ queryKey: ["project-readiness", projectId, selectedRunId], queryFn: () => api.getProjectReadiness(projectId, selectedRunId), enabled: Boolean(selectedRunId) });
  const run = runs.data?.find((item) => item.id === selectedRunId);
  const review = reviews.data?.find((item) => item.generation_run_id === selectedRunId);
  const simulation = simulations.data?.find((item) => item.generation_run_id === selectedRunId && item.status === "review_ready");
  const candidate = candidates.data?.find((item) => item.generation_run_id === selectedRunId && item.program_commit_id === review?.program_commit_id);
  const candidateEvidence = useQuery({
    queryKey: ["release-candidate-evidence", candidate?.id],
    queryFn: () => api.listReleaseCandidateEvidence(candidate!.id),
    enabled: Boolean(candidate?.id),
  });
  const persistedAcceptance = acceptances.data?.find((item) => item.generation_run_id === selectedRunId && item.program_commit_id === review?.program_commit_id && item.release_candidate_id === candidate?.id) || null;
  const activeAcceptance = acceptance?.generation_run_id === selectedRunId ? acceptance : persistedAcceptance;

  const createCandidate = async () => {
    if (!run) return;
    setBusy(true);
    try {
      const result = await api.createReleaseCandidate(projectId, run.id, run.revision);
      await queryClient.invalidateQueries({ queryKey: ["release-candidates", projectId] });
      notify(result.reused ? "不可变输入未变化，已复用交付候选包" : "交付候选包已生成；仍需集中外部验证");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const download = async (item: ReleaseCandidate) => {
    try {
      const blob = await api.downloadArtifact(item.package_artifact_id);
      saveBlob(blob, "Kongpu-" + item.version + ".zip");
      notify("交付候选包已下载");
    } catch (error) {
      notifyError(error);
    }
  };

  const downloadValidationMaterial = async (item: ReleaseCandidate, kind: "json" | "checklist") => {
    try {
      const blob = await api.downloadValidationMaterial(item.id, kind);
      const suffix = kind === "json" ? "validation.json" : "validation-checklist.md";
      saveBlob(blob, "Kongpu-" + item.version + "-" + suffix);
      notify(kind === "json" ? "验证 JSON 已下载" : "可填写验证清单已下载");
    } catch (error) {
      notifyError(error);
    }
  };

  const verifyCandidate = async () => {
    if (!candidate) return;
    setBusy(true);
    try {
      const result = await api.verifyReleaseCandidate(candidate);
      setVerification(result);
      notify(result.reused ? "候选 ZIP 输入未变化，已复用完整性复核报告" : "候选 ZIP 已重新读取并通过独立完整性复核");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const createAcceptance = async () => {
    if (!run || !candidate) return;
    setBusy(true);
    try {
      const result = await api.createAcceptanceRun(projectId, run, candidate.id);
      setAcceptance(result);
      await queryClient.invalidateQueries({ queryKey: ["acceptance-runs", projectId] });
      notify(result.reused ? "自动验收输入未变化，已复用不可变报告" : "项目自动验收完成；厂商、硬件和电气验证仍待集中进行");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const uploadCandidateEvidence = async (file?: File) => {
    if (!candidate || !file) return;
    setBusy(true);
    try {
      const result = await api.uploadReleaseCandidateEvidence(candidate, file, evidenceKind, evidenceNote);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["release-candidates", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["release-candidate-evidence", candidate.id] }),
      ]);
      notify(result.reused ? "相同候选证据已存在，已复用原记录" : "候选证据已按 SHA-256 保存；验证等级保持 manual_unverified");
      setEvidenceNote("");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
      if (evidenceInputRef.current) evidenceInputRef.current.value = "";
    }
  };

  const downloadEvidence = async (item: ReleaseCandidateEvidence) => {
    try {
      const blob = await api.downloadArtifact(item.source_artifact_id);
      saveBlob(blob, item.original_name);
      notify("候选证据原件已下载");
    } catch (error) {
      notifyError(error);
    }
  };

  const gates = candidate?.manifest.external_validation_gates || review?.external_validation_gates || [];
  return <ProjectPage kicker="P09 · DELIVERY CANDIDATE" title="交付候选包" description="把当前通过自动审核的 Commit、参考模拟与证据打成确定性不可变 ZIP；这不是正式发布或厂商通过。">
    {!runs.data?.length ? <EmptyState title="尚无程序生成任务" text="先在 P06 生成程序，在 P07 完成自动审核，并在 P08 运行参考模拟。" /> : <>
      <div className="verification-toolbar release-toolbar"><label>生成任务<select value={selectedRunId} onChange={(event) => setRunId(event.target.value)}>{runs.data.map((item) => <option value={item.id} key={item.id}>{item.generator_version} · {formatTime(item.updated_at)}</option>)}</select></label><button className="button button--primary" disabled={busy || !run} onClick={createCandidate}><DownloadSimple size={16} />{busy ? "生成中…" : candidate ? "校验并复用候选包" : "生成交付候选包"}</button></div>
      <div className="release-workbench"><section className="panel release-readiness"><div className="panel__header"><div><h3>自动交付门禁</h3><p>所有检查都绑定当前程序 Commit</p></div><Status value={readiness.data?.status || activeAcceptance?.status || candidate?.status || "待生成"} /></div>{readiness.data && <div className="readiness-preflight"><div><strong>本机就绪度</strong><span>{readiness.data.summary.ready} / {readiness.data.summary.total} 项自动门禁完成；外部待验证 {readiness.data.summary.external_pending} 项</span></div><Status value={readiness.data.status} /></div>}<div className="readiness-list"><ReleaseGate label="当前 Commit 自动审核" ready={review?.status === "passed"} value={review?.status || "尚无报告"} /><ReleaseGate label="控谱参考逻辑模拟" ready={Boolean(simulation)} value={simulation?.status || "尚未运行"} /><ReleaseGate label="候选 ZIP 独立复核" ready={Boolean(verification || activeAcceptance?.candidate_verification_id)} value={verification?.status || (activeAcceptance?.candidate_verification_id ? "passed" : "尚未复核")} /><ReleaseGate label="厂商/硬件/电气验证" ready={false} value="pending_external" /></div>{candidate ? <div className="candidate-detail"><div className="candidate-detail__head"><span><strong>{candidate.version}</strong><small>{candidate.verification_level} · {formatTime(candidate.created_at)}</small></span><div className="candidate-actions"><button className="button button--outline" disabled={busy} onClick={verifyCandidate}><CheckCircle size={16} />独立复核 ZIP</button><button className="button button--outline" onClick={() => downloadValidationMaterial(candidate, "json")}><DownloadSimple size={16} />下载验证 JSON</button><button className="button button--outline" onClick={() => downloadValidationMaterial(candidate, "checklist")}><DownloadSimple size={16} />下载填写清单</button><button className="button button--outline" onClick={() => download(candidate)}><DownloadSimple size={16} />下载 ZIP</button></div></div><dl><dt>Program Commit</dt><dd><code>{candidate.program_commit_id}</code></dd><dt>Manifest SHA-256</dt><dd><code>{candidate.manifest_hash}</code></dd><dt>ZIP SHA-256</dt><dd><code>{candidate.package_sha256}</code></dd><dt>包内文件</dt><dd>{candidate.manifest.entries.length} 项 · {candidate.package_size_bytes} bytes</dd><dt>候选证据</dt><dd>{candidate.evidence_count} 项 · manual_unverified</dd></dl><div className="review-claim"><Info size={17} /><span>{candidate.manifest.claim_boundary}</span></div><section className="candidate-evidence"><div className="candidate-evidence__heading"><div><strong>候选外部证据台账</strong><small>原件按 SHA-256 不可变保存；上传不会升级验证等级或改变候选结论。</small></div><Status value="manual_unverified" /></div><div className="candidate-evidence__form"><label>证据类型<select value={evidenceKind} onChange={(event) => setEvidenceKind(event.target.value as ReleaseEvidenceKind)}><option value="environment">环境与版本</option><option value="vendor_import">厂商工程导入</option><option value="vendor_compile">厂商编译</option><option value="vendor_simulation">厂商模拟</option><option value="hardware_test">硬件台架</option><option value="electrical_signoff">电气签字</option><option value="other">其他</option></select></label><label>证据备注（可选）<input value={evidenceNote} maxLength={2000} onChange={(event) => setEvidenceNote(event.target.value)} placeholder="记录软件版本、台架或验证步骤" /></label><input ref={evidenceInputRef} type="file" hidden aria-label="候选证据文件" onChange={(event) => uploadCandidateEvidence(event.target.files?.[0])} /><button className="button button--outline" disabled={busy} onClick={() => evidenceInputRef.current?.click()}><UploadSimple size={16} />上传证据原件</button></div><div className="candidate-evidence__list">{candidateEvidence.data?.map((item) => <article key={item.id}><span><strong>{item.original_name}</strong><small>{item.evidence_kind} · {formatTime(item.created_at)} · {item.size_bytes} bytes</small></span><code>{item.sha256}</code><Status value={item.verification_level} /><button className="button button--outline" onClick={() => downloadEvidence(item)}><DownloadSimple size={15} />原件</button>{item.note && <p>{item.note}</p>}</article>)}{candidateEvidence.isLoading && <p className="candidate-evidence__empty">正在读取候选证据…</p>}{!candidateEvidence.isLoading && !candidateEvidence.data?.length && <p className="candidate-evidence__empty">尚无候选证据；集中验证后可在此绑定日志、截图、报告或签字扫描件。</p>}</div></section><div className="acceptance-report"><div><strong>项目自动验收总报告</strong><small>汇总当前 Commit 的自动审核、静态审计、参考模拟和候选包完整性。</small></div><button className="button button--primary" disabled={busy} onClick={createAcceptance}>{activeAcceptance ? "复核并复用验收报告" : "生成自动验收报告"}</button>{activeAcceptance && <><div className="acceptance-checks">{activeAcceptance.checks.map((check) => <span key={check.id}><CheckCircle size={15} weight="fill" /><b>{check.title}</b><Status value={check.status} /></span>)}</div><dl><dt>验收状态</dt><dd><Status value={activeAcceptance.status} /></dd><dt>报告 SHA-256</dt><dd><code>{activeAcceptance.report_sha256}</code></dd><dt>外部待验证</dt><dd>{activeAcceptance.summary.external_pending} 项</dd></dl><p>{activeAcceptance.claim_boundary}</p></>}</div></div> : <EmptyState title="尚未形成候选包" text="后端会检查分支无未提交修改、最新 Commit 自动审核、静态审计和参考模拟。" />}</section>
      <aside className="panel external-gates release-gates"><div className="external-gates__title"><WarningCircle size={17} /><span><strong>集中外部验证门</strong><small>不会由自动打包升级为通过</small></span></div>{readiness.data && <div className="release-prerequisites"><div><b>所需软件</b><ul>{readiness.data.prerequisites.software.map((item) => <li key={item}>{item}</li>)}</ul></div><div><b>硬件与台架</b><ul>{readiness.data.prerequisites.hardware.map((item) => <li key={item}>{item}</li>)}</ul></div><div><b>验证范围</b><ul>{readiness.data.prerequisites.validation_scope.map((item) => <li key={item}>{item}</li>)}</ul></div></div>}{gates.map((gate) => <article key={gate.id}><span><strong>{gate.title}</strong><small>{gate.required_evidence}</small></span><Status value={gate.status} /></article>)}{!gates.length && <EmptyState title="等待自动审核" text="生成程序后会建立五项外部验证门。" />}</aside></div>
      {Boolean(candidates.data?.length) && <section className="panel candidate-history"><div className="panel__header"><div><h3>历史候选包</h3><p>旧包不可覆盖，相同输入自动复用</p></div></div>{candidates.data?.map((item) => <div className="candidate-row" key={item.id}><span><strong>{item.version}</strong><small>{formatTime(item.created_at)} · {item.program_commit_id.slice(0, 12)}</small></span><code>{item.manifest_hash.slice(0, 16)}</code><Status value={item.status} /><button onClick={() => download(item)} aria-label={"下载 " + item.version}><DownloadSimple size={16} /></button></div>)}</section>}
    </>}
  </ProjectPage>;
}

function ReleaseGate({ label, ready, value }: { label: string; ready: boolean; value: string }) {
  return <div><span className={ready ? "gate-icon gate-icon--ready" : "gate-icon"}>{ready ? <Check size={14} /> : <WarningCircle size={14} />}</span><strong>{label}</strong><Status value={value} /></div>;
}

function MonitoringPage() {
  const queryClient = useQueryClient();
  const { projectId } = useProjectContext();
  const candidates = useQuery({ queryKey: ["release-candidates", projectId], queryFn: () => api.listReleaseCandidates(projectId) });
  const plans = useQuery({ queryKey: ["monitoring-plans", projectId], queryFn: () => api.listMonitoringPlans(projectId) });
  const [candidateId, setCandidateId] = useState("");
  const [values, setValues] = useState("{}");
  const [stepId, setStepId] = useState("");
  const [note, setNote] = useState("离线导入的只读变量快照");
  const [busy, setBusy] = useState(false);
  const selectedCandidateId = candidateId || candidates.data?.[0]?.id || "";
  const candidate = candidates.data?.find((item) => item.id === selectedCandidateId);
  const plan = plans.data?.find((item) => item.release_candidate_id === selectedCandidateId);
  const evidence = useQuery({ queryKey: ["monitoring-evidence", plan?.id], queryFn: () => api.listMonitoringEvidence(plan!.id), enabled: Boolean(plan?.id) });

  const createPlan = async () => {
    if (!candidate) return;
    setBusy(true);
    try {
      const result = await api.createMonitoringPlan(projectId, candidate.id, candidate.revision);
      await queryClient.invalidateQueries({ queryKey: ["monitoring-plans", projectId] });
      notify(result.reused ? "已复用该候选包的只读监控计划" : "只读监控准备计划已创建；尚未连接 PLC");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const recordSnapshot = async () => {
    if (!plan) return;
    setBusy(true);
    try {
      const parsed = JSON.parse(values) as Record<string, boolean | number>;
      await api.createMonitoringSnapshot(plan, parsed, stepId, note);
      await queryClient.invalidateQueries({ queryKey: ["monitoring-plans", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["monitoring-evidence", plan.id] });
      notify("离线快照已按 SHA-256 保存，验证等级保持 manual_unverified");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  const createTask = async (item: MonitoringEvidence) => {
    if (!plan) return;
    setBusy(true);
    try {
      await api.createCommissioningTask(item.id, "根据离线证据检查等待条件，不连接或写入 PLC", plan.revision);
      await queryClient.invalidateQueries({ queryKey: ["monitoring-plans", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["monitoring-evidence", plan.id] });
      await queryClient.invalidateQueries({ queryKey: ["branches", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
      notify("已从候选 Commit 创建独立调试分支，发布历史未改写");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  return <ProjectPage kicker="P10 · READ-ONLY MONITORING PREP" title="只读监控准备" description="只整理离线变量快照、等待条件和证据；当前未连接 PLC，不读取实时值，也不支持下载、RUN/STOP 或强制输出。">
    {!candidates.data?.length ? <EmptyState title="尚无交付候选包" text="先在 P09 生成绑定当前 Commit 的不可变候选包。" /> : <>
      <div className="monitor-boundary"><WarningCircle size={20} /><span><strong>未连接 PLC · 未验证</strong>此工作台只接受用户导入的离线 JSON 快照，不保存连接凭据，不执行任何在线写入。</span></div>
      <div className="verification-toolbar release-toolbar"><label>交付候选<select value={selectedCandidateId} onChange={(event) => setCandidateId(event.target.value)}>{candidates.data.map((item) => <option key={item.id} value={item.id}>{item.version} · {item.manifest_hash.slice(0, 12)}</option>)}</select></label><button className="button button--primary" disabled={busy || !candidate} onClick={createPlan}><Pulse size={16} />{plan ? "校验并复用只读计划" : "创建只读监控计划"}</button></div>
      {plan ? <div className="monitoring-workbench"><section className="panel monitoring-input"><div className="panel__header"><div><h3>离线快照导入</h3><p>变量白名单来自候选 Control IR</p></div><Status value={plan.verification_level} /></div><dl className="fingerprints"><dt>目标指纹</dt><dd><code>{plan.target_fingerprint}</code></dd><dt>变量映射</dt><dd><code>{plan.variable_map_hash}</code></dd><dt>访问权限</dt><dd>{plan.access}</dd></dl><label>当前工步 ID（可选）<input value={stepId} onChange={(event) => setStepId(event.target.value)} placeholder="例如 STEP_001" /></label><label>离线变量 JSON<textarea value={values} onChange={(event) => setValues(event.target.value)} spellCheck={false} /></label><label>证据说明<input value={note} onChange={(event) => setNote(event.target.value)} /></label><button className="button button--primary" disabled={busy} onClick={recordSnapshot}><UploadSimple size={16} />保存离线快照</button><div className="variable-map"><strong>只读变量映射（{plan.variable_map.length}）</strong>{plan.variable_map.slice(0, 12).map((item) => <span key={item.name}><code>{item.name}</code><small>{item.address || "-"} · {item.data_type || "-"} · {item.access}</small></span>)}</div></section><aside className="panel evidence-list"><div className="panel__header"><div><h3>不可变证据</h3><p>{plan.evidence_count} 条 · manual_unverified</p></div></div>{evidence.data?.map((item) => <article key={item.id}><div><Status value={item.status} /><code>{item.artifact_sha256.slice(0, 16)}</code></div><strong>{item.analysis.waiting_condition || "未指定等待条件"}</strong><small>采集变量 {item.analysis.captured_variable_count} · 缺失 {item.analysis.missing_condition_values.length}</small><p>{item.analysis.claim_boundary}</p><button className="button button--outline" disabled={busy || Boolean(item.commissioning_task_id)} onClick={() => createTask(item)}><GitBranch size={15} />{item.commissioning_task_id ? "已创建调试分支" : "创建独立调试分支"}</button></article>)}{!evidence.data?.length && <EmptyState title="尚无离线证据" text="输入只读变量 JSON 后保存快照。" />}</aside></div> : <EmptyState title="尚未创建监控准备计划" text="计划会绑定候选 Manifest、PLC 目标和只读变量映射哈希。" action={<button className="button button--primary" onClick={createPlan}>创建只读计划</button>} />}
    </>}
  </ProjectPage>;
}

function CompilePage() {
  const queryClient = useQueryClient(); const { projectId, project } = useProjectContext();
  const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => api.listRuns(projectId) });
  const automatedReviews = useQuery({ queryKey: ["automated-reviews", projectId], queryFn: () => api.listAutomatedReviews(projectId) });
  const compileRuns = useQuery({ queryKey: ["compile-runs", projectId], queryFn: () => api.listCompileRuns(projectId) });
  const adapters = useQuery({ queryKey: ["adapters"], queryFn: api.listAdapters });
  const [runId, setRunId] = useState(""); const selectedRunId = runId || runs.data?.[0]?.id || "";
  const [adapterId, setAdapterId] = useState("gxworks3"); const [compileRun, setCompileRun] = useState<CompileRun | null>(null);
  const expectedAdapter = project.data?.plc_series === "H5U" ? "autoshop" : "gxworks3";
  useEffect(() => { setAdapterId(expectedAdapter); setCompileRun(null); }, [expectedAdapter]);
  const evidenceRef = useRef<HTMLInputElement>(null); const [busy, setBusy] = useState(false);
  const review = automatedReviews.data?.find((item) => item.generation_run_id === selectedRunId) || null;
  const runAutomatedReview = async () => { if (!selectedRunId) return; const selectedRun = runs.data?.find((item) => item.id === selectedRunId); if (!selectedRun) return; setBusy(true); try { const result = await api.createAutomatedReview(projectId, selectedRunId, 20, selectedRun.revision); await queryClient.invalidateQueries({ queryKey: ["automated-reviews", projectId] }); notify(result.reused ? "自动审核输入未变化，已复用不可变报告" : "项目自动审核已完成并保存不可变报告"); } catch (error) { notifyError(error); } finally { setBusy(false); } };
  const persistedCompileRun = compileRuns.data?.find((item) => item.generation_run_id === selectedRunId && item.program_commit_id === review?.program_commit_id) || null;
  const activeCompileRun = compileRun || persistedCompileRun;
  const prepareCompile = async () => { if (!selectedRunId) return; const selectedRun = runs.data?.find((item) => item.id === selectedRunId); if (!selectedRun) return; setBusy(true); try { const result = await api.createCompileRun(projectId, selectedRunId, adapterId, selectedRun.revision); setCompileRun(result); await queryClient.invalidateQueries({ queryKey: ["compile-runs", projectId] }); notify("已创建厂商编译准备任务，当前仍为未验证"); } catch (error) { notifyError(error); } finally { setBusy(false); } };
  const uploadEvidence = async (file?: File) => { if (!file || !activeCompileRun) return; setBusy(true); try { const result = await api.uploadCompileEvidence(activeCompileRun.id, file, "vendor_report", activeCompileRun.revision); setCompileRun(result.compile_run); await queryClient.invalidateQueries({ queryKey: ["compile-runs", projectId] }); notify("外部证据已按哈希保存，验证等级保持 manual_unverified"); } catch (error) { notifyError(error); } finally { setBusy(false); if (evidenceRef.current) evidenceRef.current.value = ""; } };
  const vendorAdapters = (adapters.data || []).filter((item) => item.adapter_id === expectedAdapter);
  return <ProjectPage kicker="P07 · AUTOMATED REVIEW & COMPILE PREP" title="项目自动审核与编译准备" description="生成后自动执行确定性复现、追溯、静态审计、参考执行和变异检测；厂商、硬件与电气确认仍未验证。">
    {!runs.data?.length ? <EmptyState title="尚无生成物" text="先在 P06 从已锁定 MachineSpec 生成程序。" /> : <><div className="verification-toolbar"><label>生成任务<select value={selectedRunId} onChange={(event) => { setRunId(event.target.value); setCompileRun(null); }}>{runs.data.map((run: GenerationRun) => <option key={run.id} value={run.id}>{run.generator_version} · {formatTime(run.created_at)}</option>)}</select></label><label>厂商 Adapter<select value={adapterId} onChange={(event) => setAdapterId(event.target.value)}>{vendorAdapters.map((item: AdapterDescriptor) => <option value={item.adapter_id} key={item.adapter_id}>{item.name}</option>)}</select></label><button className="button button--primary" disabled={busy || !review} onClick={runAutomatedReview}><ListChecks size={16} />{busy ? "处理中…" : "重新运行自动审核"}</button></div>
    <div className="verification-grid"><section className="panel verification-panel"><div className="panel__header"><div><h3>Automated Review v{review?.review_version || "3"}</h3><p>生成后自动执行 · 报告不可变 · 不自动修改代码</p></div><Status value={review?.status || (automatedReviews.isLoading ? "读取中" : "尚未审核")} /></div>{review ? <><div className="audit-summary"><Metric label="自动检查" value={String(review.summary.passed) + "/" + String(review.summary.total)} note={"重复生成 " + review.repeat_count + " 次"} icon={<ListChecks />} /><Metric label="失败" value={String(review.summary.failed)} note={review.input_hash.slice(0, 12)} icon={<WarningCircle />} /><Metric label="外部待验证" value={String(review.summary.external_pending)} note={review.verification_level} icon={<Info />} /></div><div className="review-claim"><Info size={17} /><span>{review.claim_boundary}</span></div><div className="finding-list automated-checks">{review.checks.map((check) => <article key={check.id}><StatusCheck status={check.status} /><span><strong>{check.title}</strong><small>{check.id} · {check.status}</small><p>{check.detail}</p>{check.action && <em>恢复动作：{check.action}</em>}</span><Status value={check.status} /></article>)}</div><div className="external-gates"><div className="external-gates__title"><WarningCircle size={17} /><span><strong>集中外部验证门</strong><small>自动审核不会将这些项目升级为通过</small></span></div>{review.external_validation_gates.map((gate) => <article key={gate.id}><span><strong>{gate.title}</strong><small>{gate.required_evidence}</small></span><Status value={gate.status} /></article>)}</div></> : <EmptyState title="自动审核报告尚未恢复" text="生成完成后会自动创建报告；若网络中断，请刷新或创建新的生成任务。" />}</section>
    <aside className="panel compile-prep"><div className="panel__header"><div><h3>厂商编译证据</h3><p>人工降级路径 · 原件不可覆盖</p></div></div><div className="boundary-card"><WarningCircle size={22} /><span><strong>{expectedAdapter === "autoshop" ? "AutoShop" : "GX Works3"} 未验证</strong>本机不会启动未知厂商程序，也不会伪造编译结果。</span></div><button className="button button--primary" disabled={busy || !review || review.status === "blocked"} onClick={prepareCompile}>创建编译准备任务</button>{activeCompileRun && <div className="compile-record"><Status value={activeCompileRun.status} /><dl><dt>验证等级</dt><dd>{activeCompileRun.verification_level}</dd><dt>Adapter</dt><dd>{activeCompileRun.adapter_id}</dd><dt>任务 ID</dt><dd>{activeCompileRun.id.slice(0, 12)}</dd><dt>证据数</dt><dd>{activeCompileRun.evidence_count ?? 0}</dd></dl>{activeCompileRun.diagnostics.map((item, index) => <p key={index}>{String(item.message || item.code || "诊断信息")}</p>)}<input ref={evidenceRef} type="file" hidden onChange={(event) => uploadEvidence(event.target.files?.[0])} /><button className="button button--outline" disabled={busy} onClick={() => evidenceRef.current?.click()}><UploadSimple size={16} />导入厂商日志或截图</button><small>导入后仍标记 manual_unverified，集中验证签字前不会升级。</small></div>}</aside></div></>}
  </ProjectPage>;
}

function StatusCheck({ status }: { status: AutomatedReviewRun["checks"][number]["status"] }) { return status === "passed" ? <CheckCircle size={18} weight="fill" color="#2f765e" /> : <WarningCircle size={18} weight="fill" color="#a44b45" />; }

function SimulationPage() {
  const queryClient = useQueryClient();
  const { projectId } = useProjectContext();
  const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => api.listRuns(projectId) });
  const reviews = useQuery({ queryKey: ["automated-reviews", projectId], queryFn: () => api.listAutomatedReviews(projectId) });
  const simulationRuns = useQuery({ queryKey: ["simulation-runs", projectId], queryFn: () => api.listSimulationRuns(projectId) });
  const [runId, setRunId] = useState("");
  const selectedRunId = runId || runs.data?.[0]?.id || "";
  const [maxCycles, setMaxCycles] = useState(100);
  const [cycleTimeMs, setCycleTimeMs] = useState(100);
  const [overrides, setOverrides] = useState("{}");
  const [schedule, setSchedule] = useState("{}");
  const [restartCycles, setRestartCycles] = useState("");
  const [disconnectCycles, setDisconnectCycles] = useState("");
  const [simulation, setSimulation] = useState<SimulationRun | null>(null);
  const [busy, setBusy] = useState(false);
  const currentReview = reviews.data?.find((item) => item.generation_run_id === selectedRunId);
  const persistedSimulation = simulationRuns.data?.find((item) => item.generation_run_id === selectedRunId && item.program_commit_id === currentReview?.program_commit_id) || null;
  const activeSimulation = simulation || persistedSimulation;
  const trace = useQuery({ queryKey: ["simulation-trace", activeSimulation?.id], queryFn: () => api.getSimulationTrace(activeSimulation!.id), enabled: Boolean(activeSimulation?.id) });
  const parseCycles = (value: string) => value.trim() ? value.split(",").map((item) => Number(item.trim())) : [];
  const runSimulation = async () => {
    if (!selectedRunId) return;
    const selectedRun = runs.data?.find((item) => item.id === selectedRunId);
    if (!selectedRun) return;
    setBusy(true);
    try {
      const inputOverrides = JSON.parse(overrides) as Record<string, SimulationScalar>;
      const inputSchedule = JSON.parse(schedule) as Record<string, Record<string, SimulationScalar>>;
      const result = await api.createSimulationRun(projectId, selectedRunId, inputOverrides, maxCycles, selectedRun.revision, {
        input_schedule: inputSchedule,
        restart_cycles: parseCycles(restartCycles),
        disconnect_cycles: parseCycles(disconnectCycles),
        cycle_time_ms: cycleTimeMs,
      });
      setSimulation(result);
      await queryClient.invalidateQueries({ queryKey: ["simulation-runs", projectId] });
      notify("控谱参考逻辑模拟已完成；不等同于 GX Simulator3");
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };
  const results = activeSimulation?.results || {};
  const diagnostics = results.diagnostics || [];
  const traces = trace.data?.traces || [];
  const lastTrace = traces[traces.length - 1];
  return <ProjectPage kicker="P08 · REFERENCE SIMULATION" title="控谱参考逻辑模拟" description="受限 TestSpec/Control IR 离散扫描执行器；不是 GX Simulator3，也不是硬件实测。">
    {!runs.data?.length ? <EmptyState title="尚无可模拟生成物" text="先在 P06 生成 Control IR 与 TestSpec。" /> : <>
      <div className="verification-toolbar verification-toolbar--simulation"><label>生成任务<select value={selectedRunId} onChange={(event) => { setRunId(event.target.value); setSimulation(null); }}>{runs.data.map((run: GenerationRun) => <option key={run.id} value={run.id}>{run.generator_version} · {formatTime(run.created_at)}</option>)}</select></label><label>最大扫描周期<input type="number" min={1} max={10000} value={maxCycles} onChange={(event) => setMaxCycles(Number(event.target.value))} /></label><label>扫描周期 ms<input type="number" min={1} max={60000} value={cycleTimeMs} onChange={(event) => setCycleTimeMs(Number(event.target.value))} /></label><button className="button button--primary" disabled={busy} onClick={runSimulation}><Pulse size={16} />{busy ? "运行中…" : "运行参考模拟"}</button></div>
      <div className="simulation-scenario-grid"><label>初始输入（JSON）<textarea value={overrides} onChange={(event) => setOverrides(event.target.value)} spellCheck={false} /></label><label>周期注入（JSON）<textarea value={schedule} onChange={(event) => setSchedule(event.target.value)} placeholder={'{"3":{"Start":true}}'} spellCheck={false} /></label><label>重启周期（逗号分隔）<input value={restartCycles} onChange={(event) => setRestartCycles(event.target.value)} placeholder="例如 10,25" /></label><label>通信断开周期（逗号分隔）<input value={disconnectCycles} onChange={(event) => setDisconnectCycles(event.target.value)} placeholder="例如 15,16" /></label></div>
      <div className="simulation-workbench"><section className="panel simulation-stage-real"><div className="panel__header"><div><h3>离散扫描结果</h3><p>{activeSimulation?.engine_version || "kongpu-reference-v2"}</p></div><Status value={activeSimulation?.status || "尚未运行"} /></div>{activeSimulation ? <><div className="reference-banner"><Info size={20} /><span><strong>{activeSimulation.verification_level}</strong>仅代表控谱参考逻辑模拟的自动验证结果。</span></div><div className="simulation-metrics"><Metric label="扫描周期" value={String(results.cycles ?? activeSimulation.trace_count)} note={cycleTimeMs + " ms 离散周期"} icon={<Pulse />} /><Metric label="最终工步" value={String(results.final_step_id ?? "END")} note="Control IR 工步" icon={<ListChecks />} /><Metric label="诊断" value={String(diagnostics.length)} note="可定位恢复动作" icon={<WarningCircle />} /></div><div className="trace-stream">{traces.slice(-30).map((item) => <article key={item.cycle}><b>{item.cycle}</b><span><strong>{item.step_id || "END"}</strong><small>{item.communication} · {JSON.stringify(item.events)}</small><small>{item.entry_condition || "TRUE"} → {item.completion_condition || "TRUE"}</small></span><code>{JSON.stringify(item.outputs)}</code></article>)}</div></> : <EmptyState title="等待参考模拟" text="默认输入均为 false；可按周期注入输入、重启或模拟通信断开。" />}</section><aside className="panel assertion-panel-real"><div className="panel__header"><div><h3>诊断与边界</h3><p>失败可定位，不继承旧结果</p></div></div>{activeSimulation ? <><Gate label="执行状态" value={activeSimulation.status === "review_ready" ? 0 : 1} /><dl><dt>验证等级</dt><dd>{activeSimulation.verification_level}</dd><dt>程序 Commit</dt><dd>{activeSimulation.program_commit_id?.slice(0, 12) || "-"}</dd><dt>TestSpec</dt><dd>{activeSimulation.test_spec_revision_id?.slice(0, 12) || "-"}</dd><dt>最后输入</dt><dd><code>{JSON.stringify(lastTrace?.inputs || {})}</code></dd><dt>内部状态（只读）</dt><dd><code>{JSON.stringify(lastTrace?.internal_state || {})}</code></dd><dt>来源</dt><dd><code>{JSON.stringify(lastTrace?.source || {})}</code></dd><dt>事件</dt><dd>{JSON.stringify(results.events || [])}</dd></dl>{results.test_summary && <p>TestSpec 用例：{results.test_summary.total} 总计，{results.test_summary.passed} 通过，{results.test_summary.failed} 失败，{results.test_summary.blocked} 阻断。</p>}<div className="simulation-diagnostics">{diagnostics.map((item: SimulationDiagnostic, index) => <article key={item.code + "-" + String(item.cycle || index)}><strong>{item.code}</strong><small>周期 {item.cycle ?? "-"} · 工步 {item.step_id || "-"}</small><p>{item.action || item.detail || "检查 Trace 和源资料。"}</p></article>)}</div></> : <p>新 Commit、不同 TestSpec 或不同引擎版本必须重新运行。</p>}<div className="boundary-card"><WarningCircle size={21} /><span><strong>厂商与硬件未验证</strong>结果不能用于声明程序可下载、可生产或安全确认。</span></div></aside></div>
    </>}
  </ProjectPage>;
}

function SettingsPage() {
  const projects = useProjects();
  const adapters = useQuery({ queryKey: ["adapters"], queryFn: api.listAdapters });
  const settings = useQuery({ queryKey: ["local-settings"], queryFn: api.getLocalSettings });
  const audit = useQuery({ queryKey: ["settings-audit"], queryFn: api.listSettingsAudit });
  const templates = useQuery({ queryKey: ["template-versions"], queryFn: api.listTemplateVersions });
  const compatibility = useQuery({ queryKey: ["compatibility-matrix"], queryFn: api.getCompatibilityMatrix });
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState("");
  const selectedProjectId = projectId || projects.data?.[0]?.id || "";
  const environments = useQuery({ queryKey: ["adapter-environments", selectedProjectId], queryFn: () => api.listAdapterEnvironments(selectedProjectId), enabled: Boolean(selectedProjectId) });
  const [detecting, setDetecting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [endpoint, setEndpoint] = useState("");
  const [modelName, setModelName] = useState("");
  const [allowProjectContext, setAllowProjectContext] = useState(false);
  const [sendRawExcel, setSendRawExcel] = useState(false);
  const [sendGeneratedArtifacts, setSendGeneratedArtifacts] = useState(false);
  useEffect(() => {
    const value = settings.data?.settings;
    if (!value) return;
    setEndpoint(value.model_endpoint || "");
    setModelName(value.model_name || "");
    setAllowProjectContext(value.allow_project_context);
    setSendRawExcel(value.send_raw_excel);
    setSendGeneratedArtifacts(value.send_generated_artifacts);
  }, [settings.data?.revision]);
  const saveSettings = async () => {
    if (!settings.data) return;
    setSaving(true);
    try {
      await api.updateLocalSettings({
        model_endpoint: endpoint.trim() || null,
        model_name: modelName.trim() || null,
        allow_project_context: allowProjectContext,
        send_raw_excel: sendRawExcel,
        send_generated_artifacts: sendGeneratedArtifacts,
      }, settings.data.revision);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["local-settings"] }),
        queryClient.invalidateQueries({ queryKey: ["settings-audit"] }),
      ]);
      notify("本地设置已保存；密钥不会写入数据库");
    } catch (error) {
      notifyError(error);
    } finally {
      setSaving(false);
    }
  };
  const detect = async (adapterId: string) => {
    if (!selectedProjectId) return;
    setDetecting(adapterId);
    try {
      await api.detectAdapter(adapterId, selectedProjectId);
      await queryClient.invalidateQueries({ queryKey: ["adapter-environments", selectedProjectId] });
      notify("环境快照已更新；检测过程未启动厂商程序");
    } catch (error) {
      notifyError(error);
    } finally {
      setDetecting(null);
    }
  };
  const byAdapter = new Map((environments.data || []).map((item: AdapterEnvironment) => [item.adapter_id, item]));
  const toggle = (label: string, checked: boolean, setChecked: (value: boolean) => void, detail: string) => <label className="setting-toggle setting-toggle--checkbox"><span><strong>{label}</strong><small>{detail}</small></span><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} /></label>;
  return <main className="hub-page">
    <PageHeading kicker="P12 · SETTINGS" title="本机设置与运行环境" description="设置只影响本机可选解释与数据最小化策略；厂商工具、PLC 硬件和安全能力仍未验证。" actions={<label className="project-select">检测项目<select value={selectedProjectId} onChange={(event) => setProjectId(event.target.value)}><option value="">未选择项目</option>{(projects.data || []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>} />
    <div className="p12-settings-layout">
      <section className="panel settings-form settings-form-real"><div className="panel__header"><div><h3>模型解释配置</h3><p>仅在用户主动请求时使用，不能决定校验、审计、版本或锁定结果</p></div><Status value={settings.data?.settings.model_status || "读取中"} /></div><div className="settings-form__body"><label>模型端点（可选）<input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="https://example.local/v1" autoComplete="off" /></label><label>模型名称（可选）<input value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder="解释模型名称" autoComplete="off" /></label>{toggle("允许项目上下文", allowProjectContext, setAllowProjectContext, "默认关闭；只在主动请求解释时发送最小上下文")}{toggle("允许发送原始 Excel", sendRawExcel, setSendRawExcel, "默认关闭；原始表格不会自动上传")}{toggle("允许发送生成工件", sendGeneratedArtifacts, setSendGeneratedArtifacts, "默认关闭；ST、Control IR 和 TestSpec 不自动外发")}<div className="settings-actions"><span>Revision {settings.data?.revision ?? "-"} · {settings.data?.secret_policy.message}</span><button className="button button--primary" onClick={saveSettings} disabled={!settings.data || saving}>{saving ? "保存中…" : "保存本机设置"}</button></div></div></section>
      <section className="panel p12-boundary-card"><div className="panel__header"><div><h3>验证边界</h3><p>当前环境的真实能力声明</p></div><WarningCircle size={22} color="#a66b16" /></div><div className="p12-boundary-list"><div><strong>模型</strong><Status value={settings.data?.settings.model_status || "not_configured"} /><small>configured_unverified 仅表示已填写端点，不代表模型已验证</small></div><div><strong>GX Works3 / AutoShop / 厂商模拟</strong><Status value="unverified" /><small>本机不启动未知程序，不猜测工具版本</small></div><div><strong>FX5U / H5U 硬件与电气工程师确认</strong><Status value="pending_external" /><small>需要集中验证包，不能由参考模拟替代</small></div></div></section>
    </div>
    <section className="panel p12-table-panel"><div className="panel__header"><div><h3>模板版本历史</h3><p>当前工作表与 MachineSpec Schema 契约</p></div><Status value={templates.isLoading ? "读取中" : `${templates.data?.length || 0} 个版本`} /></div><div className="table-scroll"><table><thead><tr><th>版本</th><th>Schema</th><th>状态</th><th>必填工作表</th><th>创建时间</th></tr></thead><tbody>{(templates.data || []).map((item: TemplateVersionHistory) => <tr key={item.id}><td><strong>Template v{item.version}</strong></td><td>{item.schema_version}</td><td><Status value={item.active ? "active" : "inactive"} /></td><td>{Array.isArray(item.definition.required_sheets) ? item.definition.required_sheets.join(" · ") : "-"}</td><td>{formatTime(item.created_at)}</td></tr>)}</tbody></table>{!templates.isLoading && !(templates.data || []).length && <EmptyState title="尚无模板版本" text="模板版本将在 API 初始化时生成。" />}</div></section>
    <section className="panel p12-table-panel"><div className="panel__header"><div><h3>PLC 兼容矩阵</h3><p>自动能力、未验证厂商能力和外部验证门分开显示</p></div><Status value={compatibility.isLoading ? "读取中" : "未验证边界"} /></div><div className="table-scroll"><table><thead><tr><th>目标</th><th>MachineSpec</th><th>ST 生成</th><th>参考模拟</th><th>厂商 IDE</th><th>厂商模拟</th><th>硬件</th><th>电气复核</th></tr></thead><tbody>{(compatibility.data?.entries || []).map((entry) => <tr key={entry.target.model}><td><strong>{entry.target.model}</strong><small>{entry.target.brand} · {entry.target.series}<br />{entry.vendor_tool}</small></td><td><Status value={entry.machine_spec} /></td><td><Status value={entry.structured_text_generation} /></td><td><Status value={entry.reference_simulation} /></td><td><Status value={entry.vendor_compile} /></td><td><Status value={entry.vendor_simulation} /></td><td><Status value={entry.hardware} /></td><td><Status value={entry.electrical_review} /></td></tr>)}</tbody></table></div><div className="profile-prerequisites">{(compatibility.data?.entries || []).map((entry) => <article key={entry.profile_id}><div className="profile-prerequisites__head"><span><strong>{entry.target.model}</strong><small>{entry.profile_id}</small></span><Status value="pending_external" /></div><div className="profile-prerequisites__groups"><div><b>所需厂商软件</b><ul>{entry.required_software.map((item) => <li key={item}>{item}</li>)}</ul></div><div><b>硬件与台架</b><ul>{entry.hardware_prerequisites.map((item) => <li key={item}>{item}</li>)}</ul></div><div><b>集中验证范围</b><ul>{entry.external_validation_scope.map((item) => <li key={item}>{item}</li>)}</ul></div></div></article>)}</div><div className="p12-claim"><Info size={15} />{compatibility.data?.claim_boundary || "兼容矩阵正在读取。"}</div></section>
    <section className="panel p12-table-panel"><div className="panel__header"><div><h3>设置审计</h3><p>只记录变更键名，不记录端点内容、模型名称或密钥</p></div><Status value={audit.isLoading ? "读取中" : `${audit.data?.length || 0} 条记录`} /></div><div className="table-scroll"><table><thead><tr><th>时间</th><th>动作</th><th>设置键</th><th>变更字段</th></tr></thead><tbody>{(audit.data || []).map((event: SettingsAuditEvent) => <tr key={event.id}><td>{formatTime(event.created_at)}</td><td><Status value={event.action} /></td><td>{event.key}</td><td><code>{event.changed_keys.join(", ") || "-"}</code></td></tr>)}</tbody></table>{!audit.isLoading && !(audit.data || []).length && <EmptyState title="尚无设置变更" text="保存设置后会在这里记录变更键名。" />}</div></section>
    <div className="p12-adapter-heading"><div><h3>Adapter 环境快照</h3><p>只读检测受控路径和版本信息；不执行厂商程序</p></div><Status value={selectedProjectId ? "项目级快照" : "未选择项目"} /></div>
    <section className="settings-grid-real">{(adapters.data || []).map((adapter: AdapterDescriptor) => { const environment = byAdapter.get(adapter.adapter_id); return <article className="panel adapter-card-real" key={adapter.adapter_id}><div className="adapter-card-real__head"><Cpu size={25} /><span><strong>{adapter.name}</strong><small>{adapter.vendor} · Adapter v{adapter.version}</small></span><Status value={environment?.status || adapter.verification_level} /></div><dl><dt>验证等级</dt><dd>{environment?.verification_level || adapter.verification_level}</dd><dt>平台</dt><dd>{String(environment?.details.platform || "未检测")}</dd><dt>Python</dt><dd>{String(environment?.details.python || "-")}</dd><dt>目标</dt><dd>{String(environment?.details.target_model || "-")}</dd></dl><div className="capability-matrix">{Object.entries(adapter.capabilities).map(([name, value]) => <span key={name}><code>{name}</code><b>{value}</b></span>)}</div><button className="button button--outline" disabled={!selectedProjectId || Boolean(detecting)} onClick={() => detect(adapter.adapter_id)}>{detecting === adapter.adapter_id ? "检测中…" : "只读检测环境"}</button></article>; })}</section>
    <section className="panel boundary-panel"><WarningCircle size={20} /><div><strong>产品安全边界</strong><p>此页面不会启动未知程序，不执行任意命令，不保存 PLC 下载、RUN/STOP、强制输出或安全 PLC 凭据。配置模型也不会改变确定性校验、审计、模拟、版本或锁定结论。</p></div></section>
  </main>;
}

function UnavailablePage({ title, detail }: { title: string; detail: string }) { return <main className="hub-page"><PageHeading kicker="NOT CONNECTED" title={title} description="尚未接入真实能力" /><UnavailableBody detail={detail} /></main>; }
function UnavailableBody({ detail }: { detail: string }) { return <section className="panel unavailable"><WarningCircle size={38} weight="duotone" /><div><strong>尚未接入真实能力</strong><p>{detail}</p><small>M1/M2 不包含真实 PLC 下载、RUN/STOP、强制输出或安全 PLC 逻辑。</small></div></section>; }

function DeviceLibrary() {
  const devices = [{ name: "FX5U 通用 CPU", type: "PLC Target", status: "自动验证 Profile" }, { name: "汇川 H5U 通用 CPU", type: "PLC Target", status: "自动验证 Profile" }, { name: "双电控气缸", type: "Control Template", status: "确定性骨架生成" }, { name: "简单伺服握手", type: "Control Template", status: "确定性骨架生成" }, { name: "安全 PLC", type: "Excluded", status: "不自动生成" }];
  return <main className="hub-page"><PageHeading kicker="DEVICE LIBRARY" title="设备库" description="独立的设备与控制模板目录，不再跳转到系统设置。" /><section className="asset-grid">{devices.map((device) => <article className="panel asset-card-static" key={device.name}><Cpu size={24} /><div><strong>{device.name}</strong><small>{device.type}</small></div><Status value={device.status} /></article>)}</section></main>;
}

function DocumentsPage() {
  const docs = [{ name: "MachineSpec Template v1", type: "Excel 契约", location: "P03 模板中心" }, { name: "MachineSpec JSON Schema v1", type: "JSON Schema", location: "/api/v1/schemas/machine-spec/v1" }, { name: "本机 API 文档", type: "OpenAPI", location: "http://127.0.0.1:8000/docs" }, { name: "开发状态与边界", type: "Markdown", location: "docs/CURRENT_STATUS.md" }];
  return <main className="hub-page"><PageHeading kicker="DOCUMENTS" title="文档资料" description="独立的产品契约、API 与工程说明入口，不再跳转到模板页面。" /><section className="panel document-panel"><div className="document-list__head"><span>名称</span><span>类型</span><span>位置</span></div>{docs.map((doc) => <div className="document-row-real" key={doc.name}><span><FileText size={17} /><strong>{doc.name}</strong></span><span>{doc.type}</span><code>{doc.location}</code></div>)}</section></main>;
}
