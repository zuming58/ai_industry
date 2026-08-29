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
  AdapterDescriptor, AdapterEnvironment, CompileRun, GenerationAudit, GenerationRun,
  MachineSpec, ProgramBranch, ProgramCommit, ProgramFile, Project, SimulationRun,
  SpecRevision, ValidationIssue,
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
  return <div className="app-shell"><AppSidebar /><div className="app-frame"><Topbar /><Routes><Route path="/" element={<Dashboard />} /><Route path="/projects" element={<ProjectsPage />} /><Route path="/specs" element={<ProjectChooser destination="review" title="规格管理" />} /><Route path="/program" element={<ProjectChooser destination="program" title="程序工程" />} /><Route path="/versions" element={<ProjectChooser destination="versions" title="版本控制" />} /><Route path="/debug" element={<ProjectChooser destination="compile" title="调试工具" />} /><Route path="/devices" element={<DeviceLibrary />} /><Route path="/documents" element={<DocumentsPage />} /><Route path="/settings" element={<SettingsPage />} /><Route path="/projects/:projectId/templates" element={<TemplatePage />} /><Route path="/projects/:projectId/imports" element={<ImportPage />} /><Route path="/projects/:projectId/review" element={<ReviewPage />} /><Route path="/projects/:projectId/program" element={<ProgramPage />} /><Route path="/projects/:projectId/versions" element={<VersionPage />} /><Route path="/projects/:projectId/:capability" element={<CapabilityPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes><div className="statusbar"><span><Database size={13} /> SQLite WAL · 本机数据</span><span>FX5U · M3 前置自动验证 · 厂商/硬件未验证</span></div></div>{toast && <div className={"toast " + (toast.tone === "error" ? "toast--error" : "")}><CheckCircle size={19} /><span>{toast.message}</span><button onClick={clearToast}><X size={15} /></button></div>}</div>;
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
    <section className="hub-metrics"><Metric label="项目总数" value={String(items.length)} note="SQLite 持久化" icon={<FolderSimple />} /><Metric label="待处理" value={String(items.filter((p) => !p.archived && p.status !== "规格锁定").length)} note="需要工程动作" icon={<ListChecks />} /><Metric label="规格锁定" value={String(items.filter((p) => p.status === "规格锁定").length)} note="可进入程序生成" icon={<CheckCircle />} /><Metric label="厂商验证" value="未验证" note="未检测 GX Works3" icon={<WarningCircle />} /></section>
    {projects.isLoading ? <EmptyState title="正在读取项目" text="连接本机 API…" /> : projects.isError ? <EmptyState title="无法连接本机 API" text={errorMessage(projects.error)} /> : active ? <section className="active-card real-active"><div className="project-identity"><div className="project-identity__mark"><Cube size={30} weight="duotone" /></div><div><div className="eyebrow">当前项目</div><h2>{active.name}</h2><p>{active.code} · {active.plc_model}</p></div></div><div><Status value={active.status} /><button className="button button--primary" onClick={() => navigate("/projects/" + active.id + "/templates")}>继续项目 <ArrowRight size={16} /></button></div></section> : <EmptyState title="还没有项目" text="创建首个 FX5U 项目后，数据会保存在本机 SQLite。" action={<button className="button button--primary" onClick={() => navigate("/projects")}><Plus size={16} />创建项目</button>} />}
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
  const [name, setName] = useState(project?.name || ""); const [customer, setCustomer] = useState(project?.customer_code || ""); const [model, setModel] = useState(project?.plc_model || "FX5U-64MT/ES"); const [saving, setSaving] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setSaving(true); try { if (project) await api.updateProject(project, { name, customer_code: customer, plc_model: model }); else await api.createProject({ name, customer_code: customer, plc_model: model }); notify(project ? "项目已保存" : "项目已创建"); onSaved(); } catch (error) { notifyError(error); } finally { setSaving(false); } };
  return <div className="modal-backdrop"><form className="modal" onSubmit={submit}><div className="modal__header"><span className="modal__icon"><FolderSimple size={22} /></span><div><h2>{project ? "编辑项目" : "新建项目"}</h2><p>首版目标固定为三菱 FX5U，本机持久化。</p></div><button type="button" className="icon-button" onClick={onClose}><X /></button></div><div className="modal__body"><label>项目名称<input required minLength={2} value={name} onChange={(event) => setName(event.target.value)} /></label><label>客户编号<input value={customer} onChange={(event) => setCustomer(event.target.value)} /></label><label>PLC 型号<select value={model} onChange={(event) => setModel(event.target.value)}><option>FX5U-64MT/ES</option><option>FX5U-80MT/ES</option><option>FX5U-32MT/ES</option></select></label><div className="modal__notice"><Info size={18} /><span><strong>环境边界</strong>当前电脑未验证 GX Works3、GX Simulator3 或 MX Component。</span></div></div><div className="modal__footer"><button type="button" className="button button--soft" onClick={onClose}>取消</button><button className="button button--primary" disabled={saving}>{saving ? "保存中…" : "保存项目"}</button></div></form></div>;
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
  return <ProjectPage kicker="P03 · TEMPLATE" title="MachineSpec 模板" description="下载与项目 PLC 目标绑定的 Excel v1 模板。"><section className="template-grid"><article className="panel template-card"><span><FileText size={28} /></span><div><h3>空白工程模板</h3><p>包含 Instructions、Project、Components、Signals、Sequence 与选填工作表。</p><small>Template v{String(template.data?.version || "1.0")} · Schema v{String(template.data?.schema_version || "1.0")}</small></div><button className="button button--primary" onClick={() => download("blank")} disabled={Boolean(downloading)}><DownloadSimple size={16} />{downloading === "blank" ? "下载中…" : "下载空白模板"}</button></article><article className="panel template-card"><span><ClipboardText size={28} /></span><div><h3>完整填写范例</h3><p>脱敏 FX5U 示例，用于理解稳定 ID、信号、工步、互锁与异常填写方式。</p><small>范例不代表 GX Works3 编译通过。</small></div><button className="button button--outline" onClick={() => download("example")} disabled={Boolean(downloading)}><DownloadSimple size={16} />{downloading === "example" ? "下载中…" : "下载完整范例"}</button></article></section><section className="panel boundary-panel"><WarningCircle size={20} /><div><strong>模板处理边界</strong><p>仅接受未加密 .xlsx，最大 20 MB；不执行公式、不接受宏、.xls 或损坏压缩包。</p></div></section></ProjectPage>;
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
  const queryClient = useQueryClient(); const { projectId, project } = useProjectContext(); const branches = useQuery({ queryKey: ["branches", projectId], queryFn: () => api.listBranches(projectId) }); const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => api.listRuns(projectId) }); const [branchId, setBranchId] = useState(""); const activeId = branchId || branches.data?.[0]?.id || ""; const files = useQuery({ queryKey: ["files", activeId], queryFn: () => api.listFiles(activeId), enabled: Boolean(activeId) }); const [path, setPath] = useState(""); const selectedPath = path || files.data?.files[0]?.path || ""; const file = useQuery({ queryKey: ["file", activeId, selectedPath], queryFn: () => api.getFile(activeId, selectedPath), enabled: Boolean(activeId && selectedPath) }); const [content, setContent] = useState(""); const [message, setMessage] = useState("Review generated program");
  useEffect(() => { if (file.data) setContent(file.data.content); }, [file.data?.content]);
  const generate = async () => { const specId = project.data?.current_spec_revision_id; if (!specId) return notifyError(new Error("没有已锁定 MachineSpec")); try { await api.generate(projectId, specId, "generated/spec-" + Date.now()); queryClient.invalidateQueries({ queryKey: ["branches", projectId] }); queryClient.invalidateQueries({ queryKey: ["runs", projectId] }); notify("已生成确定性 FX5U ST 骨架和 TestSpec"); } catch (error) { notifyError(error); } };
  const save = async () => { if (!files.data?.branch || !selectedPath) return; try { const result = await api.saveFile(activeId, selectedPath, content, files.data.branch.revision); await queryClient.invalidateQueries({ queryKey: ["files", activeId] }); queryClient.setQueryData(["file", activeId, selectedPath], { path: selectedPath, content, branch_revision: result.branch.revision }); notify("文件已保存到工作分支，尚未提交"); } catch (error) { notifyError(error); } };
  const commit = async () => { if (!files.data?.branch) return; try { await api.commit(files.data.branch, message); await queryClient.invalidateQueries({ queryKey: ["files", activeId] }); await queryClient.invalidateQueries({ queryKey: ["branches", projectId] }); notify("程序修改已提交到本地 Git 历史"); } catch (error) { notifyError(error); } };
  const latestRun = runs.data?.[0];
  return <ProjectPage kicker="P06 · PROGRAM" title="程序工作区" description="从已锁定规格生成确定性 FX5U ST；不声明通过 GX Works3 编译。" actions={<button className="button button--primary" disabled={project.data?.status !== "规格锁定"} onClick={generate}><Code size={16} />生成程序</button>}>
    {branches.data?.length ? <><div className="program-toolbar"><GitBranch size={15} /><select value={activeId} onChange={(event) => { setBranchId(event.target.value); setPath(""); }}>{branches.data.map((branch) => <option value={branch.id} key={branch.id}>{branch.name}</option>)}</select><span><Status value={files.data?.branch.status || "读取中"} /></span><span>生成器 {latestRun?.generator_version || "-"}</span><button onClick={save}>保存文件</button></div><div className="program-layout"><section className="panel file-tree"><div className="panel__header"><div><h3>程序树</h3><p>{files.data?.files.length || 0} 个文件</p></div></div>{files.data?.files.map((item: ProgramFile) => <button key={item.path} className={selectedPath === item.path ? "is-active" : ""} onClick={() => setPath(item.path)}><FileCode size={15} />{item.path}</button>)}</section><section className="code-panel"><div className="code-panel__header"><span>{selectedPath || "选择文件"}</span><button onClick={save}>保存</button></div><textarea className="code-editor" value={content} onChange={(event) => setContent(event.target.value)} spellCheck={false} /></section><aside className="panel trace-panel"><div className="panel__header"><div><h3>提交与追溯</h3><p>不改写历史</p></div></div><label className="commit-box">提交说明<input value={message} onChange={(event) => setMessage(event.target.value)} /><button className="button button--primary" disabled={files.data?.branch.status !== "modified"} onClick={commit}>创建 Commit</button></label>{latestRun?.warnings.map((warning) => <div className="trace-item" key={warning.code}><span>{warning.code}</span><strong>{warning.message}</strong></div>)}{latestRun?.trace_links.slice(0, 5).map((link, index) => <div className="trace-item" key={index}><span>{String(link.output_path)}:{String(link.output_line)}</span><strong>{String(link.entity_id)}</strong><small>{String(link.source_sheet)} 第 {String(link.source_row)} 行</small></div>)}</aside></div></> : <EmptyState title="尚未生成程序工作区" text={project.data?.status === "规格锁定" ? "点击“生成程序”创建独立分支、ST、Control IR 与 TestSpec。" : "先在 P05 完成规格锁定，才能生成程序。"} action={project.data?.status === "规格锁定" ? <button className="button button--primary" onClick={generate}>生成程序</button> : undefined} />}
  </ProjectPage>;
}

