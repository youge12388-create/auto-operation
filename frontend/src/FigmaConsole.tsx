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
      { name: "gpt-5.2", label: "GPT-5.2 Â· ä¸»åŠ›å†™ä½œ" },
      { name: "gpt-5.1", label: "GPT-5.1 Â· ç¨³å®š" },
      { name: "gpt-5-mini", label: "GPT-5 mini Â· å¿«é€Ÿçœæˆæœ¬" },
    ],
  },
  deepseek: {
    label: "DeepSeek",
    provider: "openai-compatible",
    apiBaseUrl: "https://api.deepseek.com",
    models: [
      { name: "deepseek-v4-flash", label: "DeepSeek V4 Flash Â· å¿«é€Ÿ" },
      { name: "deepseek-v4-pro", label: "DeepSeek V4 Pro Â· æ·±åº¦åˆ›ä½œ" },
    ],
  },
  zhipu: {
    label: "æ™ºè°± GLM",
    provider: "openai-compatible",
    apiBaseUrl: "https://open.bigmodel.cn/api/paas/v4",
    models: [
      { name: "glm-5.2", label: "GLM-5.2 Â· æ——èˆ°" },
      { name: "glm-4.7", label: "GLM-4.7 Â· é€šç”¨" },
      { name: "glm-4.7-flash", label: "GLM-4.7 Flash Â· å¿«é€Ÿ" },
    ],
  },
  anthropic: {
    label: "Anthropic Claude",
    provider: "anthropic",
    apiBaseUrl: "https://api.anthropic.com/v1",
    models: [
      { name: "claude-opus-4-20250514", label: "Claude Opus 4 Â· é«˜è´¨é‡" },
      { name: "claude-sonnet-4-20250514", label: "Claude Sonnet 4 Â· å¹³è¡¡" },
    ],
  },
  custom: { label: "å…¶ä»–å…¼å®¹æ¥å£", provider: "openai-compatible", apiBaseUrl: "", models: [] },
  fake: { label: "æœ¬åœ°æµ‹è¯•", provider: "fake", apiBaseUrl: "", models: [{ name: "fake", label: "Fake Â· ä¸è°ƒç”¨å¤–éƒ¨æœåŠ¡" }] },
};

const MODEL_VENDOR_OPTIONS: Array<{ value: ModelVendor; label: string }> = [
  { value: "openai", label: "OpenAI" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "zhipu", label: "æ™ºè°± GLM" },
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "custom", label: "å…¶ä»–å…¼å®¹æ¥å£" },
  { value: "fake", label: "æœ¬åœ°æµ‹è¯•" },
];
const NAV: Array<{ key: Page; label: string; icon: IconName }> = [
  { key: "dashboard", label: "å·¥ä½œå°", icon: "home" },
  { key: "materials", label: "ç´ ææ± ", icon: "image" },
  { key: "topics", label: "é€‰é¢˜é›·è¾¾", icon: "topic" },
  { key: "review", label: "å¾…å®¡æ ¸", icon: "review" },
  { key: "library", label: "æˆç¨¿åº“", icon: "article" },
  { key: "settings", label: "è‡ªåŠ¨åŒ–", icon: "settings" },
];

function formatTime(value?: string | null) {
  if (!value) return "åˆšåˆš";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "åˆšåˆš";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(date).replaceAll("/", "-");
}

function shortText(value: string, length = 82) {
  return value.length > length ? `${value.slice(0, length)}â€¦` : value;
}

function Empty({ title }: { title: string }) {
  return <div className="figma-empty"><Icon name="spark" size={22} /><strong>{title}</strong><span>å½“å‰è¿˜æ²¡æœ‰å¯å±•ç¤ºçš„å†…å®¹</span></div>;
}

function FigmaSidebar({ page, onNavigate, onCreate, onHelp, onLogout }: { page: Page; onNavigate: (page: Page) => void; onCreate: () => void; onHelp: () => void; onLogout: () => void }) {
  return <aside className="figma-sidebar">
    <div className="figma-brand"><span className="figma-brand-mark"><Icon name="robot" size={23} /></span><span><strong>Content Ops</strong><small>å†…å®¹è¿è¥å·¥ä½œå°</small></span></div>
    <button className="figma-create" type="button" onClick={() => onNavigate("materials")}><Icon name="edit" size={16} />æ–°å»ºåˆ›ä½œ</button>
    <nav className="figma-nav" aria-label="ä¸»å¯¼èˆª">{NAV.map((item) => <button key={item.key} type="button" aria-label={item.label} className={page === item.key ? "is-active" : ""} onClick={() => onNavigate(item.key)}><Icon name={item.icon} size={18} /><span>{item.label}</span></button>)}</nav>
    <div className="figma-sidebar-footer"><button type="button" onClick={onHelp}><Icon name="help" size={17} />å¸®åŠ©ä¸­å¿ƒ</button><button type="button" onClick={onLogout}><Icon name="close" size={17} />é€€å‡ºç™»å½•</button></div>
  </aside>;
}

