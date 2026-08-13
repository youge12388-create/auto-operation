import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Checkbox,
  Card,
  Form,
  Input,
  Layout,
  Menu,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  Select,
  message,
} from "antd";
import { api, Article, CalendarItem, ChannelAccount, Job, Material, Model, Skill, Source, Strategy, StrategyPayload, Theme, Topic, User } from "./api";
import "./styles.css";

const { Header, Sider, Content } = Layout;

const ENV_CHANNEL_ID = "env:default";

const NAV_ITEMS = [
  { key: "dashboard", label: "\u5DE5\u4F5C\u53F0" },
  { key: "materials", label: "\u7D20\u6750\u6C60" },
  { key: "content", label: "\u9009\u9898\u4E0E\u521B\u4F5C" },
  { key: "publish", label: "\u5BA1\u6838\u4E0E\u53D1\u5E03" },
  { key: "system", label: "\u7B56\u7565\u4E0E\u8BBE\u7F6E" },
];

const ARTICLE_STATUS_META: Record<string, { label: string; color?: string }> = {
  generated: { label: "待审核" },
  approved: { label: "已审核", color: "green" },
  changes_requested: { label: "需修改", color: "orange" },
  publishing: { label: "发布中", color: "processing" },
  published: { label: "已发布", color: "green" },
};

function ArticleStatus({ status }: { status: string }) {
  const meta = ARTICLE_STATUS_META[status] ?? { label: status };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}
const MATERIAL_STATUS_META: Record<Material["triage_status"], { label: string; color?: string }> = {
  inbox: { label: "\u5F85\u7B5B\u9009", color: "blue" },
  selected: { label: "\u5DF2\u9009\u4E3A\u4F9D\u636E", color: "gold" },
  ignored: { label: "\u5DF2\u5FFD\u7565" },
  used: { label: "\u6B63\u5728\u521B\u4F5C", color: "purple" },
};

const TOPIC_STATUS_META: Record<string, { label: string; color?: string }> = {
  candidate: { label: "\u5F85\u786E\u8BA4", color: "blue" },
  accepted: { label: "\u5DF2\u786E\u8BA4", color: "green" },
  writing: { label: "\u6B63\u5728\u521B\u4F5C", color: "purple" },
  rejected: { label: "\u5DF2\u62D2\u7EDD" },
  merged: { label: "\u5DF2\u5408\u5E76" },
};

function MaterialStatus({ status }: { status: Material["triage_status"] }) {
  const meta = MATERIAL_STATUS_META[status];
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

function TopicStatus({ status }: { status: string }) {
  const meta = TOPIC_STATUS_META[status] ?? { label: status };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

type IconName = "menu" | "grid" | "content" | "chart" | "settings" | "search" | "bell" | "help" | "user" | "team" | "file" | "send" | "upload" | "report" | "edit" | "trash" | "eye" | "database" | "clock";

function UiIcon({ name, size = 18 }: { name: IconName; size?: number }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const shapes: Record<IconName, React.ReactNode> = {
    menu: <><path {...common} d="M4 7h16M4 12h16M4 17h16" /></>,
    grid: <><rect {...common} x="4" y="4" width="6" height="6" rx="1" /><rect {...common} x="14" y="4" width="6" height="6" rx="1" /><rect {...common} x="4" y="14" width="6" height="6" rx="1" /><rect {...common} x="14" y="14" width="6" height="6" rx="1" /></>,
    content: <><path {...common} d="M6 3.8h8l4 4V20H6z" /><path {...common} d="M14 3.8v4h4M9 12h6M9 16h6" /></>,
    chart: <><path {...common} d="M4 19.5h16M6 17V9M11 17V5M16 17v-7" /></>,
    settings: <><path {...common} d="M12 4.5l1.1 1.8 2.1.4.8 2 1.8 1.2-.7 2 1 1.9-1.6 1.4-.2 2.2-2.1.5-1.1 1.8-2.1-.5-1.8.9-1.5-1.6-2.1-.4-.2-2.2-1.5-1.4 1-1.9-.7-2 1.8-1.2.8-2 2.1-.4z" /><circle {...common} cx="12" cy="12" r="2.5" /></>,
    search: <><circle {...common} cx="11" cy="11" r="6" /><path {...common} d="m16 16 4 4" /></>,
    bell: <><path {...common} d="M6 16.5h12l-1.4-2.1V10a4.6 4.6 0 0 0-9.2 0v4.4z" /><path {...common} d="M10 19h4" /></>,
    help: <><circle {...common} cx="12" cy="12" r="8" /><path {...common} d="M9.8 9.3a2.4 2.4 0 1 1 3.8 2c-1.1.7-1.6 1.2-1.6 2.2M12 16.5h.01" /></>,
    user: <><circle {...common} cx="12" cy="8" r="3" /><path {...common} d="M5.5 20a6.5 6.5 0 0 1 13 0" /></>,
    team: <><circle {...common} cx="9" cy="9" r="3" /><path {...common} d="M3.8 19a5.2 5.2 0 0 1 10.4 0M16 7a2.5 2.5 0 0 1 0 5M16 15a4.3 4.3 0 0 1 3.8 4" /></>,
    file: <><path {...common} d="M6 3.8h8l4 4V20H6z" /><path {...common} d="M14 3.8v4h4M9 12h6M9 16h4" /></>,
    send: <><path {...common} d="m4 5 16 7-16 7 3-7z" /><path {...common} d="M7 12h13" /></>,
    upload: <><path {...common} d="M5 16v3h14v-3M12 4v11M8.5 7.5 12 4l3.5 3.5" /></>,
    report: <><path {...common} d="M5 4h14v16H5z" /><path {...common} d="M8 16v-3M12 16V9M16 16v-6" /></>,
    edit: <><path {...common} d="m5 16.5-.8 3.3 3.3-.8L18 8.5 15.5 6zM14.5 7l2.5 2.5" /></>,
    trash: <><path {...common} d="M5 7h14M10 4h4l1 3H9zM7 7l1 13h8l1-13M10 10v7M14 10v7" /></>,
    eye: <><path {...common} d="M3.5 12s3-5 8.5-5 8.5 5 8.5 5-3 5-8.5 5-8.5-5-8.5-5z" /><circle {...common} cx="12" cy="12" r="2" /></>,
    database: <><ellipse {...common} cx="12" cy="6" rx="7" ry="3" /><path {...common} d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
    clock: <><circle {...common} cx="12" cy="12" r="8" /><path {...common} d="M12 7v5l3 2" /></>,
  };
  return <svg className="ui-icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">{shapes[name]}</svg>;
}

function QuickAction({ icon, label, caption, onClick }: { icon: IconName; label: string; caption: string; onClick: () => void }) {
  return (
    <button type="button" className="quick-action" onClick={onClick}>
      <span className={`quick-action-icon quick-action-icon--${icon}`}><UiIcon name={icon} size={22} /></span>
      <span className="quick-action-label">{label}</span>
      <span className="quick-action-caption">{caption}</span>
    </button>
  );
}
function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function stringRecord(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value).filter(([, item]) => typeof item === "string")) as Record<string, string>;
}