function VersionPage() {
  const { projectId } = useProjectContext(); const branches = useQuery({ queryKey: ["branches", projectId], queryFn: () => api.listBranches(projectId) }); const commits = useQuery({ queryKey: ["commits", projectId], queryFn: () => api.listCommits(projectId) }); const [selected, setSelected] = useState<ProgramCommit | null>(null); const diff = useQuery({ queryKey: ["diff", selected?.id], queryFn: () => api.commitDiff(selected!.id), enabled: Boolean(selected) });
  return <ProjectPage kicker="P11 · VERSION" title="版本中心" description="展示真实本地 Git 分支、Commit、MachineSpec 基线和差异；历史不可改写。"><div className="version-layout"><section className="panel"><div className="panel__header"><div><h3>程序分支</h3><p>{branches.data?.length || 0} 条</p></div></div>{branches.data?.map((branch: ProgramBranch) => <div className="branch-row" key={branch.id}><GitBranch size={16} /><span><strong>{branch.name}</strong><small>{branch.head_commit?.slice(0, 12) || "尚无提交"}</small></span><Status value={branch.status} /></div>)}</section><section className="panel"><div className="panel__header"><div><h3>Commit 历史</h3><p>点击查看完整差异</p></div></div>{commits.data?.map((commit: ProgramCommit) => <button className="commit-row" key={commit.id} onClick={() => setSelected(commit)}><Code size={16} /><span><strong>{commit.message}</strong><small>{commit.git_sha.slice(0, 12)} · {formatTime(commit.created_at)}</small></span><ArrowRight size={15} /></button>)}</section><section className="code-panel diff-panel"><div className="code-panel__header"><span>{selected ? selected.message : "选择 Commit"}</span></div><pre>{diff.data?.diff || "选择一条 Commit 查看真实 Git diff。"}</pre></section></div></ProjectPage>;
}

