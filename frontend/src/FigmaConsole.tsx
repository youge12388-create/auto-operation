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
  return <main className="figma-page topics-page"><div className="figma-page-heading"><div><h1>选题与创作</h1><p>浏览 AI 为您量身定制的热门选题，或直接开始创作。</p></div><PillButton tone="pink" onClick={onNew}><Icon name="edit" size={16} />手动创建选题</PillButton></div><div className="figma-tabs"><button className="is-active" type="button">候选选题 <b>{candidate.length || 12}</b></button><button type="button" onClick={onEditor}>文章创作 <b>→</b></button></di…18155 tokens truncated…egies"); setSelectedStrategyId(result.id); setCreatingStrategy(false); message.success("策略已保存"); }, onError: (error: Error) => message.error(error.message) });
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
    if (page === "materials") return <MaterialWorkspace materials={materials.data || []} categories={materialCategories.data || []} loadError={[materials.error, materialCategories.error].filter((error): error is Error => error instanceof Error).map((error) => error.message).join("；")} sources={sources.data || []} skills={skills.data || []} strategies={strategies.data || []} curationResult={curationResult} creating={createFromMaterials.isPending} onCreate={(payload) => createFromMaterials.mutate(payload)} onManageSources={() => { setSettingsTab("sources"); setPage("settings"); }} onCollect={(ids) => collectSources.mutate(ids)} collecting={collectSources.isPending} onCurate={(strategyId) => curateMaterials.mutate(strategyId)} curating={curateMaterials.isPending} onClassify={(ids) => classifyMaterials.mutate(ids)} classifying={classifyMaterials.isPending} onTriage={(id, decision) => triage.mutate({ id, decision })} onAssignCategory={(id, categoryId) => assignMaterialCategory.mutate({ id, categoryId })} onAddCategory={(payload) => addMaterialCategory.mutateAsync(payload)} onUpdateCategory={(id, payload) => updateMaterialCategory.mutateAsync({ id, payload })} onDisableCategory={(id) => disableMaterialCategory.mutateAsync(id)} onRestoreCategory={(id) => restoreMaterialCategory.mutateAsync(id)} />;
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
          <StrategyPipelinePage strategies={strategies.data || []} selectedId={creatingStrategy ? null : selectedStrategyId} onSelect={(id) => { setCreatingStrategy(false); setSelectedStrategyId(id); }} onNew={() => { setCreatingStrategy(true); setSelectedStrategyId(null); }} categories={materialCategories.data || []} skills={skills.data || []} themes={themes.data || []} models={models.data || []} channels={channels.data || []} onSave={(id, payload) => saveStrategy.mutateAsync({ id, payload })} onRun={(id, combinationId) => runStrategy.mutateAsync({ id, combinationId })} onManageMaterials={() => setPage("materials")} onImportSkill={async (file) => { await importSkill.mutateAsync(file); }} importingSkill={importSkill.isPending} />
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