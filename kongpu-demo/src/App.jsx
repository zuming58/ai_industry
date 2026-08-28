import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  ArrowSquareOut,
  ArrowsClockwise,
  Bell,
  CaretDown,
  Check,
  CheckCircle,
  CircleNotch,
  ClipboardText,
  Clock,
  CodeBlock,
  Cpu,
  Cube,
  Database,
  Desktop,
  DotsThree,
  FileCode,
  FileText,
  FolderSimple,
  Funnel,
  GearSix,
  GitBranch,
  HardDrives,
  ListChecks,
  MagnifyingGlass,
  Plugs,
  Plus,
  Pulse,
  Question,
  ShieldCheck,
  SquaresFour,
  UserCircle,
  WarningCircle,
  WifiSlash,
  X,
} from '@phosphor-icons/react';
import { EngineeringPage, workflowPages } from './EngineeringPages.jsx';

const BRAND_ICON = '/assets/brand/kongpu-app-icon.png';

const navItems = [
  { id: 'workspace', label: '工作台', icon: SquaresFour },
  { id: 'projects', label: '项目管理', icon: FolderSimple },
  { id: 'specs', label: '规格管理', icon: ClipboardText },
  { id: 'program', label: '程序工程', icon: FileCode },
  { id: 'debug', label: '调试工具', icon: Pulse },
  { id: 'devices', label: '设备库', icon: HardDrives },
  { id: 'documents', label: '文档资料', icon: FileText },
  { id: 'versions', label: '版本控制', icon: GitBranch },
];

const projects = [
  {
    id: 'KP-2508-014',
    name: '托盘举升检测站',
    model: 'Mitsubishi FX5U-64MT/ES',
    status: '规格审阅',
    statusTone: 'blue',
    progress: 46,
    updated: '今天 09:42',
    branch: 'main',
    version: 'v0.3',
    io: '256 / 512',
    blocks: 38,
    tasks: 5,
    blockers: 2,
  },
  {
    id: 'KP-2508-009',
    name: '电机转子压装线',
    model: 'Mitsubishi FX5U-80MT/ES',
    status: '编译验证',
    statusTone: 'violet',
    progress: 72,
    updated: '昨天 18:16',
    branch: 'release/0.7',
    version: 'v0.7',
    io: '384 / 512',
    blocks: 56,
    tasks: 3,
    blockers: 0,
  },
  {
    id: 'KP-2507-031',
    name: '电池包气密检测机',
    model: 'Mitsubishi FX5UC-96MT/DSS',
    status: '在线调试',
    statusTone: 'green',
    progress: 88,
    updated: '08-26 15:03',
    branch: 'commissioning',
    version: 'v1.2',
    io: '448 / 512',
    blocks: 71,
    tasks: 8,
    blockers: 1,
  },
  {
    id: 'KP-2507-018',
    name: '输送线分拣单元',
    model: 'Mitsubishi FX5U-32MT/ES',
    status: '已归档',
    statusTone: 'gray',
    progress: 100,
    updated: '08-20 11:28',
    branch: 'main',
    version: 'v1.0',
    io: '128 / 256',
    blocks: 24,
    tasks: 0,
    blockers: 0,
  },
];

const stageLabels = ['资料整理', '程序生成', '编译验证', '在线调试'];

const targetCatalog = {
  '三菱电机': {
    'MELSEC iQ-F': ['FX5U-64MT/ES', 'FX5U-80MT/ES', 'FX5U-32MT/ES'],
    'MELSEC iQ-F 紧凑型': ['FX5UC-96MT/DSS'],
  },
  '汇川技术': {
    'H5U 系列': ['H5U-1614MTD-A8', 'H5U-3232MTD-A8'],
  },
  CODESYS: {
    'Control Win': ['CODESYS Control Win SL'],
  },
};

const environmentProfiles = {
  '三菱电机': {
    software: 'GX Works3',
    softwareNote: 'v1.110W · 演示检测',
    simulator: 'GX Simulator3',
    simulatorNote: 'v1.041B · 演示检测',
    adapter: 'GX Works3 Adapter',
    adapterNote: '实验接口',
    language: 'ST / Ladder',
    capabilities: [
      ['程序编译', '演示可用', 'blue'],
      ['自动模拟', '演示可用', 'blue'],
      ['在线监控', '只读演示', 'green'],
    ],
  },
  '汇川技术': {
    software: 'AutoShop',
    softwareNote: '版本需在目标电脑复核',
    simulator: 'AutoShop 模拟模式',
    simulatorNote: '能力待实机验证',
    adapter: 'AutoShop Adapter',
    adapterNote: '技术验证中',
    language: 'ST',
    capabilities: [
      ['程序编译', '待实机验证', 'amber'],
      ['自动模拟', '人工方式', 'amber'],
      ['在线监控', '尚未接入', 'gray'],
    ],
  },
  CODESYS: {
    software: 'CODESYS Development System',
    softwareNote: 'V3.5 SP20 · 演示检测',
    simulator: 'Control Win SL',
    simulatorNote: '实验后端',
    adapter: 'CODESYS Adapter',
    adapterNote: '实验接口',
    language: 'IEC 61131-3 ST',
    capabilities: [
      ['程序编译', '演示可用', 'blue'],
      ['自动模拟', '实验能力', 'blue'],
      ['在线监控', '需配置', 'amber'],
    ],
  },
};

