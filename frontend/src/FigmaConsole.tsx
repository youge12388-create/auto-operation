import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { api, type Article, type ChannelAccount, type Job, type Material, type MaterialCategory, type Model, type Skill, type Source, type Strategy, type Theme, type Topic, type User } from "./api";
import { Icon, type IconName, StatusPill } from "./design";
import { StrategyPipelinePage } from "./StrategyPipelinePage";
import { ArticleLibrary, hasFinalArticleBody, MaterialWorkspace, ReviewQueue, TopicRadar } from "./ContentFlowPages";

type Page = "dashboard" | "materials" | "topics" | "review" | "library" | "settings" | "editor";

const COVER_PLACEHOLDER = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='200'%3E%3Crect fill='%23f2e5f0' width='300' height='200' rx='8'/%3E%3Cg transform='translate(150,100)'%3E%3Cline x1='-24' y1='-12' x2='24' y2='12' stroke='%23c9b0c7' stroke-width='2' stroke-linecap='round'/%3E%3Cline x1='24' y1='-12' x2='-24' y2='12' stroke='%23c9b0c7' stroke-width='2' stroke-linecap='round'/%3E%3C/g%3E%3Ctext x='150' y='130' text-anchor='middle' fill='%23b7a0b5' font-size='12' font-family='sans-serif'%3EClick to upload%3C/text%3E%3C/svg%3E";

type ModelProvider = "openai-compatible" | "anthropic" | "fake";
type ModelVendor = "openai" | "deepseek" | "zhipu" | "anthropic" | "custom" | "fake";
type ModelCatalog = { label: string; provider: ModelProvider; apiBaseUrl: string; models: Array<{ name: string; label: string }> };
type RecommendedSource = { name: string; source_type: "rss" | "url"; url: string; description: string };

const RECOMMENDED_SOURCES: RecommendedSource[] = [
  { name: "OpenAI News", source_type: "url", url: "https://openai.com/news/", description: "Official product, research, and safety updates" },
  { name: "Hugging Face Blog", source_type: "url", url: "https://huggingface.co/blog", description: "Open-source models, tools, and community practice" },
  { name: "arXiv cs.AI", source_type: "rss", url: "https://export.arxiv.org/rss/cs.AI", description: "Latest artificial intelligence research papers" },
];

const MODEL_CATALOG: Record<ModelVendor, ModelCatalog> = {
  openai: {
    label: "OpenAI",
    provider: "openai-compatible",
    apiBaseUrl: "https://api.openai.com/v1",
    models: [
      { name: "gpt-5.2", label: "GPT-5.2 · 主力写作" },
      { name: "gpt-5.1", label: "GPT-5.1 · 稳定" },
      { name: "gpt-5-mini", label: "GPT-5 mini · 快速省成本" },
    ],
  },
  deepseek: {
    label: "DeepSeek",
    provider: "openai-compatible",
    apiBaseUrl: "https://api.deepseek.com",
    models: [
      { name: "deepseek-v4-flash", label: "DeepSeek V4 Flash · 快速" },
      { name: "deepseek-v4-pro", label: "DeepSeek V4 Pro · 深度创作" },
    ],
  },
  zhipu: {
    label: "智谱 GLM",
    provider: "openai-compatible",
    apiBaseUrl: "https://open.bigmodel.cn/api/paas/v4",
    models: [
      { name: "glm-5.2", label: "GLM-5.2 · 旗舰" },
      { name: "glm-4.7", label: "GLM-4.7 · 通用" },
      { name: "glm-4.7-flash", label: "GLM-4.7 Flash · 快速" },
    ],
  },
  anthropic: {
    label: "Anthropic Claude",
    provider: "anthropic",
    apiBaseUrl: "https://api.anthropic.com/v1",
    models: [
      { name: "claude-opus-4-20250514", label: "Claude Opus 4 · 高质量" },
      { name: "claude-sonnet-4-20250514", label: "Claude Sonnet 4 · 平衡" },
    ],
  },
  custom: { label: "其他兼容接口", provider: "openai-compatible", apiBaseUrl: "", models: [] },
  fake: { label: "本地测试", provider: "fake", apiBaseUrl: "", models: [{ name: "fake", label: "Fake · 不调用外部服务" }] },
};

const MODEL_VENDOR_OPTIONS: Array<{ value: ModelVendor; label: string }> = [
  { value: "openai", label: "OpenAI" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "zhipu", label: "智谱 GLM" },
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "custom", label: "其他兼容接口" },
  { value: "fake", label: "本地测试" },
];
const NAV: Array<{ key: Page; label: string; icon: IconName }> = [
  { key: "dashboard", label: "工作台", icon: "home" },
  { key: "materials", label: "素材池", icon: "image" },
  { key: "topics", label: "选题雷达", icon: "topic" },
  { key: "review", label: "待审核", icon: "review" },
  { key: "library", label: "成稿库", icon: "article" },
  { key: "settings", label: "自动化", icon: "settings" },
];

function formatTime(value?: string | null) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(date).replaceAll("/", "-");
}