function FigmaTopbar({ page, user, notificationCount, onSearch, onLogout }: { page: Page; user: User; notificationCount: number; onSearch: (value: string) => void; onLogout: () => void }) {
  const label = page === "editor" ? "æ–‡ç« åˆ›ä½œ" : NAV.find((item) => item.key === page)?.label ?? "å†…å®¹è¿è¥ç³»ç»Ÿ";
  const [open, setOpen] = useState<"notifications" | "help" | "profile" | null>(null);
  return <header className="figma-topbar"><div className="figma-topbar-title"><strong>å†…å®¹è¿è¥ç³»ç»Ÿ</strong><span>/</span><span>{label}</span></div><label className="figma-search"><Icon name="search" size={17} /><input placeholder="æœç´¢å†…å®¹ã€é€‰é¢˜æˆ–ç´ æ..." onKeyDown={(event) => { if (event.key === "Enter") onSearch(event.currentTarget.value); }} /></label><div className="figma-topbar-actions"><div className="figma-topbar-menu"><button type="button" aria-label="é€šçŸ¥" aria-expanded={open === "notifications"} onClick={() => setOpen(open === "notifications" ? null : "notifications")}><Icon name="bell" size={19} />{notificationCount > 0 && <i>{notificationCount}</i>}</button>{open === "notifications" && <div className="figma-topbar-popover"><strong>å¾…å¤„ç†æé†’</strong><p>æœ‰ {notificationCount || 0} ä¸ªä»»åŠ¡éœ€è¦å…³æ³¨ã€‚</p><button type="button" onClick={() => setOpen(null)}>çŸ¥é“äº†</button></div>}</div><div className="figma-topbar-menu"><button type="button" aria-label="å¸®åŠ©" aria-expanded={open === "help"} onClick={() => setOpen(open === "help" ? null : "help")}><Icon name="help" size={19} /></button>{open === "help" && <div className="figma-topbar-popover"><strong>å¸®åŠ©ä¸­å¿ƒ</strong><p>å…ˆä»ç´ ææ± ç­›é€‰ä¾æ®ï¼Œå†ç¡®è®¤é€‰é¢˜ã€é…ç½®ç­–ç•¥ï¼Œæœ€åå®¡æ ¸å¹¶åˆ›å»ºå…¬ä¼—å·è‰ç¨¿ã€‚</p><button type="button" onClick={() => setOpen(null)}>å…³é—­</button></div>}</div><div className="figma-topbar-menu"><button className="figma-avatar" type="button" aria-label="è´¦æˆ·èœå•" aria-expanded={open === "profile"} onClick={() => setOpen(open === "profile" ? null : "profile")}>{user.email.slice(0, 1).toUpperCase()}</button>{open === "profile" && <div className="figma-topbar-popover figma-profile-popover"><strong>{user.email}</strong><span>{user.role === "admin" ? "ç®¡ç†å‘˜" : "è¿è¥æˆå‘˜"}</span><button type="button" onClick={onLogout}>é€€å‡ºç™»å½•</button></div>}</div></div></header>;
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
  if (failedJobs[0]) tasks.push({ key: `job-${failedJobs[0].id}`, icon: "alert", title: "æœ‰è‡ªåŠ¨åŒ–ä»»åŠ¡éœ€è¦å¤„ç†", detail: failedJobs[0].last_error || `ä»»åŠ¡åœåœ¨ã€Œ${failedJobs[0].current_step || "æœªçŸ¥æ­¥éª¤"}` , action: "æŸ¥çœ‹ç”Ÿäº§çº¿", tone: "danger", onClick: () => onNavigate("settings") });
  if (reviewQueue[0]) tasks.push({ key: `review-${reviewQueue[0].id}`, icon: "review", title: reviewQueue[0].title || "å¾…å®¡æ ¸æ–‡ç« ", detail: reviewQueue[0].status === "changes_requested" ? "å·²é€€å›ä¿®æ”¹ï¼Œç­‰å¾…ä½ ç¡®è®¤æ–°ç‰ˆæœ¬ã€‚" : "æ–‡ç« å·²å®Œæˆå†™ä½œï¼Œå®¡æ ¸é€šè¿‡åè¿›å…¥æˆç¨¿åº“ã€‚", action: "å»å®¡æ ¸", tone: "pink", onClick: () => onOpenReview(reviewQueue[0].id) });
  if (candidateTopics[0]) tasks.push({ key: `topic-${candidateTopics[0].id}`, icon: "topic", title: candidateTopics[0].title, detail: candidateTopics[0].rationale || "AI å·²å®Œæˆçƒ­ç‚¹æ‰«æä¸é€‰é¢˜æ‰“åˆ†ã€‚", action: "æŸ¥çœ‹é€‰é¢˜", tone: "purple", onClick: () => onNavigate("topics") });
  if (untriagedMaterials[0]) tasks.push({ key: `material-${untriagedMaterials[0].id}`, icon: "image", title: `${untriagedMaterials.length} æ¡ç´ æç­‰å¾…ç­›é€‰`, detail: untriagedMaterials[0].title || "å…ˆä¿ç•™çœŸæ­£å€¼å¾—åˆ›ä½œçš„å†…å®¹ã€‚", action: "ç­›é€‰ç´ æ", tone: "cyan", onClick: () => onNavigate("materials") });
  const nextTask = tasks[0];

  return <main className="figma-page dashboard-page dashboard-page--actionable">
    <div className="figma-page-heading dashboard-heading">
      <div><h1>ä»Šå¤©å…ˆåšä»€ä¹ˆï¼Ÿ</h1><p>åªæ˜¾ç¤ºä¼šæ¨è¿›å†…å®¹äº¤ä»˜çš„äº‹é¡¹ï¼›å®Œæˆä¸€é¡¹ï¼Œå†å¤„ç†ä¸‹ä¸€é¡¹ã€‚</p></div>
      <PillButton tone="pink" onClick={() => onNavigate("materials")}><Icon name="edit" size={16} />ä»ç´ æå¼€å§‹åˆ›ä½œ</PillButton>
    </div>
    {nextTask ? <section className={`dashboard-next-task dashboard-next-task--${nextTask.tone}`}>
      <div className="dashboard-next-icon"><Icon name={nextTask.icon} size={22} /></div><div><span>ä¸‹ä¸€ä»¶äº‹</span><h2>{nextTask.title}</h2><p>{shortText(nextTask.detail, 130)}</p></div><button type="button" onClick={nextTask.onClick}>{nextTask.action}<Icon name="chevron" size={16} /></button>
    </section> : <section className="dashboard-clear"><Icon name="check" size={23} /><div><strong>ç”Ÿäº§çº¿å·²æ¸…ç©º</strong><span>å½“å‰æ²¡æœ‰ç­‰å¾…ä½ å¤„ç†çš„å†…å®¹ã€‚å¯ä»¥æ‰«æé€‰é¢˜ï¼Œæˆ–ä»ç´ æå¼€å§‹æ–°åˆ›ä½œã€‚</span></div><PillButton tone="pink" onClick={() => onNavigate("topics")}>å»é€‰é¢˜é›·è¾¾</PillButton></section>}
    <section className="dashboard-workspace-grid">
      <div className="dashboard-queue">
        <div className="dashboard-section-head"><div><h2>å¾…ä½ å†³å®š</h2><p>æŒ‰å½±å“äº¤ä»˜çš„ä¼˜å…ˆçº§æ’åº</p></div><span>{tasks.length} é¡¹</span></div>
        {tasks.length ? <div className="dashboard-task-list">{tasks.map((task) => <button type="button" key={task.key} className="dashboard-task-row" onClick={task.onClick}><span className={`dashboard-task-icon ${task.tone}`}><Icon name={task.icon} size={17} /></span><span className="dashboard-task-copy"><strong>{task.title}</strong><small>{shortText(task.detail, 96)}</small></span><em>{task.action}<Icon name="chevron" size={14} /></em></button>)}</div> : <div className="dashboard-empty-list">æ²¡æœ‰å †ç§¯äº‹é¡¹ã€‚ä¸‹ä¸€è½®è‡ªåŠ¨åŒ–å®Œæˆåï¼Œä¼šè‡ªåŠ¨å›åˆ°è¿™é‡Œã€‚</div>}
      </div>
      <div className="dashboard-delivery">
        <div className="dashboard-section-head"><div><h2>äº¤ä»˜ä¸è¿è¡Œ</h2><p>ç¡®è®¤ç³»ç»Ÿåœ¨æŒç»­æ¨è¿›</p></div><button type="button" onClick={() => onNavigate("library")}>æŸ¥çœ‹æˆç¨¿åº“</button></div>
        <div className="dashboard-delivery-stats"><div><strong>{deliveredArticles.length}</strong><span>å¯äº¤ä»˜æ–‡ç« </span></div><div><strong>{runningJobs.length}</strong><span>è¿è¡Œä¸­ä»»åŠ¡</span></div><div><strong>{sourcesCount}</strong><span>å¯ç”¨ä¿¡æ¯æº</span></div></div>
        {runningJobs.length ? <div className="dashboard-running-list">{runningJobs.slice(0, 3).map((job) => <div key={job.id} className="dashboard-running-row"><span className={job.status === "running" ? "is-running" : ""}><Icon name={job.status.startsWith("failed") ? "alert" : "refresh"} size={15} /></span><div><strong>{job.current_step || "æ­£åœ¨å‡†å¤‡ä»»åŠ¡"}</strong><small>{job.status === "failed_retryable" ? "æ‰§è¡Œå¤±è´¥ï¼Œç³»ç»Ÿå°†è‡ªåŠ¨é‡è¯•" : job.status === "queued" ? "æ­£åœ¨æ’é˜Ÿ" : "è‡ªåŠ¨åŒ–å¤„ç†ä¸­"}</small></div><time>{formatTime(job.updated_at)}</time></div>)}</div> : <div className="dashboard-empty-list">ç›®å‰æ²¡æœ‰è¿è¡Œä¸­çš„è‡ªåŠ¨åŒ–ä»»åŠ¡ã€‚</div>}
      </div>
    </section>
  </main>;
}