function CapabilityPage() {
  const { capability = "" } = useParams();
  if (capability === "compile") return <CompilePage />;
  if (capability === "simulation") return <SimulationPage />;
  const labels: Record<string, string> = { release: "P09 发布包", monitor: "P10 在线监控" };
  return <ProjectPage kicker="M4 BOUNDARY" title={labels[capability] || capability} description="该页面尚未接入真实设备能力。"><UnavailableBody detail={capability === "monitor" ? "未实现 PLC 下载、RUN/STOP、强制输出或真实在线连接。" : "发布能力将在真实厂商编译、模拟和安全审查之后接入。"} /></ProjectPage>;
}

function CompilePage() {
  const queryClient = useQueryClient(); const { projectId } = useProjectContext();
  const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => api.listRuns(projectId) });
  const compileRuns = useQuery({ queryKey: ["compile-runs", projectId], queryFn: () => api.listCompileRuns(projectId) });
  const adapters = useQuery({ queryKey: ["adapters"], queryFn: api.listAdapters });
  const [runId, setRunId] = useState(""); const selectedRunId = runId || runs.data?.[0]?.id || "";
  const auditResult = useQuery({ queryKey: ["generation-audit", selectedRunId], queryFn: () => api.getAudit(selectedRunId), enabled: Boolean(selectedRunId), retry: false });
  const [adapterId, setAdapterId] = useState("gxworks3"); const [compileRun, setCompileRun] = useState<CompileRun | null>(null);
  const evidenceRef = useRef<HTMLInputElement>(null); const [busy, setBusy] = useState(false);
  const runAudit = async () => { if (!selectedRunId) return; setBusy(true); try { await api.auditGeneration(selectedRunId); await queryClient.invalidateQueries({ queryKey: ["generation-audit", selectedRunId] }); notify("生成物自审计已完成"); } catch (error) { notifyError(error); } finally { setBusy(false); } };
  const persistedCompileRun = compileRuns.data?.find((item) => item.generation_run_id === selectedRunId) || null;
  const activeCompileRun = compileRun || persistedCompileRun;
  const prepareCompile = async () => { if (!selectedRunId) return; const selectedRun = runs.data?.find((item) => item.id === selectedRunId); if (!selectedRun) return; setBusy(true); try { const result = await api.createCompileRun(projectId, selectedRunId, adapterId, selectedRun.revision); setCompileRun(result); await queryClient.invalidateQueries({ queryKey: ["compile-runs", projectId] }); notify("已创建厂商编译准备任务，当前仍为未验证"); } catch (error) { notifyError(error); } finally { setBusy(false); } };
  const uploadEvidence = async (file?: File) => { if (!file || !activeCompileRun) return; setBusy(true); try { const result = await api.uploadCompileEvidence(activeCompileRun.id, file, "vendor_report", activeCompileRun.revision); setCompileRun(result.compile_run); await queryClient.invalidateQueries({ queryKey: ["compile-runs", projectId] }); notify("外部证据已按哈希保存，验证等级保持 manual_unverified"); } catch (error) { notifyError(error); } finally { setBusy(false); if (evidenceRef.current) evidenceRef.current.value = ""; } };
  const audit = auditResult.data; const vendorAdapters = (adapters.data || []).filter((item) => item.adapter_id !== "reference");
  return <ProjectPage kicker="P07 · AUDIT & COMPILE PREP" title="生成物审计与编译准备" description="确定性审计已真实接入；厂商编译、GX Works3 诊断和硬件结果仍未验证。">
    {!runs.data?.length ? <EmptyState title="尚无生成物" text="先在 P06 从已锁定 MachineSpec 生成程序。" /> : <><div className="verification-toolbar"><label>生成任务<select value={selectedRunId} onChange={(event) => { setRunId(event.target.value); setCompileRun(null); }}>{runs.data.map((run: GenerationRun) => <option key={run.id} value={run.id}>{run.generator_version} · {formatTime(run.created_at)}</option>)}</select></label><label>厂商 Adapter<select value={adapterId} onChange={(event) => setAdapterId(event.target.value)}>{vendorAdapters.map((item: AdapterDescriptor) => <option value={item.adapter_id} key={item.adapter_id}>{item.name}</option>)}</select></label><button className="button button--primary" disabled={busy} onClick={runAudit}><ListChecks size={16} />{busy ? "处理中…" : "运行自审计"}</button></div>
    <div className="verification-grid"><section className="panel verification-panel"><div className="panel__header"><div><h3>Audit v{audit?.audit_version || "1"}</h3><p>同一生成物稳定复现 · 不自动修改代码</p></div><Status value={audit?.status || (auditResult.isError ? "尚未审计" : "读取中")} /></div>{audit ? <><div className="audit-summary"><Metric label="总发现" value={String(audit.summary.total)} note={audit.input_hash.slice(0, 12)} icon={<ListChecks />} /><Metric label="Blocker" value={String(audit.summary.blocker)} note="阻断编译准备" icon={<WarningCircle />} /><Metric label="Warning" value={String(audit.summary.warning)} note="需要工程复核" icon={<Info />} /></div><div className="finding-list">{audit.findings.map((finding, index) => <article key={finding.code + index}><SeverityIcon issue={{ severity: finding.severity, id: String(index) } as ValidationIssue} /><span><strong>{finding.title}</strong><small>{finding.file || "全局"}{finding.line ? " 第 " + finding.line + " 行" : ""} · {finding.entity_id || "无对象 ID"}</small><p>{finding.detail}</p></span><Status value={finding.severity} /></article>)}{audit.findings.length === 0 && <EmptyState title="未发现问题" text="可创建厂商编译准备任务；这不代表 GX Works3 编译通过。" />}</div></> : <EmptyState title="尚未运行生成物自审计" text="先执行确定性审计，编译准备门禁才会开放。" />}</section>
    <aside className="panel compile-prep"><div className="panel__header"><div><h3>厂商编译证据</h3><p>人工降级路径 · 原件不可覆盖</p></div></div><div className="boundary-card"><WarningCircle size={22} /><span><strong>GX Works3 未验证</strong>本机不会启动未知厂商程序，也不会伪造编译结果。</span></div><button className="button button--primary" disabled={busy || !audit || audit.status === "blocked"} onClick={prepareCompile}>创建编译准备任务</button>{activeCompileRun && <div className="compile-record"><Status value={activeCompileRun.status} /><dl><dt>验证等级</dt><dd>{activeCompileRun.verification_level}</dd><dt>Adapter</dt><dd>{activeCompileRun.adapter_id}</dd><dt>任务 ID</dt><dd>{activeCompileRun.id.slice(0, 12)}</dd><dt>证据数</dt><dd>{activeCompileRun.evidence_count ?? 0}</dd></dl>{activeCompileRun.diagnostics.map((item, index) => <p key={index}>{String(item.message || item.code || "诊断信息")}</p>)}<input ref={evidenceRef} type="file" hidden onChange={(event) => uploadEvidence(event.target.files?.[0])} /><button className="button button--outline" disabled={busy} onClick={() => evidenceRef.current?.click()}><UploadSimple size={16} />导入厂商日志或截图</button><small>导入后仍标记 manual_unverified，集中验证签字前不会升级。</small></div>}</aside></div></>}
  </ProjectPage>;
}

