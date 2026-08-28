import { useMemo, useState } from 'react';
import {
  ArrowLeft, ArrowRight, ArrowsClockwise, Check, CheckCircle, CircleNotch,
  ClipboardText, CodeBlock, Cpu, Database, Desktop, DownloadSimple, FileCode,
  FileText, GitBranch, HardDrives, LockKey, MagnifyingGlass, Play, Plugs,
  Pulse, ShieldCheck, SlidersHorizontal, UploadSimple, WarningCircle, XCircle,
} from '@phosphor-icons/react';

export const workflowPages = [
  { id: 'p03', short: '模板', title: '模板中心', nav: 'specs' },
  { id: 'p04', short: '导入', title: '导入与校验', nav: 'specs' },
  { id: 'p05', short: '审阅', title: 'MachineSpec 审阅', nav: 'specs' },
  { id: 'p06', short: '程序', title: '程序工作区', nav: 'program' },
  { id: 'p07', short: '编译', title: '编译验证', nav: 'debug' },
  { id: 'p08', short: '模拟', title: '模拟测试', nav: 'debug' },
  { id: 'p09', short: '发布', title: '发布评审', nav: 'program' },
  { id: 'p10', short: '监控', title: '在线只读监控', nav: 'debug' },
  { id: 'p11', short: '版本', title: '版本中心', nav: 'versions' },
  { id: 'p12', short: '设置', title: '环境与设置', nav: 'settings' },
];

const sheets = [
  ['Instructions', '填写说明', '必读'], ['Project', '项目与目标信息', '必填'],
  ['Components', '机构、元件与参数', '必填'], ['Signals', 'I/O 信号与地址', '必填'],
  ['Sequence', '动作步骤与转换条件', '必填'], ['Interlocks', '互锁关系', '选填'],
  ['Exceptions', '异常、超时与复位', '选填'],
];

const sampleRows = {
  Instructions: [['规则', '仅使用官方模板，不修改工作表名称'], ['版本', 'MachineSpec Template v1.0']],
  Project: [['ProjectName', '托盘举升检测站'], ['PLCModel', 'FX5U-64MT/ES'], ['CycleTarget', '18.0 s']],
  Components: [['CYL_LIFT', '举升气缸', 'cylinder'], ['SEN_TRAY', '托盘到位', 'photo_sensor'], ['AXIS_TRANSFER', '移载轴', 'servo']],
  Signals: [['X010', 'TrayPresent', 'BOOL'], ['Y020', 'LiftExtend', 'BOOL'], ['X011', 'LiftExtended', 'BOOL']],
  Sequence: [['S10', '等待托盘', 'TrayPresent'], ['S20', '举升到位', 'LiftExtended'], ['S30', '移载完成', 'AxisInPosition']],
  Interlocks: [['LiftExtend', 'TrayPresent AND NOT AxisMoving'], ['AxisMove', 'LiftExtended']],
  Exceptions: [['LiftTimeout', '3.0 s', '停止当前工步'], ['AxisAlarm', '立即', '进入故障状态']],
};

function DemoBadge() {
  return <span className="demo-badge"><ShieldCheck size={14} weight="duotone" /> 演示数据</span>;
}

function ProjectContext({ project }) {
  return (
    <div className="project-context">
      <div><span>当前项目</span><strong>{project.name}</strong><small>{project.id}</small></div>
      <div><span>目标 PLC</span><strong>{project.model}</strong><small>Adapter 按能力声明</small></div>
      <div><span>MachineSpec</span><strong>v0.3</strong><small>Template v1.0</small></div>
      <div><span>当前版本</span><strong>main · a84c2e1</strong><small>工作区无未提交修改</small></div>
      <DemoBadge />
    </div>
  );
}

function WorkflowNav({ page, navigate }) {
  const activeIndex = workflowPages.findIndex((item) => item.id === page);
  return (
    <nav className="workflow-nav" aria-label="工程流程页面">
      {workflowPages.map((item, index) => (
        <button key={item.id} className={item.id === page ? 'is-active' : index < activeIndex ? 'is-done' : ''} type="button" onClick={() => navigate(item.id)}>
          <span>{index < activeIndex ? <Check size={12} weight="bold" /> : String(index + 3).padStart(2, '0')}</span>{item.short}
        </button>
      ))}
    </nav>
  );
}

function PageHeader({ page, title, subtitle, navigate, actions }) {
  return (
    <div className="engineering-heading">
      <div>
        <button className="back-link" type="button" onClick={() => navigate('workspace')}><ArrowLeft size={16} /> 返回工作台</button>
        <div className="page-heading__kicker">PLC ENGINEERING FLOW / {page.toUpperCase()}</div>
        <h1>{title}</h1><p>{subtitle}</p>
      </div>
      <div className="engineering-heading__actions">{actions}</div>
    </div>
  );
}

function StatusPill({ tone = 'blue', children }) {
  return <span className={`flow-status flow-status--${tone}`}>{children}</span>;
}