function LogoLockup({ compact = false }) {
  return (
    <div className={`logo-lockup ${compact ? 'is-compact' : ''}`}>
      <img className="logo-lockup__icon" src={BRAND_ICON} alt="控谱图标" />
      {!compact && (
        <div className="logo-lockup__type">
          <strong>控谱</strong>
          <span>PLC ENGINEERING AGENT</span>
        </div>
      )}
    </div>
  );
}

function Sidebar({ active, onSelect }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <LogoLockup compact />
        <span>控谱</span>
      </div>
      <nav className="sidebar__nav" aria-label="主导航">
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            className={`nav-item ${active === id ? 'is-active' : ''}`}
            key={id}
            type="button"
            onClick={() => onSelect(id, label)}
            aria-current={active === id ? 'page' : undefined}
          >
            <span className="nav-item__icon">
              <Icon size={23} weight={active === id ? 'duotone' : 'regular'} />
            </span>
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar__bottom">
        <button className={`nav-item ${active === 'settings' ? 'is-active' : ''}`} type="button" onClick={() => onSelect('settings', '系统设置')} aria-current={active === 'settings' ? 'page' : undefined}>
          <span className="nav-item__icon"><GearSix size={23} /></span>
          <span>系统设置</span>
        </button>
        <div className="sidebar__version">KONGPU · 0.1</div>
      </div>
    </aside>
  );
}

function Header({ onToast, onSettings }) {
  const [menu, setMenu] = useState(null);

  const toggleMenu = (name) => setMenu((current) => (current === name ? null : name));

  return (
    <header className="topbar">
      <LogoLockup />
      <div className="topbar__actions">
        <button className="icon-button has-dot" type="button" aria-label="通知" onClick={() => toggleMenu('alerts')}>
          <Bell size={20} />
        </button>
        <button className="icon-button" type="button" aria-label="帮助" onClick={() => onToast('帮助中心将在后续版本接入工程知识库。')}>
          <Question size={20} />
        </button>
        <button className="icon-button" type="button" aria-label="设置" onClick={onSettings}>
          <GearSix size={20} />
        </button>
        <button className="user-button" type="button" onClick={() => toggleMenu('user')}>
          <span className="user-button__avatar"><UserCircle size={24} weight="duotone" /></span>
          <span className="user-button__copy"><strong>陈工程师</strong><small>项目管理员</small></span>
          <CaretDown size={14} />
        </button>
        {menu === 'alerts' && (
          <div className="popover popover--alerts">
            <div className="popover__heading"><strong>工程通知</strong><span>2 条未读</span></div>
            <button type="button" onClick={() => onToast('已定位到阻塞项：I/O 地址冲突。')}>
              <WarningCircle size={18} weight="fill" />
              <span><strong>2 项规格校验待处理</strong><small>托盘举升检测站 · 8 分钟前</small></span>
            </button>
            <button type="button" onClick={() => onToast('编译记录将在程序工程页展开。')}>
              <CheckCircle size={18} weight="fill" />
              <span><strong>FX5U 工程编译通过</strong><small>电机转子压装线 · 昨天</small></span>
            </button>
          </div>
        )}
        {menu === 'user' && (
          <div className="popover popover--user">
            <button type="button" onClick={() => onToast('个人设置暂未开放。')}>个人设置</button>
            <button type="button" onClick={() => onToast('当前为本机演示环境，无需退出。')}>退出登录</button>
          </div>
        )}
      </div>
    </header>
  );
}

function ProjectStage({ progress }) {
  const activeIndex = progress >= 85 ? 3 : progress >= 70 ? 2 : progress >= 60 ? 1 : 0;
  return (
    <div className="stage-track" aria-label="项目阶段">
      {stageLabels.map((label, index) => (
        <div className={`stage ${index < activeIndex ? 'is-done' : ''} ${index === activeIndex ? 'is-current' : ''}`} key={label}>
          <div className="stage__rail"><span>{index < activeIndex ? <Check size={13} weight="bold" /> : index + 1}</span></div>
          <strong>{label}</strong>
          <small>{index === activeIndex ? (index === 0 ? '规格审阅中' : '当前阶段') : index < activeIndex ? '已完成' : '待开始'}</small>
        </div>
      ))}
    </div>
  );
}

function Stat({ icon: Icon, label, value, note, tone = 'blue' }) {
  return (
    <div className="stat">
      <span className={`stat__icon tone-${tone}`}><Icon size={19} weight="duotone" /></span>
      <div><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
    </div>
  );
}

