import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Checkbox, Input, Select, Switch, Table, Tabs, Upload } from "antd";
import type { ColumnsType } from "antd/es/table";
import { api } from "./api";
import type {
  Article,
  AuditLog,
  ChannelAccount,
  EvidencePackage,
  Job,
  Material,
  Model,
  Publication,
  Skill,
  Source,
  Strategy,
  Theme,
  Topic,
  User,
} from "./api";
import { EmptyState, Icon, type IconName, StatusPill } from "./design";

export type PageKey = "dashboard" | "materials" | "topics" | "articles" | "review" | "settings";
export type SettingsTab = "strategies" | "sources" | "models" | "skills" | "themes" | "channels" | "users" | "audit";
export type ReviewTab = "pending" | "drafts" | "publications";

export const MAIN_NAV: Array<{ key: PageKey; label: string; icon: IconName }> = [
  { key: "dashboard", label: "工作台", icon: "home" },
  { key: "materials", label: "素材池", icon: "image" },
  { key: "topics", label: "选题与创作", icon: "topic" },
  { key: "articles", label: "文章创作", icon: "article" },
  { key: "review", label: "审核与发布", icon: "review" },
  { key: "settings", label: "策略与设置", icon: "settings" },
];

export const SETTINGS_TABS: Array<{ key: SettingsTab; label: string }> = [
  { key: "strategies", label: "内容策略" },
  { key: "sources", label: "信息源" },
  { key: "models", label: "模型中心" },
  { key: "skills", label: "Skill 中心" },
  { key: "themes", label: "排版主题" },
  { key: "channels", label: "渠道账号" },
  { key: "users", label: "用户与权限" },
  { key: "audit", label: "系统日志" },
];

const JOB_STATUS: Record<string, { label: string; tone: "blue" | "green" | "orange" | "purple" | "red" | "neutral" }> = {
  queued: { label: "等待中", tone: "orange" },
  running: { label: "运行中", tone: "blue" },
  waiting_review: { label: "待审核", tone: "orange" },
  succeeded: { label: "已完成", tone: "green" },
  canceled: { label: "已取消", tone: "neutral" },
  failed_retryable: { label: "失败", tone: "red" },
  failed_terminal: { label: "失败", tone: "red" },
};

const ARTICLE_STATUS: Record<string, { label: string; tone: "blue" | "green" | "orange" | "purple" | "red" | "neutral" }> = {
  waiting_review: { label: "待审核", tone: "blue" },
  pending: { label: "待审核", tone: "blue" },
  approved: { label: "已通过", tone: "green" },
  auto_approved: { label: "已通过", tone: "green" },
  changes_requested: { label: "退回修改", tone: "red" },
  rejected: { label: "已拒绝", tone: "red" },
  drafted: { label: "待建草稿", tone: "orange" },
  wechat_draft: { label: "微信草稿", tone: "purple" },
  publishing: { label: "发布中", tone: "blue" },
  published: { label: "已发布", tone: "green" },
  edited: { label: "已编辑", tone: "orange" },
};

const MATERIAL_STATUS: Record<Material["triage_status"], { label: string; tone: "blue" | "green" | "purple" | "neutral" }> = {
  inbox: { label: "待筛选", tone: "blue" },
  selected: { label: "已选为依据", tone: "green" },
  ignored: { label: "已忽略", tone: "neutral" },
  used: { label: "正在创作", tone: "purple" },
};

const TOPIC_STATUS: Record<string, { label: string; tone: "blue" | "green" | "orange" | "purple" | "red" | "neutral" }> = {
  candidate: { label: "待确认", tone: "orange" },
  accepted: { label: "已确认", tone: "blue" },
  writing: { label: "正在创作", tone: "purple" },
  rejected: { label: "已拒绝", tone: "red" },
  merged: { label: "已合并", tone: "neutral" },
  completed: { label: "已完成", tone: "green" },
};

export function formatDate(value?: string | null, includeYear = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    ...(includeYear ? { year: "numeric" as const } : {}),
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date).replace(/\//g, "-");
}

export function formatDuration(milliseconds: number) {
  if (!milliseconds) return "—";
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function PagePanel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`console-panel ${className}`}>{children}</section>;
}

function PanelTitle({ title, caption, action }: { title: string; caption?: string; action?: ReactNode }) {
  return (
    <div className="panel-heading">
      <div><h2>{title}</h2>{caption && <p>{caption}</p>}</div>
      {action}
    </div>
  );
}