function CompositionNode({ icon, label, value, tone }: { icon: IconName; label: string; value: string; tone: string }) {
  return (
    <div className={`composition-node composition-node--${tone}`}>
      <span className="composition-node-icon"><UiIcon name={icon} size={18} /></span>
      <span className="composition-node-label">{label}</span>
      <strong className="composition-node-value" title={value}>{value}</strong>
    </div>
  );
}

function StrategyComposition({
  strategy,
  sources,
  models,
  skills,
  themes,
  channelAccounts,
  onEdit,
  onRun,
  running,
}: {
  strategy: Strategy;
  sources: Source[];
  models: Model[];
  skills: Skill[];
  themes: Theme[];
  channelAccounts: ChannelAccount[];
  onEdit: (strategy: Strategy) => void;
  onRun: (id: string) => void;
  running: boolean;
}) {
  const config = strategy.config ?? {};
  const sourceIds = stringArray(config.source_ids);
  const sourceNames = sourceIds.map((id) => sources.find((source) => source.id === id)?.name).filter((name): name is string => Boolean(name));
  const modelByStage = stringRecord(config.model_by_stage);
  const modelNames = Object.values(modelByStage).map((id) => models.find((model) => model.id === id)?.name).filter((name): name is string => Boolean(name));
  const skillByStage = stringRecord(config.skill_by_stage);
  const skillIds = [...new Set([...Object.values(skillByStage), ...stringArray(config.skill_ids)])];
  const skillNames = skillIds.map((id) => skills.find((skill) => skill.id === id)?.name).filter((name): name is string => Boolean(name));
  const themeName = themes.find((theme) => theme.id === config.theme_id)?.name;
  const channelName = channelAccounts.find((account) => account.id === config.channel_account_id)?.name;
  const reviewRules = config.review_rules && typeof config.review_rules === "object" ? config.review_rules as { human_review_required?: boolean } : {};
  const disabledSteps = stringArray(config.disabled_steps);

  return (
    <article className="strategy-composition-card">
      <div className="strategy-composition-heading">
        <div>
          <span className="composition-kicker">COMPOSITION · V{strategy.version}</span>
          <strong>{strategy.name}</strong>
          <p>{strategy.objective}</p>
        </div>
        <Tag color={strategy.enabled ? "green" : "default"}>{strategy.enabled ? "自动调度" : "手动运行"}</Tag>
      </div>
      <div className="composition-flow">
        <CompositionNode icon="database" label="信息源" value={sourceNames.join("、") || "全部启用来源"} tone="blue" />
        <span className="composition-connector" aria-hidden="true" />
        <CompositionNode icon="content" label="Skill" value={skillNames.join("、") || "未绑定 Skill"} tone="purple" />
        <span className="composition-connector" aria-hidden="true" />
        <CompositionNode icon="settings" label="模型" value={modelNames.join("、") || "使用任务模型"} tone="orange" />
        <span className="composition-connector" aria-hidden="true" />
        <CompositionNode icon="report" label="排版" value={themeName || "默认排版"} tone="green" />
        <span className="composition-connector" aria-hidden="true" />
        <CompositionNode icon="send" label="发布账号" value={channelName || "手动选择账号"} tone="pink" />
      </div>
      <div className="composition-footer">
        <span>流程：{disabledSteps.length ? `已关闭 ${disabledSteps.join("、")}` : "完整内容流程"}</span>
        <span>{reviewRules.human_review_required === false ? "自动审核" : "人工审核"}</span>
        <span className="composition-actions">
          <Button size="small" onClick={() => onEdit(strategy)}>编辑组合</Button>
          <Button size="small" type="primary" loading={running} onClick={() => onRun(strategy.id)}>运行组合</Button>
        </span>
      </div>
    </article>
  );
}
function Login({ onSuccess }: { onSuccess: (user: User) => void }) {
  const mutation = useMutation({
    mutationFn: (values: { email: string; password: string }) => api.login(values.email, values.password),
    onSuccess,
    onError: (error: Error) => message.error(error.message),
  });

  return (
    <div className="login-shell">
      <Card className="login-card">
        <Typography.Title level={2}>AI 自动内容运营系统</Typography.Title>
        <Typography.Paragraph type="secondary">
          配置内容策略，自动完成采集、选题、写作、审核和草稿生成。
        </Typography.Paragraph>
        <Form layout="vertical" onFinish={(values) => mutation.mutate(values)}>
          <Form.Item label="邮箱" name="email" rules={[{ required: true, type: "email" }]}>
            <Input placeholder="admin@example.com" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={mutation.isPending} block>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const session = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });

  if (session.isLoading) return <div className="session-loading">加载中…</div>;
  const user = session.data ?? currentUser;
  if (!authenticated && !user) {
    return <Login onSuccess={(loggedInUser) => { setCurrentUser(loggedInUser); setAuthenticated(true); }} />;
  }
  return <Dashboard currentUser={user!} />;
}