function Metric({ label, value, note, tone = 'blue' }) {
  return <div className={`flow-metric flow-metric--${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

function TemplateCenter({ navigate, toast }) {
  const [sheet, setSheet] = useState('Components');
  const rows = sampleRows[sheet];
  return (
    <>
      <PageHeader page="p03" title="MachineSpec 模板中心" subtitle="下载项目专属模板，并逐表确认机械与电气需要提供的工程资料。" navigate={navigate} actions={<button className="button button--primary" type="button" onClick={() => navigate('p04')}><UploadSimple size={16} /> 上传已填写模板</button>} />
      <div className="flow-grid flow-grid--sidebar">
        <aside className="panel flow-side-list"><div className="panel__header"><div><h3>工作表</h3><p>5 张必填 · 2 张选填</p></div></div>{sheets.map(([id, label, required]) => <button key={id} className={sheet === id ? 'is-active' : ''} type="button" onClick={() => setSheet(id)}><span><strong>{id}</strong><small>{label}</small></span><StatusPill tone={required === '选填' ? 'gray' : 'blue'}>{required}</StatusPill></button>)}</aside>
        <section className="panel flow-surface">
          <div className="flow-surface__header"><div><span className="sheet-icon"><ClipboardText size={22} weight="duotone" /></span><div><h3>{sheet}</h3><p>{sheets.find(([id]) => id === sheet)[1]} · 示例预览</p></div></div><StatusPill tone="violet">Template v1.0</StatusPill></div>
          <div className="flow-callout"><ShieldCheck size={18} /><span><strong>填写原则</strong>保留字段名与工作表结构；不知道的内容留空并说明，不用猜测值填满表格。</span></div>
          <div className="data-table"><div className="data-table__head"><span>字段 / 标识</span><span>示例值</span></div>{rows.map((row) => <div className="data-table__row" key={row[0]}><strong>{row[0]}</strong><span>{row[1]}</span></div>)}</div>
          <div className="fill-notes"><h4>本表检查项</h4><div><CheckCircle size={16} weight="fill" /> 字段类型与枚举由模板约束</div><div><CheckCircle size={16} weight="fill" /> 项目、PLC 与模板版本写入文件元数据</div><div><WarningCircle size={16} weight="fill" /> 范例文件不能作为正式项目输入</div></div>
        </section>
      </div>
      <div className="flow-footer-actions"><span>项目专属：{new Date().getFullYear()} · MachineSpec v0.3</span><div><button className="button button--soft" type="button" onClick={() => toast('完整填写范例下载已模拟完成。')}><DownloadSimple size={16} /> 完整填写范例</button><button className="button button--primary" type="button" onClick={() => toast('空白工程模板下载已模拟完成。')}><DownloadSimple size={16} /> 空白工程模板</button></div></div>
    </>
  );
}

function ImportWorkspace({ navigate, toast }) {
  const [issues, setIssues] = useState([
    { id: 'E-021', tone: 'red', title: 'I/O 地址重复', detail: 'Signals!B18 与 Signals!B24 同时使用 X012', source: 'Signals · 第 24 行' },
    { id: 'E-014', tone: 'red', title: '转换条件缺少信号', detail: 'Sequence S30 引用了未定义的 AxisInPosition', source: 'Sequence · 第 8 行' },
    { id: 'W-006', tone: 'amber', title: '超时时间偏短', detail: '举升气缸超时 0.5 s，低于模板建议 2.0 s', source: 'Exceptions · 第 5 行' },
  ]);
  const [selected, setSelected] = useState('E-021');
  const current = issues.find((item) => item.id === selected) || issues[0];
  const fixCurrent = () => {
    const currentId = current?.id;
    setIssues((items) => {
      const nextItems = items.filter((item) => item.id !== currentId);
      setSelected(nextItems[0]?.id || '');
      return nextItems;
    });
    toast('已应用单项演示修正并记录差异，原始上传文件保持不变。');
  };
  return (
    <>
      <PageHeader page="p04" title="导入与校验工作区" subtitle="定位模板结构、数据引用和工程逻辑问题，所有修改都需要人工批准。" navigate={navigate} actions={<><button className="button button--soft" type="button" onClick={() => toast('重新检查完成，结果属于导入版本 import-003。')}><ArrowsClockwise size={16} /> 重新检查</button><button className="button button--primary" type="button" onClick={() => navigate('p05')} disabled={issues.some((item) => item.tone === 'red')}>进入规格审阅 <ArrowRight size={16} /></button></>} />
      <div className="metric-strip"><Metric label="导入版本" value="003" note="MachineSpec_托盘站.xlsx" /><Metric label="阻断错误" value={String(issues.filter((i) => i.tone === 'red').length)} note="必须处理" tone="red" /><Metric label="警告" value={String(issues.filter((i) => i.tone === 'amber').length)} note="可接受风险" tone="amber" /><Metric label="已通过检查" value="184" note="结构与引用" tone="green" /></div>
      <div className="flow-grid flow-grid--issues">
        <section className="panel issue-list"><div className="panel__header"><div><h3>检查问题</h3><p>按阻断程度排序</p></div><StatusPill tone="red">{issues.length} 项</StatusPill></div>{issues.length ? issues.map((item) => <button key={item.id} className={selected === item.id ? 'is-active' : ''} type="button" onClick={() => setSelected(item.id)}><WarningCircle size={18} weight="fill" className={`tone-text-${item.tone}`} /><span><strong>{item.title}</strong><small>{item.source}</small></span><b>{item.id}</b></button>) : <div className="flow-empty"><CheckCircle size={30} weight="duotone" /><strong>没有阻断问题</strong><span>当前导入版本可进入审阅</span></div>}</section>
        <section className="panel issue-detail">{current ? <><div className="flow-surface__header"><div><span className={`sheet-icon tone-${current.tone}`}><WarningCircle size={21} /></span><div><h3>{current.title}</h3><p>{current.id} · {current.source}</p></div></div><StatusPill tone={current.tone}>{current.tone === 'red' ? '阻断' : '警告'}</StatusPill></div><div className="issue-explanation"><h4>问题说明</h4><p>{current.detail}</p><h4>影响</h4><p>该问题会导致生成程序的变量映射或步骤转换不确定，不能静默推断。</p><h4>建议修正</h4><div className="diff-box"><span>- X012 · ClampClosed</span><strong>+ X014 · ClampClosed</strong></div></div><div className="issue-actions"><button className="button button--soft" type="button" onClick={() => toast('已定位到对应工作表单元格。')}>定位原始数据</button><button className="button button--primary" type="button" onClick={fixCurrent}>批准单项修正</button></div></> : <div className="flow-empty flow-empty--large"><CheckCircle size={38} weight="duotone" /><strong>导入检查完成</strong><span>原始文件和修正差异均已保存。</span><button className="button button--primary" type="button" onClick={() => navigate('p05')}>进入规格审阅 <ArrowRight size={16} /></button></div>}</section>
      </div>
    </>
  );
}

const reviewTabs = ['审阅摘要', '设备关系', '工艺流程', '节拍分析', '信号时序', 'I/O 映射', '互锁矩阵', '异常处理'];
function ReviewWorkspace({ navigate, toast }) {
  const [tab, setTab] = useState('审阅摘要');
  const [confirmed, setConfirmed] = useState(['设备关系', '工艺流程', 'I/O 映射']);
  const [locked, setLocked] = useState(false);
  const confirm = () => setConfirmed((items) => items.includes(tab) ? items : [...items, tab]);
  return (
    <>
      <PageHeader page="p05" title="MachineSpec 审阅工作区" subtitle="在程序生成前，用设备、流程、节拍和信号视图确认 Agent 对工程资料的理解。" navigate={navigate} actions={<><button className="button button--soft" type="button" onClick={() => navigate('p04')}>返回修改</button><button className="button button--primary" type="button" onClick={() => { setLocked(true); toast('MachineSpec v0.3 已在演示中锁定。'); }}><LockKey size={16} /> {locked ? '已锁定 v0.3' : '锁定 MachineSpec'}</button></>} />
      <div className="tab-strip">{reviewTabs.map((item) => <button key={item} type="button" className={tab === item ? 'is-active' : ''} onClick={() => setTab(item)}>{confirmed.includes(item) && <CheckCircle size={14} weight="fill" />}{item}</button>)}</div>
      <div className="flow-grid flow-grid--review">
        <section className="panel review-canvas"><div className="flow-surface__header"><div><span className="sheet-icon"><SlidersHorizontal size={21} /></span><div><h3>{tab}</h3><p>点击节点可回溯到模板来源</p></div></div><StatusPill tone={confirmed.includes(tab) ? 'green' : 'amber'}>{confirmed.includes(tab) ? '已确认' : '待确认'}</StatusPill></div><ReviewVisual tab={tab} toast={toast} /></section>
        <aside className="panel review-summary"><div className="panel__header"><div><h3>审阅状态</h3><p>MachineSpec v0.3</p></div></div><div className="review-score"><strong>{Math.round((confirmed.length / reviewTabs.length) * 100)}%</strong><span>{confirmed.length} / {reviewTabs.length} 个视图已确认</span></div>{reviewTabs.map((item) => <div className="review-check" key={item}>{confirmed.includes(item) ? <CheckCircle size={16} weight="fill" /> : <WarningCircle size={16} />}<span>{item}</span><small>{confirmed.includes(item) ? '已确认' : '待审阅'}</small></div>)}<button className="button button--outline button--wide" type="button" onClick={confirm}>确认当前视图</button>{locked && <button className="button button--primary button--wide" type="button" onClick={() => navigate('p06')}>进入程序生成 <ArrowRight size={16} /></button>}</aside>
      </div>
    </>
  );
}

function ReviewVisual({ tab, toast }) {
  if (tab === '工艺流程' || tab === '审阅摘要') return <div className="process-flow">{['S10 等待托盘', 'S20 举升定位', 'S30 移载取件', 'S40 降下复位'].map((item, index) => <button type="button" key={item} onClick={() => toast(`${item} 来源：Sequence 工作表。`)}><span>{index + 1}</span><strong>{item}</strong><small>{index === 3 ? 'CycleDone' : '条件满足后转移'}</small></button>)}</div>;
  if (tab === '设备关系') return <div className="device-tree"><strong>托盘举升检测站</strong><div><span>举升机构</span><button type="button">CYL_LIFT</button><button type="button">SEN_TRAY</button></div><div><span>移载机构</span><button type="button">AXIS_TRANSFER</button><button type="button">GRIPPER_01</button></div></div>;
  if (tab === '信号时序' || tab === '节拍分析') return <div className="timing-chart">{['TrayPresent', 'LiftExtend', 'LiftExtended', 'AxisMove'].map((name, index) => <div key={name}><span>{name}</span><i style={{ width: `${62 + index * 7}%`, marginLeft: `${index * 7}%` }} /></div>)}</div>;
  return <div className="matrix-view">{['LiftExtend', 'AxisMove', 'GripperClose', 'CycleReset'].map((name, index) => <div key={name}><strong>{name}</strong><span>X0{10 + index}</span><span className={index === 3 ? 'is-warning' : ''}>{index === 3 ? '待补充' : '已映射'}</span></div>)}</div>;
}

function ProgramWorkspace({ navigate, toast }) {
  const [file, setFile] = useState('PRG_AutoCycle.st');
  const [generated, setGenerated] = useState(true);
  const code = `PROGRAM PRG_AutoCycle\nVAR\n  Step : INT := 10;\n  LiftExtend : BOOL;\n  LiftExtended : BOOL;\nEND_VAR\n\nCASE Step OF\n  10: IF TrayPresent THEN Step := 20; END_IF;\n  20: LiftExtend := TRUE;\n      IF LiftExtended THEN Step := 30; END_IF;\n  30: FB_TransferAxis.Execute := TRUE;\nEND_CASE;`;
  return (
    <>
      <PageHeader page="p06" title="程序工作区" subtitle="在独立 AI 分支审阅程序、变量、TestSpec、需求追踪和版本差异。" navigate={navigate} actions={<><button className="button button--soft" type="button" onClick={() => { setGenerated(false); window.setTimeout(() => setGenerated(true), 700); }}>{generated ? <ArrowsClockwise size={16} /> : <CircleNotch className="spin" size={16} />} 重新生成</button><button className="button button--primary" type="button" onClick={() => navigate('p07')}>送去编译 <ArrowRight size={16} /></button></>} />
      <div className="program-toolbar"><StatusPill tone="violet">ai/spec-v0.3</StatusPill><span><GitBranch size={15} /> Commit a84c2e1</span><span><CheckCircle size={15} weight="fill" /> MachineSpec v0.3 已锁定</span><button type="button" onClick={() => toast('已创建演示 Commit：d31f805。')}>创建 Commit</button></div>
      <div className="program-layout">
        <aside className="panel file-tree"><div className="panel__header"><div><h3>程序树</h3><p>38 个程序块</p></div></div>{['PRG_AutoCycle.st', 'FB_LiftCylinder.st', 'FB_TransferAxis.st', 'GVL_IO.st', 'TestSpec.yaml'].map((item) => <button type="button" key={item} className={file === item ? 'is-active' : ''} onClick={() => setFile(item)}><FileCode size={16} /><span>{item}</span></button>)}</aside>
        <section className="code-panel"><div className="code-panel__header"><span>{file}</span><div><StatusPill tone="amber">未编译</StatusPill><button type="button" onClick={() => toast('编辑内容已保存到演示工作区。')}>保存</button></div></div>{generated ? <pre><code>{file.endsWith('.yaml') ? 'tests:\n  - name: normal_cycle\n    assert: CycleDone = TRUE\n  - name: lift_timeout\n    assert: AlarmLiftTimeout = TRUE' : code}</code></pre> : <div className="flow-empty flow-empty--large"><CircleNotch className="spin" size={32} /><strong>正在按 MachineSpec 重新生成</strong></div>}</section>
        <aside className="panel trace-panel"><div className="panel__header"><div><h3>需求追踪</h3><p>当前选择</p></div></div><div className="trace-item"><span>REQ-SEQ-003</span><strong>托盘到位后启动举升</strong><small>Sequence!A6 · 已覆盖</small></div><div className="trace-item"><span>REQ-EXC-002</span><strong>举升 3 秒未到位报警</strong><small>Exceptions!A5 · 已覆盖</small></div><div className="flow-callout flow-callout--amber"><WarningCircle size={17} /><span><strong>1 个 TODO</strong>报警文本未填写，不阻断程序生成。</span></div></aside>
      </div>
    </>
  );
}

function CompileWorkspace({ navigate, toast }) {
  const [state, setState] = useState('failed');
  const run = () => { setState('running'); window.setTimeout(() => setState(state === 'fixed' ? 'passed' : 'failed'), 850); };
  return (
    <>
      <PageHeader page="p07" title="编译验证" subtitle="在厂商工程副本中执行演示编译，读取诊断并批准受控修复。" navigate={navigate} actions={<><button className="button button--soft" type="button" onClick={() => toast('已模拟打开 GX Works3 工程副本。')}><Desktop size={16} /> 在厂商软件打开</button><button className="button button--primary" type="button" onClick={run} disabled={state === 'running'}>{state === 'running' ? <CircleNotch className="spin" size={16} /> : <Play size={16} />} 开始编译</button></>} />
      <div className="metric-strip"><Metric label="目标环境" value="GX Works3" note="v1.110W · 演示" /><Metric label="当前 Commit" value="a84c2e1" note="ai/spec-v0.3" /><Metric label="错误" value={state === 'passed' ? '0' : '1'} note="程序诊断" tone={state === 'passed' ? 'green' : 'red'} /><Metric label="警告" value="2" note="非阻断" tone="amber" /></div>
      <div className="compile-steps">{['准备工程副本', '导入程序与配置', '调用厂商编译器', '读取诊断'].map((item, index) => <div key={item} className={state === 'running' && index === 2 ? 'is-running' : 'is-done'}>{state === 'running' && index === 2 ? <CircleNotch className="spin" /> : <CheckCircle weight="fill" />}<span><strong>{item}</strong><small>{index === 2 ? '不执行 PLC 下载' : '演示步骤已完成'}</small></span></div>)}</div>
      <div className="flow-grid flow-grid--compile"><section className="panel diagnostic-list"><div className="panel__header"><div><h3>编译诊断</h3><p>厂商原文与统一分类</p></div></div>{state === 'passed' ? <div className="flow-empty flow-empty--large"><CheckCircle size={38} weight="duotone" /><strong>编译通过</strong><span>当前结果属于 Commit a84c2e1</span><button className="button button--primary" type="button" onClick={() => navigate('p08')}>进入模拟测试 <ArrowRight size={16} /></button></div> : <button type="button" className="diagnostic-item is-active"><XCircle size={18} weight="fill" /><span><strong>E1024 · 未声明的标识符</strong><small>PRG_AutoCycle.st · 第 18 行</small></span></button>}</section><section className="panel diagnostic-detail"><div className="flow-surface__header"><div><h3>AxisInPosition 未定义</h3><p>程序错误 · 来源 REQ-SEQ-003</p></div><StatusPill tone="red">阻断</StatusPill></div><div className="vendor-message">GX Works3: Undefined label 'AxisInPosition'.</div><div className="issue-explanation"><h4>受控修复</h4><p>将流程条件引用映射到 GVL_IO.AxisTransfer_InPosition，不改变工艺意图。</p><div className="diff-box"><span>- IF AxisInPosition THEN</span><strong>+ IF GVL_IO.AxisTransfer_InPosition THEN</strong></div></div><div className="issue-actions"><button className="button button--soft" type="button" onClick={() => navigate('p06')}>查看代码</button><button className="button button--primary" type="button" onClick={() => { setState('fixed'); toast('修复已批准并创建演示 Commit；请重新编译。'); }}>批准修复并建 Commit</button></div></section></div>
    </>
  );
}

function SimulationWorkspace({ navigate, toast }) {
  const [state, setState] = useState('ready');
  const run = () => { setState('running'); window.setTimeout(() => setState('passed'), 1100); };
  const tests = [['正常自动循环', '12 / 12', 'green'], ['举升超时', '5 / 5', 'green'], ['托盘中途移除', '4 / 4', 'green'], ['急停输入监视', '只读检查', 'amber']];
  return (
    <>
      <PageHeader page="p08" title="模拟测试工作区" subtitle="在 GX Simulator3 演示后端运行 TestSpec，查看工步、信号、Trace 与断言。" navigate={navigate} actions={<><button className="button button--soft" type="button" onClick={() => setState('ready')}>复位会话</button><button className="button button--primary" type="button" onClick={run} disabled={state === 'running'}>{state === 'running' ? <CircleNotch className="spin" size={16} /> : <Play size={16} />} 运行全部测试</button></>} />
      <div className="simulation-banner"><span className={`simulation-state simulation-state--${state}`}>{state === 'running' ? <CircleNotch className="spin" /> : <Pulse />}{state === 'passed' ? '全部测试通过' : state === 'running' ? '模拟会话运行中' : '模拟后端已就绪'}</span><span>Commit a84c2e1 · TestSpec v0.3 · GX Simulator3 演示</span>{state === 'passed' && <button type="button" onClick={() => navigate('p09')}>进入发布评审 <ArrowRight size={15} /></button>}</div>
      <div className="flow-grid flow-grid--simulation"><aside className="panel test-tree"><div className="panel__header"><div><h3>测试套件</h3><p>正常与异常路径</p></div></div>{tests.map(([name, count, tone]) => <button type="button" key={name}><CheckCircle size={17} weight="fill" className={`tone-text-${tone}`} /><span><strong>{name}</strong><small>{count} 个断言</small></span></button>)}</aside><section className="panel simulation-stage"><div className="flow-surface__header"><div><h3>实时工步与信号</h3><p>采样 100 ms · 演示变量</p></div><StatusPill tone={state === 'running' ? 'blue' : state === 'passed' ? 'green' : 'gray'}>{state === 'running' ? '运行中' : state === 'passed' ? '通过' : '待运行'}</StatusPill></div><div className="step-display"><span>当前工步</span><strong>{state === 'running' ? 'S30 · 移载取件' : state === 'passed' ? 'S40 · 循环完成' : 'S10 · 等待托盘'}</strong><small>AutoMode = TRUE · SafetyReady = TRUE</small></div><div className="signal-grid">{[['TrayPresent', 'TRUE'], ['LiftExtend', 'TRUE'], ['LiftExtended', 'TRUE'], ['AxisInPosition', state === 'passed' ? 'TRUE' : 'FALSE'], ['CycleDone', state === 'passed' ? 'TRUE' : 'FALSE'], ['AlarmActive', 'FALSE']].map(([name, value]) => <div key={name}><span>{name}</span><strong className={value === 'TRUE' ? 'is-on' : ''}>{value}</strong></div>)}</div><div className="waveform">{['TrayPresent', 'LiftExtend', 'LiftExtended', 'CycleDone'].map((name, index) => <div key={name}><span>{name}</span><i style={{ width: `${45 + index * 12}%` }} /></div>)}</div></section><aside className="panel assertion-panel"><div className="panel__header"><div><h3>断言与 Trace</h3><p>正常自动循环</p></div></div>{['托盘到位后进入 S20', '3 秒内举升到位', '移载轴互锁有效', '循环结束输出复位'].map((item) => <div key={item}><CheckCircle size={16} weight="fill" /><span>{item}</span><small>通过</small></div>)}<button className="button button--outline button--wide" type="button" onClick={() => toast('模拟报告下载已演示完成。')}><DownloadSimple size={16} /> 下载测试报告</button></aside></div>
    </>
  );
}

function ReleaseWorkspace({ navigate, toast }) {
  const [released, setReleased] = useState(false);
  const checks = [['MachineSpec v0.3', '已锁定'], ['程序 Commit a84c2e1', '已提交'], ['GX Works3 编译', '通过 · 2 警告'], ['TestSpec 模拟', '21 / 21 通过'], ['安全边界', '无 PLC 下载动作']];
  return (
    <>
      <PageHeader page="p09" title="发布评审与交付包" subtitle="确认规格、程序、编译、模拟和风险属于同一 Commit，再创建可追踪 Release。" navigate={navigate} actions={<><button className="button button--soft" type="button" onClick={() => navigate('p06')}>退回程序</button><button className="button button--primary" type="button" onClick={() => { setReleased(true); toast('Release v0.8 已在演示中创建；未向 PLC 下载任何内容。'); }}><ShieldCheck size={16} /> {released ? '已发布 v0.8' : '批准发布'}</button></>} />
      <div className="release-hero"><div><span>候选版本</span><strong>{released ? 'Release v0.8' : 'RC-2026.08.28-01'}</strong><small>托盘举升检测站 · a84c2e1</small></div><div className="release-readiness"><strong>{released ? '已发布' : '可发布'}</strong><span>5 / 5 发布门已满足</span></div></div>
      <div className="flow-grid flow-grid--release"><section className="panel release-checks"><div className="panel__header"><div><h3>发布条件</h3><p>结果必须属于当前 Commit</p></div></div>{checks.map(([name, status]) => <div key={name}><CheckCircle size={18} weight="fill" /><span><strong>{name}</strong><small>{status}</small></span><StatusPill tone="green">通过</StatusPill></div>)}</section><section className="panel package-preview"><div className="flow-surface__header"><div><h3>交付包预览</h3><p>Kongpu_KP-2508-014_v0.8.zip</p></div><button type="button" onClick={() => toast('交付包预览已刷新。')}><ArrowsClockwise size={16} /></button></div>{['MANIFEST.json', 'MachineSpec_v0.3.xlsx', 'PLC_Project_FX5U.zip', 'Compile_Report.pdf', 'Simulation_Report.pdf', 'Release_Notes.md'].map((item) => <div className="package-file" key={item}><FileText size={17} /><span>{item}</span><small>已校验</small></div>)}<div className="flow-callout flow-callout--amber"><WarningCircle size={17} /><span><strong>发布不等于下载</strong>交付包需要工程师在厂商 IDE 中人工审核和下载。</span></div></section></div>
      {released && <div className="flow-footer-actions"><span><CheckCircle size={16} weight="fill" /> Release v0.8 已生成并写入版本时间线</span><div><button className="button button--soft" type="button" onClick={() => navigate('p11')}>查看版本</button><button className="button button--primary" type="button" onClick={() => navigate('p10')}>进入只读监控 <ArrowRight size={16} /></button></div></div>}
    </>
  );
}

function MonitorWorkspace({ navigate, toast }) {
  const [connected, setConnected] = useState(false);
  const [recording, setRecording] = useState(false);
  return (
    <>
      <PageHeader page="p10" title="在线只读监控" subtitle="工程师人工下载后，读取 PLC 运行状态、变量与 Trace，形成现场调试证据。" navigate={navigate} actions={<><button className="button button--soft" type="button" onClick={() => { setRecording(!recording); toast(recording ? '演示记录已停止并保存。' : '已开始记录演示变量窗口。'); }}><Pulse size={16} /> {recording ? '停止记录' : '开始记录'}</button><button className={`button ${connected ? 'button--soft' : 'button--primary'}`} type="button" onClick={() => setConnected(!connected)}><Plugs size={16} /> {connected ? '断开连接' : '建立只读连接'}</button></>} />
      <div className={`monitor-banner ${connected ? 'is-connected' : ''}`}><span><span className="status-pulse" /> {connected ? '只读连接 · 192.168.1.10' : '未连接真实设备'}</span><strong>{connected ? 'FX5U · RUN · Release v0.8' : '所有写入能力已禁用'}</strong><StatusPill tone={connected ? 'green' : 'gray'}>{connected ? '版本匹配' : '安全待机'}</StatusPill></div>
      <div className="metric-strip"><Metric label="运行模式" value={connected ? 'AUTO' : '--'} note="只读变量" tone={connected ? 'green' : 'gray'} /><Metric label="当前工步" value={connected ? 'S30' : '--'} note="移载取件" /><Metric label="循环时间" value={connected ? '17.6s' : '--'} note="目标 18.0s" tone="cyan" /><Metric label="活动报警" value={connected ? '0' : '--'} note="无写入动作" tone="green" /></div>
      <div className="flow-grid flow-grid--monitor"><section className="panel watch-list"><div className="panel__header"><div><h3>Watch List</h3><p>采样质量 99.8%</p></div><button type="button" onClick={() => toast('已打开演示变量选择器。')}><MagnifyingGlass size={16} /></button></div>{[['ModeAuto', 'TRUE'], ['CurrentStep', connected ? '30' : '--'], ['TrayPresent', connected ? 'TRUE' : '--'], ['LiftExtended', connected ? 'TRUE' : '--'], ['AxisPosition', connected ? '425.0 mm' : '--'], ['CycleDone', connected ? 'FALSE' : '--']].map(([name, value]) => <div key={name}><span>{name}</span><strong className={value === 'TRUE' ? 'is-on' : ''}>{value}</strong></div>)}</section><section className="panel monitor-trace"><div className="flow-surface__header"><div><h3>现场 Trace</h3><p>{recording ? '正在记录 · 100 ms' : '最近 30 秒窗口'}</p></div><StatusPill tone={recording ? 'red' : 'blue'}>{recording ? 'REC' : '只读'}</StatusPill></div><div className="trace-chart">{['Step', 'LiftExtend', 'LiftExtended', 'AxisBusy', 'CycleDone'].map((name, index) => <div key={name}><span>{name}</span><i style={{ width: `${50 + index * 8}%`, marginLeft: `${index * 3}%` }} /></div>)}</div><div className="agent-analysis"><Cpu size={21} weight="duotone" /><span><strong>Agent 分析</strong>{connected ? '当前等待移载轴 InPosition，输入与 Release v0.8 变量映射一致，尚未观察到阻断条件。' : '建立只读连接后，才会基于明确授权的变量窗口生成分析。'}</span></div></section><aside className="panel field-notes"><div className="panel__header"><div><h3>现场证据</h3><p>调试观察记录</p></div></div><textarea placeholder="记录现场现象、操作和时间点..." /><button className="button button--outline button--wide" type="button" onClick={() => toast('现场证据窗口已保存到版本时间线。')}>保存证据窗口</button><button className="button button--primary button--wide" type="button" onClick={() => { toast('已从现场证据创建演示调试分支。'); navigate('p06'); }}>创建修改分支</button></aside></div>
    </>
  );
}

function VersionCenter({ navigate, toast }) {
  const [tab, setTab] = useState('时间线');
  const [compare, setCompare] = useState(false);
  const tabs = ['时间线', '分支', 'Commits', 'Releases', '比较', '工件'];
  return (
    <>
      <PageHeader page="p11" title="版本中心" subtitle="统一追踪规格、程序、编译、模拟、Release 和现场证据，恢复操作始终创建新分支。" navigate={navigate} actions={<button className="button button--primary" type="button" onClick={() => { setTab('比较'); setCompare(true); }}><GitBranch size={16} /> 比较版本</button>} />
      <div className="tab-strip">{tabs.map((item) => <button type="button" key={item} className={tab === item ? 'is-active' : ''} onClick={() => setTab(item)}>{item}</button>)}</div>
      {tab === '比较' ? <div className="compare-layout"><section className="panel compare-selectors"><div className="panel__header"><div><h3>选择两个版本</h3><p>只读比较，不改写历史</p></div></div><label>基础版本<select defaultValue="v0.7"><option>Release v0.7 · 7bc10f3</option><option>Release v0.6 · 51d2a08</option></select></label><label>目标版本<select defaultValue="v0.8"><option>Release v0.8 · a84c2e1</option></select></label><button className="button button--primary button--wide" type="button" onClick={() => setCompare(true)}>生成差异</button></section><section className="panel compare-result"><div className="flow-surface__header"><div><h3>v0.7 → v0.8</h3><p>MachineSpec、程序与测试差异</p></div><StatusPill tone="blue">12 项变更</StatusPill></div>{compare && <><div className="change-group"><strong>MachineSpec</strong><span>+ 2 个信号 · 1 个转换条件调整</span></div><div className="change-group"><strong>程序</strong><span>+ 34 行 · - 8 行 · 3 个程序块</span></div><div className="change-group"><strong>测试</strong><span>+ 2 个异常场景 · 全部通过</span></div><div className="diff-box"><span>- LiftTimeout := T#2S;</span><strong>+ LiftTimeout := T#3S;</strong></div><button className="button button--outline" type="button" onClick={() => toast('已基于 Release v0.7 创建恢复分支 restore/v0.7-demo；未改写历史。')}>基于 v0.7 创建恢复分支</button></>}</section></div> : <div className="timeline">{[['今天 10:42', 'Release v0.8', '发布', '编译与 21 个模拟断言通过'], ['今天 10:31', 'a84c2e1', 'Commit', '修正 AxisInPosition 变量映射'], ['今天 10:05', 'MachineSpec v0.3', '规格锁定', '8 个审阅视图确认'], ['昨天 18:16', 'Release v0.7', '历史发布', '电气工程师批准'], ['08-26 15:03', '现场证据 #014', '只读监控', '保存 30 秒 Trace 窗口']].map(([time, title, type, desc], index) => <div key={title}><span className="timeline__dot">{index === 0 ? <Check size={12} /> : index + 1}</span><time>{time}</time><section><div><strong>{title}</strong><StatusPill tone={index === 0 ? 'green' : index === 4 ? 'violet' : 'blue'}>{type}</StatusPill></div><p>{desc}</p><button type="button" onClick={() => toast(`已打开 ${title} 的演示详情。`)}>查看详情 <ArrowRight size={13} /></button></section></div>)}</div>}
    </>
  );
}

function SettingsWorkspace({ toast, navigate }) {
  const [tab, setTab] = useState('本机工具');
  const [cloudAllowed, setCloudAllowed] = useState(false);
  const tabs = ['本机工具', 'Adapters', '模型', '数据策略', '模板版本', '兼容矩阵'];
  const tools = [['GX Works3', 'v1.110W', '可用', 'green'], ['GX Simulator3', 'v1.041B', '可用', 'green'], ['AutoShop', '未检测', '需复核', 'amber'], ['CODESYS', 'V3.5 SP20', '实验', 'blue']];
  return (
    <>
      <PageHeader page="p12" title="环境与系统设置" subtitle="维护厂商工具、Adapter、模型、数据策略、模板版本和 PLC 兼容能力。" navigate={navigate} actions={<button className="button button--primary" type="button" onClick={() => toast('本机环境演示检测已完成。')}><ArrowsClockwise size={16} /> 重新检测全部</button>} />
      <div className="tab-strip">{tabs.map((item) => <button type="button" key={item} className={tab === item ? 'is-active' : ''} onClick={() => setTab(item)}>{item}</button>)}</div>
      {tab === '本机工具' && <div className="settings-grid">{tools.map(([name, version, status, tone]) => <section className="panel tool-card" key={name}><span className="sheet-icon"><Desktop size={22} /></span><div><strong>{name}</strong><small>{version}</small></div><StatusPill tone={tone}>{status}</StatusPill><button type="button" onClick={() => toast(`${name} 自检已模拟完成。`)}>运行自检</button></section>)}</div>}
      {tab === 'Adapters' && <div className="settings-grid">{[['GX Works3 Adapter', '编译 · 模拟 · 只读监控'], ['AutoShop Adapter', '技术验证中 · 不声明 supported'], ['CODESYS Adapter', '实验编译与 Control Win']].map(([name, desc]) => <section className="panel adapter-card" key={name}><Plugs size={24} weight="duotone" /><div><strong>{name}</strong><p>{desc}</p><small>契约版本 0.1 · 最近自检今天</small></div><button className="button button--soft" type="button" onClick={() => toast(`${name} 日志已在演示面板打开。`)}>查看日志</button></section>)}</div>}
      {tab === '模型' && <section className="panel settings-form"><div className="panel__header"><div><h3>模型网关</h3><p>云端 OpenAI-compatible 接口 · 本地模型后续接入</p></div><StatusPill tone="green">连通</StatusPill></div><div className="settings-form__body"><label>端点<input value="https://api.example.com/v1" readOnly /></label><label>模型用途<select defaultValue="工程补全"><option>工程补全</option><option>现场分析</option></select></label><div className="setting-toggle"><span><strong>允许上传项目上下文</strong><small>每次调用仍需明确授权</small></span><button className={cloudAllowed ? 'is-on' : ''} type="button" onClick={() => setCloudAllowed(!cloudAllowed)}><i /></button></div><div className="flow-callout flow-callout--amber"><ShieldCheck size={18} /><span><strong>数据最小化</strong>原始高频 PLC 数据不会未经选择直接发送到云端模型。</span></div></div></section>}
      {tab === '数据策略' && <section className="panel policy-list">{[['真实 PLC 写权限', '永久禁用', 'red'], ['云端上下文', '逐次授权', 'amber'], ['原始上传文件', '保留全部版本', 'green'], ['运行日志', '本机保留 30 天', 'blue']].map(([name, value, tone]) => <div key={name}><span><strong>{name}</strong><small>策略由项目安全边界约束</small></span><StatusPill tone={tone}>{value}</StatusPill></div>)}</section>}
      {tab === '模板版本' && <section className="panel version-table"><div className="data-table__head"><span>版本</span><span>状态</span><span>适用项目</span><span>发布时间</span></div>{[['v1.0', '当前', '4', '2026-08-28'], ['v0.9', '历史', '2', '2026-08-12'], ['v0.8', '历史', '1', '2026-07-24']].map((row) => <div className="data-table__row" key={row[0]}>{row.map((cell) => <span key={cell}>{cell}</span>)}</div>)}</section>}
      {tab === '兼容矩阵' && <section className="panel version-table"><div className="data-table__head"><span>PLC</span><span>编译</span><span>模拟</span><span>监控</span></div>{[['FX5U / GX Works3', '实验', '实验', '只读演示'], ['H5U / AutoShop', '待验证', '人工', '未接入'], ['CODESYS Control Win', '实验', '实验', '需配置']].map((row) => <div className="data-table__row" key={row[0]}>{row.map((cell) => <span key={cell}>{cell}</span>)}</div>)}</section>}
    </>
  );
}

export function EngineeringPage({ page, project, navigate, toast }) {
  const content = useMemo(() => ({
    p03: <TemplateCenter navigate={navigate} toast={toast} />,
    p04: <ImportWorkspace navigate={navigate} toast={toast} />,
    p05: <ReviewWorkspace navigate={navigate} toast={toast} />,
    p06: <ProgramWorkspace navigate={navigate} toast={toast} />,
    p07: <CompileWorkspace navigate={navigate} toast={toast} />,
    p08: <SimulationWorkspace navigate={navigate} toast={toast} />,
    p09: <ReleaseWorkspace navigate={navigate} toast={toast} />,
    p10: <MonitorWorkspace navigate={navigate} toast={toast} />,
    p11: <VersionCenter navigate={navigate} toast={toast} />,
    p12: <SettingsWorkspace navigate={navigate} toast={toast} />,
  }), [page, project, navigate, toast]);
  return <main className="engineering-page"><ProjectContext project={project} /><WorkflowNav page={page} navigate={navigate} />{content[page]}</main>;
}
