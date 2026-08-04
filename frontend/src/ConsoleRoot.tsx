import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Checkbox, Form, Input, Modal, Select, Space, Upload, message } from "antd";
import {
  api,
  type Article,
  type Material,
  type Strategy,
  type StrategyPayload,
  type User,
} from "./api";
import { Icon } from "./design";
import { FigmaConsole } from "./FigmaConsole";
import {
  ArticleEditorPage,
  DashboardPage,
  MAIN_NAV,
  MaterialsPage,
  ReviewPublishPage,
  SettingsPage,
  Sidebar,
  Topbar,
  TopicsPage,
  type PageKey,
  type ReviewTab,
  type SettingsTab,
} from "./pages";
import "./styles.css";
import "./console.css";

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function stringRecord(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value).filter(([, item]) => typeof item === "string")) as Record<string, string>;
}

function Login({ onSuccess }: { onSuccess: (user: User) => void }) {
  const [remember, setRemember] = useState(true);
  const login = useMutation({
    mutationFn: (values: { email: string; password: string }) => api.login(values.email, values.password),
    onSuccess,
    onError: (error: Error) => message.error(error.message),
  });
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="login-brand"><span>A</span><p><strong>AI 自动内容运营系统</strong><small>企业级公众号运营中枢</small></p></div>
        <div className="login-thesis">
          <h1>让内容生产回归<br /><em>判断</em>与<em>创造</em>本身。</h1>
          <p>自动采集信息、生成事实包与文章草稿。<br />关键选题、审核与发布，仍由运营人员掌控。</p>
          <div className="login-capabilities">
            <Capability icon="folder" title="自动采集" caption="Real-time monitoring, intelligent extraction" />
            <Capability icon="spark" title="AI 创作" caption="Multi-model assistance, high-quality drafts" />
            <Capability icon="user" title="人审协同" caption="Review workflow, team collaboration, compliance" />
            <Capability icon="topic" title="微信草稿" caption="One-click WeChat drafts, operational efficiency" />
          </div>
        </div>
        <footer>单租户内部系统　|　L2 人机协同　|　微信草稿安全交付</footer>
      </section>
      <section className="login-form-side">
        <div className="login-form-card">
          <span className="login-eyebrow">WELCOME BACK</span>
          <h2>欢迎回来</h2>
          <p>登录 AI 自动内容运营系统，继续高效运营</p>
          <Form layout="vertical" initialValues={{ email: "admin@example.com", password: "admin" }} onFinish={(values) => login.mutate(values)}>
            <Form.Item label="邮箱" name="email" rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}>
              <Input size="large" prefix={<Icon name="mail" size={18} />} placeholder="name@company.com" />
            </Form.Item>
            <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
              <Input.Password size="large" prefix={<Icon name="lock" size={18} />} placeholder="admin" />
            </Form.Item>
            <div className="login-options"><Checkbox checked={remember} onChange={(event) => setRemember(event.target.checked)}>保持登录状态</Checkbox><button type="button">忘记密码？</button></div>
            <Button size="large" block type="primary" htmlType="submit" loading={login.isPending}>登 录</Button>
          </Form>
          <div className="security-note"><span><Icon name="shield" />受组织权限保护</span><i /><span><Icon name="lock" />数据传输及存储已加密</span></div>
          <div className="login-help"><p>需要帮助？　<a>查看产品文档</a>　·　<a>联系系统管理员</a></p><small>系统不会在页面或日志中展示完整 API Key、AppSecret 等敏感凭证。</small></div>
        </div>
      </section>
    </main>
  );
}

function Capability({ icon, title, caption }: { icon: "folder" | "spark" | "user" | "topic"; title: string; caption: string }) {
  return <article><span><Icon name={icon} size={26} /></span><p><strong>{title}</strong><small>{caption}</small></p></article>;
}