function SimulationPage() {
  const queryClient = useQueryClient(); const { projectId } = useProjectContext(); const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => api.listRuns(projectId) });
  const simulationRuns = useQuery({ queryKey: ["simulation-runs", projectId], queryFn: () => api.listSimulationRuns(projectId) });
  const [runId, setRunId] = useState(""); const selectedRunId = runId || runs.data?.[0]?.id || ""; const [maxCycles, setMaxCycles] = useState(100); const [overrides, setOverrides] = useState("{}"); const [simulation, setSimulation] = useState<SimulationRun | null>(null); const [busy, setBusy] = useState(false);
  const persistedSimulation = simulationRuns.data?.find((item) => item.generation_run_id === selectedRunId) || null;
  const activeSimulation = simulation || persistedSimulation;
  const trace = useQuery({ queryKey: ["simulation-trace", activeSimulation?.id], queryFn: () => api.getSimulationTrace(activeSimulation!.id), enabled: Boolean(activeSimulation?.id) });
  const runSimulation = async () => { if (!selectedRunId) return; const selectedRun = runs.data?.find((item) => item.id === selectedRunId); if (!selectedRun) return; setBusy(true); try { const parsed = JSON.parse(overrides) as Record<string, boolean | number>; const result = await api.createSimulationRun(projectId, selectedRunId, parsed, maxCycles, selectedRun.revision); setSimulation(result); await queryClient.invalidateQueries({ queryKey: ["simulation-runs", projectId] }); notify("控谱参考逻辑模拟已完成；不等同于 GX Simulator3"); } catch (error) { notifyError(error); } finally { setBusy(false); } };
  const results = activeSimulation?.results || {}; const traces = trace.data?.traces || []; const lastTrace = traces[traces.length - 1];
  return <ProjectPage kicker="P08 · REFERENCE SIMULATION" title="控谱参考逻辑模拟" description="受限 TestSpec/Control IR 离散扫描执行器；不是 GX Simulator3，也不是硬件实测。">
    {!runs.data?.length ? <EmptyState title="尚无可模拟生成物" text="先在 P06 生成 Control IR 与 TestSpec。" /> : <><div className="verification-toolbar verification-toolbar--simulation"><label>生成任务<select value={selectedRunId} onChange={(event) => setRunId(event.target.value)}>{runs.data.map((run: GenerationRun) => <option key={run.id} value={run.id}>{run.generator_version} · {formatTime(run.created_at)}</option>)}</select></label><label>最大扫描周期<input type="number" min={1} max={10000} value={maxCycles} onChange={(event) => setMaxCycles(Number(event.target.value))} /></label><label className="override-field">输入覆盖（JSON）<input value={overrides} onChange={(event) => setOverrides(event.target.value)} spellCheck={false} /></label><button className="button button--primary" disabled={busy} onClick={runSimulation}><Pulse size={16} />{busy ? "运行中…" : "运行参考模拟"}</button></div>
    <div className="simulation-workbench"><section className="panel simulation-stage-real"><div className="panel__header"><div><h3>离散扫描结果</h3><p>{activeSimulation?.engine_version || "kongpu-reference-v1"}</p></div><Status value={activeSimulation?.status || "尚未运行"} /></div>{activeSimulation ? <><div className="reference-banner"><Info size={20} /><span><strong>{activeSimulation.verification_level}</strong>仅代表控谱参考逻辑模拟的自动验证结果。</span></div><div className="simulation-metrics"><Metric label="扫描周期" value={String(results.cycles ?? activeSimulation.trace_count)} note="离散逻辑周期" icon={<Pulse />} /><Metric label="最终工步" value={String(results.final_step_id ?? "END")} note="Control IR 工步" icon={<ListChecks />} /><Metric label="Trace" value={String(activeSimulation.trace_count)} note="不可变证据工件" icon={<FileText />} /></div><div className="trace-stream">{traces.slice(-30).map((item, index) => <article key={String(item.cycle || index)}><b>{String(item.cycle || index + 1)}</b><span><strong>{String(item.step_id || "END")}</strong><small>{JSON.stringify(item.events || [])}</small></span><code>{JSON.stringify(item.outputs || {})}</code></article>)}</div></> : <EmptyState title="等待参考模拟" text="默认输入均为 false；可用 JSON 覆盖已知 Control IR 信号。" />}</section><aside className="panel assertion-panel-real"><div className="panel__header"><div><h3>结果与边界</h3><p>失败可定位，不继承旧结果</p></div></div>{activeSimulation ? <><Gate label="执行状态" value={activeSimulation.status === "review_ready" ? 0 : 1} /><dl><dt>验证等级</dt><dd>{activeSimulation.verification_level}</dd><dt>程序 Commit</dt><dd>{activeSimulation.program_commit_id?.slice(0, 12) || "-"}</dd><dt>TestSpec</dt><dd>{activeSimulation.test_spec_revision_id?.slice(0, 12) || "-"}</dd><dt>最后输入</dt><dd><code>{JSON.stringify(lastTrace?.inputs || {})}</code></dd><dt>事件</dt><dd>{JSON.stringify(results.events || [])}</dd></dl>{(results.test_summary as { total?: number; passed?: number; failed?: number; blocked?: number } | undefined) && <p>TestSpec 用例：{String((results.test_summary as { total?: number }).total || 0)} 总计，{String((results.test_summary as { passed?: number }).passed || 0)} 通过，{String((results.test_summary as { failed?: number }).failed || 0)} 失败，{String((results.test_summary as { blocked?: number }).blocked || 0)} 阻断。</p>}</> : <p>新 Commit、不同 TestSpec 或不同引擎版本必须重新运行。</p>}<div className="boundary-card"><WarningCircle size={21} /><span><strong>厂商与硬件未验证</strong>结果不能用于声明程序可下载、可生产或安全确认。</span></div></aside></div></>}
  </ProjectPage>;
}