function ActiveProject({ project, onToast, onContinue }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <section className="active-card">
      <div className="active-card__header">
        <div className="project-identity">
          <div className="project-identity__mark"><Cube size={30} weight="duotone" /></div>
          <div>
            <div className="eyebrow"><span className="live-dot" /> 当前项目</div>
            <h2>{project.name}</h2>
            <p><span>{project.id}</span><i />{project.model}</p>
          </div>
        </div>
        <div className="active-card__actions">
          <button className="button button--primary" type="button" onClick={onContinue}>
            继续项目 <ArrowRight size={17} weight="bold" />
          </button>
          <div className="menu-anchor">
            <button className="button button--icon" type="button" aria-label="项目更多操作" onClick={() => setMenuOpen((open) => !open)}><DotsThree size={22} weight="bold" /></button>
            {menuOpen && (
              <div className="mini-menu">
                <button type="button" onClick={() => onToast('项目概览已在当前工作台展示。')}>查看项目概览</button>
                <button type="button" onClick={() => onToast('工程导出将在程序验证流程完成后开放。')}>导出工程包</button>
                <button type="button" onClick={() => onToast('已复制项目编号。')}>复制项目编号</button>
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="active-card__stage">
        <ProjectStage progress={project.progress} />
      </div>
      <div className="active-card__footer">
        <div className="metadata">
          <span><GitBranch size={15} /> {project.branch}</span>
          <span><CodeBlock size={15} /> 规格 {project.version}</span>
          <span><Clock size={15} /> 更新于 {project.updated}</span>
        </div>
        <div className="review-note"><ShieldCheck size={17} weight="duotone" /> 修改均由版本记录保护</div>
      </div>
    </section>
  );
}

function RecentProjects({ items, selectedId, onSelect, onToast, onAllProjects }) {
  const [query, setQuery] = useState('');
  const [filterOpen, setFilterOpen] = useState(false);
  const [filter, setFilter] = useState('全部状态');
  const filtered = items.filter((project) => {
    const matchesQuery = `${project.name}${project.id}${project.model}`.toLowerCase().includes(query.toLowerCase());
    const matchesFilter = filter === '全部状态' || project.status === filter;
    return matchesQuery && matchesFilter;
  });

  return (
    <section className="panel recent-panel">
      <div className="panel__header">
        <div><h3>最近项目</h3><p>继续处理近期的 PLC 工程</p></div>
        <div className="table-tools">
          <label className="search-box">
            <MagnifyingGlass size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目" aria-label="搜索项目" />
            {query && <button type="button" aria-label="清除搜索" onClick={() => setQuery('')}><X size={14} /></button>}
          </label>
          <div className="menu-anchor">
            <button className={`button button--soft ${filter !== '全部状态' ? 'is-filtered' : ''}`} type="button" onClick={() => setFilterOpen((open) => !open)}><Funnel size={16} /> {filter}</button>
            {filterOpen && (
              <div className="mini-menu mini-menu--filter">
                {['全部状态', '规格审阅', '编译验证', '在线调试', '已归档'].map((item) => (
                  <button type="button" className={filter === item ? 'is-selected' : ''} key={item} onClick={() => { setFilter(item); setFilterOpen(false); }}>{item}{filter === item && <Check size={14} />}</button>
                ))}
              </div>
            )}
          </div>
          <button className="button button--text" type="button" onClick={onAllProjects}>全部项目 <ArrowRight size={15} /></button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>项目</th><th>PLC 型号</th><th>当前阶段</th><th>进度</th><th>最近更新</th><th><span className="sr-only">操作</span></th></tr></thead>
          <tbody>
            {filtered.map((project) => (
              <tr className={selectedId === project.id ? 'is-selected' : ''} key={project.id} onClick={() => onSelect(project.id)}>
                <td><strong>{project.name}</strong><small>{project.id}</small></td>
                <td>{project.model}</td>
                <td><span className={`status status--${project.statusTone}`}>{project.status}</span></td>
                <td><div className="progress"><span><i style={{ width: `${project.progress}%` }} /></span><b>{project.progress}%</b></div></td>
                <td>{project.updated}</td>
                <td><button className="row-action" type="button" aria-label={`打开${project.name}`} onClick={(event) => { event.stopPropagation(); onSelect(project.id); onToast(`已切换当前项目：${project.name}`); }}><ArrowSquareOut size={18} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <div className="empty-state">没有符合条件的项目</div>}
      </div>
    </section>
  );
}

function EnvironmentPanel({ onToast }) {
  const [refreshing, setRefreshing] = useState(false);
  const [connected, setConnected] = useState(false);
  const [checkedAt, setCheckedAt] = useState('09:40');

  const refresh = () => {
    setRefreshing(true);
    window.setTimeout(() => {
      setCheckedAt(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }));
      setRefreshing(false);
      onToast('本机工程环境检查完成，所有必需组件均可用。');
    }, 650);
  };

  return (
    <aside className="environment panel">
      <div className="panel__header environment__heading">
        <div><h3>本机环境</h3><p>厂商软件与连接状态</p></div>
        <button className="icon-button icon-button--small" type="button" onClick={refresh} aria-label="刷新环境" disabled={refreshing}>
          {refreshing ? <CircleNotch className="spin" size={17} /> : <ArrowsClockwise size={17} />}
        </button>
      </div>
      <div className="environment__body">
        <div className="environment__group">
          <div className="group-label">工程软件</div>
          <div className="software-row">
            <span className="software-icon"><Desktop size={21} weight="duotone" /></span>
            <div><strong>GX Works3</strong><small>v1.110W · 已安装</small></div>
            <button type="button" onClick={() => onToast('已调用 GX Works3 连接适配器（演示）。')}>打开</button>
          </div>
          <div className="software-row">
            <span className="software-icon"><Cpu size={21} weight="duotone" /></span>
            <div><strong>GX Simulator3</strong><small>v1.041B · 可用</small></div>
            <button type="button" onClick={() => onToast('已调用 GX Simulator3 模拟器适配器（演示）。')}>打开</button>
          </div>
        </div>
        <div className="environment__group">
          <div className="group-label">PLC 连接</div>
          <div className={`connection-card ${connected ? 'is-connected' : ''}`}>
            <span className="connection-card__icon">{connected ? <Plugs size={23} weight="duotone" /> : <WifiSlash size={23} />}</span>
            <div><strong>{connected ? '只读监控已连接' : '未连接设备'}</strong><small>{connected ? '192.168.1.10 · FX5U' : '选择接口后建立安全连接'}</small></div>
          </div>
          <button className={`button button--wide ${connected ? 'button--soft' : 'button--outline'}`} type="button" onClick={() => { setConnected((value) => !value); onToast(connected ? '已断开 PLC 演示连接。' : '已建立只读监控演示连接；不会向 PLC 写入程序。'); }}>
            <Plugs size={17} /> {connected ? '断开连接' : '连接 PLC'}
          </button>
        </div>
        <div className="environment__group environment__checks">
          <div className="group-label">环境检查</div>
          {['MELSEC 通信驱动', '.NET 8 Runtime', '工程目录写入权限', '本地防火墙规则'].map((label) => (
            <div className="check-row" key={label}><CheckCircle size={17} weight="fill" /><span>{label}</span><small>正常</small></div>
          ))}
        </div>
      </div>
      <div className="environment__footer"><span><span className="status-pulse" /> 环境就绪</span><small>检查于 {checkedAt}</small></div>
    </aside>
  );
}

function CapabilityRow({ label, value, tone }) {
  return (
    <div className="capability-row">
      <span>{label}</span>
      <strong className={`setup-status setup-status--${tone}`}>{value}</strong>
    </div>
  );
}

function NewProjectPage({ onBack, onCreate, onToast }) {
  const [name, setName] = useState('');
  const [customer, setCustomer] = useState('');
  const [brand, setBrand] = useState('三菱电机');
  const [series, setSeries] = useState('MELSEC iQ-F');
  const [model, setModel] = useState('FX5U-64MT/ES');
  const [scanning, setScanning] = useState(false);
  const [checkedAt, setCheckedAt] = useState('今天 09:40');
  const [draftSaved, setDraftSaved] = useState(false);
  const seriesOptions = Object.keys(targetCatalog[brand]);
  const modelOptions = targetCatalog[brand][series];
  const profile = environmentProfiles[brand];
  const canCreate = name.trim().length > 1;

  const selectBrand = (nextBrand) => {
    const nextSeries = Object.keys(targetCatalog[nextBrand])[0];
    setBrand(nextBrand);
    setSeries(nextSeries);
    setModel(targetCatalog[nextBrand][nextSeries][0]);
    setDraftSaved(false);
  };

  const selectSeries = (nextSeries) => {
    setSeries(nextSeries);
    setModel(targetCatalog[brand][nextSeries][0]);
    setDraftSaved(false);
  };

  const rescan = () => {
    setScanning(true);
    window.setTimeout(() => {
      setScanning(false);
      setCheckedAt(`今天 ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`);
      onToast(`已按 ${model} 重新完成演示环境匹配。`);
    }, 750);
  };

  return (
    <main className="setup-page">
      <div className="setup-page__heading">
        <div>
          <button className="back-link" type="button" onClick={onBack}><ArrowLeft size={16} /> 返回工作台</button>
          <div className="page-heading__kicker">PROJECT SETUP / 01</div>
          <h1>新建设备项目</h1>
          <p>确定 PLC 目标并核对本机工程能力，随后进入设备资料准备。</p>
        </div>
        <div className="setup-progress" aria-label="创建项目步骤">
          <span className="is-current"><b>1</b>目标与环境</span>
          <i />
          <span><b>2</b>设备资料</span>
          <i />
          <span><b>3</b>规格审阅</span>
        </div>
      </div>

      <div className="setup-demo-banner">
        <ShieldCheck size={19} weight="duotone" />
        <span><strong>演示数据</strong> 本页检测结果用于验证产品流程，不代表这台电脑已安装厂商软件或真实 Adapter 已接通。</span>
      </div>

      <div className="setup-grid">
        <section className="panel setup-form">
          <div className="panel__header"><div><h3>项目与控制器</h3><p>必填项用于生成项目目标和兼容能力清单</p></div><span className="required-note">* 必填</span></div>
          <div className="setup-form__body">
            <div className="setup-section">
              <div className="setup-section__title"><span>01</span><div><strong>基本信息</strong><small>用于项目列表、版本和交付包</small></div></div>
              <div className="setup-fields">
                <label className="form-field form-field--wide"><span>项目名称 *</span><input autoFocus value={name} onChange={(event) => { setName(event.target.value); setDraftSaved(false); }} placeholder="例如：转盘装配检测站" /></label>
                <label className="form-field form-field--wide"><span>客户代号 <small>选填</small></span><input value={customer} onChange={(event) => { setCustomer(event.target.value); setDraftSaved(false); }} placeholder="仅用于内部识别" /></label>
              </div>
            </div>
            <div className="setup-section">
              <div className="setup-section__title"><span>02</span><div><strong>目标 PLC</strong><small>系统自动匹配软件、Adapter 与能力</small></div></div>
              <div className="setup-fields">
                <label className="form-field"><span>PLC 厂商 *</span><select value={brand} onChange={(event) => selectBrand(event.target.value)}>{Object.keys(targetCatalog).map((item) => <option key={item}>{item}</option>)}</select></label>
                <label className="form-field"><span>系列 *</span><select value={series} onChange={(event) => selectSeries(event.target.value)}>{seriesOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
                <label className="form-field form-field--wide"><span>型号 *</span><select value={model} onChange={(event) => { setModel(event.target.value); setDraftSaved(false); }}>{modelOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
              </div>
            </div>
            <div className="target-summary">
              <div><span>目标控制器</span><strong>{brand} · {model}</strong></div>
              <div><span>程序语言</span><strong>{profile.language}</strong></div>
              <div><span>自动匹配</span><strong>{profile.adapter}</strong></div>
            </div>
          </div>
        </section>

        <aside className="panel setup-environment">
          <div className="panel__header">
            <div><h3>本机环境匹配</h3><p>{checkedAt} · 根据目标自动检测</p></div>
            <button className="button button--soft" type="button" onClick={rescan} disabled={scanning}>{scanning ? <CircleNotch className="spin" size={16} /> : <ArrowsClockwise size={16} />}重新检查</button>
          </div>
          <div className="setup-environment__body">
            <div className="environment-match">
              <span className="software-icon"><Desktop size={21} weight="duotone" /></span>
              <div><small>工程软件</small><strong>{profile.software}</strong><span>{profile.softwareNote}</span></div>
              <CheckCircle size={18} weight="fill" />
            </div>
            <div className="environment-match">
              <span className="software-icon"><Cpu size={21} weight="duotone" /></span>
              <div><small>模拟后端</small><strong>{profile.simulator}</strong><span>{profile.simulatorNote}</span></div>
              <CheckCircle size={18} weight="fill" />
            </div>
            <div className="environment-match">
              <span className="software-icon"><Plugs size={21} weight="duotone" /></span>
              <div><small>本地 Adapter</small><strong>{profile.adapter}</strong><span>{profile.adapterNote}</span></div>
              <WarningCircle size={18} weight="fill" />
            </div>
            <div className="capability-list">
              <div className="group-label">项目能力</div>
              {profile.capabilities.map(([label, value, tone]) => <CapabilityRow key={label} label={label} value={value} tone={tone} />)}
            </div>
            <div className="safety-boundary"><ShieldCheck size={20} weight="duotone" /><span><strong>工程安全边界</strong>允许在环境缺失时继续准备资料；真实 PLC 下载、RUN/STOP 和强制输出在首版中始终禁用。</span></div>
          </div>
        </aside>
      </div>

      <div className="setup-actions">
        <span>{draftSaved ? <><CheckCircle size={16} weight="fill" /> 草稿已保存于当前演示会话</> : '项目信息尚未保存'}</span>
        <div>
          <button className="button button--soft" type="button" onClick={onBack}>取消</button>
          <button className="button button--outline" type="button" onClick={() => { setDraftSaved(true); onToast('项目草稿已保存在当前演示会话。'); }}>保存草稿</button>
          <button className="button button--primary" type="button" disabled={!canCreate} onClick={() => onCreate({ name: name.trim(), customer: customer.trim(), brand, series, model })}>创建并继续 <ArrowRight size={16} weight="bold" /></button>
        </div>
      </div>
    </main>
  );
}

function SectionHeading({ kicker, title, description, action }) {
  return (
    <div className="page-heading hub-heading">
      <div><div className="page-heading__kicker">{kicker}</div><h1>{title}</h1><p>{description}</p></div>
      {action}
    </div>
  );
}

function ProjectsPage({ items, selectedId, onSelect, navigate }) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('全部');
  const filtered = items.filter((project) => {
    const matchesQuery = `${project.name}${project.id}${project.model}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (status === '全部' || project.status === status);
  });
  const openProject = (project) => {
    onSelect(project.id);
    navigate(project.progress < 20 ? 'p03' : project.progress < 65 ? 'p05' : project.progress < 85 ? 'p07' : 'p10');
  };
  return (
    <main className="hub-page">
      <SectionHeading kicker="PROJECT PORTFOLIO" title="项目管理" description="管理全部 PLC 工程、当前阶段、版本与阻断事项。" action={<button className="button button--primary button--new" type="button" onClick={() => navigate('new-project')}><Plus size={18} /> 新建设备项目</button>} />
      <section className="hub-metrics">
        <Stat icon={FolderSimple} label="全部项目" value={String(items.length)} note="本机演示项目" />
        <Stat icon={Pulse} label="进行中" value={String(items.filter((item) => item.progress < 100).length)} note="覆盖完整工程流程" tone="cyan" />
        <Stat icon={WarningCircle} label="阻断项" value={String(items.reduce((sum, item) => sum + item.blockers, 0))} note="需要人工确认" tone="red" />
        <Stat icon={GitBranch} label="已发布" value="2" note="Release 可追踪" tone="green" />
      </section>
      <section className="panel hub-table">
        <div className="panel__header"><div><h3>项目资产</h3><p>点击项目后可进入其当前工程阶段</p></div><div className="table-tools"><label className="search-box hub-search"><MagnifyingGlass size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目、型号" /></label><select className="hub-select" value={status} onChange={(event) => setStatus(event.target.value)}>{['全部', '资料准备', '规格审阅', '编译验证', '在线调试', '已归档'].map((item) => <option key={item}>{item}</option>)}</select></div></div>
        <div className="project-cards">{filtered.map((project) => <article className={`project-card ${selectedId === project.id ? 'is-selected' : ''}`} key={project.id}><button className="project-card__main" type="button" onClick={() => onSelect(project.id)}><span className="project-card__mark"><Cube size={24} weight="duotone" /></span><span><strong>{project.name}</strong><small>{project.id} · {project.model}</small></span><span className={`status status--${project.statusTone}`}>{project.status}</span></button><div className="project-card__meta"><span><GitBranch size={14} /> {project.branch}</span><span>{project.version}</span><span>更新于 {project.updated}</span><span>{project.blockers} 个阻断项</span></div><div className="project-card__footer"><div className="progress"><span><i style={{ width: `${project.progress}%` }} /></span><b>{project.progress}%</b></div><button className="button button--soft" type="button" onClick={() => openProject(project)}>打开项目 <ArrowRight size={15} /></button></div></article>)}</div>
        {filtered.length === 0 && <div className="empty-state">没有符合条件的项目</div>}
      </section>
    </main>
  );
}

const deviceAssets = [
  ['PLC 控制器', '三菱 FX5U-64MT/ES', 'MELSEC iQ-F', '已验证模板', 'green'],
  ['PLC 控制器', '汇川 H5U-1614MTD-A8', 'H5U 系列', '能力待验证', 'amber'],
  ['伺服系统', 'MR-J5-70G', 'Ethernet 运动轴', '12 个项目引用', 'blue'],
  ['气动元件', '举升气缸组件', '双电控 · 双到位', '标准机构', 'blue'],
  ['传感器', '托盘到位光电', 'PNP · 24 VDC', '标准元件', 'green'],
  ['功能块', 'FB_AxisHandshake', 'ST · v1.4', '已审阅', 'violet'],
];

function DeviceLibraryPage({ toast }) {
  const [category, setCategory] = useState('全部资产');
  const [query, setQuery] = useState('');
  const filtered = deviceAssets.filter((item) => (category === '全部资产' || item[0] === category) && item.join('').toLowerCase().includes(query.toLowerCase()));
  return (
    <main className="hub-page">
      <SectionHeading kicker="ENGINEERING ASSET LIBRARY" title="设备库" description="统一管理 PLC、机构、元件和可复用功能块，不再与系统设置混用。" action={<button className="button button--primary" type="button" onClick={() => toast('已打开新增设备资产演示表单。')}><Plus size={17} /> 新增设备资产</button>} />
      <div className="library-layout"><aside className="panel library-filter"><div className="panel__header"><div><h3>资产分类</h3><p>按工程语义浏览</p></div></div>{['全部资产', 'PLC 控制器', '伺服系统', '气动元件', '传感器', '功能块'].map((item) => <button className={category === item ? 'is-active' : ''} type="button" key={item} onClick={() => setCategory(item)}><HardDrives size={17} /><span>{item}</span><small>{item === '全部资产' ? deviceAssets.length : deviceAssets.filter((asset) => asset[0] === item).length}</small></button>)}</aside><section className="panel library-content"><div className="panel__header"><div><h3>{category}</h3><p>演示资产只用于验证信息架构</p></div><label className="search-box hub-search"><MagnifyingGlass size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索型号或名称" /></label></div><div className="asset-grid">{filtered.map(([type, name, detail, statusText, tone]) => <button type="button" className="asset-card" key={name} onClick={() => toast(`已打开设备资产：${name}`)}><span className="asset-card__icon"><Cpu size={23} weight="duotone" /></span><span><small>{type}</small><strong>{name}</strong><em>{detail}</em></span><span className={`flow-status flow-status--${tone}`}>{statusText}</span><ArrowRight size={16} /></button>)}</div></section></div>
    </main>
  );
}

const documentAssets = [
  ['MachineSpec_v0.3.xlsx', '项目规格', 'Excel', '今天 10:05', '已锁定'],
  ['Compile_Report_a84c2e1.pdf', '编译报告', 'PDF', '今天 10:42', '编译通过'],
  ['Simulation_Report_v0.8.pdf', '模拟报告', 'PDF', '今天 10:38', '21 项通过'],
  ['Release_v0.8_MANIFEST.json', '交付清单', 'JSON', '今天 10:44', 'Release v0.8'],
  ['FX5U_User_Manual.pdf', '厂商手册', 'PDF', '08-22 15:20', '本机资料'],
  ['现场调试记录_014.md', '现场证据', 'Markdown', '08-26 15:03', '只读监控'],
];

function DocumentsPage({ toast }) {
  const [tab, setTab] = useState('全部资料');
  const visible = tab === '全部资料' ? documentAssets : documentAssets.filter((item) => item[1] === tab);
  return (
    <main className="hub-page">
      <SectionHeading kicker="PROJECT KNOWLEDGE & ARTIFACTS" title="文档资料" description="集中查看项目规格、验证报告、交付包、厂商手册和现场证据。" action={<button className="button button--primary" type="button" onClick={() => toast('文档上传入口已在演示中打开。')}><Plus size={17} /> 添加资料</button>} />
      <div className="document-summary"><section><FileText size={22} /><span><strong>{documentAssets.length}</strong><small>项目资料</small></span></section><section><ShieldCheck size={22} /><span><strong>4</strong><small>版本受保护</small></span></section><section><Database size={22} /><span><strong>18.6 MB</strong><small>本机占用</small></span></section></div>
      <section className="panel document-panel"><div className="tab-strip document-tabs">{['全部资料', '项目规格', '编译报告', '模拟报告', '交付清单', '厂商手册', '现场证据'].map((item) => <button type="button" className={tab === item ? 'is-active' : ''} key={item} onClick={() => setTab(item)}>{item}</button>)}</div><div className="document-list"><div className="document-list__head"><span>文件名</span><span>类型</span><span>格式</span><span>最近更新</span><span>状态</span><span>操作</span></div>{visible.map(([name, type, format, updated, state]) => <div className="document-row" key={name}><span><FileText size={18} /><strong>{name}</strong></span><span>{type}</span><span>{format}</span><span>{updated}</span><span>{state}</span><button type="button" onClick={() => toast(`已打开资料预览：${name}`)}>预览 <ArrowRight size={13} /></button></div>)}</div></section>
    </main>
  );
}

function OverviewPage({ kind, navigate }) {
  const config = {
    specs: { kicker: 'MACHINESPEC MANAGEMENT', title: '规格管理', description: '从模板准备、Excel 导入校验到多视图审阅，形成可锁定的 MachineSpec。', actions: [['p03', '模板中心', '下载项目专属模板并查看字段说明'], ['p04', '导入与校验', '上传 Excel 并处理阻断问题'], ['p05', '规格审阅', '确认流程、节拍、信号和互锁视图']] },
    program: { kicker: 'PROGRAM ENGINEERING', title: '程序工程', description: '管理程序生成、发布评审和工程交付，所有修改均进入版本记录。', actions: [['p06', '程序工作区', '审阅 ST、变量、功能块和需求追踪'], ['p09', '发布评审', '核对编译、模拟和风险后创建 Release'], ['p11', '版本中心', '比较分支、Commit、Release 与工件']] },
    debug: { kicker: 'VALIDATION & COMMISSIONING', title: '调试工具', description: '编译、模拟与在线只读监控各自独立，避免混淆真实设备能力。', actions: [['p07', '编译验证', '调用厂商工程副本并处理诊断'], ['p08', '模拟测试', '在演示后端运行 TestSpec'], ['p10', '在线只读监控', '人工下载后读取 PLC 状态与 Trace']] },
  }[kind];
  return <main className="hub-page"><SectionHeading kicker={config.kicker} title={config.title} description={config.description} /><div className="overview-grid">{config.actions.map(([target, title, desc], index) => <button type="button" key={target} onClick={() => navigate(target)}><span className="overview-grid__number">{String(index + 1).padStart(2, '0')}</span><span><strong>{title}</strong><small>{desc}</small></span><ArrowRight size={19} /></button>)}</div><section className="setup-demo-banner"><ShieldCheck size={19} /><span><strong>演示边界</strong> 当前为可点击产品 Demo；厂商编译器、模拟器、模型、数据库和真实 PLC 尚未接入。</span></section></main>;
}

function Toast({ message, onClose }) {
  useEffect(() => {
    const timer = window.setTimeout(onClose, 3600);
    return () => window.clearTimeout(timer);
  }, [message, onClose]);
  return <div className="toast" role="status"><CheckCircle size={19} weight="fill" /><span>{message}</span><button type="button" aria-label="关闭提示" onClick={onClose}><X size={15} /></button></div>;
}

export function App() {
  const [page, setPage] = useState('workspace');
  const [activeNav, setActiveNav] = useState('workspace');
  const [projectItems, setProjectItems] = useState(projects);
  const [selectedProjectId, setSelectedProjectId] = useState(projects[0].id);
  const [toast, setToast] = useState('');
  const activeProject = useMemo(() => projectItems.find((project) => project.id === selectedProjectId) ?? projectItems[0], [projectItems, selectedProjectId]);

  const showToast = (message) => setToast(message);
  const navigate = (nextPage) => {
    setPage(nextPage);
    const topLevel = { workspace: 'workspace', projects: 'projects', 'specs-overview': 'specs', 'program-overview': 'program', 'debug-overview': 'debug', devices: 'devices', documents: 'documents' };
    if (topLevel[nextPage]) {
      setActiveNav(topLevel[nextPage]);
      return;
    }
    if (nextPage === 'new-project') {
      setActiveNav('projects');
      return;
    }
    const destination = workflowPages.find((item) => item.id === nextPage);
    setActiveNav(destination?.nav ?? 'workspace');
  };
  const selectNav = (id, label) => {
    const destinations = { workspace: 'workspace', projects: 'projects', specs: 'specs-overview', program: 'program-overview', debug: 'debug-overview', devices: 'devices', documents: 'documents', versions: 'p11', settings: 'p12' };
    navigate(destinations[id] ?? 'workspace');
  };

  return (
    <div className="app-shell">
      <Sidebar active={activeNav} onSelect={selectNav} />
      <div className="app-frame">
        <Header onToast={showToast} onSettings={() => navigate('p12')} />
        {page === 'workspace' ? <div className="workspace">
          <main className="main-content">
            <div className="page-heading">
              <div><div className="page-heading__kicker">PLC ENGINEERING WORKSPACE</div><h1>工程工作台</h1><p>从设备规格到编译验证，集中管理每一个 PLC 工程。</p></div>
              <button className="button button--primary button--new" type="button" onClick={() => navigate('new-project')}><Plus size={18} weight="bold" /> 新建设备项目</button>
            </div>
            <ActiveProject project={activeProject} onToast={showToast} onContinue={() => navigate(activeProject.progress < 20 ? 'p03' : 'p05')} />
            <section className="stats-grid" aria-label="当前项目统计">
              <Stat icon={ListChecks} label="规格条目" value={activeProject.progress < 20 ? "0" : "12"} note={activeProject.progress < 20 ? "等待设备资料" : "已确认 9 项"} />
              <Stat icon={Database} label="I/O 点数" value={activeProject.io} note="点" tone="cyan" />
              <Stat icon={CodeBlock} label="程序块" value={String(activeProject.blocks)} note={activeProject.blocks ? "含 6 个功能块" : "尚未生成"} tone="violet" />
              <Stat icon={ClipboardText} label="待办事项" value={String(activeProject.tasks)} note="本周需处理" tone="amber" />
              <Stat icon={WarningCircle} label="阻塞项" value={String(activeProject.blockers)} note={activeProject.blockers ? '需人工确认' : '当前无阻塞'} tone={activeProject.blockers ? 'red' : 'green'} />
            </section>
            <RecentProjects items={projectItems} selectedId={selectedProjectId} onSelect={setSelectedProjectId} onToast={showToast} onAllProjects={() => navigate('projects')} />
          </main>
          <EnvironmentPanel onToast={showToast} />
        </div> : page === 'projects' ? <ProjectsPage items={projectItems} selectedId={selectedProjectId} onSelect={setSelectedProjectId} navigate={navigate} /> : page === 'devices' ? <DeviceLibraryPage toast={showToast} /> : page === 'documents' ? <DocumentsPage toast={showToast} /> : ['specs-overview', 'program-overview', 'debug-overview'].includes(page) ? <OverviewPage kind={page.replace('-overview', '')} navigate={navigate} /> : page === 'new-project' ? <NewProjectPage onBack={() => navigate('projects')} onToast={showToast} onCreate={({ name, brand, model }) => {
          const created = { id: `KP-2608-${String(projectItems.length + 15).padStart(3, '0')}`, name, model: `${brand} ${model}`, status: '资料准备', statusTone: 'blue', progress: 12, updated: '刚刚', branch: 'main', version: 'v0.1', io: '0 / 0', blocks: 0, tasks: 1, blockers: 0 };
          setProjectItems((items) => [created, ...items]);
          setSelectedProjectId(created.id);
          navigate('p03');
          showToast(`项目“${name}”已创建，已进入 MachineSpec 模板中心。`);
        }} /> : <EngineeringPage page={page} project={activeProject} navigate={navigate} toast={showToast} />}
        <footer className="statusbar"><span><span className="status-pulse" /> 控谱服务运行正常</span><span>{page === 'workspace' ? '本地演示环境 · 云端模型已连接 · 自动保存已开启' : page === 'new-project' ? 'P02 项目与目标环境 · 演示数据' : `${page.toUpperCase()} 工程流程 · 演示数据`}</span></footer>
      </div>
      {toast && <Toast message={toast} onClose={() => setToast('')} />}
    </div>
  );
}