export default function ConsoleRoot() {
  const [authenticatedUser, setAuthenticatedUser] = useState<User | null>(null);
  const session = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
  if (session.isLoading) return <div className="session-loading"><span>A</span><p>正在加载运营工作区...</p></div>;
  const user = session.data ?? authenticatedUser;
  if (!user) return <Login onSuccess={setAuthenticatedUser} />;
  return <FigmaConsole currentUser={user} />;
}

function Console({ currentUser }: { currentUser: User }) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState<PageKey>("dashboard");
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("strategies");
  const [reviewTab, setReviewTab] = useState<ReviewTab>("pending");
  const [sidebarVisible, setSidebarVisible] = useState(false);
  const [selectedMaterialId, setSelectedMaterialId] = useState<string | null>(null);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [selectedArticleId, setSelectedArticleId] = useState<string | null>(null);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [selectedChannelId, setSelectedChannelId] = useState("");
  const [selectedThemeId, setSelectedThemeId] = useState("");
  const [thumbMediaId, setThumbMediaId] = useState("");
  const [sourceOpen, setSourceOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [channelOpen, setChannelOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [strategyOpen, setStrategyOpen] = useState(false);
  const [topicOpen, setTopicOpen] = useState(false);
  const [topicMaterial, setTopicMaterial] = useState<Material | null>(null);
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null);

  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  const materials = useQuery({ queryKey: ["materials"], queryFn: () => api.materials(), refetchInterval: 10000 });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const skills = useQuery({ queryKey: ["skills"], queryFn: api.skills });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.jobs, refetchInterval: 5000 });
  const articles = useQuery({ queryKey: ["articles"], queryFn: api.articles, refetchInterval: 8000 });
  const themes = useQuery({ queryKey: ["themes"], queryFn: api.themes });
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics, refetchInterval: 8000 });
  const channels = useQuery({ queryKey: ["channel-accounts"], queryFn: api.channelAccounts });
  const publications = useQuery({ queryKey: ["publications"], queryFn: api.publications, refetchInterval: 10000 });
  const users = useQuery({ queryKey: ["users"], queryFn: api.users, enabled: currentUser.role === "admin" });
  const auditLogs = useQuery({ queryKey: ["audit-logs"], queryFn: api.auditLogs, enabled: currentUser.role === "admin" });

  const activeArticleId = selectedArticleId ?? articles.data?.[0]?.id ?? null;
  const articleEvidence = useQuery({
    queryKey: ["evidence", activeArticleId],
    queryFn: () => api.articleEvidence(activeArticleId!),
    enabled: Boolean(activeArticleId && page === "articles"),
  });
  const notificationCount = (jobs.data ?? []).filter((item) => item.status.startsWith("failed") || item.status === "waiting_review").length;
  const thumbStorageKey = `content-ops:wechat-thumb:${selectedChannelId || "env:default"}`;

  useEffect(() => {
    if (!selectedChannelId && channels.data?.[0]) setSelectedChannelId(channels.data[0].id);
  }, [channels.data, selectedChannelId]);
  useEffect(() => {
    if (!selectedThemeId && themes.data?.[0]) setSelectedThemeId(themes.data[0].id);
  }, [selectedThemeId, themes.data]);
  useEffect(() => {
    setThumbMediaId(window.localStorage.getItem(thumbStorageKey) ?? "");
  }, [thumbStorageKey]);
  useEffect(() => {
    const stream = new EventSource("/api/v1/events/jobs");
    stream.onmessage = () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
      void queryClient.invalidateQueries({ queryKey: ["topics"] });
      void queryClient.invalidateQueries({ queryKey: ["materials"] });
    };
    return () => stream.close();
  }, [queryClient]);

  const invalidate = (...keys: string[]) => Promise.all(keys.map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
  const navigate = (nextPage: PageKey, subtab?: SettingsTab | ReviewTab) => {
    setPage(nextPage);
    if (nextPage === "settings" && subtab) setSettingsTab(subtab as SettingsTab);
    if (nextPage === "review" && subtab) setReviewTab(subtab as ReviewTab);
    setSidebarVisible(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const handleSearch = (value: string) => {
    const term = value.trim().toLowerCase();
    if (!term) return;
    const material = materials.data?.find((item) => `${item.title} ${item.content_excerpt}`.toLowerCase().includes(term));
    if (material) { setSelectedMaterialId(material.id); navigate("materials"); return; }
    const topic = topics.data?.find((item) => item.title.toLowerCase().includes(term));
    if (topic) { setSelectedTopicId(topic.id); navigate("topics"); return; }
    const article = articles.data?.find((item) => item.title.toLowerCase().includes(term));
    if (article) { setSelectedArticleId(article.id); navigate("articles"); return; }
    message.info("没有找到匹配的内容、选题或素材");
  };

  const triageMaterial = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "ignore" | "reopen" }) => api.triageMaterial(id, decision),
    onSuccess: () => void invalidate("materials"),
    onError: (error: Error) => message.error(error.message),
  });
  const scanSources = useMutation({
    mutationFn: async () => {
      const enabled = (sources.data ?? []).filter((item) => item.enabled);
      const results = await Promise.all(enabled.map((item) => api.collectSource(item.id)));
      return results.reduce((total, item) => total + item.count, 0);
    },
    onSuccess: (count) => { message.success(`扫描完成，共采集 ${count} 条素材`); void invalidate("sources", "materials"); },
    onError: (error: Error) => message.error(error.message),
  });
  const createTopicFromMaterial = useMutation({
    mutationFn: ({ materialId, strategyId }: { materialId: string; strategyId: string }) => api.createTopicFromMaterial(materialId, { strategy_id: strategyId }),
    onSuccess: (topic) => { setTopicMaterial(null); setSelectedTopicId(topic.id); message.success("候选选题已创建"); void invalidate("materials", "topics"); navigate("topics"); },
    onError: (error: Error) => message.error(error.message),
  });
  const createTopic = useMutation({
    mutationFn: api.addTopic,
    onSuccess: (topic) => { setTopicOpen(false); setSelectedTopicId(topic.id); void invalidate("topics"); message.success("候选选题已创建"); },
    onError: (error: Error) => message.error(error.message),
  });
  const decideTopic = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "accept" | "reject" | "merge" }) => api.decideTopic(id, decision),
    onSuccess: () => void invalidate("topics"),
    onError: (error: Error) => message.error(error.message),
  });
  const startWriting = useMutation({
    mutationFn: async (id: string) => {
      const topic = topics.data?.find((item) => item.id === id);
      if (topic?.status === "candidate") await api.decideTopic(id, "accept");
      return api.startTopicWriting(id);
    },
    onSuccess: () => { message.success("创作任务已启动"); void invalidate("topics", "materials", "jobs", "articles"); },
    onError: (error: Error) => message.error(error.message),
  });
  const saveRevision = useMutation({
    mutationFn: ({ articleId, markdown }: { articleId: string; markdown: string }) => api.addRevision(articleId, markdown),
    onSuccess: () => { message.success("文章新版本已保存"); void invalidate("articles"); },
    onError: (error: Error) => message.error(error.message),
  });
  const reviewArticle = useMutation({
    mutationFn: ({ articleId, revisionId, decision, comment }: { articleId: string; revisionId: string; decision: "approve" | "request_changes"; comment: string }) => api.reviewArticle(articleId, revisionId, decision, comment),
    onSuccess: (_result, variables) => { message.success(variables.decision === "approve" ? "审核已通过" : "文章已退回修改"); void invalidate("articles", "jobs"); },
    onError: (error: Error) => message.error(error.message),
  });
  const uploadThumb = useMutation({
    mutationFn: (file: File) => api.uploadWechatThumb(file, selectedChannelId || undefined),
    onSuccess: (result) => { setThumbMediaId(result.media_id); window.localStorage.setItem(thumbStorageKey, result.media_id); message.success("封面上传成功"); },
    onError: (error: Error) => message.error(error.message),
  });
  const createDraft = useMutation({
    mutationFn: ({ articleId, revisionId }: { articleId: string; revisionId: string }) => api.createWechatDraft(articleId, revisionId, { thumb_media_id: thumbMediaId, channel_account_id: selectedChannelId || undefined, theme_id: selectedThemeId || undefined }),
    onSuccess: () => { message.success("微信草稿已创建"); void invalidate("articles", "publications"); },
    onError: (error: Error) => message.error(error.message),
  });
  const updateDraft = useMutation({
    mutationFn: ({ articleId, revisionId }: { articleId: string; revisionId: string }) => api.updateWechatDraft(articleId, revisionId, { thumb_media_id: thumbMediaId, channel_account_id: selectedChannelId || undefined, theme_id: selectedThemeId || undefined }),
    onSuccess: () => { message.success("微信草稿已更新"); void invalidate("articles", "publications"); },
    onError: (error: Error) => message.error(error.message),
  });
  const publishDraft = useMutation({
    mutationFn: ({ articleId, revisionId }: { articleId: string; revisionId: string }) => api.publishWechatDraft(articleId, revisionId, selectedChannelId),
    onSuccess: () => { message.success("已提交微信发布"); void invalidate("articles", "publications"); },
    onError: (error: Error) => message.error(error.message),
  });
  const testChannel = useMutation({
    mutationFn: api.testChannelAccount,
    onSuccess: (result) => result.connected ? message.success(result.message) : message.warning(result.message),
    onError: (error: Error) => message.error(error.message),
  });
  const retryJob = useMutation({ mutationFn: api.retryJob, onSuccess: () => void invalidate("jobs"), onError: (error: Error) => message.error(error.message) });
  const runStrategy = useMutation({ mutationFn: (id: string) => api.runStrategy(id), onSuccess: () => { message.success("策略任务已启动"); void invalidate("jobs", "articles"); }, onError: (error: Error) => message.error(error.message) });
  const saveStrategy = useMutation({
    mutationFn: ({ id, payload }: { id?: string; payload: StrategyPayload }) => id ? api.updateStrategy(id, payload) : api.addStrategy(payload),
    onSuccess: (result) => { setStrategyOpen(false); setEditingStrategy(null); setSelectedStrategyId(result.id); message.success("策略组合已保存"); void invalidate("strategies"); },
    onError: (error: Error) => message.error(error.message),
  });
  const toggleStrategy = (strategy: Strategy, enabled: boolean) => saveStrategy.mutate({ id: strategy.id, payload: { name: strategy.name, objective: strategy.objective, schedule: strategy.schedule, automation_level: strategy.automation_level, enabled, config: strategy.config } });
  const addSource = useMutation({ mutationFn: api.addSource, onSuccess: () => { setSourceOpen(false); void invalidate("sources"); }, onError: (error: Error) => message.error(error.message) });
  const collectSource = useMutation({ mutationFn: api.collectSource, onSuccess: (result) => { message.success(`已采集 ${result.count} 条素材`); void invalidate("sources", "materials"); }, onError: (error: Error) => message.error(error.message) });
  const disableSource = useMutation({ mutationFn: api.disableSource, onSuccess: () => void invalidate("sources"), onError: (error: Error) => message.error(error.message) });
  const addModel = useMutation({ mutationFn: api.addModel, onSuccess: () => { setModelOpen(false); void invalidate("models"); }, onError: (error: Error) => message.error(error.message) });
  const testModel = useMutation({ mutationFn: api.testModel, onSuccess: (result) => result.ok ? message.success(result.message) : message.warning(result.message), onError: (error: Error) => message.error(error.message) });
  const disableModel = useMutation({ mutationFn: api.disableModel, onSuccess: () => void invalidate("models"), onError: (error: Error) => message.error(error.message) });
  const importSkill = useMutation({ mutationFn: api.importSkill, onSuccess: () => { message.success("Skill 导入成功"); void invalidate("skills"); }, onError: (error: Error) => message.error(error.message) });
  const publishSkill = useMutation({ mutationFn: api.publishSkill, onSuccess: () => void invalidate("skills"), onError: (error: Error) => message.error(error.message) });
  const disableSkill = useMutation({ mutationFn: api.disableSkill, onSuccess: () => void invalidate("skills"), onError: (error: Error) => message.error(error.message) });
  const addChannel = useMutation({ mutationFn: api.addChannelAccount, onSuccess: () => { setChannelOpen(false); void invalidate("channel-accounts"); }, onError: (error: Error) => message.error(error.message) });
  const disableChannel = useMutation({ mutationFn: api.disableChannelAccount, onSuccess: () => void invalidate("channel-accounts"), onError: (error: Error) => message.error(error.message) });
  const addUser = useMutation({ mutationFn: api.addUser, onSuccess: () => { setUserOpen(false); void invalidate("users"); }, onError: (error: Error) => message.error(error.message) });

  const openStrategy = (strategy?: Strategy) => { setEditingStrategy(strategy ?? null); setStrategyOpen(true); };
  const editingConfig = editingStrategy?.config ?? {};
  const editingModels = stringRecord(editingConfig.model_by_stage);
  const editingSkills = stringRecord(editingConfig.skill_by_stage);
  const strategyInitialValues = editingStrategy ? {
    name: editingStrategy.name,
    objective: editingStrategy.objective,
    schedule: editingStrategy.schedule,
    automation_level: editingStrategy.automation_level,
    enabled: editingStrategy.enabled,
    source_ids: stringArray(editingConfig.source_ids),
    channel_account_id: editingConfig.channel_account_id,
    theme_id: editingConfig.theme_id,
    writing_model_id: editingModels.writing,
    rewrite_model_id: editingModels.rewrite,
    writing_skill_id: editingSkills.writing,
    rewrite_skill_id: editingSkills.rewrite,
    review_skill_id: editingSkills.review,
    human_review_required: (editingConfig.review_rules as { human_review_required?: boolean } | undefined)?.human_review_required !== false,
  } : { schedule: "manual", automation_level: "L2", source_ids: [], enabled: true, human_review_required: true };

  const pageContent = useMemo(() => {
    const shared = {
      sources: sources.data ?? [],
      strategies: strategies.data ?? [],
      materials: materials.data ?? [],
      topics: topics.data ?? [],
      articles: articles.data ?? [],
      jobs: jobs.data ?? [],
    };
    if (page === "dashboard") return <DashboardPage {...shared} onNavigate={navigate} onRetryJob={(id) => retryJob.mutate(id)} onRefresh={() => void invalidate("jobs", "articles", "topics", "materials")} />;
    if (page === "materials") return <MaterialsPage materials={shared.materials} sources={shared.sources} selectedId={selectedMaterialId} onSelect={setSelectedMaterialId} onTriage={(id, decision) => triageMaterial.mutate({ id, decision })} onUse={setTopicMaterial} onScan={() => scanSources.mutate()} scanning={scanSources.isPending} />;
    if (page === "topics") return <TopicsPage topics={shared.topics} strategies={shared.strategies} materials={shared.materials} selectedId={selectedTopicId} onSelect={setSelectedTopicId} onDecision={(id, decision) => decideTopic.mutate({ id, decision })} onStart={(id) => startWriting.mutate(id)} onCreate={() => setTopicOpen(true)} onOpenArticles={() => navigate("articles")} starting={startWriting.isPending} />;
    if (page === "articles") return <ArticleEditorPage articles={shared.articles} selectedId={activeArticleId} evidence={articleEvidence.data} themes={themes.data ?? []} selectedThemeId={selectedThemeId} onSelect={setSelectedArticleId} onThemeChange={setSelectedThemeId} onSave={(articleId, markdown) => saveRevision.mutate({ articleId, markdown })} onOpenReview={(id) => { setSelectedReviewId(id); navigate("review", "pending"); }} saving={saveRevision.isPending} />;
    if (page === "review") return <ReviewPublishPage tab={reviewTab} onTabChange={setReviewTab} articles={shared.articles} publications={publications.data ?? []} selectedId={selectedReviewId} onSelect={setSelectedReviewId} onReview={(articleId, revisionId, decision, comment) => reviewArticle.mutate({ articleId, revisionId, decision, comment })} channels={channels.data ?? []} themes={themes.data ?? []} selectedChannelId={selectedChannelId} selectedThemeId={selectedThemeId} thumbMediaId={thumbMediaId} onChannelChange={setSelectedChannelId} onThemeChange={setSelectedThemeId} onThumb={(file) => uploadThumb.mutate(file)} onCreateDraft={(articleId, revisionId) => createDraft.mutate({ articleId, revisionId })} onUpdateDraft={(articleId, revisionId) => updateDraft.mutate({ articleId, revisionId })} onPublish={(articleId, revisionId) => publishDraft.mutate({ articleId, revisionId })} onTestChannel={(id) => testChannel.mutate(id)} busy={createDraft.isPending || updateDraft.isPending || uploadThumb.isPending} />;
    return <SettingsPage tab={settingsTab} onTabChange={setSettingsTab} strategies={shared.strategies} sources={shared.sources} models={models.data ?? []} skills={skills.data ?? []} themes={themes.data ?? []} channels={channels.data ?? []} users={users.data ?? []} auditLogs={auditLogs.data ?? []} selectedStrategyId={selectedStrategyId} onSelectStrategy={setSelectedStrategyId} onNewStrategy={() => openStrategy()} onEditStrategy={openStrategy} onRunStrategy={(id) => runStrategy.mutate(id)} onToggleStrategy={toggleStrategy} onAddSource={() => setSourceOpen(true)} onCollectSource={(id) => collectSource.mutate(id)} onDisableSource={(id) => disableSource.mutate(id)} onAddModel={() => setModelOpen(true)} onTestModel={(id) => testModel.mutate(id)} onDisableModel={(id) => disableModel.mutate(id)} onImportSkill={(file) => importSkill.mutate(file)} onPublishSkill={(id) => publishSkill.mutate(id)} onDisableSkill={(id) => disableSkill.mutate(id)} onAddChannel={() => setChannelOpen(true)} onTestChannel={(id) => testChannel.mutate(id)} onDisableChannel={(id) => disableChannel.mutate(id)} onAddUser={() => setUserOpen(true)} />;
  }, [activeArticleId, articleEvidence.data, articles.data, auditLogs.data, channels.data, createDraft.isPending, jobs.data, materials.data, models.data, page, publications.data, reviewTab, scanSources.isPending, selectedChannelId, selectedMaterialId, selectedReviewId, selectedStrategyId, selectedThemeId, selectedTopicId, settingsTab, skills.data, sources.data, strategies.data, themes.data, thumbMediaId, topics.data, updateDraft.isPending, uploadThumb.isPending, users.data]);

  return (
    <div className={`console-shell ${sidebarVisible ? "sidebar-visible" : ""}`}>
      <Sidebar page={page} settingsTab={settingsTab} onNavigate={navigate} />
      <div className="console-main">
        <Topbar page={page} settingsTab={settingsTab} currentUser={currentUser} notificationCount={notificationCount} onToggleSidebar={() => setSidebarVisible((value) => !value)} onSearch={handleSearch} onLogout={() => Modal.confirm({ title: "退出当前账号？", content: currentUser.email, okText: "退出登录", cancelText: "取消", onOk: async () => { await api.logout(); window.location.reload(); } })} />
        <div className="console-content">{pageContent}</div>
      </div>
      <button className="sidebar-backdrop" type="button" aria-label="关闭侧栏" onClick={() => setSidebarVisible(false)} />

      <Modal title={editingStrategy ? "编辑内容策略" : "新增内容策略"} open={strategyOpen} footer={null} onCancel={() => setStrategyOpen(false)} width={760}>
        <Form key={editingStrategy?.id ?? "new"} layout="vertical" initialValues={strategyInitialValues} onFinish={(values: Record<string, unknown>) => {
          const modelByStage = Object.fromEntries([["writing", values.writing_model_id], ["rewrite", values.rewrite_model_id]].filter(([, value]) => typeof value === "string"));
          const skillByStage = Object.fromEntries([["writing", values.writing_skill_id], ["rewrite", values.rewrite_skill_id], ["review", values.review_skill_id]].filter(([, value]) => typeof value === "string"));
          saveStrategy.mutate({ id: editingStrategy?.id, payload: { name: String(values.name), objective: String(values.objective), schedule: String(values.schedule), automation_level: String(values.automation_level), enabled: values.enabled === true, config: { source_ids: values.source_ids as string[] ?? [], channel_account_id: values.channel_account_id as string || undefined, theme_id: values.theme_id as string || undefined, model_by_stage: modelByStage as Record<string, string>, skill_by_stage: skillByStage as Record<string, string>, review_rules: { human_review_required: values.human_review_required !== false } } } });
        }}>
          <div className="modal-form-grid">
            <Form.Item label="策略名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item label="运行频率" name="schedule"><Select options={[{ label: "手动执行", value: "manual" }, { label: "每小时", value: "hourly" }, { label: "每天", value: "daily" }]} /></Form.Item>
            <Form.Item className="span-2" label="内容目标" name="objective" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
            <Form.Item className="span-2" label="信息源组合" name="source_ids" extra="留空表示使用全部启用的信息源"><Select mode="multiple" allowClear options={(sources.data ?? []).map((item) => ({ label: item.name, value: item.id }))} /></Form.Item>
            <Form.Item label="自动化等级" name="automation_level"><Select options={["L1", "L2", "L3", "L4"].map((value) => ({ label: value, value }))} /></Form.Item>
            <Form.Item label="默认发布账号" name="channel_account_id"><Select allowClear options={(channels.data ?? []).map((item) => ({ label: item.name, value: item.id }))} /></Form.Item>
            <Form.Item label="写作模型" name="writing_model_id"><Select allowClear options={(models.data ?? []).filter((item) => item.enabled).map((item) => ({ label: `${item.provider} / ${item.name}`, value: item.id }))} /></Form.Item>
            <Form.Item label="改写模型" name="rewrite_model_id"><Select allowClear options={(models.data ?? []).filter((item) => item.enabled).map((item) => ({ label: `${item.provider} / ${item.name}`, value: item.id }))} /></Form.Item>
            <Form.Item label="Writing Skill" name="writing_skill_id"><Select allowClear options={(skills.data ?? []).filter((item) => item.status === "published").map((item) => ({ label: `${item.name} / ${item.version}`, value: item.id }))} /></Form.Item>
            <Form.Item label="Rewrite Skill" name="rewrite_skill_id"><Select allowClear options={(skills.data ?? []).filter((item) => item.status === "published").map((item) => ({ label: `${item.name} / ${item.version}`, value: item.id }))} /></Form.Item>
            <Form.Item label="Review Skill" name="review_skill_id"><Select allowClear options={(skills.data ?? []).filter((item) => item.status === "published").map((item) => ({ label: `${item.name} / ${item.version}`, value: item.id }))} /></Form.Item>
            <Form.Item label="默认排版主题" name="theme_id"><Select allowClear options={(themes.data ?? []).filter((item) => item.enabled).map((item) => ({ label: item.name, value: item.id }))} /></Form.Item>
          </div>
          <Space><Form.Item name="enabled" valuePropName="checked"><Checkbox>启用自动调度</Checkbox></Form.Item><Form.Item name="human_review_required" valuePropName="checked"><Checkbox>生成后必须人工审核</Checkbox></Form.Item></Space>
          <Button type="primary" htmlType="submit" loading={saveStrategy.isPending}>保存策略组合</Button>
        </Form>
      </Modal>

      <Modal title="创建候选选题" open={topicOpen} footer={null} onCancel={() => setTopicOpen(false)}>
        <Form layout="vertical" onFinish={(values) => createTopic.mutate(values)}>
          <Form.Item label="选题标题" name="title" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="所属策略" name="strategy_id" rules={[{ required: true }]}><Select options={(strategies.data ?? []).map((item) => ({ label: item.name, value: item.id }))} /></Form.Item>
          <Form.Item label="选题说明" name="rationale"><Input.TextArea rows={3} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={createTopic.isPending}>创建候选选题</Button>
        </Form>
      </Modal>
      <Modal title="选择写作策略" open={Boolean(topicMaterial)} footer={null} onCancel={() => setTopicMaterial(null)}>
        {topicMaterial && <Form layout="vertical" onFinish={(values: { strategy_id: string }) => createTopicFromMaterial.mutate({ materialId: topicMaterial.id, strategyId: values.strategy_id })}><h3>{topicMaterial.title}</h3><p>{topicMaterial.content_excerpt}</p><Form.Item label="写入哪个内容策略" name="strategy_id" rules={[{ required: true }]}><Select options={(strategies.data ?? []).filter((item) => item.enabled).map((item) => ({ label: item.name, value: item.id }))} /></Form.Item><Button type="primary" htmlType="submit">创建候选选题</Button></Form>}
      </Modal>
      <Modal title="添加信息源" open={sourceOpen} footer={null} onCancel={() => setSourceOpen(false)}><Form layout="vertical" onFinish={(values) => addSource.mutate(values)}><Form.Item label="名称" name="name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item label="类型" name="source_type" initialValue="rss"><Select options={[{ label: "RSS", value: "rss" }, { label: "网页 URL", value: "url" }, { label: "手动", value: "manual" }]} /></Form.Item><Form.Item label="地址" name="url"><Input /></Form.Item><Button type="primary" htmlType="submit">保存</Button></Form></Modal>
      <Modal title="添加模型" open={modelOpen} footer={null} onCancel={() => setModelOpen(false)}><Form layout="vertical" onFinish={(values) => addModel.mutate(values)}><Form.Item label="供应商" name="provider" initialValue="openai"><Input /></Form.Item><Form.Item label="模型名称" name="name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item label="API Base URL" name="api_base_url"><Input /></Form.Item><Form.Item label="API Key" name="api_key"><Input.Password /></Form.Item><Button type="primary" htmlType="submit">保存模型</Button></Form></Modal>
      <Modal title="绑定微信公众号" open={channelOpen} footer={null} onCancel={() => setChannelOpen(false)}><Form layout="vertical" onFinish={(values) => addChannel.mutate(values)}><Form.Item label="账号名称" name="name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item label="App ID" name="app_id" rules={[{ required: true }]}><Input /></Form.Item><Form.Item label="App Secret" name="app_secret" rules={[{ required: true }]}><Input.Password /></Form.Item><Form.Item name="publish_enabled" valuePropName="checked"><Checkbox>允许发布</Checkbox></Form.Item><Button type="primary" htmlType="submit">保存账号</Button></Form></Modal>
      <Modal title="添加用户" open={userOpen} footer={null} onCancel={() => setUserOpen(false)}><Form layout="vertical" onFinish={(values) => addUser.mutate(values)}><Form.Item label="邮箱" name="email" rules={[{ required: true, type: "email" }]}><Input /></Form.Item><Form.Item label="密码" name="password" rules={[{ required: true, min: 12 }]}><Input.Password /></Form.Item><Form.Item label="角色" name="role" initialValue="operator"><Select options={[{ label: "运营", value: "operator" }, { label: "审核", value: "reviewer" }, { label: "管理员", value: "admin" }]} /></Form.Item><Button type="primary" htmlType="submit">保存用户</Button></Form></Modal>
    </div>
  );
}