function SettingsPage() {
  const projects = useProjects(); const adapters = useQuery({ queryKey: ["adapters"], queryFn: api.listAdapters }); const [projectId, setProjectId] = useState(""); const selectedProjectId = projectId || projects.data?.[0]?.id || ""; const queryClient = useQueryClient();
  const environments = useQuery({ queryKey: ["adapter-environments", selectedProjectId], queryFn: () => api.listAdapterEnvironments(selectedProjectId), enabled: Boolean(selectedProjectId) });
  const [detecting, setDetecting] = useState<string | null>(null); const detect = async (adapterId: string) => { if (!selectedProjectId) return; setDetecting(adapterId); try { await api.detectAdapter(adapterId, selectedProjectId); await queryClient.invalidateQueries({ queryKey: ["adapter-environments", selectedProjectId] }); notify("环境快照已更新；检测过程未启动厂商程序"); } catch (error) { notifyError(error); } finally { setDetecting(null); } };
  const byAdapter = new Map((environments.data || []).map((item: AdapterEnvironment) => [item.adapter_id, item]));
  return <main className="hub-page"><PageHeading kicker="P12 · ENVIRONMENT" title="运行环境与 Adapter" description="只读检测本机能力、版本与允许路径；不保存 PLC 写入凭据。" actions={<label className="project-select">项目<select value={selectedProjectId} onChange={(event) => setProjectId(event.target.value)}>{(projects.data || []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>} /><section className="settings-grid-real">{(adapters.data || []).map((adapter: AdapterDescriptor) => { const environment = byAdapter.get(adapter.adapter_id); return <article className="panel adapter-card-real" key={adapter.adapter_id}><div className="adapter-card-real__head"><Cpu size={25} /><span><strong>{adapter.name}</strong><small>{adapter.vendor} · Adapter v{adapter.version}</small></span><Status value={environment?.status || adapter.verification_level} /></div><dl><dt>验证等级</dt><dd>{environment?.verification_level || adapter.verification_level}</dd><dt>平台</dt><dd>{String(environment?.details.platform || "未检测")}</dd><dt>Python</dt><dd>{String(environment?.details.python || "-")}</dd><dt>目标</dt><dd>{String(environment?.details.target_model || "-")}</dd></dl><div className="capability-matrix">{Object.entries(adapter.capabilities).map(([name, value]) => <span key={name}><code>{name}</code><b>{value}</b></span>)}</div><button className="button button--outline" disabled={!selectedProjectId || Boolean(detecting)} onClick={() => detect(adapter.adapter_id)}>{detecting === adapter.adapter_id ? "检测中…" : "只读检测环境"}</button></article>; })}</section><section className="panel boundary-panel"><WarningCircle size={20} /><div><strong>产品安全边界</strong><p>此页面不会启动未知程序，不执行任意命令，不保存 PLC 下载、RUN/STOP、强制输出或安全 PLC 凭据。</p></div></section></main>;
}

function UnavailablePage({ title, detail }: { title: string; detail: string }) { return <main className="hub-page"><PageHeading kicker="NOT CONNECTED" title={title} description="尚未接入真实能力" /><UnavailableBody detail={detail} /></main>; }
function UnavailableBody({ detail }: { detail: string }) { return <section className="panel unavailable"><WarningCircle size={38} weight="duotone" /><div><strong>尚未接入真实能力</strong><p>{detail}</p><small>M1/M2 不包含真实 PLC 下载、RUN/STOP、强制输出或安全 PLC 逻辑。</small></div></section>; }

function DeviceLibrary() {
  const devices = [{ name: "FX5U 通用 CPU", type: "PLC Target", status: "目标信息可用" }, { name: "双电控气缸", type: "Control Template", status: "M2 骨架生成" }, { name: "简单伺服握手", type: "Control Template", status: "M2 骨架生成" }, { name: "安全 PLC", type: "Excluded", status: "不自动生成" }];
  return <main className="hub-page"><PageHeading kicker="DEVICE LIBRARY" title="设备库" description="独立的设备与控制模板目录，不再跳转到系统设置。" /><section className="asset-grid">{devices.map((device) => <article className="panel asset-card-static" key={device.name}><Cpu size={24} /><div><strong>{device.name}</strong><small>{device.type}</small></div><Status value={device.status} /></article>)}</section></main>;
}

function DocumentsPage() {
  const docs = [{ name: "MachineSpec Template v1", type: "Excel 契约", location: "P03 模板中心" }, { name: "MachineSpec JSON Schema v1", type: "JSON Schema", location: "/api/v1/schemas/machine-spec/v1" }, { name: "本机 API 文档", type: "OpenAPI", location: "http://127.0.0.1:8000/docs" }, { name: "开发状态与边界", type: "Markdown", location: "docs/CURRENT_STATUS.md" }];
  return <main className="hub-page"><PageHeading kicker="DOCUMENTS" title="文档资料" description="独立的产品契约、API 与工程说明入口，不再跳转到模板页面。" /><section className="panel document-panel"><div className="document-list__head"><span>名称</span><span>类型</span><span>位置</span></div>{docs.map((doc) => <div className="document-row-real" key={doc.name}><span><FileText size={17} /><strong>{doc.name}</strong></span><span>{doc.type}</span><code>{doc.location}</code></div>)}</section></main>;
}
