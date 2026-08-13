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
            <Input prefix={<Icon na…7125 tokens truncated…"}</small></p></div>
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