export function Sidebar({
  page,
  settingsTab,
  onNavigate,
}: {
  page: PageKey;
  settingsTab: SettingsTab;
  onNavigate: (page: PageKey, settingsTab?: SettingsTab) => void;
}) {
  return (
    <aside className="console-sidebar">
      <div className="console-brand">
        <span className="brand-mark">A</span>
        <span><strong>Content Ops</strong><small>内容运营工作台</small></span>
      </div>
      <button type="button" className="sidebar-create" onClick={() => onNavigate("topics")}><Icon name="edit" size={16} />新建创作</button>
      <nav className="main-navigation" aria-label="主导航">
        {MAIN_NAV.map((item) => (
          <button key={item.key} type="button" className={page === item.key ? "is-active" : ""} onClick={() => onNavigate(item.key)}>
            <Icon name={item.icon} size={19} /><span>{item.label}</span>
            {item.key === "settings" && <Icon name="chevron" size={15} className="nav-chevron" />}
          </button>
        ))}
        {page === "settings" && (
          <div className="settings-subnav">
            {SETTINGS_TABS.map((item) => (
              <button key={item.key} type="button" className={settingsTab === item.key ? "is-active" : ""} onClick={() => onNavigate("settings", item.key)}>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        )}
      </nav>
      <div className="sidebar-bottom">
        <div className="license-card">
          <strong>企业高级版</strong>
          <span>有效期至 2026-12-31</span>
          <span>正在使用 23 / 100 任务并发</span>
          <i><b /></i>
        </div>
        <button type="button" className="help-entry"><Icon name="help" size={17} />帮助与文档</button>
      </div>
    </aside>
  );
}

export function Topbar({
  page,
  settingsTab,
  currentUser,
  notificationCount,
  onToggleSidebar,
  onSearch,
  onLogout,
}: {
  page: PageKey;
  settingsTab: SettingsTab;
  currentUser: User;
  notificationCount: number;
  onToggleSidebar: () => void;
  onSearch: (value: string) => void;
  onLogout: () => void;
}) {
  const pageName = MAIN_NAV.find((item) => item.key === page)?.label ?? "工作台";
  const settingsName = SETTINGS_TABS.find((item) => item.key === settingsTab)?.label;
  return (
    <header className="console-topbar">
      <div className="topbar-title">
        <button type="button" aria-label="展开或收起侧栏" onClick={onToggleSidebar}><Icon name="menu" size={20} /></button>
        <h1>{pageName}{page === "settings" && settingsName ? <><span>/</span>{settingsName}</> : null}</h1>
      </div>
      <div className="topbar-actions">
        <Input
          className="global-search"
          prefix={<Icon name="search" size={17} />}
          suffix={<kbd>⌘K</kbd>}
          placeholder="搜索内容、策略、任务或素材..."
          onPressEnter={(event) => onSearch(event.currentTarget.value)}
        />
        <button type="button" className="icon-button notification-button" aria-label="通知">
          <Icon name="bell" size={19} />{notificationCount > 0 && <b>{Math.min(notificationCount, 99)}</b>}
        </button>
        <button type="button" className="icon-button" aria-label="帮助"><Icon name="help" size={19} /></button>
        <button type="button" className="account-button" onClick={onLogout}>
          <span>{currentUser.email.slice(0, 1).toUpperCase()}</span>
          <strong>{currentUser.email.split("@")[0]}</strong>
          <Icon name="chevron" size={14} />
        </button>
      </div>
    </header>
  );
}

function QueueCard({
  icon,
  label,
  value,
  caption,
  tone,
  action,
}: {
  icon: IconName;
  label: string;
  value: number;
  caption: string;
  tone: string;
  action: () => void;
}) {
  return (
    <article className={`queue-card queue-card--${tone}`}>
      <div className="queue-card-main">
        <span className="queue-icon"><Icon name={icon} size={25} /></span>
        <span><small>{label}</small><strong>{value.toLocaleString()}</strong><em>条</em></span>
      </div>
      <p>{caption}</p>
      <button type="button" onClick={action}>去处理 <span>→</span></button>
    </article>
  );
}

export function DashboardPage({
  sources,
  strategies,
  materials,
  topics,
  articles,
  jobs,
  onNavigate,
  onRetryJob,
  onRefresh,
}: {
  sources: Source[];
  strategies: Strategy[];
  materials: Material[];
  topics: Topic[];
  articles: Article[];
  jobs: Job[];
  onNavigate: (page: PageKey, tab?: ReviewTab) => void;
  onRetryJob: (id: string) => void;
  onRefresh: () => void;
}) {
  const inboxMaterials = materials.filter((item) => item.triage_status === "inbox").length;
  const candidateTopics = topics.filter((item) => item.status === "candidate").length;
  const pendingArticles = articles.filter((item) => ["waiting_review", "pending", "edited"].includes(item.status)).length;
  const failedJobs = jobs.filter((item) => item.status.startsWith("failed"));
  const runningJobs = jobs.filter((item) => item.status === "running");
  const completedJobs = jobs.filter((item) => item.status === "succeeded");
  const recentJobs = jobs.slice(0, 8);
  const strategyNames = new Map(strategies.map((item) => [item.id, item.name]));
  const completionRate = jobs.length ? Math.round(completedJobs.length / jobs.length * 100) : 0;
  const chart = `conic-gradient(#42c995 0 ${completionRate}%, #ffb24a ${completionRate}% ${Math.min(100, completionRate + 7)}%, #f05b70 ${Math.min(100, completionRate + 7)}% 100%)`;

  return (
    <div className="dashboard-layout">
      <main className="dashboard-main">
        <PagePanel>
          <PanelTitle title="待处理高优先级任务" caption="以下任务需要优先处理，以保障内容生产流程顺畅运行" action={<button className="text-action" onClick={() => onNavigate("review")}>全部任务 <span>›</span></button>} />
          <div className="queue-grid">
            <QueueCard icon="folder" label="待筛选素材" value={inboxMaterials} caption={`来自 ${sources.filter((item) => item.enabled).length} 个启用信息源`} tone="blue" action={() => onNavigate("materials")} />
            <QueueCard icon="edit" label="待确认选题" value={candidateTopics} caption={`来自 ${strategies.filter((item) => item.enabled).length} 个内容策略`} tone="purple" action={() => onNavigate("topics")} />
            <QueueCard icon="article" label="待审核文章" value={pendingArticles} caption={`当前共有 ${articles.length} 篇文章`} tone="orange" action={() => onNavigate("review", "pending")} />
          </div>
        </PagePanel>

        <PagePanel>
          <PanelTitle title="运营概况" caption="数据来自当前系统真实记录" />
          <div className="metric-strip">
            {[
              ["启用信息源", sources.filter((item) => item.enabled).length, `共 ${sources.length} 个`],
              ["启用策略", strategies.filter((item) => item.enabled).length, `共 ${strategies.length} 套`],
              ["今日采集素材数", materials.length, `${inboxMaterials} 条待筛选`],
              ["今日生成文章数", articles.length, `${pendingArticles} 篇待审核`],
              ["微信草稿创建数", articles.filter((item) => item.status === "wechat_draft").length, "可进入发布区处理"],
              ["失败任务数", failedJobs.length, failedJobs.length ? "需要立即处理" : "当前运行稳定"],
            ].map(([label, value, caption]) => (
              <div className="metric-cell" key={label as string}><span>{label}</span><strong>{Number(value).toLocaleString()}</strong><small>{caption}</small></div>
            ))}
          </div>
        </PagePanel>

        <PagePanel>
          <PanelTitle title="最近任务" action={<span className="panel-actions"><button className="text-action" onClick={onRefresh}><Icon name="refresh" size={14} />刷新</button><button className="text-action" onClick={() => onNavigate("review")}>查看全部任务 ›</button></span>} />
          <Tabs size="small" items={[
            { key: "all", label: `全部任务` },
            { key: "running", label: <>运行中 <b className="tab-count">{runningJobs.length}</b></> },
            { key: "waiting", label: <>等待中 <b className="tab-count">{jobs.filter((item) => item.status === "queued").length}</b></> },
            { key: "done", label: "已完成" },
            { key: "failed", label: "已失败" },
          ]} />
          <Table
            rowKey="id"
            size="small"
            pagination={false}
            dataSource={recentJobs}
            locale={{ emptyText: <EmptyState icon="clock" title="还没有任务" description="运行一套内容策略后，任务会出现在这里。" /> }}
            columns={[
              { title: "任务名称", key: "name", render: (_, item: Job) => strategyNames.get(item.strategy_id) ?? item.id.slice(0, 8) },
              { title: "所属策略", dataIndex: "strategy_id", render: (id) => strategyNames.get(id) ?? "—" },
              { title: "当前步骤", dataIndex: "current_step", render: (value) => value || "等待调度" },
              { title: "状态", dataIndex: "status", render: (value) => { const meta = JOB_STATUS[value] ?? { label: value, tone: "neutral" as const }; return <StatusPill tone={meta.tone}>{meta.label}</StatusPill>; } },
              { title: "开始时间", dataIndex: "started_at", render: (value) => formatDate(value) },
              { title: "运行时长", dataIndex: "duration_ms", render: formatDuration },
              { title: "错误原因", dataIndex: "last_error", ellipsis: true, render: (value) => value || "—" },
              { title: "操作", key: "action", render: (_, item) => <span className="table-actions"><button onClick={() => onNavigate("review")}>查看</button>{item.status.startsWith("failed") && <button onClick={() => onRetryJob(item.id)}>重试</button>}</span> },
            ]}
          />
        </PagePanel>
      </main>
      <aside className="dashboard-rail">
        <PagePanel>
          <PanelTitle title="任务异常" action={<button className="text-action" onClick={() => onNavigate("review")}>查看全部</button>} />
          <div className="rail-list">
            {failedJobs.slice(0, 3).map((item) => <button key={item.id} onClick={() => onNavigate("review")}><i className="dot dot--red" /><span><strong>{strategyNames.get(item.strategy_id) ?? "内容任务"}</strong><small>{item.last_error || "任务执行失败"}</small></span><time>{formatDate(item.updated_at)}</time></button>)}
            {!failedJobs.length && <EmptyState icon="check" title="运行正常" description="当前没有失败任务。" />}
          </div>
        </PagePanel>
        <PagePanel>
          <PanelTitle title="今日提醒" action={<button className="text-action" onClick={() => onNavigate("dashboard")}>查看全部</button>} />
          <div className="reminder-list">
            <button onClick={() => onNavigate("review")}><Icon name="bell" /><span><strong>有 {pendingArticles} 篇待审核文章</strong><small>来自当前内容策略</small></span></button>
            <button onClick={() => onNavigate("topics")}><Icon name="edit" /><span><strong>有 {candidateTopics} 个待确认选题</strong><small>确认后可进入创作</small></span></button>
            <button onClick={() => onNavigate("materials")}><Icon name="folder" /><span><strong>有 {inboxMaterials} 条待筛选素材</strong><small>来自启用信息源</small></span></button>
          </div>
        </PagePanel>
        <PagePanel>
          <PanelTitle title="今日概览" />
          <div className="donut-wrap">
            <div className="donut" style={{ background: chart }}><span><strong>{jobs.length}</strong><small>总任务数</small></span></div>
            <div className="donut-legend">
              <span><i className="dot dot--blue" />运行中 <b>{runningJobs.length}</b></span>
              <span><i className="dot dot--orange" />等待中 <b>{jobs.filter((item) => item.status === "queued").length}</b></span>
              <span><i className="dot dot--green" />已完成 <b>{completedJobs.length}</b></span>
              <span><i className="dot dot--red" />已失败 <b>{failedJobs.length}</b></span>
            </div>
          </div>
        </PagePanel>
      </aside>
      <PagePanel className="dashboard-quick">
        <PanelTitle title="快捷操作" />
        <div className="dashboard-quick-grid">
          {[
            { title: "立即扫描信息源", caption: "手动触发信息源扫描", icon: "refresh", tone: "blue", action: () => onNavigate("materials") },
            { title: "添加信息源", caption: "接入新的内容数据源", icon: "database", tone: "purple", action: () => onNavigate("settings") },
            { title: "新建内容策略", caption: "创建新的内容生产策略", icon: "play", tone: "green", action: () => onNavigate("settings") },
            { title: "进入待审核文章", caption: "快速审核文章内容", icon: "review", tone: "orange", action: () => onNavigate("review") },
          ].map((item) => (
            <button key={item.title} type="button" onClick={item.action}><span className={`quick-square quick-square--${item.tone}`}><Icon name={item.icon as IconName} /></span><span><strong>{item.title}</strong><small>{item.caption}</small></span><b>→</b></button>
          ))}
        </div>
      </PagePanel>
    </div>
  );
}

export function MaterialsPage({
  materials,
  sources,
  selectedId,
  onSelect,
  onTriage,
  onUse,
  onScan,
  scanning,
}: {
  materials: Material[];
  sources: Source[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onTriage: (id: string, decision: "ignore" | "reopen") => void;
  onUse: (item: Material) => void;
  onScan: () => void;
  scanning: boolean;
}) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [sourceId, setSourceId] = useState<string>("all");
  const selected = materials.find((item) => item.id === selectedId) ?? null;
  const filtered = useMemo(() => materials.filter((item) => {
    if (status !== "all" && item.triage_status !== status) return false;
    if (sourceId !== "all" && item.source_id !== sourceId) return false;
    const keyword = search.trim().toLowerCase();
    return !keyword || `${item.title} ${item.content_excerpt} ${item.source_name}`.toLowerCase().includes(keyword);
  }), [materials, search, sourceId, status]);
  const counts = {
    all: materials.length,
    inbox: materials.filter((item) => item.triage_status === "inbox").length,
    selected: materials.filter((item) => item.triage_status === "selected").length,
    ignored: materials.filter((item) => item.triage_status === "ignored").length,
    used: materials.filter((item) => item.triage_status === "used").length,
  };
  return (
    <div className={`material-page ${selected ? "has-detail" : ""}`}>
      <main>
        <PagePanel>
          <div className="filter-toolbar">
            <Input prefix={<Icon name="search" size={16} />} placeholder="搜索标题和正文" value={search} onChange={(event) => setSearch(event.target.value)} />
            <label>信息源<Select value={sourceId} onChange={setSourceId} options={[{ label: "全部", value: "all" }, ...sources.map((item) => ({ label: item.name, value: item.id }))]} /></label>
            <label>素材状态<Select value={status} onChange={setStatus} options={[{ label: "全部", value: "all" }, { label: "待筛选", value: "inbox" }, { label: "已选为依据", value: "selected" }, { label: "已忽略", value: "ignored" }, { label: "正在创作", value: "used" }]} /></label>
            <Button icon={<Icon name="refresh" size={15} />} onClick={() => { setSearch(""); setStatus("all"); setSourceId("all"); }}>重置</Button>
            <Button type="primary" icon={<Icon name="refresh" size={15} />} loading={scanning} onClick={onScan}>立即扫描</Button>
          </div>
        </PagePanel>
        <PagePanel className="material-table-panel">
          <div className="material-stats">
            {[
              ["all", "全部", counts.all],
              ["inbox", "待筛选", counts.inbox],
              ["selected", "已选为依据", counts.selected],
              ["ignored", "已忽略", counts.ignored],
              ["used", "正在创作", counts.used],
            ].map(([key, label, count]) => <button type="button" key={key as string} className={status === key ? "is-active" : ""} onClick={() => setStatus(key as string)}><span>{label}</span><strong>{count}</strong></button>)}
          </div>
          <Table
            rowKey="id"
            size="small"
            dataSource={filtered}
            pagination={{ pageSize: 12, showSizeChanger: true, showTotal: (total) => `共 ${total.toLocaleString()} 条` }}
            rowClassName={(item) => item.id === selectedId ? "selected-row" : ""}
            onRow={(item) => ({ onClick: () => onSelect(item.id) })}
            locale={{ emptyText: <EmptyState icon="image" title="没有匹配素材" description="调整筛选条件，或立即扫描信息源。" /> }}
            columns={[
              { title: "标题", dataIndex: "title", width: 250, render: (value) => <strong className="table-title">{value}</strong> },
              { title: "内容摘要", dataIndex: "content_excerpt", width: 300, ellipsis: true },
              { title: "信息源名称", dataIndex: "source_name", width: 130 },
              { title: "原文地址", dataIndex: "url", width: 90, render: (value) => <a href={value} onClick={(event) => event.stopPropagation()} target="_blank" rel="noreferrer"><Icon name="external" size={15} /></a> },
              { title: "发布时间", dataIndex: "published_at", width: 120, render: (value) => formatDate(value) },
              { title: "采集时间", dataIndex: "created_at", width: 120, render: (value) => formatDate(value) },
              { title: "素材状态", dataIndex: "triage_status", width: 100, render: (value) => { const meta = MATERIAL_STATUS[value as Material["triage_status"]]; return <StatusPill tone={meta.tone}>{meta.label}</StatusPill>; } },
              { title: "操作", width: 80, render: (_, item) => <button className="table-icon-action" onClick={(event) => { event.stopPropagation(); onSelect(item.id); }}><Icon name="eye" size={15} /></button> },
            ]}
          />
        </PagePanel>
      </main>
      {selected && (
        <aside className="context-panel material-detail">
          <div className="context-title"><h2>素材详情</h2><button type="button" onClick={() => onSelect(null)}><Icon name="close" /></button></div>
          <dl>
            <dt>完整标题</dt><dd><strong>{selected.title}</strong></dd>
            <dt>来源名称</dt><dd>{selected.source_name}</dd>
            <dt>原文链接</dt><dd><a href={selected.url} target="_blank" rel="noreferrer">{selected.url}<Icon name="external" size={13} /></a></dd>
            <dt>原文发布时间</dt><dd>{formatDate(selected.published_at, true)}</dd>
            <dt>采集时间</dt><dd>{formatDate(selected.created_at, true)}</dd>
          </dl>
          <section><h3>清洗后的正文摘要</h3><p className="long-copy">{selected.content_excerpt || "当前素材没有摘要。"}</p></section>
          <section><h3>处理状态</h3><p><i className="dot dot--green" /> {MATERIAL_STATUS[selected.triage_status].label}</p><p><i className="dot dot--green" /> 内容已完成基础清洗</p></section>
          <div className="context-footer">
            <Button onClick={() => onTriage(selected.id, selected.triage_status === "ignored" ? "reopen" : "ignore")}>{selected.triage_status === "ignored" ? "重新打开" : "忽略"}</Button>
            <Button type="primary" onClick={() => onUse(selected)}>选作写作依据</Button>
            <Button onClick={() => onSelect(null)}>关闭</Button>
          </div>
        </aside>
      )}
    </div>
  );
}

export function TopicsPage({
  topics,
  strategies,
  materials,
  selectedId,
  onSelect,
  onDecision,
  onStart,
  onCreate,
  onOpenArticles,
  starting,
}: {
  topics: Topic[];
  strategies: Strategy[];
  materials: Material[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDecision: (id: string, decision: "accept" | "reject" | "merge") => void;
  onStart: (id: string) => void;
  onCreate: () => void;
  onOpenArticles: () => void;
  starting: boolean;
}) {
  const [status, setStatus] = useState("all");
  const [strategyId, setStrategyId] = useState("all");
  const selected = topics.find((item) => item.id === selectedId) ?? topics[0] ?? null;
  const strategyMap = new Map(strategies.map((item) => [item.id, item]));
  const filtered = topics.filter((item) => (status === "all" || item.status === status) && (strategyId === "all" || item.strategy_id === strategyId));
  const selectedStrategy = selected ? strategyMap.get(selected.strategy_id) : undefined;
  const config = selectedStrategy?.config ?? {};
  const stageSkills = config.skill_by_stage && typeof config.skill_by_stage === "object" ? Object.keys(config.skill_by_stage).length : 0;
  const sourceMaterials = materials.filter((item) => item.id === selected?.source_item_id || item.triage_status === "selected").slice(0, 4);
  return (
    <div className="topics-page">
      <div className="page-tabs"><button className="is-active">候选选题</button><button onClick={onOpenArticles}>文章创作</button></div>
      <div className="topics-toolbar">
        <Select value={strategyId} onChange={setStrategyId} options={[{ label: "全部策略", value: "all" }, ...strategies.map((item) => ({ label: item.name, value: item.id }))]} />
        <Select value={status} onChange={setStatus} options={[{ label: "全部状态", value: "all" }, { label: "待确认", value: "candidate" }, { label: "已确认", value: "accepted" }, { label: "正在创作", value: "writing" }, { label: "已拒绝", value: "rejected" }]} />
        <Input prefix={<Icon name="search" size={16} />} placeholder="搜索选题标题、来源或关键词" />
        <Button icon={<Icon name="refresh" size={15} />} onClick={() => { setStatus("all"); setStrategyId("all"); }}>重置</Button>
        <Button type="primary" icon={<span>＋</span>} onClick={onCreate}>新建选题</Button>
      </div>
      <div className="topic-workspace">
        <main>
          <PagePanel className="topic-list-panel">
            <Table
              rowKey="id"
              size="small"
              pagination={{ pageSize: 7, showTotal: (total) => `共 ${total} 条` }}
              dataSource={filtered}
              rowClassName={(item) => item.id === selected?.id ? "selected-row" : ""}
              onRow={(item) => ({ onClick: () => onSelect(item.id) })}
              locale={{ emptyText: <EmptyState icon="topic" title="还没有候选选题" description="从素材池选择素材，或手动创建一个选题。" /> }}
              columns={[
                { title: "选题标题", dataIndex: "title", width: 330, render: (value) => <strong className="table-title">{value}</strong> },
                { title: "写作依据", key: "source", width: 160, render: (_, item) => item.source_item_id ? "来自已选素材" : "人工创建" },
                { title: "所属策略", dataIndex: "strategy_id", width: 150, render: (id) => strategyMap.get(id)?.name ?? "—" },
                { title: "综合评分", dataIndex: "score", width: 90, render: (value) => <b>{Math.round(value || 0)}</b> },
                { title: "评分理由", dataIndex: "rationale", ellipsis: true },
                { title: "当前状态", dataIndex: "status", width: 100, render: (value) => { const meta = TOPIC_STATUS[value] ?? { label: value, tone: "neutral" as const }; return <StatusPill tone={meta.tone}>{meta.label}</StatusPill>; } },
                { title: "操作", width: 120, render: (_, item) => <span className="table-actions"><button onClick={() => onSelect(item.id)}>查看</button>{item.status === "candidate" && <button onClick={() => onDecision(item.id, "accept")}>确认</button>}</span> },
              ]}
            />
          </PagePanel>
          {selected && (
            <PagePanel className="topic-detail-card">
              <PanelTitle title={selected.title} action={<StatusPill tone={(TOPIC_STATUS[selected.status] ?? { tone: "neutral" }).tone}>{(TOPIC_STATUS[selected.status] ?? { label: selected.status }).label}</StatusPill>} />
              <div className="topic-detail-grid">
                <section>
                  <h3>原始素材（{sourceMaterials.length}）</h3>
                  <div className="source-material-list">
                    {sourceMaterials.map((item) => <article key={item.id}><Icon name="link" /><span><strong>{item.title}</strong><small>来源：{item.source_name}</small></span><b>{item.triage_status === "selected" ? "依据" : "相关"}</b></article>)}
                    {!sourceMaterials.length && <p className="muted-copy">该选题没有绑定素材。</p>}
                  </div>
                </section>
                <section className="topic-score-area">
                  <div className="topic-meta"><span><small>来源</small><strong>{selected.source_item_id ? "素材池 / 已选素材" : "人工创建"}</strong></span><span><small>策略</small><strong>{selectedStrategy?.name ?? "—"}</strong></span></div>
                  <div className="score-grid">
                    {selected.scores.length ? selected.scores.slice(0, 4).map((score) => <span key={score.id}><small>{score.dimension}</small><strong>{Math.round(score.score)}</strong><em>{score.rationale}</em></span>) : <><span><small>机会评分</small><strong>{Math.round(selected.score)}</strong><em>综合评分</em></span><span><small>时效性评分</small><strong>—</strong><em>暂无维度数据</em></span></>}
                  </div>
                  <h3>AI 评分依据</h3><p>{selected.rationale || "暂无评分说明。"}</p>
                </section>
              </div>
            </PagePanel>
          )}
        </main>
        <aside className="context-panel creation-confirm">
          <div className="context-title"><h2>开始创作确认</h2><Icon name="close" /></div>
          {!selected ? <EmptyState icon="topic" title="请选择一个选题" description="选中候选选题后，这里会展示创作组合。" /> : <>
            <p className="context-intro">确认以下创作配置，确认后将自动启动创作流程。</p>
            <div className="composition-summary">
              <SummaryRow icon="robot" title="写作策略" value={selectedStrategy?.name ?? "未绑定策略"} caption={selectedStrategy?.objective || "—"} />
              <SummaryRow icon="settings" title="阶段模型" value={`${Object.keys((config.model_by_stage as Record<string, string>) ?? {}).length || 0} 个阶段模型`} caption="由策略组合决定" />
              <SummaryRow icon="magic" title="Writing Skill" value={stageSkills ? `${stageSkills} 个阶段 Skill` : "使用系统默认 Skill"} caption="写作、风格、改写与审核" />
              <SummaryRow icon="image" title="排版主题" value={typeof config.theme_id === "string" ? "已绑定主题" : "默认主题"} caption="生成后可再次切换" />
            </div>
            <label className="switch-row"><span><strong>是否需要人工审核</strong><small>创作完成后需人工审核再发布</small></span><Switch checked={(config.review_rules as { human_review_required?: boolean } | undefined)?.human_review_required !== false} disabled /></label>
            <div className="execution-steps"><h3>预计执行步骤</h3>{["选题确认与素材整理", "AI 初稿生成", "内容优化与润色", "质量检查与格式排版"].map((item, index) => <span key={item}><b>{index + 1}</b>{item}<small>预计 {index + 2}-{index + 6} 分钟</small></span>)}</div>
            {selected.status === "candidate" && <Button block onClick={() => onDecision(selected.id, "accept")}>先确认选题</Button>}
            <Button block type="primary" icon={<Icon name="play" size={16} />} loading={starting} disabled={!["accepted", "candidate"].includes(selected.status)} onClick={() => onStart(selected.id)}>确认启动创作</Button>
          </>}
        </aside>
      </div>
    </div>
  );
}

function SummaryRow({ icon, title, value, caption }: { icon: IconName; title: string; value: string; caption: string }) {
  return <div><span><Icon name={icon} /></span><p><small>{title}</small><strong>{value}</strong><em>{caption}</em></p></div>;
}

export function ArticleEditorPage({
  articles,
  selectedId,
  evidence,
  themes,
  selectedThemeId,
  onSelect,
  onThemeChange,
  onSave,
  onOpenReview,
  saving,
}: {
  articles: Article[];
  selectedId: string | null;
  evidence?: EvidencePackage;
  themes: Theme[];
  selectedThemeId: string;
  onSelect: (id: string) => void;
  onThemeChange: (id: string) => void;
  onSave: (articleId: string, markdown: string) => void;
  onOpenReview: (id: string) => void;
  saving: boolean;
}) {
  const article = articles.find((item) => item.id === selectedId) ?? articles[0] ?? null;
  const revision = article?.revisions[article.revisions.length - 1];
  const [draft, setDraft] = useState("");
  const draftValue = draft || revision?.content_markdown || "";
  if (!article || !revision) return <PagePanel><EmptyState icon="article" title="还没有可编辑文章" description="从候选选题启动创作后，文章会出现在这里。" /></PagePanel>;
  const wordCount = draftValue.replace(/\s/g, "").length;
  const sourceLinks = evidence?.sources ?? [];
  const claims = evidence?.claims ?? [];
  return (
    <div className="article-editor-page">
      <aside className="article-evidence">
        <PagePanel>
          <PanelTitle title="来源和事实包" />
          <Select value={article.id} onChange={(id) => { setDraft(""); onSelect(id); }} options={articles.map((item) => ({ label: item.title || "未命名文章", value: item.id }))} />
          <div className="evidence-metrics"><span><small>原文链接</small><strong>{sourceLinks.length}</strong></span><span><small>已确认事实</small><strong>{claims.filter((item) => item.status === "confirmed").length}</strong></span><span><small>引用位置</small><strong>{claims.length}</strong></span></div>
          <h3>原文链接（{sourceLinks.length}）</h3>
          <div className="evidence-link-list">{sourceLinks.map((item) => <a key={item.id} href={item.url} target="_blank" rel="noreferrer"><Icon name="link" size={15} /><span><strong>{item.title}</strong><small>{item.url}</small></span></a>)}{!sourceLinks.length && <p className="muted-copy">暂无来源记录。</p>}</div>
          <h3>原文快照</h3><p className="snapshot-copy">{evidence?.summary || "当前文章暂无事实包摘要。"}</p>
          <h3 className="claim-heading">已确认事实（{claims.length}）</h3>
          <ul className="claim-list">{claims.slice(0, 8).map((item) => <li key={item.id}>{item.statement}</li>)}</ul>
        </PagePanel>
      </aside>
      <main className="editor-canvas">
        <PagePanel>
          <label className="editor-field">标题<Input value={article.title} readOnly suffix={<span>{article.title.length}/100</span>} /></label>
          <label className="editor-field">摘要<Input.TextArea value={evidence?.summary || article.title} readOnly autoSize={{ minRows: 2, maxRows: 4 }} /></label>
          <div className="editor-toolbar">
            <span>正文⌄</span><b>H1</b><b>H2</b><b>H3</b><b>B</b><i>I</i><u>U</u><span>• 列表</span><span>“ 引用</span><Icon name="link" size={15} /><Icon name="image" size={15} />
          </div>
          <Input.TextArea className="markdown-editor" value={draftValue} onChange={(event) => setDraft(event.target.value)} />
          <div className="editor-footer"><span><Icon name="check" size={14} /> 本地草稿已同步</span><Button onClick={() => onSave(article.id, draftValue)} loading={saving}>手动保存新版本</Button><Select value={selectedThemeId || undefined} placeholder="选择排版主题" onChange={onThemeChange} options={themes.filter((item) => item.enabled).map((item) => ({ label: item.name, value: item.id }))} /><Button type="primary" onClick={() => onOpenReview(article.id)}>进入审核</Button><small>字数：{wordCount.toLocaleString()}</small></div>
        </PagePanel>
      </main>
      <aside className="article-tools">
        <PagePanel>
          <PanelTitle title="AI 操作" />
          <div className="ai-action-grid">
            {[
              ["改写选中段落", "magic"],
              ["缩短", "article"],
              ["扩写", "edit"],
              ["优化标题", "topic"],
              ["去 AI 味", "spark"],
              ["调整语气", "review"],
              ["检查事实", "check"],
              ["重新生成此段", "refresh"],
            ].map(([label, icon]) => <button type="button" key={label} disabled title="当前后端暂未提供段落级 AI 编辑接口"><Icon name={icon as IconName} /><span>{label}</span></button>)}
          </div>
        </PagePanel>
        <PagePanel>
          <PanelTitle title="版本历史" />
          <div className="revision-list">{[...article.revisions].reverse().map((item, index) => <button type="button" key={item.id}><span><b>v{item.version}.0</b>{index === 0 && <StatusPill tone="green">最新</StatusPill>}</span><strong>{item.content_markdown.slice(0, 32).replace(/[#\n]/g, " ") || "文章版本"}</strong><small>{item.content_markdown.length.toLocaleString()} 字</small></button>)}</div>
        </PagePanel>
        <PagePanel><PanelTitle title="编辑信息" /><dl className="compact-dl"><dt>创建人</dt><dd>{article.revisions[0]?.created_by || "系统"}</dd><dt>当前版本</dt><dd>v{revision.version}.0</dd><dt>文章状态</dt><dd>{(ARTICLE_STATUS[article.status] ?? { label: article.status }).label}</dd></dl></PagePanel>
      </aside>
    </div>
  );
}

export function ReviewPublishPage({
  tab,
  onTabChange,
  articles,
  publications,
  selectedId,
  onSelect,
  onReview,
  channels,
  themes,
  selectedChannelId,
  selectedThemeId,
  thumbMediaId,
  onChannelChange,
  onThemeChange,
  onThumb,
  onCreateDraft,
  onUpdateDraft,
  onPublish,
  onTestChannel,
  busy,
}: {
  tab: ReviewTab;
  onTabChange: (tab: ReviewTab) => void;
  articles: Article[];
  publications: Publication[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onReview: (articleId: string, revisionId: string, decision: "approve" | "request_changes", comment: string) => void;
  channels: ChannelAccount[];
  themes: Theme[];
  selectedChannelId: string;
  selectedThemeId: string;
  thumbMediaId: string;
  onChannelChange: (id: string) => void;
  onThemeChange: (id: string) => void;
  onThumb: (file: File) => void;
  onCreateDraft: (articleId: string, revisionId: string) => void;
  onUpdateDraft: (articleId: string, revisionId: string) => void;
  onPublish: (articleId: string, revisionId: string) => void;
  onTestChannel: (id: string) => void;
  busy: boolean;
}) {
  const [comment, setComment] = useState("");
  const [aiPreview, setAiPreview] = useState<{ loading: boolean; html: string; error: string }>({ loading: false, html: "", error: "" });
  const pending = articles.filter((item) => ["waiting_review", "pending", "edited", "changes_requested"].includes(item.status));
  const draftArticles = articles.filter((item) => ["approved", "drafted", "wechat_draft", "publishing", "published"].includes(item.status));
  const selected = (tab === "pending" ? pending : draftArticles).find((item) => item.id === selectedId) ?? (tab === "pending" ? pending[0] : draftArticles[0]) ?? articles[0] ?? null;
  const revision = selected?.revisions[selected.revisions.length - 1];
  const selectedAccount = channels.find((item) => item.id === selectedChannelId);
  const selectedTheme = themes.find((item) => item.id === selectedThemeId);
  const themePreview = useQuery({
    queryKey: ["theme-preview", selected?.id, revision?.id, selectedThemeId],
    queryFn: () => api.previewTheme(selected!.id, revision!.id, selectedThemeId),
    enabled: Boolean(selected && revision && selectedThemeId),
  });
  const runAiPreview = async () => {
    if (!selected || !revision || !selectedThemeId) return;
    setAiPreview({ loading: true, html: "", error: "" });
    try {
      const result = await api.previewTheme(selected.id, revision.id, selectedThemeId, "ai");
      setAiPreview({ loading: false, html: result.html, error: "" });
    } catch (error) {
      setAiPreview({ loading: false, html: "", error: error instanceof Error ? error.message : String(error) });
    }
  };
  const reviewMeta = selected?.review?.auto_result ?? {};
  const factCount = Array.isArray(selected?.evidence?.confirmed_facts) ? selected?.evidence.confirmed_facts.length : 0;
  return (
    <div className="review-page">
      <div className="page-tabs">
        <button className={tab === "pending" ? "is-active" : ""} onClick={() => onTabChange("pending")}>待审核 <b>{pending.length}</b></button>
        <button className={tab === "drafts" ? "is-active" : ""} onClick={() => onTabChange("drafts")}>微信草稿 <b>{draftArticles.filter((item) => item.status === "wechat_draft").length}</b></button>
        <button className={tab === "publications" ? "is-active" : ""} onClick={() => onTabChange("publications")}>发布记录 <b>{publications.length}</b></button>
      </div>
      {tab === "pending" && (
        <div className="review-workspace">
          <main>
            <div className="review-filters"><Select defaultValue="all" options={[{ label: "风险等级：全部", value: "all" }]} /><Select defaultValue="all" options={[{ label: "审核状态：全部", value: "all" }]} /><Input prefix={<Icon name="search" size={15} />} placeholder="搜索标题或正文关键词" /><Button icon={<Icon name="refresh" size={14} />}>刷新</Button></div>
            <PagePanel>
              <Table
                rowKey="id"
                size="small"
                pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
                dataSource={pending}
                rowClassName={(item) => item.id === selected?.id ? "selected-row" : ""}
                onRow={(item) => ({ onClick: () => onSelect(item.id) })}
                locale={{ emptyText: <EmptyState icon="check" title="审核队列已清空" description="新生成的文章会自动进入这里。" /> }}
                columns={[
                  { title: "文章标题", dataIndex: "title", width: 280, render: (value) => <strong className="table-title">{value}</strong> },
                  { title: "来源", key: "source", render: () => "内容策略" },
                  { title: "自动审核结果", dataIndex: "status", render: (value) => { const meta = ARTICLE_STATUS[value] ?? { label: value, tone: "neutral" as const }; return <StatusPill tone={meta.tone}>{meta.label}</StatusPill>; } },
                  { title: "风险提示", key: "risk", render: (_, item) => <StatusPill tone={item.review?.status === "changes_requested" ? "orange" : "green"}>{item.review?.status === "changes_requested" ? "中等风险" : "低风险"}</StatusPill> },
                  { title: "事实完整性", key: "facts", render: () => `${factCount ? 90 : 75}%` },
                  { title: "当前版本", key: "version", render: (_, item) => `v${item.revisions[item.revisions.length - 1]?.version ?? 1}.0` },
                  { title: "操作", render: (_, item) => <button className="text-action" onClick={() => onSelect(item.id)}>查看</button> },
                ]}
              />
            </PagePanel>
          </main>
          <aside className="context-panel review-detail">
            {!selected || !revision ? <EmptyState icon="review" title="请选择文章" description="选择一篇文章查看审核详情。" /> : <>
              <div className="context-title"><h2>文章快照 <small>版本 v{revision.version}.0</small></h2><Icon name="chevron" /></div>
              <section><h3>{selected.title}</h3><p className="long-copy">{revision.content_markdown.slice(0, 420)}</p><button className="text-action">查看完整内容 ›</button></section>
              <section><div className="context-title compact"><h3>事实包摘要</h3><button className="text-action">查看全部</button></div><div className="fact-metrics"><span><Icon name="article" /><small>引用来源</small><strong>{factCount}</strong></span><span><Icon name="topic" /><small>关键事实</small><strong>{Array.isArray(selected.evidence?.confirmed_facts) ? selected.evidence.confirmed_facts.length : 0}</strong></span><span><Icon name="chart" /><small>数据图表</small><strong>0</strong></span></div></section>
              <section><h3>风险检测结果</h3><div className="risk-cards"><span className="risk-card risk-card--orange"><Icon name="alert" /><b>轻微风险</b><strong>{Object.keys(reviewMeta).length}</strong></span><span className="risk-card risk-card--green"><Icon name="check" /><b>低风险</b><strong>{factCount}</strong></span><span className="risk-card"><Icon name="shield" /><b>无风险</b><strong>{Math.max(0, 5 - factCount)}</strong></span></div></section>
              <section><h3>事实完整性评估</h3><div className="integrity-score"><span><strong>{factCount ? 90 : 75}%</strong><small>较高</small></span><ul><li>关键事实覆盖</li><li>数据与来源匹配</li><li>逻辑与因果完整</li><li>时效性</li></ul></div></section>
              <label className="review-comment">填写审核意见（必填）<Input.TextArea value={comment} onChange={(event) => setComment(event.target.value)} rows={3} maxLength={500} showCount placeholder="请输入审核意见，说明通过或退回的原因，给作者提供改进建议..." /></label>
              <div className="review-actions"><Button danger onClick={() => onReview(selected.id, revision.id, "request_changes", comment)}>退回修改</Button><Button type="primary" onClick={() => onReview(selected.id, revision.id, "approve", comment)}>审核通过</Button></div>
            </>}
          </aside>
        </div>
      )}
      {tab === "drafts" && (
        <div className="wechat-workspace">
          <PagePanel className="publish-settings">
            <PanelTitle title="发布准备区" caption="配置并确认本次微信发布的参数" />
            <label>公众号账号 *<Select value={selectedChannelId || undefined} placeholder="选择公众号账号" onChange={onChannelChange} options={channels.filter((item) => item.enabled).map((item) => ({ label: item.name, value: item.id }))} /></label>
            <label>排版主题 *<Select value={selectedThemeId || undefined} placeholder="选择排版主题" onChange={onThemeChange} options={themes.filter((item) => item.enabled).map((item) => ({ label: item.name, value: item.id }))} /></label>
            <label>发布文章<Select value={selected?.id} onChange={onSelect} options={draftArticles.map((item) => ({ label: item.title, value: item.id }))} /></label>
            <label>封面图片 *</label>
            <div className="cover-upload"><span><Icon name="image" size={26} /></span><p><strong>{thumbMediaId ? "封面素材已上传" : "尚未上传封面"}</strong><small>{thumbMediaId || "请上传 JPG/PNG 封面"}</small></p></div>
            <Upload accept="image/*" showUploadList={false} beforeUpload={(file) => { onThumb(file); return false; }}><Button block icon={<Icon name="upload" size={15} />}>上传封面</Button></Upload>
            <label>作者<Input value="AI 内容团队" readOnly /></label>
            <label>摘要<Input.TextArea value={selected?.title || ""} readOnly rows={3} /></label>
          </PagePanel>
          <PagePanel className="wechat-preview">
            <PanelTitle title="排版预览" action={<span className="panel-actions"><Button size="small" loading={aiPreview.loading} disabled={!selectedThemeId || !selected || !revision} onClick={() => void runAiPreview()}>AI 排版预览</Button><Button>更换主题</Button><Button>重新渲染</Button></span>} />
            <Tabs items={[{ key: "mobile", label: "手机预览" }, { key: "desktop", label: "桌面预览" }]} />
            <div className="phone-frame">
              <div className="phone-status"><span>9:41</span><span>● ◔ ▰</span></div>
              <div className="wechat-titlebar"><Icon name="close" />{selectedAccount?.name || "公众号预览"}<Icon name="more" /></div>
              <article className="wechat-article-preview"><h1>{selected?.title || "请选择文章"}</h1><p className="wechat-meta">AI内容团队　{selectedAccount?.name || "公众号"}　{formatDate(new Date().toISOString(), true)}</p>{aiPreview.html ? <div dangerouslySetInnerHTML={{ __html: aiPreview.html }} /> : aiPreview.loading ? <div className="wechat-preview-loading">AI 正在装配排版，请稍候…</div> : aiPreview.error ? <div className="wechat-preview-error">AI 排版失败：{aiPreview.error}</div> : selectedThemeId && revision ? themePreview.isLoading ? <div className="wechat-preview-loading">正在应用排版模板…</div> : themePreview.error ? <div className="wechat-preview-error">模板预览失败：{(themePreview.error as Error).message}</div> : <div dangerouslySetInnerHTML={{ __html: themePreview.data?.html || "<p>暂无可预览正文</p>" }} /> : <div dangerouslySetInnerHTML={{ __html: revision?.rendered_html || "<p>暂无可预览正文</p>" }} />}</article>

            </div>
          </PagePanel>
          <aside className="publish-status">
            <PagePanel>
              <PanelTitle title="微信操作与状态" caption="检查账号状态并创建或更新微信草稿" />
              <div className="connection-list"><span>账号连接状态 <StatusPill tone={selectedAccount?.enabled ? "green" : "red"}>{selectedAccount?.enabled ? "已连接" : "未连接"}</StatusPill></span><span>草稿权限 <StatusPill tone={selectedAccount?.has_credentials ? "green" : "orange"}>{selectedAccount?.has_credentials ? "有权限" : "待配置"}</StatusPill></span><span>发布权限 <StatusPill tone={selectedAccount?.capabilities?.publish ? "green" : "red"}>{selectedAccount?.capabilities?.publish ? "有权限" : "无权限"}</StatusPill></span></div>
              {selectedChannelId && <Button block type="primary" onClick={() => onTestChannel(selectedChannelId)}>测试公众号连接</Button>}
            </PagePanel>
            <PagePanel><PanelTitle title="草稿信息" /><dl className="compact-dl"><dt>草稿状态</dt><dd>{selected?.status === "wechat_draft" ? "已创建" : "尚未创建"}</dd><dt>排版主题</dt><dd>{selectedTheme?.name || "—"}</dd><dt>公众号账号</dt><dd>{selectedAccount?.name || "—"}</dd></dl></PagePanel>
            <PagePanel><PanelTitle title="操作" />{selected && revision ? <div className="publish-buttons"><Button type="primary" loading={busy} disabled={!thumbMediaId || !selectedChannelId} onClick={() => onCreateDraft(selected.id, revision.id)}>创建微信草稿</Button><Button loading={busy} disabled={selected.status !== "wechat_draft" || !selectedChannelId} onClick={() => onUpdateDraft(selected.id, revision.id)}>更新微信草稿</Button><Button disabled={!selectedAccount?.capabilities?.publish || selected.status !== "wechat_draft"} onClick={() => onPublish(selected.id, revision.id)}>提交发布</Button></div> : <EmptyState icon="send" title="请选择文章" description="选择已审核文章后才能创建草稿。" />}</PagePanel>
          </aside>
        </div>
      )}
      {tab === "publications" && (
        <PagePanel>
          <PanelTitle title="发布记录" caption="系统记录的真实微信草稿与发布请求" />
          <Table rowKey="id" dataSource={publications} pagination={{ pageSize: 12 }} columns={[
            { title: "记录 ID", dataIndex: "id", render: (value) => value.slice(0, 8) },
            { title: "文章版本", dataIndex: "article_revision_id", render: (value) => value.slice(0, 8) },
            { title: "渠道账号", dataIndex: "channel_account_id" },
            { title: "操作类型", dataIndex: "action", render: (value) => value === "publish" ? "提交发布" : value === "create_draft" ? "创建草稿" : "更新草稿" },
            { title: "状态", dataIndex: "status", render: (value) => <StatusPill tone={value === "succeeded" ? "green" : value.includes("failed") ? "red" : "blue"}>{value}</StatusPill> },
            { title: "远端 ID", dataIndex: "remote_id", ellipsis: true, render: (value) => value || "—" },
            { title: "创建时间", dataIndex: "created_at", render: (value) => formatDate(value) },
            { title: "错误", dataIndex: "error", ellipsis: true, render: (value) => value || "—" },
          ]} />
        </PagePanel>
      )}
    </div>
  );
}

export function SettingsPage({
  tab,
  onTabChange,
  strategies,
  sources,
  models,
  skills,
  themes,
  channels,
  users,
  auditLogs,
  selectedStrategyId,
  onSelectStrategy,
  onNewStrategy,
  onEditStrategy,
  onRunStrategy,
  onToggleStrategy,
  onAddSource,
  onCollectSource,
  onDisableSource,
  onAddModel,
  onTestModel,
  onDisableModel,
  onImportSkill,
  onPublishSkill,
  onDisableSkill,
  onAddChannel,
  onTestChannel,
  onDisableChannel,
  onAddUser,
}: {
  tab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
  strategies: Strategy[];
  sources: Source[];
  models: Model[];
  skills: Skill[];
  themes: Theme[];
  channels: ChannelAccount[];
  users: User[];
  auditLogs: AuditLog[];
  selectedStrategyId: string | null;
  onSelectStrategy: (id: string) => void;
  onNewStrategy: () => void;
  onEditStrategy: (strategy: Strategy) => void;
  onRunStrategy: (id: string) => void;
  onToggleStrategy: (strategy: Strategy, enabled: boolean) => void;
  onAddSource: () => void;
  onCollectSource: (id: string) => void;
  onDisableSource: (id: string) => void;
  onAddModel: () => void;
  onTestModel: (id: string) => void;
  onDisableModel: (id: string) => void;
  onImportSkill: (file: File) => void;
  onPublishSkill: (id: string) => void;
  onDisableSkill: (id: string) => void;
  onAddChannel: () => void;
  onTestChannel: (id: string) => void;
  onDisableChannel: (id: string) => void;
  onAddUser: () => void;
}) {
  const strategy = strategies.find((item) => item.id === selectedStrategyId) ?? strategies[0];
  return (
    <div className="settings-page">
      <div className="settings-tabs">{SETTINGS_TABS.map((item) => <button key={item.key} className={tab === item.key ? "is-active" : ""} onClick={() => onTabChange(item.key)}>{item.label}</button>)}</div>
      {tab === "strategies" && (
        <>
          <PagePanel>
            <PanelTitle title="策略列表" caption="管理内容策略，实现标准化、自动化的内容生产流程" action={<span className="panel-actions"><Input prefix={<Icon name="search" size={15} />} placeholder="搜索策略名称" /><Button type="primary" onClick={onNewStrategy}>新增策略</Button></span>} />
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={strategies}
              rowClassName={(item) => item.id === strategy?.id ? "selected-row" : ""}
              onRow={(item) => ({ onClick: () => onSelectStrategy(item.id) })}
              locale={{ emptyText: <EmptyState icon="play" title="还没有内容策略" description="创建一套策略，组合信息源、模型、Skill、排版与账号。" /> }}
              columns={[
                { title: "策略名称", dataIndex: "name", width: 180, render: (value) => <strong className="table-title">{value}</strong> },
                { title: "内容目标", dataIndex: "objective", width: 220, ellipsis: true },
                { title: "信息源组合", key: "sources", render: (_, item) => `${Array.isArray(item.config.source_ids) && item.config.source_ids.length ? item.config.source_ids.length : "全部"} 个` },
                { title: "运行频率", dataIndex: "schedule" },
                { title: "自动化等级", dataIndex: "automation_level", render: (value) => <StatusPill tone={value === "L4" ? "green" : value === "L3" ? "orange" : "blue"}>{value}</StatusPill> },
                { title: "写作模型", key: "writing", render: (_, item) => { const id = (item.config.model_by_stage as Record<string, string> | undefined)?.writing; return models.find((model) => model.id === id)?.name || "系统默认"; } },
                { title: "排版主题", key: "theme", render: (_, item) => themes.find((theme) => theme.id === item.config.theme_id)?.name || "默认主题" },
                { title: "是否启用", dataIndex: "enabled", render: (value, item) => <Switch size="small" checked={value} onChange={(checked) => onToggleStrategy(item, checked)} /> },
                { title: "操作", render: (_, item) => <span className="table-actions"><button onClick={() => onEditStrategy(item)}>编辑</button><button onClick={() => onRunStrategy(item.id)}>执行</button></span> },
              ]}
            />
          </PagePanel>
          {strategy && (
            <div className="strategy-settings-workspace">
              <PagePanel className="strategy-detail">
                <Tabs items={[{ key: "detail", label: "策略详情" }, { key: "versions", label: "版本历史" }, { key: "runs", label: "执行历史" }, { key: "jobs", label: "关联任务" }, { key: "coverage", label: "信息源覆盖" }]} />
                <PanelTitle title={`编辑策略：${strategy.name}`} />
                <div className="strategy-composition-map" aria-label="当前内容策略的模块化组合">
                  <div className="composition-map-heading">
                    <div><span>可组合生产链路</span><p>节点可独立替换，保存后将按此链路执行。</p></div>
                    <small>当前配置</small>
                  </div>
                  <div className="composition-map-flow">
                    <CompositionBox icon="database" label="信息源" value={`${Array.isArray(strategy.config.source_ids) && strategy.config.source_ids.length ? strategy.config.source_ids.length : "全部"} 个来源`} />
                    <b aria-hidden="true">→</b><CompositionBox icon="magic" label="Writing Skill" value={skillName(skills, strategy, "writing")} />
                    <b aria-hidden="true">→</b><CompositionBox icon="robot" label="写作模型" value={modelName(models, strategy, "writing")} />
                    <b aria-hidden="true">→</b><CompositionBox icon="image" label="排版主题" value={themes.find((item) => item.id === strategy.config.theme_id)?.name || "默认主题"} />
                    <b aria-hidden="true">→</b><CompositionBox icon="send" label="发布账号" value={channels.find((item) => item.id === strategy.config.channel_account_id)?.name || "手动选择"} />
                  </div>
                </div>
                <div className="strategy-form-preview">
                  <label>策略名称<Input value={strategy.name} readOnly /></label><label>内容目标<Input.TextArea value={strategy.objective} readOnly autoSize /></label>
                  <label>运行频率<Input value={strategy.schedule} readOnly /></label><label>自动化等级<Input value={strategy.automation_level} readOnly /></label>
                  <label>Rewrite Skill<Input value={skillName(skills, strategy, "rewrite")} readOnly /></label><label>Review Skill<Input value={skillName(skills, strategy, "review")} readOnly /></label>
                </div>
                <div className="form-actions"><Button type="primary" onClick={() => onEditStrategy(strategy)}>编辑完整组合</Button><Button onClick={() => onRunStrategy(strategy.id)}>立即执行</Button></div>
              </PagePanel>
              <aside><PagePanel><PanelTitle title="操作" /><div className="settings-actions"><button onClick={onNewStrategy}><Icon name="play" />新建<small>创建一个新的内容策略</small></button><button onClick={() => onEditStrategy(strategy)}><Icon name="edit" />编辑<small>编辑当前选中的策略</small></button><button onClick={() => onRunStrategy(strategy.id)}><Icon name="refresh" />立即扫描信息源<small>按当前组合采集并运行</small></button></div></PagePanel><PagePanel className="info-callout"><Icon name="help" /><p><strong>说明</strong><span>策略是一套可自定义组合：信息源、Skill、模型、排版主题和渠道账号都可以独立配置。</span></p></PagePanel></aside>
            </div>
          )}
        </>
      )}
      {tab === "sources" && <ResourceTable title="信息源" caption="管理采集入口与内容数据源" action={<Button type="primary" onClick={onAddSource}>添加信息源</Button>} data={sources} columns={[
        { title: "名称", dataIndex: "name" }, { title: "类型", dataIndex: "source_type" }, { title: "分组", dataIndex: "group_name", render: (value) => value || "未分组" }, { title: "地址", dataIndex: "url", ellipsis: true }, { title: "状态", dataIndex: "enabled", render: (value) => <StatusPill tone={value ? "green" : "neutral"}>{value ? "启用" : "停用"}</StatusPill> }, { title: "最近错误", dataIndex: "last_error", ellipsis: true, render: (value) => value || "—" }, { title: "操作", render: (_, item: Source) => <span className="table-actions"><button onClick={() => onCollectSource(item.id)}>采集</button><button onClick={() => onDisableSource(item.id)}>停用</button></span> },
      ]} />}
      {tab === "models" && <ResourceTable title="模型中心" caption="管理写作、改写和审核阶段使用的模型" action={<Button type="primary" onClick={onAddModel}>添加模型</Button>} data={models} columns={[
        { title: "供应商", dataIndex: "provider" }, { title: "模型", dataIndex: "name" }, { title: "API 地址", dataIndex: "api_base_url", ellipsis: true, render: (value) => value || "系统默认" }, { title: "凭证", dataIndex: "has_api_key", render: (value) => <StatusPill tone={value ? "green" : "orange"}>{value ? "已配置" : "未配置"}</StatusPill> }, { title: "状态", dataIndex: "enabled", render: (value) => <StatusPill tone={value ? "green" : "neutral"}>{value ? "启用" : "停用"}</StatusPill> }, { title: "操作", render: (_, item: Model) => <span className="table-actions"><button onClick={() => onTestModel(item.id)}>测试</button><button onClick={() => onDisableModel(item.id)}>停用</button></span> },
      ]} />}
      {tab === "skills" && <ResourceTable title="Skill 中心" caption="管理写作、改写与审核能力包" action={<Upload accept=".zip" showUploadList={false} beforeUpload={(file) => { onImportSkill(file); return false; }}><Button type="primary">导入 Skill</Button></Upload>} data={skills} columns={[
        { title: "名称", dataIndex: "name" }, { title: "类型", dataIndex: "skill_type" }, { title: "版本", dataIndex: "version" }, { title: "状态", dataIndex: "status", render: (value) => <StatusPill tone={value === "published" ? "green" : "orange"}>{value}</StatusPill> }, { title: "操作", render: (_, item: Skill) => <span className="table-actions">{item.status !== "published" && <button onClick={() => onPublishSkill(item.id)}>发布</button>}<button onClick={() => onDisableSkill(item.id)}>停用</button></span> },
      ]} />}
      {tab === "themes" && <ResourceTable title="排版主题" caption="管理公众号文章的版式与视觉主题" data={themes} columns={[
        { title: "主题名称", dataIndex: "name" }, { title: "标识", dataIndex: "slug" }, { title: "说明", dataIndex: "description", ellipsis: true }, { title: "版本", dataIndex: "current_version", render: (value) => `v${value}` }, { title: "类型", dataIndex: "is_builtin", render: (value) => value ? "系统内置" : "自定义" }, { title: "状态", dataIndex: "enabled", render: (value) => <StatusPill tone={value ? "green" : "neutral"}>{value ? "启用" : "停用"}</StatusPill> },
      ]} />}
      {tab === "channels" && <ResourceTable title="渠道账号" caption="管理微信公众号账号、凭证和发布能力" action={<Button type="primary" onClick={onAddChannel}>绑定公众号</Button>} data={channels} columns={[
        { title: "账号名称", dataIndex: "name" }, { title: "渠道类型", dataIndex: "channel_type" }, { title: "凭证", dataIndex: "has_credentials", render: (value) => <StatusPill tone={value ? "green" : "orange"}>{value ? "已配置" : "未配置"}</StatusPill> }, { title: "发布能力", key: "publish", render: (_, item: ChannelAccount) => <StatusPill tone={item.capabilities.publish ? "green" : "red"}>{item.capabilities.publish ? "可发布" : "仅草稿"}</StatusPill> }, { title: "状态", dataIndex: "enabled", render: (value) => <StatusPill tone={value ? "green" : "neutral"}>{value ? "启用" : "停用"}</StatusPill> }, { title: "操作", render: (_, item: ChannelAccount) => <span className="table-actions"><button onClick={() => onTestChannel(item.id)}>测试</button><button onClick={() => onDisableChannel(item.id)}>停用</button></span> },
      ]} />}
      {tab === "users" && <ResourceTable title="用户与权限" caption="管理企业内部用户与角色" action={<Button type="primary" onClick={onAddUser}>添加用户</Button>} data={users} columns={[
        { title: "邮箱", dataIndex: "email" }, { title: "角色", dataIndex: "role" }, { title: "用户 ID", dataIndex: "id" },
      ]} />}
      {tab === "audit" && <ResourceTable title="系统日志" caption="最近 200 条审计记录" data={auditLogs} columns={[
        { title: "时间", dataIndex: "created_at", render: (value) => formatDate(value) }, { title: "操作", dataIndex: "action" }, { title: "资源类型", dataIndex: "resource_type" }, { title: "资源 ID", dataIndex: "resource_id", ellipsis: true }, { title: "用户", dataIndex: "user_id", render: (value) => value || "系统" }, { title: "IP 地址", dataIndex: "ip_address", render: (value) => value || "—" },
      ]} />}
    </div>
  );
}

function ResourceTable({ title, caption, action, data, columns }: { title: string; caption: string; action?: ReactNode; data: unknown[]; columns: ColumnsType<any> }) {
  return <PagePanel><PanelTitle title={title} caption={caption} action={action} /><Table rowKey="id" size="small" dataSource={data as Array<{ id: string }>} columns={columns} pagination={{ pageSize: 12, showTotal: (total) => `共 ${total} 条` }} /></PagePanel>;
}

function CompositionBox({ icon, label, value }: { icon: IconName; label: string; value: string }) {
  return <span className={`composition-box composition-box--${icon}`}><Icon name={icon} /><small>{label}</small><strong>{value}</strong></span>;
}

function modelName(models: Model[], strategy: Strategy, stage: string) {
  const id = (strategy.config.model_by_stage as Record<string, string> | undefined)?.[stage];
  return models.find((item) => item.id === id)?.name || "系统默认";
}

function skillName(skills: Skill[], strategy: Strategy, stage: string) {
  const id = (strategy.config.skill_by_stage as Record<string, string> | undefined)?.[stage];
  return skills.find((item) => item.id === id)?.name || "系统默认 Skill";
}