function MaterialCard({ material, selected, onSelect }: { material: Material; selected: boolean; onSelect: () => void }) {
  return <button type="button" className={`material-card ${selected ? "is-selected" : ""}`} onClick={oÛ¾}öÚ$z{-®éÜj×W2†'F–6ÆRç7FGW2’bb†4f–æÄ'F–6ÆT&öG’†'F–6ÆR’ÀĞ¢“°Ğ¢&WGW&âÆ–'&'’æf–æB‚†'F–6ÆR’Óâ'F–6ÆRæ–BÓÓÒ6VÆV7FVD'F–6ÆT–B’óòÆ–'&'•³Ó°Ğ¢ÒÂ¶'F–6ÆW2æFFÂ6VÆV7FVD'F–6ÆT–EÒ“°Ğ¢6öç7BÆ–'&'•&Wf–Wu&Wf—6–öâÒÆ–'&'•&Wf–Wt'F–6ÆSòç&Wf—6–öç3òå²†Æ–'&'•&Wf–Wt'F–6ÆRç&Wf—6–öç3òæÆVæwF‚óò’ÒÓ°Ğ¢6öç7BÆ–'&'•F†VÖT–BÒW6TÖVÖò‚‚’Óâ°Ğ¢6öç7B6æ6†÷BÒÆ–'&'•&Wf–Wt'F–6ÆSòç'VçF–ÖU÷6æ6†÷BÇÂ·Ó°Ğ¢6öç7BF†VÖRÒ6æ6†÷BçF†VÖR2²–Có¢Væ¶æ÷vâÒÂVæFVf–æVC°Ğ¢6öç7BW†V7WF–öâÒ6æ6†÷BæW†V7WF–öåö6öæf–r2²F†VÖUö–Có¢Væ¶æ÷vâÒÂVæFVf–æVC°Ğ¢&WGW&âG—VöbF†VÖSòæ–BÓÓÒ'7G&–ær Ğ¢òF†VÖRæ–@Ğ¢¢G—VöbW†V7WF–öãòçF†VÖUö–BÓÓÒ'7G&–ær Ğ¢òW†V7WF–öâçF†VÖUö–@Ğ¢¢"#°Ğ¢ÒÂ¶Æ–'&'•&Wf–Wt'F–6ÆUÒ“°Ğ¢W6TVffV7B‚‚’Óâ°Ğ¢–b‡vRÓÓÒ&Æ–'&'’"bbÆ–'&'•F†VÖT–BbbÆ–'&'•F†VÖT–BÓÒ6VÆV7FVEF†VÖT–B’°Ğ¢6WE6VÆV7FVEF†VÖT–B†Æ–'&'•F†VÖT–B“°Ğ¢ĞĞ¢ÒÂ¶Æ–'&'•F†VÖT–BÂvUÒ“°Ğ¢6öç7BF†VÖU&Wf–WrÒW6UVW'’‡°Ğ¢VW'”¶W“¢²'F†VÖR×&Wf–Wr"ÂÆ–'&'•&Wf–Wt'F–6ÆSòæ–BÂÆ–'&'•&Wf–Wu&Wf—6–öãòæ–BÂ6VÆV7FVEF†VÖT–EÒÀĞ¢VW'”fã¢‚’Óâ’ç&Wf–WuF†VÖR†Æ–'&'•&Wf–Wt'F–6ÆRæ–BÂÆ–'&'•&Wf–Wu&Wf—6–öâæ–BÂ6VÆV7FVEF†VÖT–B’ÀĞ¢Væ&ÆVC¢vRÓÓÒ&Æ–'&'’"bb&ööÆVâ†Æ–'&'•&Wf–Wt'F–6ÆRbbÆ–'&'•&Wf–Wu&Wf—6–öâbb6VÆV7FVEF†VÖT–B’ÀĞ¢Ò“°Ğ¢6öç7B6öçFVçBÒW6TÖVÖò‚‚’Óâ°Ğ¢–b‡vRÓÓÒ&F6†&ö&B"’&WGW&âÄF6†&ö&BÖFW&–Ç3×¶ÖFW&–Ç2æFFÇÂµ×ÒF÷–73×·F÷–72æFFÇÂµ×Ò'F–6ÆW3×¶'F–6ÆW2æFFÇÂµ×Ò¦ö'3×¶¦ö'2æFFÇÂµ×Ò6÷W&6W46÷VçC×¶F6†&ö&BæFFòç6÷W&6W2ÇÂÒöäæf–vFS×·6WEvWÒöä÷Vå&Wf–Ws×²†–B’Óâ²6WE6VÆV7FVD'F–6ÆT–B†–B“²6WEvR‚'&Wf–Wr"“²×Òóã°Ğ¢–b‡vRÓÓÒ&ÖFW&–Ç2"’&WGW&âÄÖFW&–Åv÷&·76RÖFW&–Ç3×¶ÖFW&–Ç2æFFÇÂµ×Ò6FVv÷&–W3×¶ÖFW&–Ä6FVv÷&–W2æFFÇÂµ×ÒÆöDW'&÷#×µ¶ÖFW&–Ç2æW'&÷"ÂÖFW&–Ä6FVv÷&–W2æW'&÷%Òæf–ÇFW"‚†W'&÷"“¢W'&÷"—2W'&÷"ÓâW'&÷"–ç7Fæ6VöbW'&÷"’æÖ‚†W'&÷"’ÓâW'&÷"æÖW76vR’æ¦ö–â‚.ûÉ²"—Ò6÷W&6W3×·6÷W&6W2æFFÇÂµ×Ò6¶–ÆÇ3×·6¶–ÆÇ2æFFÇÂµ×Ò7G&FVv–W3×·7G&FVv–W2æFFÇÂµ×Ò7W&F–öå&W7VÇC×¶7W&F–öå&W7VÇGÒ7&VF–æs×¶7&VFTg&öÔÖFW&–Ç2æ—5VæF–æwÒöä7&VFS×²‡–ÆöB’Óâ7&VFTg&öÔÖFW&–Ç2æ×WFFR‡–ÆöB—ÒöäÖævU6÷W&6W3×²‚’Óâ²6WE6WGF–æw5F"‚'6÷W&6W2"“²6WEvR‚'6WGF–æw2"“²×ÒöäÖævU7G&FVv–W3×²‚’Óâ²6WE6WGF–æw5F"‚'7G&FVw’"“²6WEvR‚'6WGF–æw2"“²×Òöä6öÆÆV7C×²†–G2’Óâ6öÆÆV7E6÷W&6W2æ×WFFR†–G2—Ò6öÆÆV7F–æs×¶6öÆÆV7E6÷W&6W2æ—5VæF–æwÒöä7W&FS×²‡7G&FVw”–B’Óâ7W&FTÖFW&–Ç2æ×WFFR‡7G&FVw”–B—Ò7W&F–æs×¶7W&FTÖFW&–Ç2æ—5VæF–æwÒöä6Æ76–g“×²†–G2’Óâ6Æ76–g”ÖFW&–Ç2æ×WFFR†–G2—Ò6Æ76–g––æs×¶6Æ76–g”ÖFW&–Ç2æ—5VæF–æwÒöåG&–vS×²†–BÂFV6—6–öâ’ÓâG&–vRæ×WFFR‡²–BÂFV6—6–öâÒ—Òöä76–vä6FVv÷'“×²†–BÂ6FVv÷'”–B’Óâ76–väÖFW&–Ä6FVv÷'’æ×WFFR‡²–BÂ6FVv÷'”–BÒ—ÒöäFD6FVv÷'“×²‡–ÆöB’ÓâFDÖFW&–Ä6FVv÷'’æ×WFFT7–æ2‡–ÆöB—ÒöåWFFT6FVv÷'“×²†–BÂ–ÆöB’ÓâWFFTÖFW&–Ä6FVv÷'’æ×WFFT7–æ2‡²–BÂ–ÆöBÒ—ÒöäF—6&ÆT6FVv÷'“×²†–B’ÓâF—6&ÆTÖFW&–Ä6FVv÷'’æ×WFFT7–æ2†–B—Òöå&W7F÷&T6FVv÷'“×²†–B’Óâ&W7F÷&TÖFW&–Ä6FVv÷'’æ×WFFT7–æ2†–B—Òóã°Ğ¢–b‡vRÓÓÒ'F÷–72"’&WGW&âÅF÷–5&F"F÷–73×·F÷–72æFFÇÂµ×Ò7G&FVv–W3×·7G&FVv–W2æFFÇÂµ×ÒÆv÷&—F†×3×·F÷–4Æv÷&—F†×2æFFÇÂµ×Ò66ææ–æs×·66åF÷–72æ—5VæF–æwÒw&—F–æs×¶66WEF÷–2æ—5VæF–æwÒÖæv–ætÆv÷&—F†×3×¶7&VFUF÷–4Æv÷&—F†Òæ—5VæF–ærÇÂWFFUF÷–4Æv÷&—F†Òæ—5VæF–ærÇÂFVÆWFUF÷–4Æv÷&—F†Òæ—5VæF–æwÒöå66ã×²‡7G&FVw”–BÂÆv÷&—F†Ô–B’Óâ66åF÷–72æ×WFFR‡²7G&FVw”–BÂÆv÷&—F†Ô–BÒ—Òöåw&—FS×²‡F÷–2’Óâ66WEF÷–2æ×WFFR‡F÷–2—ÒöäF—6Ö—73×²‡F÷–2’Óâ²fö–B’æFV6–FUF÷–2‡F÷–2æ–BÂ'&V¦V7B"’çF†Vâ‚‚’Óâ&Vg&W6‚‚'F÷–72"Â&ÖFW&–Ç2"’’æ6F6‚‚†W'&÷#¢W'&÷"’ÓâÖW76vRæW'&÷"†W'&÷"æÖW76vR’“²×Òöå6fTÖFW&–Ç3×²‡F÷–2’Óâ6fUF÷–4ÖFW&–Ç2æ×WFFR‡F÷–2—Òöä7&VFTÆv÷&—F†Ó×²‡–ÆöB’Óâ7&VFUF÷–4Æv÷&—F†Òæ×WFFT7–æ2‡–ÆöB—ÒöåWFFTÆv÷&—F†Ó×²†–BÂ–ÆöB’ÓâWFFUF÷–4Æv÷&—F†Òæ×WFFT7–æ2‡²–BÂ–ÆöBÒ—ÒöäFVÆWFTÆv÷&—F†Ó×²†–B’ÓâFVÆWFUF÷–4Æv÷&—F†Òæ×WFFT7–æ2†–B—Òóã°Ğ¢–b‡vRÓÓÒ'&Wf–Wr"’&WGW&âÅ&Wf–WuVWVR'F–6ÆW3×¶'F–6ÆW2æFFÇÂµ×Ò¦ö'3×¶¦ö'2æFFÇÂµ×Ò6VÆV7FVD–C×·6VÆV7FVD'F–6ÆT–GÒVæF–æs×·&Wf–Wt'F–6ÆRæ—5VæF–æwÒ&WG'––æs×·&WG'”¦ö"æ—5VæF–æwÒöå6VÆV7C×·6WE6VÆV7FVD'F–6ÆT–GÒöä&÷fS×²†'F–6ÆR’Óâ&Wf–Wt'F–6ÆRæ×WFFR‡²'F–6ÆRÂFV6—6–öã¢&&÷fR"Ò—Òöä6†ævW3×²†'F–6ÆR’Óâ&Wf–Wt'F–6ÆRæ×WFFR‡²'F–6ÆRÂFV6—6–öã¢'&WVW7Eö6†ævW2"Ò—ÒöäVF—C×²†–B’Óâ²6WE6VÆV7FVD'F–6ÆT–B†–B“²6WDVF—F÷%&WGW&åvR‚'&Wf–Wr"“²6WEvR‚&VF—F÷""“²×Òöå&WG'“×²†–B’Óâ&WG'”¦ö"æ×WFFR†–B—Òóã°Ğ¢–b‡vRÓÓÒ&Æ–'&'’"’&WGW&âÄ'F–6ÆTÆ–'&'’'F–6ÆW3×¶'F–6ÆW2æFFÇÂµ×Ò6VÆV7FVD–C×·6VÆV7FVD'F–6ÆT–GÒF†VÖW3×·F†VÖW2æFFÇÂµ×Ò6†ææVÇ3×¶6†ææVÇ2æFFÇÂµ×Ò6VÆV7FVEF†VÖT–C×·6VÆV7FVEF†VÖT–GÒ6VÆV7FVD6†ææVÄ–C×·6VÆV7FVD6†ææVÄ–GÒF‡VÖ$ÖVF––C×·F‡VÖ$ÖVF––GÒ6÷fW%&Wf–WuW&Ã×¶6÷fW%&Wf–WuW&ÇÒF†VÖU&Wf–Wt‡FÖÃ×·F†VÖU&Wf–WræFFòæ‡FÖÂÇÂ"'ÒF†VÖU&Wf–WtÆöF–æs×·F†VÖU&Wf–Wræ—4ÆöF–æwÒF†VÖU&Wf–WtW'&÷#×·F†VÖU&Wf–WræW'&÷"–ç7Fæ6VöbW'&÷"òF†VÖU&Wf–WræW'&÷"æÖW76vR¢"'ÒVæF–æs×¶7&VFTG&gBæ—5VæF–ærÇÂWÆöEF‡VÖ"æ—5VæF–ærÇÂ&6†—fT'F–6ÆRæ—5VæF–æwÒFVÆ—fW'”W'&÷#×¶FVÆ—fW'”W'&÷'Òöå6VÆV7C×²†–B’Óâ²6WE6VÆV7FVD'F–6ÆT–B†–B“²6WDFVÆ—fW'”W'&÷"‚""“²×ÒöäVF—C×²†–B’Óâ²6WE6VÆV7FVD'F–6ÆT–B†–B“²6WDVF—F÷%&WGW&åvR‚&Æ–'&'’"“²6WEvR‚&VF—F÷""“²×Òöä&6†—fS×²†'F–6ÆR’Óâ&6†—fT'F–6ÆRæ×WFFR†'F–6ÆRæ–B—ÒöåF†VÖT6†ævS×·6WE6VÆV7FVEF†VÖT–GÒöä6†ææVÄ6†ævS×²†–B’Óâ²6WE6VÆV7FVD6†ææVÄ–B†–B“²6WEF‡VÖ$ÖVF––B‚""“²6WDFVÆ—fW'”W'&÷"‚""“²×ÒöåWÆöC×²†f–ÆR’ÓâWÆöEF‡VÖ"æ×WFFR†f–ÆR—ÒöäG&gC×²†'F–6ÆR’Óâ7&VFTG&gBæ×WFFR†'F–6ÆR—Òóã°Ğ¢–b‡vRÓÓÒ&VF—F÷""’&WGW&âÄ'F–6ÆTVF—F÷"'F–6ÆS×·6VÆV7FVD'F–6ÆWÒöä&6³×²‚’Óâ6WEvR†VF—F÷%&WGW&åvR—Òöå6fS×²†'F–6ÆT–BÂF—FÆRÂÖ&¶F÷vâ’Óâ6fU&Wf—6–öâæ×WFFR‡²'F–6ÆT–BÂF—FÆRÂÖ&¶F÷vâÒ—Ò6f–æs×·6fU&Wf—6–öâæ—5VæF–æwÒóã°Ğ¢–b‡vRÓÓÒ'6WGF–æw2"’&WGW&â€Ğ¢ÆF—càĞ¢ÆF—b6Æ74æÖSÒ&f–vÖ×vR"7G–ÆS×·²FF–æt&÷GFöÓ¢×ÓàĞ¢ÆF—b6Æ74æÖSÒ&f–vÖ×F'2#àĞ¢Æ'WGFöâ6Æ74æÖS×·6WGF–æw5F"ÓÓÒ'7G&FVw’"ò&—2Ö7F—fR"¢"'ÒG—SÒ&'WGFöâ"öä6Æ–6³×²‚’Óâ6WE6WGF–æw5F"‚'7G&FVw’"—Óîˆz®XªXÉnyIşKª~{«óÂö'WGFöãàĞ¢Æ'WGFöâ6Æ74æÖS×·6WGF–æw5F"ÓÓÒ'6÷W&6W2"ò&—2Ö7F—fR"¢"'ÒG—SÒ&'WGFöâ"öä6Æ–6³×²‚’Óâ6WE6WGF–æw5F"‚'6÷W&6W2"—ÓîKúhşk©Æ#ç·6÷W&6W2æFFòæÆVæwF‚ÇÂÓÂö#ãÂö'WGFöãàĞ¢Æ'WGFöâ6Æ74æÖS×·6WGF–æw5F"ÓÓÒ&ÖöFVÇ2"ò&—2Ö7F—fR"¢"'ÒG—SÒ&'WGFöâ"öä6Æ–6³×²‚’Óâ6WE6WGF–æw5F"‚&ÖöFVÇ2"—ÓîjŠYè¾KŠŞ[ø2Æ#ç¶ÖöFVÇ2æFFòæÆVæwF‚ÇÂÓÂö#ãÂö'WGFöãàĞ¢Æ'WGFöâ6Æ74æÖS×·6WGF–æw5F"ÓÓÒ&6†ææVÇ2"ò&—2Ö7F—fR"¢"'ÒG—SÒ&'WGFöâ"öä6Æ–6³×²‚’Óâ6WE6WGF–æw5F"‚&6†ææVÇ2"—ÓîXZÎKÉ~Xû~‹JnXûrÆ#ç¶6†ææVÇ2æFFòæÆVæwF‚ÇÂÓÂö#ãÂö'WGFöãàĞ¢¶7W'&VçEW6W"ç&öÆRÓÓÒ&FÖ–â"bbÆ'WGFöâ6Æ74æÖS×·6WGF–æw5F"ÓÓÒ'W6W'2"ò&—2Ö7F—fR"¢"'ÒG—SÒ&'WGFöâ"öä6Æ–6³×²‚’Óâ6WE6WGF–æw5F"‚'W6W'2"—ÓîyJh‹~KŠŞ[ø2Æ#ç·W6W'2æFFòæÆVæwF‚ÇÂÓÂö#ãÂö'WGFöãçĞĞ¢ÂöF—càĞ¢ÂöF—càĞ¢·6WGF–æw5F"ÓÓÒ'7G&FVw’"ò€Ğ¢Å7G&FVw•—VÆ–æUvR7G&FVv–W3×·7G&FVv–W2æFFÇÂµ×Ò6VÆV7FVD–C×¶7&VF–æu7G&FVw’òçVÆÂ¢6VÆV7FVE7G&FVw”–GÒöå6VÆV7C×²†–B’Óâ²6WD7&VF–æu7G&FVw’†fÇ6R“²6WE6VÆV7FVE7G&FVw”–B†–B“²×ÒöäæWs×²‚’Óâ²6WD7&VF–æu7G&FVw’‡G'VR“²6WE6VÆV7FVE7G&FVw”–B†çVÆÂ“²×Ò6FVv÷&–W3×¶ÖFW&–Ä6FVv÷&–W2æFFÇÂµ×Ò6¶–ÆÇ3×·6¶–ÆÇ2æFFÇÂµ×ÒF†VÖW3×·F†VÖW2æFFÇÂµ×ÒÖöFVÇ3×¶ÖöFVÇ2æFFÇÂµ×Ò6†ææVÇ3×¶6†ææVÇ2æFFÇÂµ×Òöå6fS×²†–BÂ–ÆöB’Óâ6fU7G&FVw’æ×WFFT7–æ2‡²–BÂ–ÆöBÒ—Òöå'Vã×²†–BÂ6öÖ&–æF–öä–B’Óâ'Vå7G&FVw’æ×WFFT7–æ2‡²–BÂ6öÖ&–æF–öä–BÒ—ÒöäÖævTÖFW&–Ç3×²‚’Óâ6WEvR‚&ÖFW&–Ç2"—ÒöåWÆöEF‡VÖ#×¶7–æ2†f–ÆRÂ6†ææVÄ–B’Óâ†v—B’çWÆöEvV6†EF‡VÖ"†f–ÆRÂ6†ææVÄ–B’’æÖVF–ö–GÒöä–×÷'E6¶–ÆÃ×¶7–æ2†f–ÆR’Óâ²v—B–×÷'E6¶–ÆÂæ×WFFT7–æ2†f–ÆR“²×Ò–×÷'F–æu6¶–ÆÃ×¶–×÷'E6¶–ÆÂæ—5VæF–æwÒóàĞ¢’¢6WGF–æw5F"ÓÓÒ'6÷W&6W2"ò€Ğ¢Å6÷W&6T6VçFW"6÷W&6W3×·6÷W&6W2æFFÇÂµ×ÒöäFC×²‚’Óâ6WE6÷W&6T÷Vâ‡G'VR—ÒöäFE&V6öÖÖVæFVC×¶7–æ2‡6÷W&6R’Óâ²v—BFE&V6öÖÖVæFVE6÷W&6Ræ×WFFT7–æ2‡6÷W&6R“²×Òöä6öÆÆV7C×¶7–æ2†–B’Óâ²v—B6öÆÆV7E6÷W&6Ræ×WFFT7–æ2†–B“²×ÒöåWFFS×¶7–æ2†–BÂ6÷W&6R’Óâ²v—BWFFU6÷W&6Ræ×WFFT7–æ2‡²–BÂ6÷W&6RÒ“²×ÒöäF—6&ÆS×¶7–æ2†–B’Óâ²v—BF—6&ÆU6÷W&6Ræ×WFFT7–æ2†–B“²×ÒóàĞ¢’¢6WGF–æw5F"ÓÓÒ&ÖöFVÇ2"ò‚ÄÖöFVÄ6VçFW"ÖöFVÇ3×¶ÖöFVÇ2æFFÇÂµ×ÒöäFC×¶7–æ2‡’Óâ²v—BFDÖöFVÂæ×WFFT7–æ2‡“²×ÒöåWFFS×¶7–æ2†–BÂ’Óâ²v—BWFFTÖöFVÂæ×WFFT7–æ2‡²–BÂÒ“²×ÒöåFW7C×²†–B’ÓâFW7DÖöFVÂæ×WFFR†–B—ÒöäFVÆWFS×¶7–æ2†–B’Óâ²v—BFVÆWFTÖöFVÂæ×WFFT7–æ2†–B“²×ÒóàĞ¢’¢6WGF–æw5F"ÓÓÒ&6†ææVÇ2"ò€Ğ¢Ä6†ææVÄ6VçFW"66÷VçG3×¶6†ææVÇ2æFFÇÂµ×ÒöäFC×¶7–æ2‡–ÆöB’Óâ²v—BFD6†ææVÂæ×WFFT7–æ2‡–ÆöB“²×ÒöåWFFS×¶7–æ2†–BÂ²æÖRÂö–BÂ÷6V7&WBÂVæ&ÆVBÒ’Óâ²v—BWFFT6†ææVÂæ×WFFT7–æ2‡²–BÂ–ÆöC¢²æÖRÂö–BÂ÷6V7&WBÂVæ&ÆVBÒÒ“²×ÒöåFW7C×²†–B’ÓâFW7D6†ææVÂæ×WFFR†–B—ÒöäF—6&ÆS×¶7–æ2†–B’Óâ²v—BF—6&ÆT6†ææVÂæ×WFFT7–æ2†–B“²×ÒóàĞ¢’¢€Ğ¢ÅW6W$6VçFW"W6W'3×·W6W'2æFFÇÂµ×ÒöäFC×¶7–æ2‡–ÆöB’Óâ²v—BFEW6W"æ×WFFT7–æ2‡–ÆöB“²×ÒóàĞ¢—ĞĞ¢ÂöF—càĞ¢“°Ğ¢ÒÂ¶66WEF÷–2Â&6†—fT'F–6ÆRÂ'F–6ÆW2æFFÂ6†ææVÇ2æFFÂ6÷fW%&Wf–WuW&ÂÂ7&VFTG&gBÂ7&VFTg&öÔÖFW&–Ç2ÂF6†&ö&BæFFÂFVÆ—fW'”W'&÷"ÂVF—F÷%&WGW&åvRÂ¦ö'2æFFÂÖFW&–Ä6FVv÷&–W2æFFÂÖFW&–Ä6FVv÷&–W2æW'&÷"ÂÖFW&–Ç2æFFÂÖFW&–Ç2æW'&÷"ÂÖöFVÇ2æFFÂvRÂV&Æ—6„G&gBÂ&Wf–Wt'F–6ÆRÂ6fUF÷–4ÖFW&–Ç2Â66åF÷–72Â6VÆV7FVD'F–6ÆT–BÂ6VÆV7FVD6†ææVÄ–BÂ6VÆV7FVDÖFW&–Ä–BÂ6VÆV7FVE6¶–ÆÄ–BÂ6VÆV7FVE7G&FVw”–BÂ6VÆV7FVEF†VÖT–BÂ6WGF–æw5F"Â6¶–ÆÇ2æFFÂ6÷W&6W2æFFÂ6÷W&6UG—RÂ7G&FVv–W2æFFÂF†VÖW2æFFÂF†VÖU&Wf–WræFFòæ‡FÖÂÂF‡VÖ$ÖVF––BÂF÷–4Æv÷&—F†×2æFFÂF÷–72æFFÂG&–vRÂWFFUF÷–4Æv÷&—F†ÒÂW6W'2æFFÂWFFU6÷W&6RÂWÆöEF‡VÖ"Â6öÆÆV7E6÷W&6W2Â7W&FTÖFW&–Ç2Â6Æ76–g”ÖFW&–Ç2Â76–väÖFW&–Ä6FVv÷'’ÂFDÖFW&–Ä6FVv÷'’ÂWFFTÖFW&–Ä6FVv÷'’ÂF—6&ÆTÖFW&–Ä6FVv÷'’Â&W7F÷&TÖFW&–Ä6FVv÷'’Â&WG'”¦ö%Ò“°Ğ¢&WGW&âÆF—b6Æ74æÖSÒ&f–vÖÖ6öç6öÆR#ãÄf–vÖ6–FV&"vS×·vWÒöäæf–vFS×·6WEvWÒöä7&VFS×²‚’Óâ²6WEvR‚'F÷–72"“²6WEF÷–4÷Vâ‡G'VR“²×Òöä†VÇ×²‚’ÓâÖW76vRæ–æfò‚.[ŠîXªKŠŞ[ø>ûÉ®XXzÙ¾˜{JiÙûÈÎXhŞzîŠêN˜š)8˜XŞ{ÚîzÙnyZ^[›nZêjXù[ˆ>8""—ÒöäÆöv÷WC×²‚’Óâ²fö–B’æÆöv÷WB‚’çF†Vâ‚‚’Óâv–æF÷ræÆö6F–öâç&VÆöB‚’’æ6F6‚‚†W'&÷#¢W'&÷"’ÓâÖW76vRæW'&÷"†W'&÷"æÖW76vR’“²×ÒóãÆF—b6Æ74æÖSÒ&f–vÖÖÖ–â#ãÄf–vÖF÷&"vS×·vWÒW6W#×¶7W'&VçEW6W'Òæ÷F–f–6F–öä6÷VçC×²†¦ö'2æFFÇÂµÒ’æf–ÇFW"‚†—FVÒ’Óâ—FVÒç7FGW2ç7F'G5v—F‚‚&f–ÆVB"’ÇÂ—FVÒç7FGW2ÓÓÒ'v—F–æu÷&Wf–Wr"’æÆVæwF‡Òöå6V&6ƒ×·6V&6‡ÒöäÆöv÷WC×²‚’Óâ²fö–B’æÆöv÷WB‚’çF†Vâ‚‚’Óâv–æF÷ræÆö6F–öâç&VÆöB‚’’æ6F6‚‚†W'&÷#¢W'&÷"’ÓâÖW76vRæW'&÷"†W'&÷"æÖW76vR’“²×Òóç¶6öçFVçGÓÂöF—cç²‡6÷W&6T÷VâÇÂF÷–4÷Vâ’bbÆF—b6Æ74æÖSÒ&f–vÖÖÖöFÂÖ&6¶G&÷#ãÆF—b6Æ74æÖSÒ&f–vÖÖÖöFÂ#ãÆ'WGFöâ6Æ74æÖSÒ&ÖöFÂÖ6Æ÷6R"G—SÒ&'WGFöâ"&–ÖÆ&VÃÒ.X[>™zÒ"öä6Æ–6³×²‚’Óâ²6WE6÷W&6T÷Vâ†fÇ6R“²6WEF÷–4÷Vâ†fÇ6R“²×ÓãÄ–6öâæÖSÒ&6Æ÷6R"6—¦S×³‡ÒóãÂö'WGFöãç·6÷W&6T÷VâòÃãÇ7â6Æ74æÖSÒ&W–V'&÷r#å4õU$4SÂ÷7ããÆƒ#ç·6÷W&6UG—RÓÓÒ&ÖçVÂ"ò.{)‹KNh˜¾Xª{JiÙ"¢.k{¾XªKúhşk©'ÓÂöƒ#ãÇç·6÷W&6UG—RÓÓÒ&ÖçVÂ"ò.y»Nhê^{)‹KNKˆiÚ{JiÙûÈÎKùŞZÙYîz¸¾XÛ>‹ù¾XZ^{JiÙkûÈÎiz™ÈXhŞzØ[è^˜x~™¸n8""¢6÷W&6UG—RÓÓÒ''72"ò.k{¾XªKˆKŠ¢%52Šê.™ˆ^YËYØûÈÎ{;¾{¹şKÉ®hÈyIşKª~{«şy¨Nš)xè~˜x~™¸nikXh^Zë8""¢6÷W&6UG—RÓÓÒ&–†÷Eö’"ò.hê^XZR’„õBiÈ‹ù#B[şi{n{+î˜‹XNŠêşûÈÎhÈZéikXˆn{¾ˆz®XªXZ^[©>8""¢.k{¾XªKˆKŠ®{Ùš^h‰njşyºîš^YËYØûÈÎ{;¾{¹şKÉ®hš¾høşš^™Ú.jÚ>ih~[›n˜XZ^[è^zÙ¾˜{JiÙ8"'ÓÂ÷ãÆf÷&Òöå7V&Ö—C×²†WfVçB’Óâ²WfVçBç&WfVçDFVfVÇB‚“²6öç7Bf÷&ÒÒæWrf÷&ÔFF†WfVçBæ7W'&VçEF&vWB“²–b‡6÷W&6UG—RÓÓÒ&ÖçVÂ"’²6öç7BF—FÆRÒ7G&–ær†f÷&ÒævWB‚'F—FÆR"’ÇÂ""’çG&–Ò‚“²6öç7B6öçFVçBÒ7G&–ær†f÷&ÒævWB‚&6öçFVçB"’ÇÂ""’çG&–Ò‚“²6öç7B6÷W&6TæÖRÒ7G&–ær†f÷&ÒævWB‚'6÷W&6UöæÖR"’ÇÂ.h˜¾Xª[Ù^XZR"’çG&–Ò‚“²–b‚F—FÆRÇÂ6öçFVçB’²ÖW76vRæW'&÷"‚.Šû~Z¾Xi{JiÙj~š)Y(ÎjÚ>ih~8""“²&WGW&ã²ÒFDÖçVÄÖFW&–Âæ×WFFR‡²F—FÆRÂ6öçFVçBÂ6÷W&6UöæÖS¢6÷W&6TæÖRÇÂ.h˜¾Xª[Ù^XZR"Ò“²&WGW&ã²Ò6öç7BæÖRÒ7G&–ær†f÷&ÒævWB‚&æÖR"’ÇÂ""’çG&–Ò‚“²6öç7BW&ÂÒ7G&–ær†f÷&ÒævWB‚'W&Â"’ÇÂ""’çG&–Ò‚“²6öç7B6FVv÷'’Ò7G&–ær†f÷&ÒævWB‚&6FVv÷'’"’ÇÂ""’çG&–Ò‚’ÇÂVæFVf–æVC²–b‚æÖRÇÂ‡6÷W&6UG—RÓÒ&–†÷Eö’"bbW&Â’’²ÖW76vRæW'&÷"‡6÷W&6UG—RÓÓÒ&–†÷Eö’"ò.Šû~Z¾XiKúhşk©YŞz{8""¢.Šû~Z¾XiKúhşk©YŞz{Y(ÎYËYØ8""“²&WGW&ã²ÒFE6÷W&6Ræ×WFFR‡²æÖRÂ6÷W&6U÷G—S¢6÷W&6UG—RÂW&ÂÂ6FVv÷'’Ò“²×ÓãÆÆ&VÃî{¾Yè³Ç6VÆV7BfÇVS×·6÷W&6UG—WÒöä6†ævS×²†WfVçB’Óâ6WE6÷W&6UG—R†WfVçBçF&vWBçfÇVR2''72"Â'W&Â"Â&ÖçVÂ"Â&–†÷Eö’"—ÓãÆ÷F–öâfÇVSÒ''72#å%52Šê.™ˆSÂö÷F–öããÆ÷F–öâfÇVSÒ'W&Â#î{ÙšRU$ÃÂö÷F–öããÆ÷F–öâfÇVSÒ&–†÷Eö’#ä’„õBûÈƒ#F‚{+î˜ûÈ“Âö÷F–öããÆ÷F–öâfÇVSÒ&ÖçVÂ#îh˜¾Xª{)‹KN{JiÙÂö÷F–öããÂ÷6VÆV7CãÂöÆ&VÃç·6÷W&6UG—RÓÓÒ&ÖçVÂ"òÃãÆÆ&VÃî{JiÙj~š)ƒÆ–çWBæÖSÒ'F—FÆR"&WV—&VBÆ6V†öÆFW#Ò.‹ùiÚ{JiÙŠë.K¸K˜ûÉò"óãÂöÆ&VÃãÆÆ&VÃî{JiÙjÚ>ihsÇFW‡F&VæÖSÒ&6öçFVçB"&WV—&VBÆ6V†öÆFW#Ò.{)‹KNZèÎi[NjÚ>ih~8i[Ù^h‰nKÚy¨Nh;>k9^(
b"óãÂöÆ&VÃãÆÆ&VÃîiÚ^k©j~zÛîûÈXúş˜ûÈ“Æ–çWBæÖSÒ'6÷W&6UöæÖR"Æ6V†öÆFW#Ò.Kè¾Zh.ûÉ®h‰y¨NŠx.Zùò"óãÂöÆ&VÃãÂóâ¢6÷W&6UG—RÓÓÒ&–†÷Eö’"òÃãÆÆ&VÃîKúhşk©YŞz{Æ–çWBæÖSÒ&æÖR"&WV—&VBÆ6V†öÆFW#Ò.Kè¾Zh.ûÉ¤’„õB#F‚{+î˜’"óãÂöÆ&VÃãÆÆ&VÃîXˆn{¾ûÈXúş˜ûÈ“Ç6VÆV7BæÖSÒ&6FVv÷'’#ãÆ÷F–öâfÇVSÒ"#îXZ˜:Xˆn{³Âö÷F–öããÆ÷F–öâfÇVSÒ&’ÖÖöFVÇ2#ä’jŠYè³Âö÷F–öããÆ÷F–öâfÇVSÒ&’×&öGV7G2#ä’Kª~Y8Âö÷F–öããÆ÷F–öâfÇVSÒ&–æGW7G'’#îŠÎK‰®XªhÂö÷F–öããÆ÷F–öâfÇVSÒ'W"#îŠë®ihsÂö÷F–öããÆ÷F–öâfÇVSÒ'F—#îh¨[zsÂö÷F–öããÂ÷6VÆV7CãÂöÆ&VÃãÂóâ¢ÃãÆÆ&VÃîKúhşk©YŞz{Æ–çWBæÖSÒ&æÖR"&WV—&VBÆ6V†öÆFW#×·6÷W&6UG—RÓÓÒ''72"ò.Kè¾Zh.ûÉ£3nk
¢%52"¢.Kè¾Zh.ûÉ¤Ô•BFV6†æöÆöw’&Wf–Wr'ÒóãÂöÆ&VÃãÆÆ&VÃç·6÷W&6UG—RÓÓÒ''72"ò%%52YËYØ"¢.{Ùš^YËYØ'ÓÆ–çWBæÖSÒ'W&Â"G—SÒ'W&Â"&WV—&VBÆ6V†öÆFW#Ò&‡GG3¢òòâââ"óãÂöÆ&VÃãÂóçÓÅ–ÆÄ'WGFöâG—SÒ'7V&Ö—B"FöæSÒ'–æ²#ç·6÷W&6UG—RÓÓÒ&ÖçVÂ"ò.XªXZ^{JiÙk"¢.k{¾XªKúhşk©'ÓÂõ–ÆÄ'WGFöããÂöf÷&ÓãÂóâ¢ÃãÇ7â6Æ74æÖSÒ&W–V'&÷r#ääUrDõ”3Â÷7ããÆƒ#îX‰¾[»®X	˜˜š)ƒÂöƒ#ãÇîXXzîŠêN˜š)ûÈÎXhŞ‹ù¾XZR’X‰¾KÙÎkXzˆ¾8#Â÷ãÆf÷&Òöå7V&Ö—C×²†WfVçB’Óâ²WfVçBç&WfVçDFVfVÇB‚“²7&VFUF÷–2æ×WFFR‚“²×ÓãÆÆ&VÃî˜š)j~š)ƒÆ–çWBfÇVS×·F÷–5F—FÆWÒöä6†ævS×²†WfVçB’Óâ6WEF÷–5F—FÆR†WfVçBçF&vWBçfÇVR—Ò&WV—&VBÆ6V†öÆFW#Ò.‹é>XZ^KˆKŠ®XÎ[é~X‰¾KÙÎy¨N˜š)‚"óãÂöÆ&VÃãÆÆ&VÃîh˜[îzÙnyZSÇ6VÆV7BfÇVS×·F÷–57G&FVw”–GÒöä6†ævS×²†WfVçB’Óâ6WEF÷–57G&FVw”–B†WfVçBçF&vWBçfÇVR—Ò&WV—&VCãÆ÷F–öâfÇVSÒ"#îŠû~˜hºzÙnyZSÂö÷F–öãç²‡7G&FVv–W2æFFÇÂµÒ’æÖ‚‡7G&FVw’’ÓâÆ÷F–öâ¶W“×·7G&FVw’æ–GÒfÇVS×·7G&FVw’æ–GÓç·7G&FVw’ææÖWÓÂö÷F–öãâ—ÓÂ÷6VÆV7CãÂöÆ&VÃãÅ–ÆÄ'WGFöâG—SÒ'7V&Ö—B"FöæSÒ'–æ²#îX‰¾[»®X	˜˜š)ƒÂõ–ÆÄ'WGFöããÂöf÷&ÓãÂóçÓÂöF—cãÂöF—cç×·6VÆV7FVDÖFW&–ÂbbçVÆÇÓÂöF—cã°Ğ§ĞĞ