function shortText(value: string, length = 82) {
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

function Empty({ title }: { title: string }) {
  return <div className="figma-empty"><Icon name="spark" size={22} /><strong>{title}</strong><span>当前还没有可展示的内容</span></div>;
}

function FigmaSidebar({ page, onNavigate, onCreate, onHelp, onLogout }: { page: Page; onNavigate: (page: Page) => void; onCreate: () => void; onHelp: () => void; onLogout: () => void }) {
  return <aside className="figma-sidebar">
    <div className="figma-brand"><span className="figma-brand-mark"><Icon name="robot" size={23} /></span><span><strong>Content Ops</strong><small>内容运营工作台</small></span></div>
    <button className="figma-create" type="button" onClick={() => onNavigate("materials")}><Icon name="edit" size={16} />新建创作</button>
    <nav className="figma-nav" aria-label="主导航">{NAV.map((item) => <button key={item.key} type="button" aria-label={item.label} className={page === item.key ? "is-active" : ""} onClick={() => onNavigate(item.key)}><Icon name={item.icon} size={18} /><span>{item.label}</span></button>)}</nav>
    <div className="figma-sidebar-footer"><button type="button" onClick={onHelp}><Icon name="help" size={17} />帮助中心</button><button type="button" onClick={onLogout}><Icon name="close" size={17} />退出登录</button></div>
  </aside>;
}

function FigmaTopbar({ page, user, notificationCount, onSearch, onLogout }: { page: Page; user: User; notificationCount: number; onSearch: (value: string) => void; onLogout: () => void }) {
  const label = page === "editor" ? "文章创作" : NAV.find((item) => item.key === page)?.label ?? "内容运营系统";
  const [open, setOpen] = useState<"notifications" | "help" | "profile" | null>(null);
  return <header className="figma-topbar"><div className="figma-topbar-title"><strong>内容运营系统</strong><span>/</span><span>{label}</span></div><label className="figma-search"><Icon name="search" size={17} /><input placeholder="搜索内容、选题或素材..." onKeyDown={(event) => { if (event.key === "Enter") onSearch(event.currentTarget.value); }} /></label><div className="figma-topbar-actions"><div className="figma-topbar-menu"><button type="button" aria-label="通知" aria-expanded={open === "notifications"} onClick={() => setOpen(open === "notifications" ? null : "notifications")}><Icon name="bell" size={19} />{notificationCount > 0 && <i>{notificationCount}</i>}</button>{open === "notifications" && <div className="figma-topbar-popover"><strong>待处理提醒</strong><p>有 {notificationCount || 0} 个任务需要关注。</p><button type="button" onClick={() => setOpen(null)}>知道了</button></div>}</div><div className="figma-topbar-menu"><button type="button" aria-label="帮助" aria-expanded={open === "help"} onClick={() => setOpen(open === "help" ? null : "help")}><Icon name="help" size={19} /></button>{open === "help" && <div className="figma-topbar-popover"><strong>帮助中心</strong><p>先从素材池筛选依据，再确认选题、配置策略，最后审核并创建公众号草稿。</p><button type="button" onClick={() => setOpen(null)}>关闭</button></div>}</div><div className="figma-topbar-menu"><button className="figma-avatar" type="button" aria-label="账户菜单" aria-expanded={open === "profile"} onClick={() => setOpen(open === "profile" ? null : "profile")}>{user.email.slice(0, 1).toUpperCase()}</button>{open === "profile" && <div className="figma-topbar-popover figma-profile-popover"><strong>{user.email}</strong><span>{user.role === "admin" ? "管理员" : "运营成员"}</span><button type="button" onClick={onLogout}>退出登录</button></div>}</div></div></header>;
}
function PillButton({ children, tone = "soft", type = "button", onClick, disabled = false }: { children: ReactNode; tone?: "soft" | "pink" | "purple"; type?: "button" | "submit"; onClick?: () => void; disabled?: boolean }) {
  return <button type={type} className={"figma-pill figma-pill--" + tone} disabled={disabled} onClick={onClick}>{children}</button>;
}

function Dashboard({ materials, topics, articles, jobs, sourcesCount, onNavigate, onOpenReview }: { materials: Material[]; topics: Topic[]; articles: Article[]; jobs: Job[]; sourcesCount: number; onNavigate: (page: Page) => void; onOpenReview: (id: string) => void }) {
  const reviewQueue = articles.filter((item) => ["waiting_review", "changes_requested"].includes(item.status));
  const candidateTopics = topics.filter((item) => item.status === "candidate");
  const untriagedMaterials = materials.filter((item) => item.triage_status === "inbox");
  const failedJobs = jobs.filter((item) => item.status.startsWith("failed"));
  const runningJobs = jobs.filter((item) => ["queued", "running", "failed_retryable", "waiting_topic"].includes(item.status));
  const deliveredArticles = articles.filter((item) => ["approved", "drafted", "wechat_draft", "published"].includes(item.status));
  const tasks: Array<{ key: string; icon: IconName; title: string; detail: string; action: string; tone: string; onClick: () => void }> = [];
  if (failedJobs[0]) tasks.push({ key: `job-${failedJobs[0].id}`, icon: "alert", title: "有自动化任务需要处理", detail: failedJobs[0].last_error || `任务停在「${failedJobs[0].current_step || "未知步骤"}` , action: "查看生产线", tone: "danger", onClick: () => onNavigate("settings") });
  if (reviewQueue[0]) tasks.push({ key: `review-${reviewQueue[0].id}`, icon: "review", title: reviewQueue[0].title || "待审核文章", detail: reviewQueue[0].status === "changes_requested" ? "已退回修改，等待你确认新版本。" : "文章已完成写作，审核通过后进入成稿库。", action: "去审核", tone: "pink", onClick: () => onOpenReview(reviewQueue[0].id) });
  if (candidateTopics[0]) tasks.push({ key: `topic-${candidateTopics[0].id}`, icon: "topic", title: candidateTopics[0].title, detail: candidateTopics[0].rationale || "AI 已完成热点扫描与选题打分。", action: "查看选题", tone: "purple", onClick: () => onNavigate("topics") });
  if (untriagedMaterials[0]) tasks.push({ key: `material-${untriagedMaterials[0].id}`, icon: "image", title: `${untriagedMaterials.length} 条素材等待筛选`, detail: untriagedMaterials[0].title || "先保留真正值得创作的内容。", action: "筛选素材", tone: "cyan", onClick: () => onNavigate("materials") });
  const nextTask = tasks[0];

  return <main className="figma-page dashboard-page dashboard-page--actionable">
    <div className="figma-page-heading dashboard-heading">
      <div><h1>今天先做什么？</h1><p>只显示会推进内容交付的事项；完成一项，再处理下一项。</p></div>
      <PillButton tone="pink" onClick={() => onNavigate("materials")}><Icon name="edit" size={16} />从素材开始创作</PillButton>
    </div>
    {nextTask ? <section className={`dashboard-next-task dashboard-next-task--${nextTask.tone}`}>
      <div className="dashboard-next-icon"><Icon name={nextTask.icon} size={22} /></div><div><span>下一件事</span><h2>{nextTask.title}</h2><p>{shortText(nextTask.detail, 130)}</p></div><button type="button" onClick={nextTask.onClick}>{nextTask.action}<Icon name="chevron" size={16} /></button>
    </section> : <section className="dashboard-clear"><Icon name="check" size={23} /><div><strong>生产线已清空</strong><span>当前没有等待你处理的内容。可以扫描选题，或从素材开始新创作。</span></div><PillButton tone="pink" onClick={() => onNavigate("topics")}>去选题雷达</PillButton></section>}
    <section className="dashboard-workspace-grid">
      <div className="dashboard-queue">
        <div className="dashboard-section-head"><div><h2>待你决定</h2><p>按影响交付的优先级排序</p></div><span>{tasks.length} 项</span></div>
        {tasks.length ? <div className="dashboard-task-list">{tasks.map((task) => <button type="button" key={task.key} className="dashboard-task-row" onClick={task.onClick}><span className={`dashboard-task-icon ${task.tone}`}><Icon name={task.icon} size={17} /></span><span className="dashboard-task-copy"><strong>{task.title}</strong><small>{shortText(task.detail, 96)}</small></span><em>{task.action}<Icon name="chevron" size={14} /></em></button>)}</div> : <div className="dashboard-empty-list">没有堆积事项。下一轮自动化完成后，会自动回到这里。</div>}
      </div>
      <div className="dashboard-delivery">
        <div className="dashboard-section-head"><div><h2>交付与运行</h2><p>确认系统在持续推进</p></div><button type="button" onClick={() => onNavigate("library")}>查看成稿库</button></div>
        <div className="dashboard-delivery-stats"><div><strong>{deliveredArticles.length}</strong><span>可交付文章</span></div><div><strong>{runningJobs.length}</strong><span>运行中任务</span></div><div><strong>{sourcesCount}</strong><span>启用信息源</span></div></div>
        {runningJobs.length ? <div className="dashboard-running-list">{runningJobs.slice(0, 3).map((job) => <div key={job.id} className="dashboard-running-row"><span className={job.status === "running" ? "is-running" : ""}><Icon name={job.status.startsWith("failed") ? "alert" : "refresh"} size={15} /></span><div><strong>{job.current_step || "正在准备任务"}</strong><small>{job.status === "failed_retryable" ? "执行失败，系统将自动重试" : job.status === "queued" ? "正在排队" : "自动化处理中"}</small></div><time>{formatTime(job.updated_at)}</time></div>)}</div> : <div className="dashboard-empty-list">目前没有运行中的自动化任务。</div>}
      </div>
    </section>
  </main>;
}

function MaterialCard({ material, selected, onSelect }: { material: Material; selected: boolean; onSelect: () => void }) {
  return <button type="button" className={`material-card ${selected ? "is-selected" : ""}`} onClick={onSelect}><div className="material-card-top"><span className="figma-tag">{material.source_name || "科技资讯"}</span><time>{formatTime(material.published_at || material.created_at)}</time></div><h3>{material.title}</h3><p>{shortText(material.content_excerpt || "暂无摘要")}</p><div className="material-card-bottom"><span>{material.source_name || "信息源"}</span><span className="material-score">AI 评分 {material.ai_score != null ? `${material.ai_score}%` : "—"}</span></div></button>;
}

function Materials({ materials, selectedId, onSelect, onIgnore, onUse, onAddSource }: { materials: Material[]; selectedId: string | null; onSelect: (id: string) => void; onIgnore: (id: string) => void; onUse: (material: Material) => void; onAddSource: () => void }) {
  const selected = materials.find((item) => item.id === selectedId) ?? materials[0];
  return <main className="figma-page materials-page"><div className="figma-page-heading"><div><h1><Icon name="image" size={26} />素材池 <small>({materials.filter((item) => item.triage_status !== "ignored").length || 42})</small></h1><p>从信息源中筛选、沉淀真正值得创作的内容依据。</p></div><div className="heading-actions"><button type="button" className="figma-link-button" onClick={() => { materials.filter(m => m.triage_status === "inbox").forEach(m => onIgnore(m.id)); }}>全部标记已读</button><PillButton tone="pink" onClick={onAddSource}><Icon name="link" size={16} />添加信息源</PillButton></div></div><section className="materials-layout"><div className="material-list">{materials.length ? materials.filter((item) => item.triage_status !== "ignored").slice(0, 12).map((item) => <MaterialCard key={item.id} material={item} selected={selected?.id === item.id} onSelect={() => onSelect(item.id)} />) : <Empty title="素材池为空" />}</div>{selected ? <aside className="material-detail"><div className="detail-heading"><h2>素材详情</h2><button type="button" aria-label="关闭" onClick={() => onSelect("")}><Icon name="close" size={18} /></button></div><div className="detail-meta"><span className="figma-tag">{selected.source_name || "科技资讯"}</span><time>{formatTime(selected.published_at || selected.created_at)}</time></div><h2 className="detail-title">{selected.title}</h2><div className="detail-source"><span className="source-avatar"><Icon name="link" size={16} /></span><div><strong>{selected.source_name || "信息源"}</strong><small>{selected.url || "内部素材库"}</small></div>{selected.url && <a href={selected.url} target="_blank" rel="noreferrer"><Icon name="external" size={16} /></a>}</div><div className="ai-summary"><div><span className="circle-icon circle-icon--pink"><Icon name="spark" size={16} /></span><strong>AI 智能摘要</strong></div><p>{shortText(selected.content_excerpt || "AI 将在这里提炼素材中的关键信息、事实与可创作角度。", 210)}</p></div><h3>正文内容</h3><p className="detail-content">{selected.content_excerpt || "暂无正文内容。选择这条素材作为写作依据后，可以在策略配置中继续选择写作 Skill、去 AI 味道 Skill、模板和配图。"}</p><div className="detail-actions"><PillButton onClick={() => onIgnore(selected.id)}>忽略</PillButton><PillButton tone="pink" onClick={() => onUse(selected)}>选作写作依据 <Icon name="chevron" size={15} /></PillButton></div></aside> : null}</section></main>;
}

function TopicCard({ topic, featured = false, onConfirm }: { topic: Topic; featured?: boolean; onConfirm: () => void }) {
  return <article className={`topic-card ${featured ? "topic-card--featured" : ""}`}><div className="topic-card-top"><span className="figma-tag">{featured ? "本周强推" : "AI 推荐"}</span><strong>{topic.score || (featured ? 98 : 92)}<small>分</small></strong></div><h3>{topic.title}</h3><p>{shortText(topic.rationale || "基于热点趋势、用户兴趣与信息源内容生成的创作建议。", 118)}</p><div className="topic-card-footer"><span>AI 洞察 · {topic.scores?.[0]?.dimension || "趋势"}</span><PillButton tone={featured ? "pink" : "soft"} onClick={onConfirm}>确认选题 <Icon name="chevron" size={14} /></PillButton></div></article>;
}

function Topics({ topics, onConfirm, onNew, onEditor }: { topics: Topic[]; onConfirm: (topic: Topic) => void; onNew: () => void; onEditor: () => void }) {
  const candidate = topics.filter((item) => item.status === "candidate");
  const featured = candidate[0] ?? topics[0];
  return <main className="figma-page topics-page"><div className="figma-page-heading"><div><h1>选题与创作</h1><p>浏览 AI 为您量身定制的热门选题，或直接开始创作。</p></div><PillButton tone="pink" onClick={onNew}><Icon name="edit" size={16} />手动创建选题</PillButton></div><div className="figma-tabs"><button className="is-active" type="button">候选选题 <b>{candidate.length || 12}</b></button><button type="button" onClick={onEditor}>文章创作 <b>→</b></button></div>{featured ? <section className="topics-bento"><div className="topic-featured-column"><TopicCard topic={featured} featured onConfirm={() => onConfirm(featured)} /><div className="ai-insight"><span className="circle-icon circle-icon--cyan"><Icon name="spark" size={18} /></span><div><strong>AI 洞察</strong><p>今天的热点集中在智能硬件、AI 应用和内容创作效率，建议优先关注有明确用户场景的选题。</p></div></div></div><div className="topic-recommendations"><div className="section-title"><div><span className="eyebrow">TODAY'S PICKS</span><h2>AI 推荐列表</h2></div><button type="button" onClick={onNew}>换一批 <Icon name="refresh" size={15} /></button></div>{candidate.slice(1, 4).map((topic, index) => <TopicCard key={topic.id} topic={topic} onConfirm={() => onConfirm(topic)} />)}{!candidate.slice(1, 4).length && <Empty title="暂无候选选题" />}</div></section> : <Empty title="暂无候选选题" />}</main>;
}

function PhonePreview({ title, html }: { title?: string; html?: string }) {
  return (
    <div className="wechat-preview-card">
      {title && <h2 className="wechat-preview-title">{title}</h2>}
      {html
        ? <div className="wechat-preview-content" dangerouslySetInnerHTML={{ __html: html }} />
        : <p className="wechat-preview-placeholder">选择文章和排版主题后即可预览效果</p>
      }
    </div>
  );
}

/* ---- 步骤向导 Stepper ---- */

const REVIEW_STEPS = [
  { key: "article", label: "选择文章", icon: "article" as IconName },
  { key: "skill", label: "写作 Skill", icon: "magic" as IconName },
  { key: "theme", label: "选择模板", icon: "image" as IconName },
  { key: "preview", label: "生成预览", icon: "eye" as IconName },
  { key: "channel", label: "选择公众号", icon: "send" as IconName },
  { key: "draft", label: "写入草稿", icon: "check" as IconName },
] as const;

function StepNavVertical({ current, onStep }: { current: number; onStep: (step: number) => void }) {
  return (
    <nav className="step-nav-vertical">
      {REVIEW_STEPS.map((step, index) => (
        <button
          key={step.key}
          type="button"
          className={`step-nav-item ${index === current ? "is-active" : ""} ${index < current ? "is-done" : ""}`}
          onClick={() => onStep(index)}
        >
          <span className="step-nav-icon">
            {index < current ? <Icon name="check" size={14} /> : <Icon name={step.icon} size={14} />}
          </span>
          <span className="step-nav-label">
            <strong>{step.label}</strong>
            <small>步骤 {index + 1}</small>
          </span>
        </button>
      ))}
    </nav>
  );
}

function Review({
  articles, selectedId, onSelect, onApprove, onRequestChanges, onEditor, onDraft, onPublish,
  thumbMediaId, onUpload, themes, selectedThemeId, onThemeChange,
  channels, selectedChannelId, onChannelChange,
  skills, selectedSkillId, onSkillChange,
  pending, themePreviewHtml, coverPreviewUrl,
}: {
  articles: Article[]; selectedId: string | null; onSelect: (id: string) => void;
  onApprove: (article: Article) => void; onRequestChanges: (article: Article) => void;
  onEditor: (id: string) => void; onDraft: (article: Article) => void; onPublish: (article: Article) => void;
  thumbMediaId: string; onUpload: (file: File) => void;
  themes: Theme[]; selectedThemeId: string; onThemeChange: (id: string) => void;
  channels: ChannelAccount[]; selectedChannelId: string; onChannelChange: (id: string) => void;
  skills: Skill[]; selectedSkillId: string; onSkillChange: (id: string) => void;
  pending: boolean; themePreviewHtml?: string; coverPreviewUrl?: string;
}) {
  const [step, setStep] = useState(0);
  const pendingArticles = articles.filter((item) => !["published", "wechat_draft"].includes(item.status));
  const article = articles.find((item) => item.id === selectedId) ?? pendingArticles[0] ?? articles[0];
  const revision = article?.revisions?.[article.revisions.length - 1];

  const canApprove = article && !pending;
  const canCreateDraft = Boolean(selectedChannelId) && Boolean(thumbMediaId) && article && revision;

  const selectedChannel = channels.find((c) => c.id === selectedChannelId);

  return (
    <main className="figma-page review-page">
      <div className="figma-page-heading">
        <div>
          <h1>审核与发布</h1>
          <p>按步骤完成文章审核、配置和微信草稿创建。</p>
        </div>
        <span className="review-count">待审核 <strong>{pendingArticles.length || 0}</strong></span>
      </div>

      <section className="review-wizard-layout">
        {/* Left: 步骤导航 */}
        <StepNavVertical current={step} onStep={setStep} />

        {/* Middle: 实时预览 */}
        <div className="review-preview-panel">
          <div className="preview-label">
            <span className="eyebrow">LIVE PREVIEW</span>
            <h2>实时预览</h2>
          </div>
          <div className="phone-frame">
            <PhonePreview title={article?.title} html={themePreviewHtml} />
          </div>
        </div>

        {/* Right: 操作区 */}
        <div className="review-action-panel">
          {/* Step 0: 选择文章 */}
          {step === 0 && (
            <>
              <div className="step-section">
                <div className="strategy-section-title">
                  <span className="circle-icon circle-icon--pink"><Icon name="article" size={18} /></span>
                  <div><h2>选择文章</h2><p>选择一篇待审核文章</p></div>
                </div>
              </div>
              <div className="review-article-scroll">
                {pendingArticles.map((item) => (
                  <button
                    key={item.id}
                    className={`review-article-mini ${article?.id === item.id ? "is-selected" : ""}`}
                    type="button"
                    onClick={() => onSelect(item.id)}
                  >
                    <strong>{item.title}</strong>
                    <small>AI 创作 · {formatTime(item.revisions?.[0]?.created_by)}</small>
                    <span className="review-article-mini-foot">
                      AI 评分 {item.review?.auto_result?.score ? `${item.review.auto_result.score}%` : "98%"}
                      <em>{item.status === "approved" ? "已通过" : "待审核"}</em>
                    </span>
                  </button>
                ))}
                {!pendingArticles.length && <div className="skill-empty">暂无待审核文章</div>}
              </div>
              {article && (
                <div className="ai-summary" style={{ marginTop: 0 }}>
                  <div><span className="circle-icon circle-icon--pink"><Icon name="spark" size={14} /></span><strong>AI 摘要</strong></div>
                  <p style={{ fontSize: 11 }}>{shortText(revision?.content_markdown || "", 180) || "文章尚未生成完整内容。"}</p>
                </div>
              )}
              <div className="review-article-actions">
                <PillButton onClick={() => article && onRequestChanges(article)} disabled={!canApprove}>打回重写</PillButton>
                <PillButton tone="pink" onClick={() => article && onApprove(article)} disabled={!canApprove}>审核通过</PillButton>
                <PillButton tone="purple" onClick={() => article && onEditor(article.id)} disabled={!article}>编辑</PillButton>
              </div>
            </>
          )}

          {/* Step 1: 选择写作 Skill */}
          {step === 1 && (
            <div className="step-section">
              <div className="strategy-section-title">
                <span className="circle-icon circle-icon--pink"><Icon name="magic" size={18} /></span>
                <div><h2>写作 Skill</h2><p>选择写作技能包</p></div>
              </div>
              <div className="skill-module-grid" style={{ marginTop: 12 }}>
                {skills.filter(s => s.status === "published").map((item) => (
                  <button
                    type="button" key={item.id}
                    className={`skill-module ${selectedSkillId === item.id ? "is-selected" : ""}`}
                    onClick={() => onSkillChange(item.id)}
                  >
                    <span className="skill-module-icon"><Icon name="magic" size={16} /></span>
                    <span><strong>{item.name}</strong><small>{item.skill_type} · v{item.version}</small></span>
                    <em>{selectedSkillId === item.id ? "已选" : ""}</em>
                  </button>
                ))}
                {skills.filter(s => s.status === "published").length === 0 && (
                  <div className="skill-empty">还没有已发布的 Skill。</div>
                )}
              </div>
            </div>
          )}

          {/* Step 2: 选择模板 */}
          {step === 2 && (
            <div className="step-section">
              <div className="strategy-section-title">
                <span className="circle-icon circle-icon--purple"><Icon name="image" size={18} /></span>
                <div><h2>排版模板</h2><p>选择排版样式</p></div>
              </div>
              <div className="template-grid" style={{ marginTop: 12, gridTemplateColumns: "1fr 1fr" }}>
                {themes.filter(t => t.enabled).map((theme) => {
                  const tokens = (theme.tokens || {}) as Record<string, string>;
                  return (
                    <button
                      type="button" key={theme.id}
                      className={selectedThemeId === theme.id ? "is-selected" : ""}
                      onClick={() => onThemeChange(theme.id)}
                    >
                      <span className="theme-preview" style={{ background: tokens.surface || "#fff", color: tokens.text || "#222", borderColor: tokens.accent || "#e040a0" }}>
                        <i style={{ background: tokens.accent || "#e040a0" }} />
                        <i style={{ background: tokens.muted || "#b7a8b8" }} />
                        <b style={{ background: tokens.accent || "#e040a0" }} />
                        <small style={{ background: tokens.muted || "#b7a8b8" }} />
                      </span>
                      <strong>{theme.name}</strong>
                      <small className="template-description">{shortText(theme.description || "", 20)}</small>
                      {selectedThemeId === theme.id && <em>✓</em>}
                    </button>
                  );
                })}
                {themes.filter(t => t.enabled).length === 0 && (
                  <div className="skill-empty">还没有可用排版模板。</div>
                )}
              </div>
            </div>
          )}

          {/* Step 3: 预览确认 */}
          {step === 3 && (
            <div className="step-section">
              <div className="strategy-section-title">
                <span className="circle-icon circle-icon--cyan"><Icon name="eye" size={18} /></span>
                <div>
                  <h2>预览确认</h2>
                  <p>{article?.title || "请先选择文章"}</p>
                  <p style={{ marginTop: 4 }}>{themes.find(t => t.id === selectedThemeId)?.name || "默认主题"} · {skills.find(s => s.id === selectedSkillId)?.name || "默认 Skill"}</p>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: 选择公众号 + 封面 */}
          {step === 4 && (
            <>
              <div className="step-section">
                <div className="strategy-section-title">
                  <span className="circle-icon circle-icon--cyan"><Icon name="send" size={18} /></span>
                  <div><h2>公众号 & 封面</h2><p>选择发布账号和上传封面</p></div>
                </div>
              </div>
              <div className="publish-card" style={{ marginBottom: 0 }}>
                <div>
                  <span className="circle-icon circle-icon--cyan"><Icon name="send" size={18} /></span>
                  <div>
                    <strong>同步到微信公众号</strong>
                    <small>{selectedChannel?.name || "尚未选择发布账号"}</small>
                  </div>
                </div>
                <select value={selectedChannelId} onChange={(e) => onChannelChange(e.target.value)}>
                  <option value="">选择账号</option>
                  {channels.map((channel) => (
                    <option key={channel.id} value={channel.id}>{channel.name}</option>
                  ))}
                </select>
                {selectedChannel && (
                  <div className="channel-info">
                    <span>连接状态 <b className={selectedChannel.enabled ? "text-green" : "text-red"}>{selectedChannel.enabled ? "已连接" : "未连接"}</b></span>
                    <span>发布权限 <b className={selectedChannel.capabilities?.publish ? "text-green" : "text-red"}>{selectedChannel.capabilities?.publish ? "可发布" : "仅草稿"}</b></span>
                  </div>
                )}
              </div>
              <div className="cover-card" style={{ marginBottom: 0 }}>
                <div className="cover-image">
                  <img src={coverPreviewUrl || COVER_PLACEHOLDER} alt="封面预览" />
                </div>
                <div className="cover-info">
                  <span className="eyebrow">COVER</span>
                  <h3>封面图片</h3>
                  <p>{thumbMediaId ? `已上传 media_id: ${thumbMediaId.slice(0, 16)}...` : "请上传 JPG/PNG 格式封面"}</p>
                </div>
                <label className="upload-cover">
                  <Icon name="upload" size={18} />
                  {thumbMediaId ? "重新上传" : "上传封面"}
                  <input type="file" accept="image/*" onChange={(e) => { const file = e.target.files?.[0]; if (file) onUpload(file); }} />
                </label>
              </div>
            </>
          )}

          {/* Step 5: 创建草稿 */}
          {step === 5 && (
            <>
              <div className="step-section">
                <div className="strategy-section-title">
                  <span className="circle-icon circle-icon--green"><Icon name="check" size={18} /></span>
                  <div><h2>确认创建草稿</h2><p>确认配置无误后写入微信草稿</p></div>
                </div>
              </div>
              <div className="summary-grid" style={{ marginTop: 0, gridTemplateColumns: "1fr" }}>
                <div className="summary-item">
                  <span className="summary-icon"><Icon name="article" size={16} /></span>
                  <div><small>文章</small><strong>{article?.title || "—"}</strong></div>
                </div>
                <div className="summary-item">
                  <span className="summary-icon"><Icon name="magic" size={16} /></span>
                  <div><small>Skill</small><strong>{skills.find(s => s.id === selectedSkillId)?.name || "系统默认"}</strong></div>
                </div>
                <div className="summary-item">
                  <span className="summary-icon"><Icon name="image" size={16} /></span>
                  <div><small>模板</small><strong>{themes.find(t => t.id === selectedThemeId)?.name || "—"}</strong></div>
                </div>
                <div className="summary-item">
                  <span className="summary-icon"><Icon name="send" size={16} /></span>
                  <div><small>公众号</small><strong>{selectedChannel?.name || "—"}</strong></div>
                </div>
                <div className="summary-item">
                  <span className="summary-icon"><Icon name="image" size={16} /></span>
                  <div><small>封面</small><strong>{thumbMediaId ? "已上传" : "未上传"}</strong></div>
                </div>
              </div>
              <div className="draft-actions" style={{ marginTop: 12, justifyContent: "stretch" }}>
                <PillButton tone="pink" onClick={() => article && onDraft(article)} disabled={!canCreateDraft || pending}>
                  创建微信草稿
                </PillButton>
                {article?.status === "wechat_draft" && (
                  <PillButton tone="purple" onClick={() => article && onPublish(article)} disabled={pending}>
                    提交发布
                  </PillButton>
                )}
              </div>
            </>
          )}

          {/* 步骤导航按钮 */}
          <div className="step-navigation">
            <PillButton onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
              上一步
            </PillButton>
            <div className="step-info">步骤 {step + 1} / {REVIEW_STEPS.length}</div>
            {step < REVIEW_STEPS.length - 1 && (
              <PillButton tone="pink" onClick={() => setStep(step + 1)}>
                下一步
              </PillButton>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

function ArticleEditor({ article, onBack, onSave, saving }: { article?: Article; onBack: () => void; onSave: (articleId: string, title: string, markdown: string) => void; saving: boolean }) {
  const revision = article?.revisions?.[article.revisions.length - 1];
  const [title, setTitle] = useState(article?.title || "");
  const [markdown, setMarkdown] = useState(revision?.content_markdown || "");
  useEffect(() => {
    setTitle(article?.title || "");
    setMarkdown(revision?.content_markdown || "");
  }, [article?.id, revision?.id]);
  if (!article) return <main className="figma-page"><Empty title="暂无可编辑文章" /></main>;
  return <main className="figma-page article-editor-page"><div className="figma-page-heading"><div><button type="button" className="figma-link-button" onClick={onBack}>← 返回上一页</button><h1>编辑文章</h1><p>保存会创建新版本并送回待审核；已存在的微信草稿不会自动更新。</p></div><PillButton tone="pink" onClick={() => onSave(article.id, title.trim(), markdown)} disabled={saving || !title.trim() || !markdown.trim()}>{saving ? "保存中..." : "保存并重新送审"}</PillButton></div><section className="article-editor-layout"><div className="article-editor-pane"><label className="article-title-field"><span>文章标题</span><input maxLength={500} value={title} onChange={(event) => setTitle(event.target.value)} /></label><div className="editor-pane-head"><span className="eyebrow">MARKDOWN EDITOR</span><span>自动保存关闭 · 手动保存版本</span></div><textarea value={markdown} onChange={(event) => setMarkdown(event.target.value)} /></div><div className="article-render-pane"><div className="editor-pane-head"><span className="eyebrow">CURRENT PREVIEW</span><span>保存前为当前版本预览</span></div><PhonePreview title={title} html={revision?.rendered_html} /></div></section></main>;
}

type ModelFormPayload = { provider: ModelProvider; name: string; api_base_url: string; api_key: string };

function sourceTypeLabel(type: string) {
  if (type === "rss") return "RSS";
  if (type === "url") return "网页";
  if (type === "aihot_api") return "AI HOT";
  if (type === "manual") return "手动";
  return type.toUpperCase();
}

function SourceCenter({ sources, onAdd, onAddRecommended, onCollect, onUpdate, onDisable }: { sources: Source[]; onAdd: () => void; onAddRecommended: (source: RecommendedSource) => Promise<void>; onCollect: (id: string) => Promise<void>; onUpdate: (id: string, source: Source) => Promise<void>; onDisable: (id: string) => Promise<void> }) {
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Source | null>(null);
  const [form, setForm] = useState({ name: "", url: "" });
  const run = async (id: string, action: (id: string) => Promise<void>) => {
    setPendingId(id);
    try { await action(id); } catch { /* The mutation reports the user-facing error. */ } finally { setPendingId(null); }
  };
  const edit = (source: Source) => {
    setEditing(source);
    setForm({ name: source.name, url: source.url });
  };
  const save = async () => {
    if (!editing || !form.name.trim() || (editing.source_type !== "manual" && editing.source_type !== "aihot_api" && !form.url.trim())) return;
    setPendingId(editing.id);
    try {
      await onUpdate(editing.id, { ...editing, name: form.name.trim(), url: form.url.trim(), enabled: editing.enabled });
      setEditing(null);
    } catch { /* The mutation reports the user-facing error. */ } finally { setPendingId(null); }
  };
  const restore = (source: Source) => onUpdate(source.id, { ...source, enabled: true });

  return (
    <main className="figma-page">
      <div className="figma-page-heading"><div><h1><span className="title-icon"><Icon name="link" size={22} /></span>采集设置</h1><p>信息源只负责把内容采集到素材池；自动化生产线从素材池分类中选材。</p></div><PillButton tone="pink" onClick={onAdd}>+ 添加信息源</PillButton></div>
      <section className="recommended-sources" aria-label="推荐信息源">
        <div><strong>优质推荐</strong><span>官方产品动态、开源社区与论文来源，点击后才会添加到你的信息源列表。</span></div>
        <div className="recommended-source-list">{RECOMMENDED_SOURCES.map((source) => {
          const exists = sources.some((item) => item.url.replace(/\/$/, "") === source.url.replace(/\/$/, ""));
          return <button key={source.url} type="button" disabled={exists || pendingId === source.url} onClick={() => void run(source.url, () => onAddRecommended(source))}>
            <strong>{source.name}</strong><small>{source.description}</small><em>{exists ? "已添加" : pendingId === source.url ? "添加中…" : "添加"}</em>
          </button>;
        })}</div>
      </section>
      <section className="model-page-section source-page-section">
        {!sources.length ? <div className="model-empty-hint">还没有信息源。添加 RSS、网页 URL 或手动来源后，它们会出现在这里。</div> : <div className="source-list">{sources.map((source) => <div key={source.id} className="source-list-item"><div className="source-list-main"><span className="model-list-provider">{sourceTypeLabel(source.source_type)}</span><strong>{source.name}</strong><span className="source-list-url">{source.url || "手动录入"}</span>{source.last_error && <small className="source-list-error">最近失败：{source.last_error}</small>}</div><div className="source-list-actions"><StatusPill tone={source.enabled ? "green" : "neutral"}>{source.enabled ? "启用" : "已停用"}</StatusPill><button type="button" className="text-action" onClick={() => edit(source)}>编辑</button>{source.enabled && source.source_type !== "manual" && <button type="button" className="text-action" disabled={pendingId === source.id} onClick={() => void run(source.id, onCollect)}>{pendingId === source.id ? "采集中…" : "立即采集"}</button>}{source.enabled ? <button type="button" className="text-action text-action--danger" disabled={pendingId === source.id} onClick={() => void run(source.id, onDisable)}>停用</button> : <button type="button" className="text-action" disabled={pendingId === source.id} onClick={() => void run(source.id, () => restore(source))}>恢复</button>}</div></div>)}</div>}
      </section>
      {editing && <div className="figma-modal-backdrop" role="presentation" onClick={(event) => { if (event.target === event.currentTarget) setEditing(null); }}><section className="figma-modal" role="dialog" aria-modal="true" aria-label="编辑信息源"><button className="modal-close" type="button" aria-label="关闭" onClick={() => setEditing(null)}><Icon name="close" size={18} /></button><span className="eyebrow">COLLECTION SOURCE</span><h2>编辑信息源</h2><p>修改只影响后续采集，已经进入素材池的历史内容保持不变。</p><label>名称<input value={form.name} onChange={(event) => setForm((value) => ({ ...value, name: event.target.value }))} /></label>{editing.source_type !== "manual" && editing.source_type !== "aihot_api" && <label>{editing.source_type === "rss" ? "RSS 地址" : "网页地址"}<input type="url" value={form.url} onChange={(event) => setForm((value) => ({ ...value, url: event.target.value }))} /></label>}{editing.source_type === "aihot_api" && <label>分类<select value={String((editing.config?.category) || "")} onChange={(event) => setEditing({ ...editing, config: { ...(editing.config || {}), category: event.target.value || undefined } })}><option value="">全部分类</option><option value="ai-models">AI 模型</option><option value="ai-products">AI 产品</option><option value="industry">行业动态</option><option value="paper">论文</option><option value="tip">技巧</option></select></label>}<PillButton tone="pink" disabled={pendingId === editing.id} onClick={() => void save()}>{pendingId === editing.id ? "保存中…" : "保存修改"}</PillButton></section></div>}
    </main>
  );
}
type ChannelFormPayload = { name: string; app_id: string; app_secret: string; publish_enabled: boolean };

function ChannelCenter({ accounts, onAdd, onUpdate, onTest, onDisable }: { accounts: ChannelAccount[]; onAdd: (payload: ChannelFormPayload) => Promise<void>; onUpdate: (id: string, payload: ChannelFormPayload & { enabled?: boolean }) => Promise<void>; onTest: (id: string) => void; onDisable: (id: string) => Promise<void> }) {
  const emptyForm = (): ChannelFormPayload => ({ name: "", app_id: "", app_secret: "", publish_enabled: false });
  const [form, setForm] = useState<ChannelFormPayload>(emptyForm());
  const [editing, setEditing] = useState<ChannelAccount | null>(null);
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const close = () => { setOpen(false); setEditing(null); setForm(emptyForm()); setFormError(""); };
  const startEdit = (account: ChannelAccount) => { setEditing(account); setForm({ name: account.name, app_id: "", app_secret: "", publish_enabled: Boolean(account.capabilities.publish) }); setFormError(""); setOpen(true); };
  const submit = async () => {
    if (!form.name.trim() || !form.app_id.trim() || !form.app_secret.trim()) { setFormError("请填写公众号名称、AppID 和 AppSecret。"); return; }
    setSubmitting(true);
    setFormError("");
    try {
      if (editing) await onUpdate(editing.id, { ...form, name: form.name.trim(), app_id: form.app_id.trim(), app_secret: form.app_secret.trim() });
      else await onAdd({ ...form, name: form.name.trim(), app_id: form.app_id.trim(), app_secret: form.app_secret.trim() });
      close();
    } catch (error) { setFormError(error instanceof Error ? error.message : "保存失败，请检查凭证后重试。"); } finally { setSubmitting(false); }
  };
  const restore = async (account: ChannelAccount) => { setSubmitting(true); try { await onUpdate(account.id, { ...emptyForm(), name: account.name, enabled: true }); } finally { setSubmitting(false); } };

  return <main className="figma-page model-center-page"><div className="figma-page-heading"><div><h1><span className="title-icon"><Icon name="send" size={22} /></span>公众号账号</h1><p>绑定公众号 AppID 与 AppSecret。凭证仅在保存时发送，页面不会回显；默认只允许创建草稿。</p></div><PillButton tone="pink" onClick={() => { setForm(emptyForm()); setEditing(null); setFormError(""); setOpen(true); }}>+ 绑定公众号</PillButton></div><section className="model-guidance"><strong>使用前请确认：</strong><span>已在微信公众平台配置服务器出口 IP 白名单；只有管理员可在绑定时打开正式发布权限。</span></section><section className="model-page-section">{!accounts.length ? <div className="model-empty-hint">还没有绑定公众号。绑定后可在策略与成稿库中选择它来创建草稿。</div> : <div className="model-list">{accounts.map((account) => { const readonly = account.config.source === "environment"; return <div key={account.id} className="model-list-item"><div className="model-list-main"><span className="model-list-provider">WECHAT</span><strong>{account.name}</strong><span className={account.has_credentials ? "model-list-key" : "model-list-key miss"}><Icon name={account.has_credentials ? "check" : "close"} size={10} />{account.has_credentials ? "凭证已配置" : "凭证未配置"}</span></div><div className="model-list-actions"><StatusPill tone={account.enabled ? "green" : "neutral"}>{account.enabled ? "启用中" : "已停用"}</StatusPill><StatusPill tone={account.capabilities.publish ? "green" : "blue"}>{account.capabilities.publish ? "可发布" : "仅草稿"}</StatusPill>{readonly ? <span className="account-readonly">环境配置</span> : <><button type="button" className="text-action" disabled={submitting} onClick={() => onTest(account.id)}>测试</button><button type="button" className="text-action" disabled={submitting} onClick={() => startEdit(account)}>编辑凭证</button>{account.enabled ? <button type="button" className="text-action text-action--danger" disabled={submitting} onClick={() => void onDisable(account.id)}>停用</button> : <button type="button" className="text-action" disabled={submitting} onClick={() => void restore(account)}>恢复</button>}</>}</div></div>; })}</div>}</section>{open && <div className="figma-modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget && !submitting) close(); }}><div className="figma-modal model-modal"><button type="button" className="modal-close" disabled={submitting} onClick={close}><Icon name="close" size={14} /></button><h2>{editing ? "更新公众号凭证" : "绑定微信公众号"}</h2><p>{editing ? "重新填写 AppID 与 AppSecret 后才会更新凭证。" : "凭证将加密保存；建议先保留“仅草稿”权限，确认流程后再开启发布。"}</p><form onSubmit={(event) => { event.preventDefault(); void submit(); }}><label>公众号名称<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="例如：品牌内容号" required /></label><label>AppID<input value={form.app_id} onChange={(event) => setForm((current) => ({ ...current, app_id: event.target.value }))} placeholder="wx..." required /></label><label>AppSecret<input type="password" value={form.app_secret} onChange={(event) => setForm((current) => ({ ...current, app_secret: event.target.value }))} placeholder="公众号 AppSecret" required /></label>{!editing && <label className="form-check"><input type="checkbox" checked={form.publish_enabled} onChange={(event) => setForm((current) => ({ ...current, publish_enabled: event.target.checked }))} />允许正式发布（仅管理员）</label>}{formError && <div className="form-error" role="alert">{formError}</div>}<div className="modal-form-actions"><PillButton type="button" onClick={close} disabled={submitting}>取消</PillButton><PillButton type="submit" tone="pink" disabled={submitting}>{submitting ? "保存中…" : editing ? "保存凭证" : "绑定公众号"}</PillButton></div></form></div></div>}</main>;
}

type UserFormPayload = { email: string; password: string; role: "admin" | "operator" | "reviewer" };

function UserCenter({ users, onAdd }: { users: User[]; onAdd: (payload: UserFormPayload) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<UserFormPayload>({ email: "", password: "", role: "operator" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const close = () => { setOpen(false); setForm({ email: "", password: "", role: "operator" }); setError(""); };
  const submit = async () => {
    if (!form.email.trim() || form.password.length < 12) { setError("请填写有效邮箱，密码至少 12 位。"); return; }
    setSubmitting(true); setError("");
    try { await onAdd({ ...form, email: form.email.trim() }); close(); } catch (reason) { setError(reason instanceof Error ? reason.message : "添加用户失败。"); } finally { setSubmitting(false); }
  };
  return <main className="figma-page model-center-page"><div className="figma-page-heading"><div><h1><span className="title-icon"><Icon name="user" size={22} /></span>用户中心</h1><p>管理内部成员及其角色：管理员可管理配置与发布，运营可处理内容，审核员只处理审核流程。</p></div><PillButton tone="pink" onClick={() => setOpen(true)}>+ 添加用户</PillButton></div><section className="model-page-section">{!users.length ? <div className="model-empty-hint">暂无可管理用户。</div> : <div className="model-list">{users.map((user) => <div key={user.id} className="model-list-item"><div className="model-list-main"><span className="model-list-provider">{user.role}</span><strong>{user.email}</strong></div><div className="model-list-actions"><StatusPill tone={user.role === "admin" ? "green" : "blue"}>{user.role === "admin" ? "管理员" : user.role === "operator" ? "运营" : "审核"}</StatusPill></div></div>)}</div>}</section>{open && <div className="figma-modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget && !submitting) close(); }}><div className="figma-modal model-modal"><button type="button" className="modal-close" disabled={submitting} onClick={close}><Icon name="close" size={14} /></button><h2>添加内部用户</h2><p>新用户将使用此邮箱和密码登录后台。</p><form onSubmit={(event) => { event.preventDefault(); void submit(); }}><label>邮箱<input type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} required /></label><label>初始密码<input type="password" minLength={12} value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} required /></label><label>角色<select value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as UserFormPayload["role"] }))}><option value="operator">运营</option><option value="reviewer">审核</option><option value="admin">管理员</option></select></label>{error && <div className="form-error" role="alert">{error}</div>}<div className="modal-form-actions"><PillButton type="button" onClick={close} disabled={submitting}>取消</PillButton><PillButton type="submit" tone="pink" disabled={submitting}>{submitting ? "添加中…" : "添加用户"}</PillButton></div></form></div></div>}</main>;
}
function ModelCenter({ models, onAdd, onUpdate, onTest, onDelete }: { models: Model[]; onAdd: (p: ModelFormPayload) => Promise<void>; onUpdate: (id: string, p: Partial<ModelFormPayload> & { enabled?: boolean }) => Promise<void>; onTest: (id: string) => void; onDelete: (id: string) => Promise<void> }) {
  const defaultForm = (vendor: ModelVendor = "openai"): ModelFormPayload => {
    const catalog = MODEL_CATALOG[vendor];
    return { provider: catalog.provider, name: catalog.models[0]?.name || "", api_base_url: catalog.apiBaseUrl, api_key: "" };
  };
  const [form, setForm] = useState<ModelFormPayload>(defaultForm());
  const [vendor, setVendor] = useState<ModelVendor>("openai");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const vendorFor = (model: Model): ModelVendor => {
    const found = (Object.keys(MODEL_CATALOG) as ModelVendor[]).find((key) => {
      const catalog = MODEL_CATALOG[key];
      return catalog.provider === model.provider && catalog.apiBaseUrl === (model.api_base_url || "") && catalog.models.some((item) => item.name === model.name);
    });
    return found || "custom";
  };
  const reset = () => {
    setEditingId(null);
    setVendor("openai");
    setForm(defaultForm());
    setFormError("");
    setOpen(false);
  };
  const changeVendor = (next: ModelVendor) => {
    setVendor(next);
    setForm(defaultForm(next));
    setFormError("");
  };
  const startEdit = (model: Model) => {
    const nextVendor = vendorFor(model);
    setEditingId(model.id);
    setVendor(nextVendor);
    setForm({ provider: model.provider as ModelProvider, name: model.name, api_base_url: model.api_base_url || "", api_key: "" });
    setFormError("");
    setOpen(true);
  };
  const submit = async () => {
    const provider = form.provider.trim() as ModelProvider;
    const name = form.name.trim();
    const apiBaseUrl = form.api_base_url.trim();
    if (!provider || !name) {
      setFormError("请选择供应商和模型，或填写自定义模型 ID。");
      return;
    }
    if (provider !== "fake" && !apiBaseUrl) {
      setFormError("请填写该供应商的 API Base URL。");
      return;
    }
    if (apiBaseUrl) {
      try { new URL(apiBaseUrl); } catch { setFormError("API Base URL 需要是完整地址，例如 https://api.example.com/v1。"); return; }
    }
    setSubmitting(true);
    setFormError("");
    try {
      const payload = { ...form, provider, name, api_base_url: apiBaseUrl };
      if (editingId) await onUpdate(editingId, payload);
      else await onAdd(payload);
      reset();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "保存失败，请检查接口地址和凭证后重试。");
    } finally { setSubmitting(false); }
  };
  const remove = async (model: Model) => {
    if (!window.confirm(`永久删除模型“${model.name}”？仅当没有策略或未完成任务引用它时才会删除；历史文章快照会保留。`)) return;
    setSubmitting(true);
    try { await onDelete(model.id); } catch { /* Mutation already reports the server message. */ } finally { setSubmitting(false); }
  };
  const catalog = MODEL_CATALOG[vendor];

  return (
    <main className="figma-page model-center-page">
      <div className="figma-page-heading">
        <div>
          <h1><span className="title-icon"><Icon name="robot" size={22} /></span>模型中心</h1>
          <p>先选供应商，再选模型。策略只会看到已启用的连接；删除会先检查生产线与未完成任务引用。</p>
        </div>
        <PillButton tone="pink" onClick={() => { setEditingId(null); changeVendor("openai"); setOpen(true); }}>+ 添加模型</PillButton>
      </div>
      <section className="model-guidance" aria-label="模型配置说明">
        <strong>推荐搭配</strong><span>日常创作选 DeepSeek Flash 或 GLM-4.7 Flash；深度写作选 DeepSeek Pro、GLM-5.2 或 Claude Opus。</span><span>账户若开放 GPT-5.6，请在“其他兼容接口”填写 `gpt-5.6`。</span>
      </section>
      <section className="model-page-section">
        {!models.length ? <div className="model-empty-hint">还没有配置模型。添加一条连接后，才能在自动化生产线中选择它。</div> : (
          <div className="model-list">
            {models.map((model) => <div key={model.id} className="model-list-item">
              <div className="model-list-main">
                <span className="model-list-provider">{MODEL_CATALOG[vendorFor(model)].label}</span>
                <strong>{model.name}</strong>
                <span className={model.has_api_key ? "model-list-key" : "model-list-key miss"}><Icon name={model.has_api_key ? "check" : "close"} size={10} />{model.has_api_key ? "已配置凭证" : "未配置凭证"}</span>
              </div>
              <div className="model-list-actions">
                <StatusPill tone={model.enabled ? "green" : "neutral"}>{model.enabled ? "启用中" : "已停用"}</StatusPill>
                <button type="button" className="text-action" disabled={submitting} onClick={() => void onUpdate(model.id, { enabled: !model.enabled })}>{model.enabled ? "停用" : "启用"}</button>
                <button type="button" className="text-action" disabled={submitting} onClick={() => onTest(model.id)}>测试</button>
                <button type="button" className="text-action" disabled={submitting} onClick={() => startEdit(model)}>编辑</button>
                <button type="button" className="text-action text-action--danger" disabled={submitting} onClick={() => void remove(model)}>删除</button>
              </div>
            </div>)}
          </div>
        )}
      </section>
      {open && <div className="figma-modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget && !submitting) reset(); }}>
        <div className="figma-modal model-modal">
          <button type="button" className="modal-close" disabled={submitting} onClick={reset}><Icon name="close" size={14} /></button>
          <h2>{editingId ? "编辑模型连接" : "添加模型连接"}</h2>
          <p>密钥只在你保存时发送，编辑时留空则不覆盖已有密钥。</p>
          <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
            <label>供应商<select value={vendor} onChange={(event) => changeVendor(event.target.value as ModelVendor)}>{MODEL_VENDOR_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            {catalog.models.length ? <label>模型<select value={catalog.models.some((item) => item.name === form.name) ? form.name : "custom"} onChange={(event) => { const name = event.target.value; setForm((current) => ({ ...current, name: name === "custom" ? "" : name })); }}><option value="">请选择模型</option>{catalog.models.map((item) => <option key={item.name} value={item.name}>{item.label}</option>)}<option value="custom">自定义模型 ID</option></select></label> : null}
            <label>模型 ID<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder={vendor === "openai" ? "例如 gpt-5.6（按账户开放）" : "填写服务商给出的模型 ID"} required /></label>
            <label>API Base URL<input value={form.api_base_url} disabled={vendor === "fake"} onChange={(event) => setForm((current) => ({ ...current, api_base_url: event.target.value }))} placeholder="https://api.example.com/v1" /></label>
            <label>API Key<input type="password" value={form.api_key} onChange={(event) => setForm((current) => ({ ...current, api_key: event.target.value }))} placeholder={editingId ? "留空表示不修改" : "sk-..."} /></label>
            {formError && <div className="form-error" role="alert">{formError}</div>}
            <div className="modal-form-actions"><PillButton type="button" onClick={reset} disabled={submitting}>取消</PillButton><PillButton type="submit" tone="pink" disabled={submitting || !form.name.trim()}>{submitting ? "保存中…" : editingId ? "保存修改" : "添加模型"}</PillButton></div>
          </form>
        </div>
      </div>}
    </main>
  );
}
type StrategySavePayload = { name: string; objective: string; schedule: string; automation_level: string; enabled: boolean; config: Strategy["config"] };

function StrategyList({ strategies, selectedId, onSelect, onNew, onRun, models, skills, themes }: { strategies: Strategy[]; selectedId: string | null; onSelect: (id: string) => void; onNew: () => void; onRun: (id: string) => void; models: Model[]; skills: Skill[]; themes: Theme[] }) {
  const modelMap = new Map(models.map(m => [m.id, m]));
  const skillMap = new Map(skills.map(s => [s.id, s]));
  const themeMap = new Map(themes.map(t => [t.id, t]));
  return (
    <aside className="strategy-list-panel">
      <div className="strategy-list-head">
        <h2>我的策略 <small>({strategies.length})</small></h2>
        <button type="button" className="figma-link-button" onClick={onNew}>+ 新建</button>
      </div>
      <div className="strategy-list-items">
        {strategies.map(s => {
          const modelByStage = (s.config.model_by_stage || {}) as Record<string, string>;
          const skillId = s.config.skill_ids?.[0];
          const mid = modelByStage.writing;
          const tid = s.config.theme_id;
          const sk = skillId ? skillMap.get(skillId) : undefined;
          const m = mid ? modelMap.get(mid) : undefined;
          const t = tid ? themeMap.get(tid) : undefined;
          return (
            <button key={s.id} type="button" className={`strategy-list-item ${s.id === selectedId ? "is-selected" : ""}`} onClick={() => onSelect(s.id)}>
              <div className="strategy-item-top">
                <strong>{s.name}</strong>
                <span className={`strategy-dot ${s.enabled ? "dot-on" : "dot-off"}`} />
              </div>
              <div className="strategy-item-chain">
                <span>{sk?.name || "—"}</span><i>→</i><span>{m ? `${m.provider}/${m.name}` : "—"}</span><i>→</i><span>{t?.name || "—"}</span>
              </div>
              <small className="strategy-item-meta">{s.automation_level} · {s.schedule === "manual" ? "手动" : s.schedule === "hourly" ? "每小时" : "每天"}</small>
              {s.id === selectedId && <button className="strategy-run-btn" type="button" onClick={(e) => { e.stopPropagation(); onRun(s.id); }}><Icon name="play" size={12} />运行</button>}
            </button>
          );
        })}
        {!strategies.length && <div className="strategy-empty-hint">还没有策略组合，点击上方「+ 新建」创建。</div>}
      </div>
    </aside>
  );
}

function Strategy({ strategies, selectedId, onSelect, onNew, sources, skills, themes, models, selectedMaterial, onSave, onRun, onAddSource, onImportSkill, onPublishSkill }: { strategies: Strategy[]; selectedId: string | null; onSelect: (id: string) => void; onNew: () => void; sources: Source[]; skills: Skill[]; themes: Theme[]; models: Model[]; selectedMaterial?: Material; onSave: (id: string | undefined, payload: StrategySavePayload) => void; onRun: (id: string) => void; onAddSource: () => void; onImportSkill: (file: File) => void; onPublishSkill: (id: string) => void }) {
  const current = strategies.find(s => s.id === selectedId) ?? null;
  const modelByStage = (current?.config.model_by_stage || {}) as Record<string, string>;
  const [name, setName] = useState(current?.name || "");
  const [objective, setObjective] = useState(current?.objective || "");
  const [schedule, setSchedule] = useState(current?.schedule || "manual");
  const [autoLevel, setAutoLevel] = useState(current?.automation_level || "L2");
  const [enabled, setEnabled] = useState(current?.enabled ?? true);
  const [sourceMode, setSourceMode] = useState(String(current?.config.source_mode || "internal"));
  const [skill, setSkill] = useState(current?.config.skill_ids?.[0] || skills[0]?.id || "");
  const [model, setModel] = useState(modelByStage.writing || models[0]?.id || "");
  const [humanization, setHumanization] = useState(Number(current?.config.humanization || 75));
  const [theme, setTheme] = useState(current?.config.theme_id || themes[0]?.id || "");

  useEffect(() => {
    setName(current?.name || "");
    setObjective(current?.objective || "");
    setSchedule(current?.schedule || "manual");
    setAutoLevel(current?.automation_level || "L2");
    setEnabled(current?.enabled ?? true);
    setSourceMode(String(current?.config.source_mode || "internal"));
    setSkill(current?.config.skill_ids?.[0] || skills[0]?.id || "");
    setModel(((current?.config.model_by_stage || {}) as Record<string, string>).writing || models[0]?.id || "");
    setHumanization(Number(current?.config.humanization || 75));
    setTheme(current?.config.theme_id || themes[0]?.id || "");
  }, [selectedId]);

  useEffect(() => { if (!skill && skills[0]) setSkill(skills[0].id); }, [skill, skills]);
  useEffect(() => { if (!model && models[0]) setModel(models[0].id); }, [model, models]);
  useEffect(() => { if (!theme && themes[0]) setTheme(themes[0].id); }, [theme, themes]);

  const chosenSkill = skills.find((item) => item.id === skill);
  const chosenModel = models.find((item) => item.id === model);
  const chosenTheme = themes.find((item) => item.id === theme);
  const chosenTokens = (chosenTheme?.tokens || {}) as Record<string, string>;
  const enabledModels = models.filter(m => m.enabled);
  const save = () => onSave(current?.id, { name: name || "未命名策略", objective: objective || "围绕热点与用户场景生成高质量公众号内容", schedule, automation_level: autoLevel, enabled, config: { ...(current?.config || {}), source_ids: sourceMode === "internal" ? sources.map((item) => item.id) : [], material_ids: selectedMaterial ? [selectedMaterial.id] : [], skill_ids: skill ? [skill] : [], model_by_stage: { writing: model }, theme_id: theme, humanization, source_mode: sourceMode } });

  if (!current && strategies.length > 0) return null;

  return <main className="figma-page strategy-page"><div className="figma-page-heading strategy-heading"><div><h1><span className="title-icon"><Icon name="settings" size={22} /></span>策略组合</h1><p>管理你的多套内容生产流水线，每套可独立配置并随时切换执行。</p></div><div className="heading-actions"><button type="button" className="strategy-source-link" onClick={onAddSource}><Icon name="link" size={16} />信息源 <span>{sources.length}</span></button></div></div><section className="strategy-layout-v2"><StrategyList strategies={strategies} selectedId={selectedId} onSelect={onSelect} onNew={onNew} onRun={onRun} models={models} skills={skills} themes={themes} /><div className="strategy-detail-area">{current ? <div className="strategy-controls"><section className="strategy-section strategy-meta-section"><div className="strategy-meta-grid"><label className="strategy-meta-field"><small>策略名称</small><input value={name} onChange={e => setName(e.target.value)} placeholder="例如：科技快讯日更策略" /></label><label className="strategy-meta-field"><small>内容目标</small><input value={objective} onChange={e => setObjective(e.target.value)} placeholder="围绕热点与用户场景生成高质量内容" /></label><label className="strategy-meta-field"><small>运行频率</small><select value={schedule} onChange={e => setSchedule(e.target.value)}><option value="manual">手动执行</option><option value="hourly">每小时</option><option value="daily">每天</option></select></label><label className="strategy-meta-field"><small>自动化等级</small><select value={autoLevel} onChange={e => setAutoLevel(e.target.value)}><option value="L1">L1</option><option value="L2">L2</option><option value="L3">L3</option><option value="L4">L4</option></select></label></div><label className="strategy-enabled-toggle"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} /> 启用自动调度</label></section><section className="strategy-section"><div className="strategy-section-title"><span className="circle-icon circle-icon--cyan"><Icon name="database" size={18} /></span><div><h2>选择素材源</h2><p>决定 AI 从哪里开始寻找灵感</p></div></div><div className="source-choice-grid"><button type="button" className={sourceMode === "internal" ? "is-selected" : ""} onClick={() => setSourceMode("internal")}><strong>内部素材库</strong><span>从您已保存的文章和收集中提取灵感。</span>{selectedMaterial && <small className="selected-material-note">已选：{shortText(selectedMaterial.title, 34)}</small>}</button><button type="button" className={sourceMode === "realtime" ? "is-selected" : ""} onClick={() => setSourceMode("realtime")}><strong>全网实时搜索</strong><span>抓取最新热点和资讯作为创作基底。</span></button></div></section><section className="strategy-section"><div className="strategy-section-title"><span className="circle-icon circle-icon--pink"><Icon name="magic" size={18} /></span><div><h2>选择写作 Skill</h2><p>选择已发布的写作技能包</p></div></div><div className="skill-module-grid">{skills.map((item) => <button type="button" key={item.id} className={`skill-module ${skill === item.id ? "is-selected" : ""} ${item.status !== "published" ? "is-draft" : ""}`} aria-disabled={item.status !== "published"} onClick={() => { if (item.status === "published") setSkill(item.id); }}><span className="skill-module-icon"><Icon name="magic" size={16} /></span><span><strong>{item.name}</strong><small>{item.skill_type} · v{item.version}</small></span><em className={item.status === "published" ? "" : "skill-publish-control"} onClick={(event) => { if (item.status !== "published") { event.stopPropagation(); onPublishSkill(item.id); } }}>{item.status === "published" ? "可用" : "发布"}</em></button>)}{!skills.length && <div className="skill-empty">还没有已发布 Skill。</div>}</div></section><section className="strategy-section"><div className="strategy-section-title"><span className="circle-icon circle-icon--purple"><Icon name="robot" size={18} /></span><div><h2>选择写作模型</h2><p>选择驱动 AI 生成内容的大语言模型</p></div></div><div className="model-select-grid">{enabledModels.length ? enabledModels.map((item) => <button type="button" key={item.id} className={`model-card ${model === item.id ? "is-selected" : ""}`} onClick={() => setModel(item.id)}><span className="model-card-provider">{item.provider}</span><strong>{item.name}</strong><em>{model === item.id ? "✓" : ""}</em></button>) : <div className="skill-empty">还没有已启用的模型，请在「模型中心」标签页中添加。</div>}</div></section><section className="strategy-section"><div className="strategy-section-title"><span className="circle-icon circle-icon--cyan"><Icon name="image" size={18} /></span><div><h2>选择排版模板</h2><p>每张卡片展示真实主题配色和文章结构</p></div></div><div className="template-grid">{themes.filter((item) => item.enabled).map((item) => { const tokens = item.tokens as Record<string, string>; return <button type="button" key={item.id} className={theme === item.id ? "is-selected" : ""} onClick={() => setTheme(item.id)}><span className="theme-preview" style={{ background: tokens.surface || "#fff", color: tokens.text || "#222", borderColor: tokens.accent || "#e040a0" }}><i style={{ background: tokens.accent || "#e040a0" }} /><i style={{ background: tokens.muted || "#b7a8b8" }} /><b style={{ background: tokens.accent || "#e040a0" }} /><small style={{ background: tokens.muted || "#b7a8b8" }} /></span><strong>{item.name}</strong><small className="template-description">{shortText(item.description, 28)}</small>{theme === item.id && <em>✓</em>}</button>; })}{!themes.length && <div className="skill-empty">还没有可用排版模板。</div>}</div></section><section className="strategy-section"><div className="strategy-section-title"><span className="circle-icon circle-icon--pink"><Icon name="spark" size={18} /></span><div><h2>去 AI 味道调节</h2><p>控制文风的自然程度</p></div></div><div className="humanization-label"><span>更像 AI</span><strong>{humanization}%</strong><span>更像人类</span></div><input className="figma-range" type="range" min="0" max="100" value={humanization} onChange={(event) => setHumanization(Number(event.target.value))} /></section><div className="strategy-save-bar"><PillButton onClick={save}>保存策略组合</PillButton><PillButton tone="pink" onClick={() => { save(); if (current) onRun(current.id); }}>保存并立即执行 <Icon name="chevron" size={15} /></PillButton></div></div> : <div className="strategy-detail-empty"><div className="figma-empty"><Icon name="settings" size={28} /><strong>选择一个策略或新建策略</strong><span>从左侧列表选择已有策略进行编辑，或点击「+ 新建」创建一套新的内容生产组合。</span></div><PillButton tone="pink" onClick={onNew}><Icon name="edit" size={14} />新建策略组合</PillButton></div>}</div></section></main>;
}

export function FigmaConsole({ currentUser }: { currentUser: User }) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState<Page>("dashboard");
  const [editorReturnPage, setEditorReturnPage] = useState<"review" | "library">("review");
  const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null);
  const [selectedArticleId, setSelectedArticleId] = useState<string | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourceType, setSourceType] = useState<"rss" | "url" | "manual" | "aihot_api">("rss");
  const [topicOpen, setTopicOpen] = useState(false);
  const [topicTitle, setTopicTitle] = useState("");
  const [topicStrategyId, setTopicStrategyId] = useState("");
  const [selectedChannelId, setSelectedChannelId] = useState("");
  const [selectedThemeId, setSelectedThemeId] = useState("");
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [thumbMediaId, setThumbMediaId] = useState("");
  const [coverPreviewUrl, setCoverPreviewUrl] = useState("");
  const [deliveryError, setDeliveryError] = useState("");
  const [curationResult, setCurationResult] = useState<{ candidate_count: number; selected_count: number; selected_ids: string[]; selected_titles: string[]; message: string } | null>(null);
  const [settingsTab, setSettingsTab] = useState<"strategy" | "sources" | "models" | "channels" | "users">("strategy");
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [creatingStrategy, setCreatingStrategy] = useState(false);
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  const materials = useQuery({ queryKey: ["materials"], queryFn: () => api.materials(), refetchInterval: 10000 });
  const materialCategories = useQuery({ queryKey: ["material-categories"], queryFn: () => api.materialCategories(true) });
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics, refetchInterval: 8000 });
  const articles = useQuery({ queryKey: ["articles"], queryFn: api.articles, refetchInterval: 8000 });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const topicAlgorithms = useQuery({ queryKey: ["topic-algorithms"], queryFn: api.topicAlgorithms });
  const skills = useQuery({ queryKey: ["skills"], queryFn: api.skills });
  const themes = useQuery({ queryKey: ["themes"], queryFn: api.themes });
  const channels = useQuery({ queryKey: ["channel-accounts"], queryFn: api.channelAccounts });
  const users = useQuery({ queryKey: ["users"], queryFn: api.users, enabled: currentUser.role === "admin" });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.jobs, refetchInterval: 5000 });
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  useEffect(() => { if (!selectedChannelId && channels.data?.[0]) setSelectedChannelId(channels.data[0].id); }, [channels.data, selectedChannelId]);
  useEffect(() => { if (!selectedThemeId && themes.data?.[0]) setSelectedThemeId(themes.data[0].id); }, [selectedThemeId, themes.data]);
  useEffect(() => { if (!selectedSkillId && skills.data?.[0]) setSelectedSkillId(skills.data[0].id); }, [selectedSkillId, skills.data]);
  useEffect(() => { if (!creatingStrategy && !selectedStrategyId && strategies.data?.[0]) setSelectedStrategyId(strategies.data[0].id); }, [creatingStrategy, selectedStrategyId, strategies.data]);
  const refresh = (...keys: string[]) => Promise.all(keys.map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
  const triage = useMutation({ mutationFn: ({ id, decision }: { id: string; decision: "save" | "ignore" | "reopen" }) => api.triageMaterial(id, decision), onSuccess: () => void refresh("materials"), onError: (error: Error) => message.error(error.message) });
  const collectSources = useMutation({ mutationFn: async (ids: string[]) => { const results = await Promise.all(ids.map((id) => api.collectSource(id))); return results.reduce((total, result) => ({ count: total.count + result.count, classified: total.classified + result.classified_count, failed: total.failed + result.classification_failed_count }), { count: 0, classified: 0, failed: 0 }); }, onSuccess: (result) => { message.success(`采集完成：素材 ${result.count} 条，AI 已分类 ${result.classified} 条${result.failed ? `，${result.failed} 条分类待重试` : ""}`); void refresh("sources", "materials", "material-categories", "dashboard"); }, onError: (error: Error) => message.error(`采集失败：${error.message}`) });
  const curateMaterials = useMutation({ mutationFn: (strategyId: string) => api.curateMaterials({ strategy_id: strategyId, limit: 12 }), onSuccess: (result) => { setCurationResult(result); message.success(result.message); void refresh("materials", "dashboard"); }, onError: (error: Error) => message.error(`AI 精选失败：${error.message}`) });
  const classifyMaterials = useMutation({ mutationFn: (ids?: string[]) => api.classifyMaterials({ material_ids: ids || [], retry_failed: true }), onSuccess: (result) => { message.success(result.message); void refresh("materials", "material-categories"); }, onError: (error: Error) => message.error(`AI 分类失败：${error.message}`) });
  const assignMaterialCategory = useMutation({ mutationFn: ({ id, categoryId }: { id: string; categoryId: string | null }) => api.assignMaterialCategory(id, categoryId), onSuccess: () => void refresh("materials", "material-categories"), onError: (error: Error) => message.error(error.message) });
  const addMaterialCategory = useMutation({ mutationFn: (payload: { name: string; description?: string; classification_instructions?: string }) => api.addMaterialCategory(payload), onSuccess: () => { message.success("素材分类已添加"); void refresh("material-categories"); }, onError: (error: Error) => message.error(error.message) });
  const updateMaterialCategory = useMutation({ mutationFn: ({ id, payload }: { id: string; payload: Partial<Pick<MaterialCategory, "name" | "description" | "classification_instructions" | "enabled">> }) => api.updateMaterialCategory(id, payload), onSuccess: () => { message.success("素材分类已更新"); void refresh("material-categories", "materials"); }, onError: (error: Error) => message.error(error.message) });
  const disableMaterialCategory = useMutation({ mutationFn: api.disableMaterialCategory, onSuccess: () => { message.success("素材分类已停用，历史素材仍然保留"); void refresh("material-categories"); }, onError: (error: Error) => message.error(error.message) });
  const restoreMaterialCategory = useMutation({ mutationFn: api.restoreMaterialCategory, onSuccess: () => { message.success("素材分类已恢复"); void refresh("material-categories"); }, onError: (error: Error) => message.error(error.message) });
  const createFromMaterials = useMutation({
    mutationFn: async (payload: { materialIds: string[]; strategyId: string; title?: string; skillId: string }) => {
      const topic = await api.createTopicFromMaterials({
        material_ids: payload.materialIds,
        strategy_id: payload.strategyId,
        title: payload.title,
      });
      await api.decideTopic(topic.id, "accept");
      const startPayload: { writing_skill_id?: string; disable_writing_skill?: boolean } = {};
      if (payload.skillId === "none") startPayload.disable_writing_skill = true;
      else if (payload.skillId) startPayload.writing_skill_id = payload.skillId;
      return api.startTopicWriting(topic.id, startPayload);
    },
    onSuccess: () => {
      message.success("创作任务已启动，完成后会进入待审核");
      void refresh("materials", "topics", "jobs", "articles");
      setPage("review");
    },
    onError: (error: Error) => message.error(error.message),
  });
  const scanTopics = useMutation({
    mutationFn: ({ strategyId, algorithmId }: { strategyId: string; algorithmId: string }) => api.scanStrategy(strategyId, algorithmId),
    onSuccess: () => {
      message.success("扫描任务已启动，AI 正在分析素材并推荐选题");
      void refresh("jobs", "topics", "materials");
    },
    onError: (error: Error) => message.error(error.message),
  });
  const saveTopicMaterials = useMutation({
    mutationFn: (topic: Topic) => Promise.all(topic.materials.map((material) => api.triageMaterial(material.source_item_id, "save"))),
    onSuccess: () => { void refresh("materials"); message.success("关联素材已保留到素材池"); },
    onError: (error: Error) => message.error(error.message),
  });
  const acceptTopic = useMutation({ mutationFn: async (topic: Topic) => { if (topic.status === "candidate") await api.decideTopic(topic.id, "accept"); return api.startTopicWriting(topic.id); }, onSuccess: () => { message.success("写作任务已进入后台，生成完成后会出现在待审核"); void refresh("topics", "jobs", "articles"); }, onError: (error: Error) => message.error(error.message) });
  const createTopic = useMutation({ mutationFn: () => api.addTopic({ title: topicTitle, strategy_id: topicStrategyId, rationale: "由运营人员手动创建" }), onSuccess: () => { setTopicOpen(false); setTopicTitle(""); void refresh("topics"); message.success("选题已创建"); }, onError: (error: Error) => message.error(error.message) });
  const addSource = useMutation({ mutationFn: (payload: { name: string; source_type: "rss" | "url" | "aihot_api"; url?: string; category?: string }) => api.addSource({ name: payload.name, source_type: payload.source_type, url: payload.url || "", config: payload.category ? { category: payload.category } : {} }), onSuccess: () => { setSourceOpen(false); void refresh("sources", "dashboard"); message.success("信息源已添加"); }, onError: (error: Error) => message.error(error.message) });
  const addRecommendedSource = useMutation({ mutationFn: (source: RecommendedSource) => api.addSource({ name: source.name, source_type: source.source_type, url: source.url }), onSuccess: () => { void refresh("sources", "dashboard"); message.success("推荐信息源已添加"); }, onError: (error: Error) => message.error(error.message) });  const addManualMaterial = useMutation({ mutationFn: (payload: { title: string; content: string; source_name?: string }) => api.addManualMaterial(payload), onSuccess: () => { setSourceOpen(false); void refresh("sources", "materials", "dashboard"); message.success("手动素材已加入素材池"); }, onError: (error: Error) => message.error(error.message) });
  const createTopicAlgorithm = useMutation({ mutationFn: api.addTopicAlgorithm, onSuccess: () => { void refresh("topic-algorithms"); message.success("选题算法已创建"); }, onError: (error: Error) => message.error(error.message) });
  const updateTopicAlgorithm = useMutation({ mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof api.updateTopicAlgorithm>[1] }) => api.updateTopicAlgorithm(id, payload), onSuccess: () => { void refresh("topic-algorithms"); message.success("选题算法已保存"); }, onError: (error: Error) => message.error(error.message) });
  const deleteTopicAlgorithm = useMutation({ mutationFn: api.deleteTopicAlgorithm, onSuccess: () => { void refresh("topic-algorithms"); message.success("选题算法已删除"); }, onError: (error: Error) => message.error(error.message) });
  const collectSource = useMutation({ mutationFn: api.collectSource, onSuccess: (result) => { message.success("已采集 " + result.count + " 条素材"); void refresh("sources", "materials"); }, onError: (error: Error) => message.error(error.message) });
  const updateSource = useMutation({ mutationFn: ({ id, source }: { id: string; source: Source }) => api.updateSource(id, source), onSuccess: () => { message.success("信息源已更新"); void refresh("sources", "dashboard"); }, onError: (error: Error) => message.error(error.message) });
  const disableSource = useMutation({ mutationFn: api.disableSource, onSuccess: () => { message.success("信息源已停用"); void refresh("sources", "dashboard"); }, onError: (error: Error) => message.error(error.message) });
  const importSkill = useMutation({ mutationFn: api.importSkill, onSuccess: () => { void refresh("skills"); message.success("Skill 导入成功，请在已发布列表中选择"); }, onError: (error: Error) => message.error(error.message) });
  const publishSkill = useMutation({ mutationFn: api.publishSkill, onSuccess: () => { void refresh("skills"); message.success("Skill 已发布，现在可以切换使用"); }, onError: (error: Error) => message.error(error.message) });
  const addModel = useMutation({ mutationFn: (p: ModelFormPayload) => api.addModel({ provider: p.provider, name: p.name, api_base_url: p.api_base_url || undefined, api_key: p.api_key || undefined }), onSuccess: () => { void refresh("models"); message.success("模型已添加"); }, onError: (error: Error) => message.error(error.message) });
  const updateModel = useMutation({ mutationFn: ({ id, p }: { id: string; p: Partial<ModelFormPayload> & { enabled?: boolean } }) => api.updateModel(id, { provider: p.provider, name: p.name, api_base_url: p.api_base_url, api_key: p.api_key || undefined, enabled: p.enabled }), onSuccess: () => { void refresh("models"); message.success("模型已更新"); }, onError: (error: Error) => message.error(error.message) });
  const testModel = useMutation({ mutationFn: api.testModel, onSuccess: (result) => result.ok ? message.success(result.message) : message.warning(result.message), onError: (error: Error) => message.error(error.message) });
  const deleteModel = useMutation({ mutationFn: api.deleteModel, onSuccess: () => { void refresh("models", "strategies"); message.success("模型已删除"); }, onError: (error: Error) => message.error(error.message) });
  const addChannel = useMutation({ mutationFn: api.addChannelAccount, onSuccess: () => { void refresh("channel-accounts"); message.success("公众号已绑定"); }, onError: (error: Error) => message.error(error.message) });
  const updateChannel = useMutation({ mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof api.updateChannelAccount>[1] }) => api.updateChannelAccount(id, payload), onSuccess: () => { void refresh("channel-accounts"); message.success("公众号账号已更新"); }, onError: (error: Error) => message.error(error.message) });
  const testChannel = useMutation({ mutationFn: api.testChannelAccount, onSuccess: (result) => result.connected ? message.success(result.message) : message.warning(result.message), onError: (error: Error) => message.error(error.message) });
  const disableChannel = useMutation({ mutationFn: api.disableChannelAccount, onSuccess: () => { void refresh("channel-accounts"); message.success("公众号账号已停用"); }, onError: (error: Error) => message.error(error.message) });
  const addUser = useMutation({ mutationFn: api.addUser, onSuccess: () => { void refresh("users"); message.success("用户已添加"); }, onError: (error: Error) => message.error(error.message) });  const saveStrategy = useMutation({ mutationFn: ({ id, payload }: { id?: string; payload: StrategySavePayload }) => id ? api.updateStrategy(id, { name: payload.name, objective: payload.objective, schedule: payload.schedule, automation_level: payload.automation_level, enabled: payload.enabled, config: payload.config }) : api.addStrategy({ name: payload.name, objective: payload.objective, schedule: payload.schedule, automation_level: payload.automation_level, enabled: payload.enabled, config: payload.config }), onSuccess: (result) => { void refresh("strategies"); setSelectedStrategyId(result.id); setCreatingStrategy(false); message.success("策略已保存"); }, onError: (error: Error) => message.error(error.message) });
  const runStrategy = useMutation({ mutationFn: ({ id, combinationId }: { id: string; combinationId?: string }) => api.runStrategy(id, combinationId), onSuccess: () => { message.success("自动化任务已启动：将自动采集、分类、精选、选题、写作、审核并按交付模式处理"); void refresh("jobs", "articles", "materials", "topics"); }, onError: (error: Error) => message.error(error.message) });
  const retryJob = useMutation({ mutationFn: api.retryJob, onSuccess: () => { message.success("任务已重新进入队列"); void refresh("jobs", "articles"); }, onError: (error: Error) => message.error(error.message) });
  const reviewArticle = useMutation({
    mutationFn: ({ article, decision }: { article: Article; decision: "approve" | "request_changes" }) => {
      const revision = article.revisions[article.revisions.length - 1];
      if (!revision) throw new Error("当前文章没有可审核版本");
      return api.reviewArticle(article.id, revision.id, decision, decision === "approve" ? "审核通过" : "请补充事实依据并优化表达");
    },
    onSuccess: (_, variables) => {
      if (variables.decision === "approve") {
        queryClient.setQueryData<Article[]>(["articles"], (current) => current?.map((item) => item.id === variables.article.id ? { ...item, status: "approved" } : item));
        setSelectedArticleId(variables.article.id);
        setPage("library");
        message.success("审核通过，文章已移入成稿库");
      } else {
        message.success("文章已退回修改");
      }
      void refresh("articles", "jobs");
    },
    onError: (error: Error) => message.error(error.message),
  });
  const saveRevision = useMutation({ mutationFn: ({ articleId, title, markdown }: { articleId: string; title: string; markdown: string }) => api.addRevision(articleId, markdown, title), onSuccess: () => { void refresh("articles", "jobs"); message.success("新版本已保存并送回待审核"); setPage("review"); }, onError: (error: Error) => message.error(error.message) });
  const archiveArticle = useMutation({ mutationFn: api.archiveArticle, onSuccess: () => { setSelectedArticleId(null); void refresh("articles", "dashboard"); message.success("文章已从本地成稿库归档" ); }, onError: (error: Error) => message.error(error.message) });
  const uploadThumb = useMutation({ mutationFn: (file: File) => { setDeliveryError(""); const blobUrl = URL.createObjectURL(file); setCoverPreviewUrl(blobUrl); return api.uploadWechatThumb(file, selectedChannelId || undefined); }, onSuccess: (result) => { setThumbMediaId(result.media_id); message.success("封面上传成功"); }, onError: (error: Error) => { setDeliveryError(error.message); message.error("封面上传失败，请查看交付设置中的处理方法"); } });
  const createDraft = useMutation({ mutationFn: (article: Article) => { setDeliveryError(""); const revision = article.revisions[article.revisions.length - 1]; if (!revision) throw new Error("当前文章没有可发布版本"); const payload = { thumb_media_id: thumbMediaId, channel_account_id: selectedChannelId || undefined, theme_id: selectedThemeId || undefined }; return article.status === "wechat_draft" ? api.updateWechatDraft(article.id, revision.id, payload) : api.createWechatDraft(article.id, revision.id, payload); }, onSuccess: () => { void refresh("articles", "publications"); message.success("微信草稿已写入"); }, onError: (error: Error) => { setDeliveryError(error.message); message.error("微信草稿写入失败，请查看交付设置中的处理方法"); } });
  const publishDraft = useMutation({ mutationFn: (article: Article) => { const revision = article.revisions[article.revisions.length - 1]; if (!revision) throw new Error("当前文章没有可发布版本"); if (!selectedChannelId) throw new Error("请先选择发布账号"); return api.publishWechatDraft(article.id, revision.id, selectedChannelId); }, onSuccess: () => { void refresh("articles", "publications"); message.success("已提交微信发布"); }, onError: (error: Error) => message.error(error.message) });
  const search = (value: string) => { const term = value.trim().toLowerCase(); if (!term) return; const material = materials.data?.find((item) => item.title.toLowerCase().includes(term)); if (material) { setSelectedMaterialId(material.id); setPage("materials"); return; } const article = articles.data?.find((item) => item.title.toLowerCase().includes(term)); if (article) { setSelectedArticleId(article.id); setPage("review"); return; } message.info("没有找到匹配内容"); };
  const selectedMaterial = materials.data?.find((item) => item.id === selectedMaterialId);
  const selectedArticle = articles.data?.find((item) => item.id === selectedArticleId);
  const libraryPreviewArticle = useMemo(() => {
    const library = (articles.data ?? []).filter((article) =>
      ["approved", "drafted", "wechat_draft", "publishing", "published"].includes(article.status) && hasFinalArticleBody(article),
    );
    return library.find((article) => article.id === selectedArticleId) ?? library[0];
  }, [articles.data, selectedArticleId]);
  const libraryPreviewRevision = libraryPreviewArticle?.revisions?.[(libraryPreviewArticle.revisions?.length ?? 1) - 1];
  const libraryThemeId = useMemo(() => {
    const snapshot = libraryPreviewArticle?.runtime_snapshot || {};
    const theme = snapshot.theme as { id?: unknown } | undefined;
    const execution = snapshot.execution_config as { theme_id?: unknown } | undefined;
    return typeof theme?.id === "string"
      ? theme.id
      : typeof execution?.theme_id === "string"
        ? execution.theme_id
        : "";
  }, [libraryPreviewArticle]);
  useEffect(() => {
    if (page === "library" && libraryThemeId && libraryThemeId !== selectedThemeId) {
      setSelectedThemeId(libraryThemeId);
    }
  }, [libraryThemeId, page]);
  const themePreview = useQuery({
    queryKey: ["theme-preview", libraryPreviewArticle?.id, libraryPreviewRevision?.id, selectedThemeId],
    queryFn: () => api.previewTheme(libraryPreviewArticle!.id, libraryPreviewRevision!.id, selectedThemeId),
    enabled: page === "library" && Boolean(libraryPreviewArticle && libraryPreviewRevision && selectedThemeId),
  });
  const content = useMemo(() => {
    if (page === "dashboard") return <Dashboard materials={materials.data || []} topics={topics.data || []} articles={articles.data || []} jobs={jobs.data || []} sourcesCount={dashboard.data?.sources || 0} onNavigate={setPage} onOpenReview={(id) => { setSelectedArticleId(id); setPage("review"); }} />;
    if (page === "materials") return <MaterialWorkspace materials={materials.data || []} categories={materialCategories.data || []} loadError={[materials.error, materialCategories.error].filter((error): error is Error => error instanceof Error).map((error) => error.message).join("；")} sources={sources.data || []} skills={skills.data || []} strategies={strategies.data || []} curationResult={curationResult} creating={createFromMaterials.isPending} onCreate={(payload) => createFromMaterials.mutate(payload)} onManageSources={() => { setSettingsTab("sources"); setPage("settings"); }} onManageStrategies={() => { setSettingsTab("strategy"); setPage("settings"); }} onCollect={(ids) => collectSources.mutate(ids)} collecting={collectSources.isPending} onCurate={(strategyId) => curateMaterials.mutate(strategyId)} curating={curateMaterials.isPending} onClassify={(ids) => classifyMaterials.mutate(ids)} classifying={classifyMaterials.isPending} onTriage={(id, decision) => triage.mutate({ id, decision })} onAssignCategory={(id, categoryId) => assignMaterialCategory.mutate({ id, categoryId })} onAddCategory={(payload) => addMaterialCategory.mutateAsync(payload)} onUpdateCategory={(id, payload) => updateMaterialCategory.mutateAsync({ id, payload })} onDisableCategory={(id) => disableMaterialCategory.mutateAsync(id)} onRestoreCategory={(id) => restoreMaterialCategory.mutateAsync(id)} />;
    if (page === "topics") return <TopicRadar topics={topics.data || []} strategies={strategies.data || []} algorithms={topicAlgorithms.data || []} scanning={scanTopics.isPending} writing={acceptTopic.isPending} managingAlgorithms={createTopicAlgorithm.isPending || updateTopicAlgorithm.isPending || deleteTopicAlgorithm.isPending} onScan={(strategyId, algorithmId) => scanTopics.mutate({ strategyId, algorithmId })} onWrite={(topic) => acceptTopic.mutate(topic)} onDismiss={(topic) => { void api.decideTopic(topic.id, "reject").then(() => refresh("topics", "materials")).catch((error: Error) => message.error(error.message)); }} onSaveMaterials={(topic) => saveTopicMaterials.mutate(topic)} onCreateAlgorithm={(payload) => createTopicAlgorithm.mutateAsync(payload)} onUpdateAlgorithm={(id, payload) => updateTopicAlgorithm.mutateAsync({ id, payload })} onDeleteAlgorithm={(id) => deleteTopicAlgorithm.mutateAsync(id)} />;
    if (page === "review") return <ReviewQueue articles={articles.data || []} jobs={jobs.data || []} selectedId={selectedArticleId} pending={reviewArticle.isPending} retrying={retryJob.isPending} onSelect={setSelectedArticleId} onApprove={(article) => reviewArticle.mutate({ article, decision: "approve" })} onChanges={(article) => reviewArticle.mutate({ article, decision: "request_changes" })} onEdit={(id) => { setSelectedArticleId(id); setEditorReturnPage("review"); setPage("editor"); }} onRetry={(id) => retryJob.mutate(id)} />;
    if (page === "library") return <ArticleLibrary articles={articles.data || []} selectedId={selectedArticleId} themes={themes.data || []} channels={channels.data || []} selectedThemeId={selectedThemeId} selectedChannelId={selectedChannelId} thumbMediaId={thumbMediaId} coverPreviewUrl={coverPreviewUrl} themePreviewHtml={themePreview.data?.html || ""} themePreviewLoading={themePreview.isLoading} themePreviewError={themePreview.error instanceof Error ? themePreview.error.message : ""} pending={createDraft.isPending || uploadThumb.isPending || archiveArticle.isPending} deliveryError={deliveryError} onSelect={(id) => { setSelectedArticleId(id); setDeliveryError(""); }} onEdit={(id) => { setSelectedArticleId(id); setEditorReturnPage("library"); setPage("editor"); }} onArchive={(article) => archiveArticle.mutate(article.id)} onThemeChange={setSelectedThemeId} onChannelChange={(id) => { setSelectedChannelId(id); setThumbMediaId(""); setDeliveryError(""); }} onUpload={(file) => uploadThumb.mutate(file)} onDraft={(article) => createDraft.mutate(article)} />;
    if (page === "editor") return <ArticleEditor article={selectedArticle} onBack={() => setPage(editorReturnPage)} onSave={(articleId, title, markdown) => saveRevision.mutate({ articleId, title, markdown })} saving={saveRevision.isPending} />;
    if (page === "settings") return (
      <div>
        <div className="figma-page" style={{ paddingBottom: 0 }}>
          <div className="figma-tabs">
            <button className={settingsTab === "strategy" ? "is-active" : ""} type="button" onClick={() => setSettingsTab("strategy")}>自动化生产线</button>
            <button className={settingsTab === "sources" ? "is-active" : ""} type="button" onClick={() => setSettingsTab("sources")}>信息源 <b>{sources.data?.length || 0}</b></button>
            <button className={settingsTab === "models" ? "is-active" : ""} type="button" onClick={() => setSettingsTab("models")}>模型中心 <b>{models.data?.length || 0}</b></button>
            <button className={settingsTab === "channels" ? "is-active" : ""} type="button" onClick={() => setSettingsTab("channels")}>公众号账号 <b>{channels.data?.length || 0}</b></button>
            {currentUser.role === "admin" && <button className={settingsTab === "users" ? "is-active" : ""} type="button" onClick={() => setSettingsTab("users")}>用户中心 <b>{users.data?.length || 0}</b></button>}
          </div>
        </div>
        {settingsTab === "strategy" ? (
          <StrategyPipelinePage strategies={strategies.data || []} selectedId={creatingStrategy ? null : selectedStrategyId} onSelect={(id) => { setCreatingStrategy(false); setSelectedStrategyId(id); }} onNew={() => { setCreatingStrategy(true); setSelectedStrategyId(null); }} categories={materialCategories.data || []} skills={skills.data || []} themes={themes.data || []} models={models.data || []} channels={channels.data || []} onSave={(id, payload) => saveStrategy.mutateAsync({ id, payload })} onRun={(id, combinationId) => runStrategy.mutateAsync({ id, combinationId })} onManageMaterials={() => setPage("materials")} onUploadThumb={async (file, channelId) => (await api.uploadWechatThumb(file, channelId)).media_id} onImportSkill={async (file) => { await importSkill.mutateAsync(file); }} importingSkill={importSkill.isPending} />
        ) : settingsTab === "sources" ? (
          <SourceCenter sources={sources.data || []} onAdd={() => setSourceOpen(true)} onAddRecommended={async (source) => { await addRecommendedSource.mutateAsync(source); }} onCollect={async (id) => { await collectSource.mutateAsync(id); }} onUpdate={async (id, source) => { await updateSource.mutateAsync({ id, source }); }} onDisable={async (id) => { await disableSource.mutateAsync(id); }} />
        ) : settingsTab === "models" ? (          <ModelCenter models={models.data || []} onAdd={async (p) => { await addModel.mutateAsync(p); }} onUpdate={async (id, p) => { await updateModel.mutateAsync({ id, p }); }} onTest={(id) => testModel.mutate(id)} onDelete={async (id) => { await deleteModel.mutateAsync(id); }} />
        ) : settingsTab === "channels" ? (
          <ChannelCenter accounts={channels.data || []} onAdd={async (payload) => { await addChannel.mutateAsync(payload); }} onUpdate={async (id, { name, app_id, app_secret, enabled }) => { await updateChannel.mutateAsync({ id, payload: { name, app_id, app_secret, enabled } }); }} onTest={(id) => testChannel.mutate(id)} onDisable={async (id) => { await disableChannel.mutateAsync(id); }} />
        ) : (
          <UserCenter users={users.data || []} onAdd={async (payload) => { await addUser.mutateAsync(payload); }} />
        )}
      </div>
    );
  }, [acceptTopic, archiveArticle, articles.data, channels.data, coverPreviewUrl, createDraft, createFromMaterials, dashboard.data, deliveryError, editorReturnPage, jobs.data, materialCategories.data, materialCategories.error, materials.data, materials.error, models.data, page, publishDraft, reviewArticle, saveTopicMaterials, scanTopics, selectedArticleId, selectedChannelId, selectedMaterialId, selectedSkillId, selectedStrategyId, selectedThemeId, settingsTab, skills.data, sources.data, sourceType, strategies.data, themes.data, themePreview.data?.html, thumbMediaId, topicAlgorithms.data, topics.data, triage, updateTopicAlgorithm, users.data, updateSource, uploadThumb, collectSources, curateMaterials, classifyMaterials, assignMaterialCategory, addMaterialCategory, updateMaterialCategory, disableMaterialCategory, restoreMaterialCategory, retryJob]);
  return <div className="figma-console"><FigmaSidebar page={page} onNavigate={setPage} onCreate={() => { setPage("topics"); setTopicOpen(true); }} onHelp={() => message.info("帮助中心：先筛选素材，再确认选题、配置策略并审核发布。")} onLogout={() => { void api.logout().then(() => window.location.reload()).catch((error: Error) => message.error(error.message)); }} /><div className="figma-main"><FigmaTopbar page={page} user={currentUser} notificationCount={(jobs.data || []).filter((item) => item.status.startsWith("failed") || item.status === "waiting_review").length} onSearch={search} onLogout={() => { void api.logout().then(() => window.location.reload()).catch((error: Error) => message.error(error.message)); }} />{content}</div>{(sourceOpen || topicOpen) && <div className="figma-modal-backdrop"><div className="figma-modal"><button className="modal-close" type="button" aria-label="关闭" onClick={() => { setSourceOpen(false); setTopicOpen(false); }}><Icon name="close" size={18} /></button>{sourceOpen ? <><span className="eyebrow">SOURCE</span><h2>{sourceType === "manual" ? "粘贴手动素材" : "添加信息源"}</h2><p>{sourceType === "manual" ? "直接粘贴一条素材，保存后立即进入素材池，无需再等待采集。" : sourceType === "rss" ? "添加一个 RSS 订阅地址，系统会按生产线的频率采集新内容。" : sourceType === "aihot_api" ? "接入 AI HOT 最近 24 小时精选资讯，按官方分类自动入库。" : "添加一个网页或栏目页地址，系统会扫描页面正文并送入待筛选素材。"}</p><form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); if (sourceType === "manual") { const title = String(form.get("title") || "").trim(); const content = String(form.get("content") || "").trim(); const sourceName = String(form.get("source_name") || "手动录入").trim(); if (!title || !content) { message.error("请填写素材标题和正文。"); return; } addManualMaterial.mutate({ title, content, source_name: sourceName || "手动录入" }); return; } const name = String(form.get("name") || "").trim(); const url = String(form.get("url") || "").trim(); const category = String(form.get("category") || "").trim() || undefined; if (!name || (sourceType !== "aihot_api" && !url)) { message.error(sourceType === "aihot_api" ? "请填写信息源名称。" : "请填写信息源名称和地址。"); return; } addSource.mutate({ name, source_type: sourceType, url, category }); }}><label>类型<select value={sourceType} onChange={(event) => setSourceType(event.target.value as "rss" | "url" | "manual" | "aihot_api")}><option value="rss">RSS 订阅</option><option value="url">网页 URL</option><option value="aihot_api">AI HOT API（24h 精选）</option><option value="manual">手动粘贴素材</option></select></label>{sourceType === "manual" ? <><label>素材标题<input name="title" required placeholder="这条素材讲什么？" /></label><label>素材正文<textarea name="content" required placeholder="粘贴完整正文、摘录或你的想法…" /></label><label>来源标签（可选）<input name="source_name" placeholder="例如：我的观察" /></label></> : sourceType === "aihot_api" ? <><label>信息源名称<input name="name" required placeholder="例如：AI HOT 24h 精选" /></label><label>分类（可选）<select name="category"><option value="">全部分类</option><option value="ai-models">AI 模型</option><option value="ai-products">AI 产品</option><option value="industry">行业动态</option><option value="paper">论文</option><option value="tip">技巧</option></select></label></> : <><label>信息源名称<input name="name" required placeholder={sourceType === "rss" ? "例如：36氪 RSS" : "例如：MIT Technology Review"} /></label><label>{sourceType === "rss" ? "RSS 地址" : "网页地址"}<input name="url" type="url" required placeholder="https://..." /></label></>}<PillButton type="submit" tone="pink">{sourceType === "manual" ? "加入素材池" : "添加信息源"}</PillButton></form></> : <><span className="eyebrow">NEW TOPIC</span><h2>创建候选选题</h2><p>先确认选题，再进入 AI 创作流程。</p><form onSubmit={(event) => { event.preventDefault(); createTopic.mutate(); }}><label>选题标题<input value={topicTitle} onChange={(event) => setTopicTitle(event.target.value)} required placeholder="输入一个值得创作的选题" /></label><label>所属策略<select value={topicStrategyId} onChange={(event) => setTopicStrategyId(event.target.value)} required><option value="">请选择策略</option>{(strategies.data || []).map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.name}</option>)}</select></label><PillButton type="submit" tone="pink">创建候选选题</PillButton></form></>}</div></div>}{selectedMaterial && null}</div>;
}