function Dashboard({ currentUser }: { currentUser: User }) {
  const queryClient = useQueryClient();
  const [sourceOpen, setSourceOpen] = useState(false);
  const [strategyOpen, setStrategyOpen] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null);
  const [modelOpen, setModelOpen] = useState(false);
  const [channelOpen, setChannelOpen] = useState(false);
  const [selectedChannelId, setSelectedChannelId] = useState("");
  const [thumbMediaId, setThumbMediaId] = useState("");
  const [editingArticle, setEditingArticle] = useState<Article | null>(null);
  const [selectedThemeId, setSelectedThemeId] = useState("");
  const [evidenceArticleId, setEvidenceArticleId] = useState<string | null>(null);
  const [materialPreviewId, setMaterialPreviewId] = useState<string | null>(null);
  const [topicMaterial, setTopicMaterial] = useState<Material | null>(null);
  const [userOpen, setUserOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const users = useQuery({ queryKey: ["users"], queryFn: api.users, enabled: currentUser.role === "admin" });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  const materials = useQuery({ queryKey: ["materials"], queryFn: () => api.materials(), refetchInterval: 5000 });
  const strategies = useQuery({ queryKey: ["strategies"], queryFn: api.strategies });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const skills = useQuery({ queryKey: ["skills"], queryFn: api.skills });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.jobs, refetchInterval: 5000 });
  const calendar = useQuery({ queryKey: ["calendar"], queryFn: api.calendar, refetchInterval: 10000 });
  const articles = useQuery({ queryKey: ["articles"], queryFn: api.articles, refetchInterval: 5000 });
  const themes = useQuery({ queryKey: ["themes"], queryFn: api.themes });
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics, refetchInterval: 5000 });
  const channelAccounts = useQuery({ queryKey: ["channel-accounts"], queryFn: api.channelAccounts });
  const currentRevision = editingArticle?.revisions[editingArticle.revisions.length - 1];
  const thumbStorageKey = `content-ops:wechat-thumb:${selectedChannelId || ENV_CHANNEL_ID}`;
  const notificationCount = jobs.data?.filter((job) => ["failed_retryable", "failed_terminal", "waiting_review"].includes(job.status)).length ?? 0;
  const activeNavItem = NAV_ITEMS.find((item) => item.key === activeSection) ?? NAV_ITEMS[0];
  const editingConfig = editingStrategy?.config ?? {};
  const editingModelByStage = stringRecord(editingConfig.model_by_stage);
  const editingSkillByStage = stringRecord(editingConfig.skill_by_stage);
  const editingReviewRules = editingConfig.review_rules && typeof editingConfig.review_rules === "object" ? editingConfig.review_rules as { human_review_required?: boolean } : {};
  const strategyInitialValues = editingStrategy ? {
    name: editingStrategy.name,
    objective: editingStrategy.objective,
    schedule: editingStrategy.schedule,
    automation_level: editingStrategy.automation_level,
    enabled: editingStrategy.enabled,
    source_ids: stringArray(editingConfig.source_ids),
    channel_account_id: typeof editingConfig.channel_account_id === "string" ? editingConfig.channel_account_id : undefined,
    theme_id: typeof editingConfig.theme_id === "string" ? editingConfig.theme_id : undefined,
    writing_model_id: editingModelByStage.writing,
    style_model_id: editingModelByStage.style,
    rewrite_model_id: editingModelByStage.rewrite,
    writing_skill_id: editingSkillByStage.writing,
    style_skill_id: editingSkillByStage.style,
    rewrite_skill_id: editingSkillByStage.rewrite,
    disabled_steps: stringArray(editingConfig.disabled_steps),
    human_review_required: editingReviewRules.human_review_required !== false,
  } : { schedule: "manual", automation_level: "L2", enabled: false, source_ids: [], human_review_required: true };
  const selectSection = (key: string) => {
    const item = NAV_ITEMS.find((navItem) => navItem.key === key) ?? NAV_ITEMS[0];
    setActiveSection(item.key);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const themePreview = useQuery({
    queryKey: ["theme-preview", editingArticle?.id, currentRevision?.id, selectedThemeId],
    queryFn: () => api.previewTheme(editingArticle!.id, currentRevision!.id, selectedThemeId),
    enabled: Boolean(editingArticle && currentRevision && selectedThemeId),
  });
  const evidence = useQuery({
    queryKey: ["evidence", evidenceArticleId],
    queryFn: () => api.articleEvidence(evidenceArticleId!),
    enabled: Boolean(evidenceArticleId),
  });

  const materialPreview = useQuery({
    queryKey: ["material", materialPreviewId],
    queryFn: () => api.material(materialPreviewId!),
    enabled: Boolean(materialPreviewId),
  });
  useEffect(() => {
    if (editingArticle && !selectedThemeId && themes.data?.[0]) setSelectedThemeId(themes.data[0].id);
  }, [editingArticle, selectedThemeId, themes.data]);
  useEffect(() => {
    if (!selectedChannelId && channelAccounts.data?.length) setSelectedChannelId(channelAccounts.data[0].id);
  }, [channelAccounts.data, selectedChannelId]);

  useEffect(() => {
    setThumbMediaId(window.localStorage.getItem(thumbStorageKey) ?? "");
  }, [thumbStorageKey]);

  useEffect(() => {
    const stream = new EventSource("/api/v1/events/jobs");
    stream.onmessage = () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    };
    return () => stream.close();
  }, [queryClient]);

  const triageMaterial = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "ignore" | "reopen" }) => api.triageMaterial(id, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["materials"] }),
    onError: (error: Error) => message.error(error.message),
  });
  const createTopicFromMaterial = useMutation({
    mutationFn: ({ materialId, strategyId }: { materialId: string; strategyId: string }) => api.createTopicFromMaterial(materialId, { strategy_id: strategyId }),
    onSuccess: () => {
      setTopicMaterial(null);
      queryClient.invalidateQueries({ queryKey: ["materials"] });
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      selectSection("content");
      message.success("\u5DF2\u521B\u5EFA\u5019\u9009\u9009\u9898\uFF0C\u8BF7\u786E\u8BA4\u540E\u5F00\u59CB\u521B\u4F5C");
    },
    onError: (error: Error) => message.error(error.message),
  });
  const startTopicWriting = useMutation({
    mutationFn: (id: string) => api.startTopicWriting(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      queryClient.invalidateQueries({ queryKey: ["materials"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      message.success("\u521B\u4F5C\u4EFB\u52A1\u5DF2\u542F\u52A8");
    },
    onError: (error: Error) => message.error(error.message),
  });
  const addUser = useMutation({
    mutationFn: api.addUser,
    onSuccess: () => { setUserOpen(false); queryClient.invalidateQueries({ queryKey: ["users"] }); },
    onError: (error: Error) => message.error(error.message),
  });  const addSource = useMutation({
    mutationFn: api.addSource,
    onSuccess: () => {
      setSourceOpen(false);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error: Error) => message.error(error.message),
  });
  const disableSource = useMutation({
    mutationFn: api.disableSource,
    onSuccess: () => queryC…5796 tokens truncated…"点击后选择 JPG 封面" : undefined} disabled={!revision} loading={createWechatDraft.isPending} onClick={() => { if (!revision) return; if (!thumbMediaId) { message.info("请先选择一张 JPG 封面"); openCoverPicker(); return; } createWechatDraft.mutate({ articleId: row.id, revisionId: revision.id }); }}>{thumbMediaId ? "创建微信草稿" : "先上传封面"}</Button>
                  {selectedChannelId && Boolean(channelAccounts.data?.find((account) => account.id === selectedChannelId)?.capabilities.publish) && <Button danger disabled={!revision || ["publishing", "published"].includes(row.status)} loading={publishWechatDraft.isPending} onClick={() => revision && publishWechatDraft.mutate({ articleId: row.id, revisionId: revision.id })}>{row.status === "publishing" ? "发布中" : "提交发布"}</Button>}
                </Space>;
              } },
            ]} />
          </Card>

          {currentUser.role === "admin" && <Card title="用户与权限" extra={<Button type="primary" onClick={() => setUserOpen(true)}>添加用户</Button>} className="panel page-section page-panel page-system">
            <Table rowKey="id" loading={users.isLoading} dataSource={users.data} pagination={false} columns={[
              { title: "邮箱", dataIndex: "email" },
              { title: "角色", dataIndex: "role" },
            ]} />
          </Card>}
          <Card title="模型中心" id="system-settings" extra={<Button type="primary" onClick={() => setModelOpen(true)}>添加模型</Button>} className="panel page-section page-panel page-system">
            <Table rowKey="id" loading={models.isLoading} dataSource={models.data} pagination={false} columns={[
              { title: "供应商", dataIndex: "provider" },
              { title: "模型", dataIndex: "name" },
              { title: "密钥", render: (_: unknown, row: Model) => row.has_api_key ? <Tag color="green">已配置</Tag> : <Tag>未配置</Tag> },
              { title: "操作", render: (_: unknown, row: Model) => <Space><Button size="small" loading={testModel.isPending} onClick={() => testModel.mutate(row.id)}>测试模型</Button><Button size="small" danger loading={disableModel.isPending} onClick={() => disableModel.mutate(row.id)}>停用</Button></Space> },
            ]} />
          </Card>

          <Card title="Skill 中心" extra={<Upload accept=".zip" showUploadList={false} beforeUpload={(file) => { importSkill.mutate(file); return false; }}><Button loading={importSkill.isPending}>导入 Skill</Button></Upload>} className="panel page-section page-panel page-system">
            <Table rowKey="id" loading={skills.isLoading} dataSource={skills.data} pagination={false} columns={[
              { title: "名称", dataIndex: "name" },
              { title: "类型", dataIndex: "skill_type" },
              { title: "版本", dataIndex: "version" },
              { title: "状态", render: (_: unknown, row: Skill) => <Tag>{row.status}</Tag> },
              { title: "操作", render: (_: unknown, row: Skill) => <Space>{row.status === "draft" && <Button size="small" onClick={() => publishSkill.mutate(row.id)}>发布</Button>}{row.status === "published" && <Button size="small" danger onClick={() => disableSkill.mutate(row.id)}>停用</Button>}</Space> },
            ]} />
          </Card>

          <Card title="策略组合" extra={<Button type="primary" onClick={() => openNewStrategy()}>新增组合</Button>} className="panel page-section page-panel page-system composition-panel">
            {strategies.isLoading ? <div className="composition-empty">正在读取策略组合…</div> : strategies.data?.length ? <div className="composition-list">
              {strategies.data.map((strategy) => <StrategyComposition key={strategy.id} strategy={strategy} sources={sources.data ?? []} models={models.data ?? []} skills={skills.data ?? []} themes={themes.data ?? []} channelAccounts={channelAccounts.data ?? []} onEdit={(selected) => { setEditingStrategy(selected); setStrategyOpen(true); }} onRun={(id) => runStrategy.mutate(id)} running={runStrategy.isPending} />)}
            </div> : <div className="composition-empty">还没有策略组合，先把信息源、Skill、模型和发布账号组装起来。</div>}
          </Card>
          <Card title="内容策略" extra={<Button type="primary" onClick={() => openNewStrategy()}>新增策略</Button>} className="panel page-section page-panel page-content">
            <Table rowKey="id" loading={strategies.isLoading} dataSource={strategies.data} pagination={false} columns={[
              { title: "名称", dataIndex: "name" },
              { title: "运行频率", dataIndex: "schedule" },
              { title: "自动化等级", dataIndex: "automation_level" },
              { title: "操作", render: (_: unknown, row: { id: string }) => <Button onClick={() => runStrategy.mutate(row.id)} loading={runStrategy.isPending}>立即执行</Button> },
            ]} />
          </Card>

          <Card title="最近任务" id="publish-management" className="panel page-section page-panel page-dashboard page-publish">
            <Table rowKey="id" loading={jobs.isLoading} dataSource={jobs.data} pagination={false} columns={[
              { title: "任务", dataIndex: "id", ellipsis: true },
              { title: "状态", dataIndex: "status" },
              { title: "步骤", dataIndex: "current_step" },
              { title: "操作", render: (_: unknown, row: Job) => <Space>{(row.status === "failed_retryable" || row.status === "failed_terminal") && <Button size="small" onClick={() => retryJob.mutate(row.id)}>重试</Button>}{["queued", "running", "waiting_review", "failed_retryable"].includes(row.status) && <Button size="small" danger onClick={() => cancelJob.mutate(row.id)}>取消</Button>}</Space> },
              { title: "尝试", render: (_: unknown, row: Job) => `${row.attempt_count}/${row.max_attempts}` },
            ]} />
          </Card>

          <Card title="内容日历" className="panel page-section page-panel page-dashboard page-publish">
            <Table rowKey="job_id" loading={calendar.isLoading} dataSource={calendar.data} pagination={false} columns={[
              { title: "计划时间", dataIndex: "scheduled_at", render: (value: string | null) => value ? new Date(value).toLocaleString() : "未安排" },
              { title: "文章", render: (_: unknown, row: CalendarItem) => row.title || "待生成" },
              { title: "状态", dataIndex: "status" },
            ]} />
          </Card>
        </Content>
      </Layout>

      <Modal title="添加用户" open={userOpen} footer={null} onCancel={() => setUserOpen(false)}>
        <Form layout="vertical" onFinish={(values) => addUser.mutate(values)}>
          <Form.Item label="邮箱" name="email" rules={[{ required: true, type: "email" }]}><Input /></Form.Item>
          <Form.Item label="初始密码" name="password" rules={[{ required: true, min: 12 }]}><Input.Password /></Form.Item>
          <Form.Item label="角色" name="role" initialValue="operator"><Select options={[{ label: "管理员", value: "admin" }, { label: "运营人员", value: "operator" }, { label: "审核人员", value: "reviewer" }]} /></Form.Item>
          <Button type="primary" htmlType="submit" loading={addUser.isPending}>保存用户</Button>
        </Form>
      </Modal>      <Modal title="绑定微信公众号" open={channelOpen} footer={null} onCancel={() => setChannelOpen(false)}>
        <Form layout="vertical" onFinish={(values) => addChannelAccount.mutate(values)}>
          <Form.Item label="名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="AppID" name="app_id" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="AppSecret" name="app_secret" rules={[{ required: true }]}><Input.Password /></Form.Item>
          <Form.Item name="publish_enabled" valuePropName="checked"><Checkbox>允许提交发布（需管理员权限）</Checkbox></Form.Item>
          <Button type="primary" htmlType="submit" loading={addChannelAccount.isPending}>保存账号</Button>
        </Form>
      </Modal>
      <Modal title="添加模型" open={modelOpen} footer={null} onCancel={() => setModelOpen(false)}>
        <Form layout="vertical" onFinish={(values) => addModel.mutate(values)}>
          <Form.Item label="供应商" name="provider" initialValue="openai-compatible" rules={[{ required: true }]}><Select options={[{ label: "OpenAI-compatible", value: "openai-compatible" }, { label: "Anthropic", value: "anthropic" }, { label: "Fake", value: "fake" }]} /></Form.Item>
          <Form.Item label="模型名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="API Base URL" name="api_base_url"><Input placeholder="https://api.openai.com/v1" /></Form.Item>
          <Form.Item label="API Key" name="api_key"><Input.Password /></Form.Item>
          <Button type="primary" htmlType="submit" loading={addModel.isPending}>保存模型</Button>
        </Form>
      </Modal>
      <Modal title="编辑文章" open={Boolean(editingArticle)} footer={null} onCancel={() => setEditingArticle(null)}>
        <Form
          key={editingArticle?.id ?? "empty"}
          layout="vertical"
          initialValues={{ content_markdown: currentRevision?.content_markdown ?? "" }}
          onFinish={(values: { content_markdown: string }) => editingArticle && saveRevision.mutate({ articleId: editingArticle.id, contentMarkdown: values.content_markdown })}
        >
          <Form.Item label="Markdown 正文" name="content_markdown" rules={[{ required: true, min: 1 }]}>
            <Input.TextArea rows={18} />
          </Form.Item>
          <Form.Item label="排版主题">
            <Select
              value={selectedThemeId || undefined}
              loading={themes.isLoading}
              placeholder="选择排版主题"
              style={{ width: "100%" }}
              options={themes.data?.map((theme: Theme) => ({ label: theme.name, value: theme.id }))}
              onChange={setSelectedThemeId}
            />
          </Form.Item>
          {themePreview.data && <div className="theme-preview-shell"><div className="theme-preview-label">WECHAT ARTICLE PREVIEW · {themePreview.data.theme.name}</div><div className="theme-preview" dangerouslySetInnerHTML={{ __html: themePreview.data.html }} /></div>}
          <Button type="primary" htmlType="submit" loading={saveRevision.isPending}>保存新版本</Button>
        </Form>
      </Modal>

      <Modal title="事实包" open={Boolean(evidenceArticleId)} footer={null} onCancel={() => setEvidenceArticleId(null)}>
        {evidence.data && <>
          <Typography.Paragraph>{evidence.data.summary}</Typography.Paragraph>
          <Typography.Title level={5}>来源</Typography.Title>
          <ul>{evidence.data.sources.map((source) => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a></li>)}</ul>
          <Typography.Title level={5}>事实声明</Typography.Title>
          <ul>{evidence.data.claims.map((claim) => <li key={claim.id}>{claim.statement}</li>)}</ul>
        </>}
      </Modal>

      <Modal title={editingStrategy ? "编辑策略组合" : "新增策略组合"} open={strategyOpen} footer={null} onCancel={closeStrategy}>
        <Form key={editingStrategy?.id ?? "new-strategy"} initialValues={strategyInitialValues} layout="vertical" onFinish={(values: Record<string, any>) => {
          const modelByStage = Object.fromEntries(
            [["writing", values.writing_model_id], ["style", values.style_model_id], ["rewrite", values.rewrite_model_id]]
              .filter(([, value]) => Boolean(value)),
          );
          const skillByStage = Object.fromEntries(
            [["writing", values.writing_skill_id], ["style", values.style_skill_id], ["rewrite", values.rewrite_skill_id]]
              .filter(([, value]) => Boolean(value)),
          );
          saveStrategy.mutate({
            id: editingStrategy?.id,
            payload: {
              name: values.name,
              objective: values.objective,
              schedule: values.schedule,
              automation_level: values.automation_level,
              enabled: values.enabled === true,
              config: {
                source_ids: values.source_ids ?? [],
                channel_account_id: values.channel_account_id || undefined,
                disabled_steps: values.disabled_steps ?? [],
                model_by_stage: modelByStage,
                skill_by_stage: skillByStage,
                theme_id: values.theme_id || undefined,
                review_rules: { human_review_required: values.human_review_required !== false },
              },
            },
          });
        }}>
          <Form.Item label="名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="信息源组合" name="source_ids" extra="留空表示使用全部启用的信息源"><Select mode="multiple" allowClear placeholder="选择一个或多个信息源" options={sources.data?.filter((source) => source.enabled || stringArray(editingConfig.source_ids).includes(source.id)).map((source) => ({ label: source.name, value: source.id }))} /></Form.Item>
          <Form.Item label="默认发布账号" name="channel_account_id" extra="发布时可覆盖这个默认账号"><Select allowClear placeholder="选择公众号账号" options={channelAccounts.data?.filter((account) => account.enabled || account.id === editingConfig.channel_account_id).map((account) => ({ label: account.name, value: account.id }))} /></Form.Item>
          <Form.Item label="运行频率" name="schedule" initialValue="manual"><Select options={[{ label: "手动", value: "manual" }, { label: "每小时", value: "hourly" }, { label: "每日", value: "daily" }]} /></Form.Item>
          <Form.Item label="自动化等级" name="automation_level"><Select options={["L1", "L2", "L3", "L4"].map((value) => ({ label: value, value }))} /></Form.Item>
          <Form.Item label="默认排版主题" name="theme_id"><Select allowClear placeholder="选择公众号排版主题" options={themes.data?.filter((theme) => theme.enabled).map((theme) => ({ label: theme.name, value: theme.id }))} /></Form.Item>
          <Form.Item label="阶段模型">
            <Space direction="vertical" style={{ width: "100%" }}>
              <Form.Item noStyle name="writing_model_id"><Select allowClear placeholder="写作模型" options={models.data?.filter((model) => model.enabled).map((model) => ({ label: `${model.provider} / ${model.name}`, value: model.id }))} /></Form.Item>
              <Form.Item noStyle name="style_model_id"><Select allowClear placeholder="风格模型" options={models.data?.filter((model) => model.enabled).map((model) => ({ label: `${model.provider} / ${model.name}`, value: model.id }))} /></Form.Item>
              <Form.Item noStyle name="rewrite_model_id"><Select allowClear placeholder="改写模型" options={models.data?.filter((model) => model.enabled).map((model) => ({ label: `${model.provider} / ${model.name}`, value: model.id }))} /></Form.Item>
            </Space>
          </Form.Item>
          <Form.Item label="阶段 Skill">
            <Space direction="vertical" style={{ width: "100%" }}>
              <Form.Item noStyle name="writing_skill_id"><Select allowClear placeholder="写作 Skill" options={skills.data?.filter((skill) => skill.status === "published" && skill.skill_type === "writing").map((skill) => ({ label: `${skill.name} / ${skill.version}`, value: skill.id }))} /></Form.Item>
              <Form.Item noStyle name="style_skill_id"><Select allowClear placeholder="风格 Skill" options={skills.data?.filter((skill) => skill.status === "published" && skill.skill_type === "style").map((skill) => ({ label: `${skill.name} / ${skill.version}`, value: skill.id }))} /></Form.Item>
              <Form.Item noStyle name="rewrite_skill_id"><Select allowClear placeholder="改写 Skill" options={skills.data?.filter((skill) => skill.status === "published" && skill.skill_type === "rewrite").map((skill) => ({ label: `${skill.name} / ${skill.version}`, value: skill.id }))} /></Form.Item>
            </Space>
          </Form.Item>
          <Form.Item label="关闭可选步骤" name="disabled_steps"><Checkbox.Group options={[{ label: "风格处理", value: "style" }, { label: "最终改写", value: "rewrite" }]} /></Form.Item>
          <Form.Item name="enabled" valuePropName="checked"><Checkbox>允许自动调度这套组合</Checkbox></Form.Item>
          <Form.Item name="human_review_required" valuePropName="checked"><Checkbox>生成后等待人工审核</Checkbox></Form.Item>
          <Button type="primary" htmlType="submit" loading={saveStrategy.isPending}>保存策略组合</Button>
        </Form>
      </Modal>

      <Modal title={"\u9009\u62E9\u5199\u4F5C\u4F9D\u636E"} open={Boolean(topicMaterial)} footer={null} onCancel={() => setTopicMaterial(null)}>
        {topicMaterial && <>
          <Typography.Title level={5}>{topicMaterial.title}</Typography.Title>
          <Typography.Paragraph type="secondary">{topicMaterial.source_name}</Typography.Paragraph>
          <Typography.Paragraph>{topicMaterial.content_excerpt}</Typography.Paragraph>
          <Form layout="vertical" onFinish={(values: { strategy_id: string }) => createTopicFromMaterial.mutate({ materialId: topicMaterial.id, strategyId: values.strategy_id })}>
            <Form.Item label={"\u5199\u5165\u54EA\u4E2A\u5185\u5BB9\u7B56\u7565"} name="strategy_id" rules={[{ required: true, message: "\u8BF7\u9009\u62E9\u7B56\u7565" }]}>
              <Select placeholder={"\u9009\u62E9\u7B56\u7565"} options={strategies.data?.filter((strategy) => strategy.enabled).map((strategy) => ({ label: strategy.name, value: strategy.id }))} />
            </Form.Item>
            <Typography.Paragraph type="secondary" className="panel-note">{"\u63D0\u4EA4\u540E\u4F1A\u751F\u6210\u5019\u9009\u9009\u9898\uFF0C\u4ECD\u9700\u5728\u201C\u9009\u9898\u4E0E\u521B\u4F5C\u201D\u4E2D\u786E\u8BA4\u540E\u624D\u4F1A\u751F\u6210\u6587\u7AE0\u3002"}</Typography.Paragraph>
            <Button type="primary" htmlType="submit" loading={createTopicFromMaterial.isPending}>{"\u521B\u5EFA\u5019\u9009\u9009\u9898"}</Button>
          </Form>
        </>}
      </Modal>

      <Modal title={"\u7D20\u6750\u539F\u6587"} open={Boolean(materialPreviewId)} footer={null} onCancel={() => setMaterialPreviewId(null)} width={760}>
        {materialPreview.isLoading && <Typography.Paragraph>{"\u6B63\u5728\u8BFB\u53D6\u7D20\u6750\u2026"}</Typography.Paragraph>}
        {materialPreview.data && <>
          <Typography.Title level={4}>{materialPreview.data.title}</Typography.Title>
          <Typography.Paragraph type="secondary">{materialPreview.data.source_name} · <a href={materialPreview.data.url} target="_blank" rel="noreferrer">{"\u6253\u5F00\u539F\u6587"}</a></Typography.Paragraph>
          <Typography.Paragraph className="material-preview-content">{materialPreview.data.content}</Typography.Paragraph>
        </>}
      </Modal>
      <Modal title="添加信息源" open={sourceOpen} footer={null} onCancel={() => setSourceOpen(false)}>
        <Form layout="vertical" onFinish={(values) => addSource.mutate(values)}>
          <Form.Item label="名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="类型" name="source_type" initialValue="rss"><Select options={[{ label: "RSS", value: "rss" }, { label: "网页 URL", value: "url" }, { label: "手动", value: "manual" }]} /></Form.Item>
          <Form.Item label="地址" name="url"><Input /></Form.Item>
          <Button type="primary" htmlType="submit" loading={addSource.isPending}>保存</Button>
        </Form>
      </Modal>
    </Layout>
  );
}

export default App;