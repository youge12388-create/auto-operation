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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources"] }),
    onError: (error: Error) => message.error(error.message),
  });  const collectSource = useMutation({
    mutationFn: api.collectSource,
    onSuccess: (result) => {
      message.success(`已采集 ${result.count} 条内容`);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: Error) => message.error(error.message),
  });
  const saveStrategy = useMutation({
    mutationFn: ({ id, payload }: { id?: string; payload: StrategyPayload }) => id ? api.updateStrategy(id, payload) : api.addStrategy(payload),
    onSuccess: () => {
      setStrategyOpen(false);
      setEditingStrategy(null);
      queryClient.invalidateQueries({ queryKey: ["strategies"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      message.success("策略组合已保存");
    },
    onError: (error: Error) => message.error(error.message),
  });
const openNewStrategy = () => { setEditingStrategy(null); setStrategyOpen(true); };
  const openCoverPicker = () => {
    selectSection("publish");
    window.requestAnimationFrame(() => document.querySelector<HTMLInputElement>(".wechat-panel input[type=file]")?.click());
  };
  const handleLogout = () => {
    Modal.confirm({
      title: "退出当前账号？",
      content: currentUser.email,
      okText: "退出登录",
      cancelText: "取消",
      onOk: async () => {
        await api.logout();
        window.location.reload();
      },
    });
  };
  const closeStrategy = () => { setStrategyOpen(false); setEditingStrategy(null); };
  const runStrategy = useMutation({
    mutationFn: (id: string) => api.runStrategy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error: Error) => message.error(error.message),
  });
  const retryJob = useMutation({
    mutationFn: api.retryJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
    onError: (error: Error) => message.error(error.message),
  });
  const cancelJob = useMutation({
    mutationFn: api.cancelJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
    onError: (error: Error) => message.error(error.message),
  });
  const publishSkill = useMutation({
    mutationFn: api.publishSkill,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
    onError: (error: Error) => message.error(error.message),
  });
  const disableSkill = useMutation({
    mutationFn: api.disableSkill,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
    onError: (error: Error) => message.error(error.message),
  });  const addModel = useMutation({
    mutationFn: api.addModel,
    onSuccess: () => { setModelOpen(false); queryClient.invalidateQueries({ queryKey: ["models"] }); },
    onError: (error: Error) => message.error(error.message),
  });
  const importSkill = useMutation({
    mutationFn: api.importSkill,
    onSuccess: () => { message.success("Skill 导入成功"); queryClient.invalidateQueries({ queryKey: ["skills"] }); },
    onError: (error: Error) => message.error(error.message),
  });  const disableModel = useMutation({
    mutationFn: api.disableModel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models"] }),
    onError: (error: Error) => message.error(error.message),
  });  const testModel = useMutation({
    mutationFn: api.testModel,
    onSuccess: (result) => (result.ok ? message.success(result.message) : message.error(result.message)),
    onError: (error: Error) => message.error(error.message),
  });
  const testWechat = useMutation({
    mutationFn: api.testWechatConnection,
    onSuccess: (result) => (result.connected ? message.success(result.message) : message.error(result.message)),
    onError: (error: Error) => message.error(error.message),
  });
  const addChannelAccount = useMutation({
    mutationFn: api.addChannelAccount,
    onSuccess: () => { setChannelOpen(false); queryClient.invalidateQueries({ queryKey: ["channel-accounts"] }); },
    onError: (error: Error) => message.error(error.message),
  });  const disableChannelAccount = useMutation({
    mutationFn: api.disableChannelAccount,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["channel-accounts"] }),
    onError: (error: Error) => message.error(error.message),
  });  const testChannelAccount = useMutation({
    mutationFn: api.testChannelAccount,
    onSuccess: (result) => (result.connected ? message.success(result.message) : message.error(result.message)),
    onError: (error: Error) => message.error(error.message),
  });
  const uploadWechatThumb = useMutation({
    mutationFn: (file: File) => api.uploadWechatThumb(file, selectedChannelId || undefined),
    onSuccess: (result) => {
      setThumbMediaId(result.media_id);
      window.localStorage.setItem(thumbStorageKey, result.media_id);
      message.success("封面素材上传成功，后续刷新会自动恢复");
    },
    onError: (error: Error) => message.error(error.message),
  });
  const reviewArticle = useMutation({
    mutationFn: ({ articleId, revisionId, decision }: { articleId: string; revisionId: string; decision: "approve" | "reject" | "request_changes" }) =>
      api.reviewArticle(articleId, revisionId, decision),
    onSuccess: (_result, variables) => {
      message.success(variables.decision === "approve" ? "审核已通过，任务将继续执行" : "审核结果已保存");
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error: Error) => message.error(error.message),
  });
  const decideTopic = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "accept" | "reject" | "merge" }) =>
      api.decideTopic(id, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["topics"] }),
    onError: (error: Error) => message.error(error.message),
  });
  const saveRevision = useMutation({
    mutationFn: ({ articleId, contentMarkdown }: { articleId: string; contentMarkdown: string }) =>
      api.addRevision(articleId, contentMarkdown),
    onSuccess: () => {
      setEditingArticle(null);
      message.success("文章新版本已保存");
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error: Error) => message.error(error.message),
  });
  const publishWechatDraft = useMutation({
    mutationFn: ({ articleId, revisionId }: { articleId: string; revisionId: string }) =>
      api.publishWechatDraft(articleId, revisionId, selectedChannelId),
    onSuccess: () => {
      message.success("已提交，等待微信官方确认发布状态");
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error: Error) => message.error(error.message),
  });  const createWechatDraft = useMutation({
    mutationFn: ({ articleId, revisionId }: { articleId: string; revisionId: string }) =>
      api.createWechatDraft(articleId, revisionId, { thumb_media_id: thumbMediaId, channel_account_id: selectedChannelId || undefined, theme_id: selectedThemeId || undefined }),
    onSuccess: () => {
      message.success("微信公众号草稿已创建");
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  return (
    <Layout className="app-shell">
      <Sider className="app-sider" theme="light" collapsed={sidebarCollapsed} collapsedWidth={64} trigger={null}>
        <div className="brand">内容运营平台</div>
        <Menu className="app-nav"
          selectedKeys={[activeSection]}
          onClick={({ key }) => selectSection(key)}
          items={[
            { key: "dashboard", icon: <UiIcon name="grid" />, label: "\u5DE5\u4F5C\u53F0" },
            { key: "materials", icon: <UiIcon name="database" />, label: "\u7D20\u6750\u6C60" },
            { key: "content", icon: <UiIcon name="content" />, label: "\u9009\u9898\u4E0E\u521B\u4F5C" },
            { key: "publish", icon: <UiIcon name="send" />, label: "\u5BA1\u6838\u4E0E\u53D1\u5E03" },
            { key: "system", icon: <UiIcon name="settings" />, label: "\u7B56\u7565\u4E0E\u8BBE\u7F6E" },
          ]}
        />
<button type="button" className="sidebar-user" onClick={handleLogout} title="账号与退出登录">
          <span className="sidebar-avatar"><UiIcon name="user" size={20} /></span>
          <span className="sidebar-user-copy"><strong>{currentUser.email.split("@")[0]}</strong><small>{currentUser.role === "admin" ? "超级管理员" : "内容运营"}</small></span>
          <span className="sidebar-online" />
        </button>
      </Sider>
      <Layout className="app-main">
        <Header className="app-header">
          <div className="header-leading">
            <button type="button" className="header-menu-button" aria-label="打开导航" onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}><UiIcon name="menu" /></button>
            <div className="header-title-block">
              <Typography.Title level={3}>{activeNavItem.label}</Typography.Title>
              <Typography.Text type="secondary">欢迎回来，{currentUser.email.split("@")[0]}</Typography.Text>
            </div>
          </div>
          <div className="header-tools">
            <button type="button" className="header-tool-button" aria-label="搜索" onClick={() => selectSection("content")}><UiIcon name="search" /></button>
            <button type="button" className="header-tool-button header-notification" aria-label="通知" onClick={() => selectSection("publish")}><UiIcon name="bell" />{notificationCount > 0 && <span>{notificationCount}</span>}</button>
            <button type="button" className="header-tool-button" aria-label="帮助" onClick={() => message.info("左侧菜单可定位到内容、发布、素材、数据和系统区域") }><UiIcon name="help" /></button>
            <button type="button" className="header-account-button" onClick={handleLogout} title="账号与退出登录">
              <span className="header-avatar"><UiIcon name="user" size={17} /></span>
              <span className="header-account">{currentUser.email.split("@")[0]} <span className="header-chevron" aria-hidden="true" /></span>
            </button>          </div>
        </Header>
        <Content className={`content content--${activeSection}`}>
          <Space wrap className="stats page-section page-dashboard page-analytics" id="analytics-overview">
            <Card className="stat-card stat-card--red"><div className="stat-card-inner"><span className="stat-icon"><UiIcon name="team" size={24} /></span><span><span className="stat-label">信息源</span><strong className="stat-value">{dashboard.data?.sources ?? 0}</strong></span></div></Card>
            <Card className="stat-card stat-card--blue"><div className="stat-card-inner"><span className="stat-icon"><UiIcon name="file" size={24} /></span><span><span className="stat-label">内容策略</span><strong className="stat-value">{dashboard.data?.strategies ?? 0}</strong></span></div></Card>
            <Card className="stat-card stat-card--green"><div className="stat-card-inner"><span className="stat-icon"><UiIcon name="send" size={24} /></span><span><span className="stat-label">自动任务</span><strong className="stat-value">{dashboard.data?.jobs ?? 0}</strong></span></div></Card>
            <Card className="stat-card stat-card--purple"><div className="stat-card-inner"><span className="stat-icon"><UiIcon name="edit" size={24} /></span><span><span className="stat-label">文章</span><strong className="stat-value">{dashboard.data?.articles ?? 0}</strong></span></div></Card>
          </Space>

          <Card title={"\u5F85\u5904\u7406\u5DE5\u4F5C"} className="panel page-section page-panel page-dashboard queue-panel">
            <div className="queue-items">
              <button type="button" className="queue-item queue-item--materials" onClick={() => selectSection("materials")}>
                <span><strong>{materials.data?.filter((item) => item.triage_status === "inbox").length ?? 0}</strong><small>{"\u6761\u5F85\u7B5B\u9009\u7D20\u6750"}</small></span>
                <em>{"\u53BB\u9009\u5199\u4F5C\u4F9D\u636E"}</em>
              </button>
              <button type="button" className="queue-item queue-item--topics" onClick={() => selectSection("content")}>
                <span><strong>{topics.data?.filter((topic) => topic.status === "candidate").length ?? 0}</strong><small>{"\u4E2A\u5F85\u786E\u8BA4\u9009\u9898"}</small></span>
                <em>{"\u786E\u8BA4\u540E\u624D\u521B\u4F5C"}</em>
              </button>
              <button type="button" className="queue-item queue-item--review" onClick={() => selectSection("publish")}>
                <span><strong>{articles.data?.filter((article) => article.review?.status === "pending").length ?? 0}</strong><small>{"\u7BC7\u5F85\u5BA1\u6838\u6587\u7AE0"}</small></span>
                <em>{"\u5BA1\u6838\u540E\u521B\u5EFA\u8349\u7A3F"}</em>
              </button>
            </div>
          </Card>
          <Card title="微信公众号" id="materials-management" className="panel page-section page-panel page-publish wechat-panel">
            <Space wrap>
              <Button loading={testWechat.isPending} onClick={() => testWechat.mutate()}>测试环境连接</Button>
              <Select
                value={selectedChannelId || undefined}
                placeholder="选择公众号账号"
                style={{ minWidth: 220 }}
                options={channelAccounts.data?.map((account) => ({ label: account.name, value: account.id }))}
                onChange={setSelectedChannelId}
              />
              <Upload
                accept=".jpg,.jpeg,image/jpeg"
                showUploadList={false}
                beforeUpload={(file) => { uploadWechatThumb.mutate(file); return false; }}
              >
                <Button loading={uploadWechatThumb.isPending}>上传 JPG 封面</Button>
              </Upload>
            </Space>
            <Typography.Paragraph type="secondary" className="panel-note">
              封面素材上传成功后会返回 media_id，创建草稿时使用该素材。
              {testWechat.data && <><Tag color={testWechat.data.connected ? "green" : "red"}>{testWechat.data.connected ? "公众号连接正常" : "公众号连接失败"}</Tag><Typography.Text type={testWechat.data.connected ? "secondary" : "danger"}>{testWechat.data.message}</Typography.Text></>}
            </Typography.Paragraph>
          </Card>

          <Card title="快捷操作" id="dashboard-overview" className="panel page-section page-panel page-dashboard quick-panel">
            <div className="quick-actions">
              <QuickAction icon="content" label="新建策略" caption="创建内容策略" onClick={() => openNewStrategy()} />
              <QuickAction icon="file" label="添加来源" caption="接入信息来源" onClick={() => setSourceOpen(true)} />
              <QuickAction icon="upload" label="上传素材" caption="上传 JPG 封面" onClick={() => document.querySelector<HTMLInputElement>(".wechat-panel input[type=file]")?.click()} />
              <QuickAction icon="report" label="查看指标" caption="查看运营概况" onClick={() => document.querySelector(".stats")?.scrollIntoView({ behavior: "smooth", block: "center" })} />
            </div>
          </Card>
          <Card title="渠道账号" extra={<Button type="primary" onClick={() => setChannelOpen(true)}>绑定公众号</Button>} className="panel page-section page-panel page-publish">
            <Table rowKey="id" loading={channelAccounts.isLoading} dataSource={channelAccounts.data} pagination={false} columns={[
              { title: "名称", dataIndex: "name" },
              { title: "类型", dataIndex: "channel_type" },
              { title: "凭证", render: (_: unknown, row: ChannelAccount) => row.has_credentials ? <Tag color="green">已配置</Tag> : <Tag>未配置</Tag> },
              { title: "操作", render: (_: unknown, row: ChannelAccount) => row.id === ENV_CHANNEL_ID ? <Space><Button size="small" loading={testWechat.isPending} onClick={() => testWechat.mutate()}>测试连接</Button><Tag>来自 .env</Tag></Space> : <Space><Button size="small" loading={testChannelAccount.isPending} onClick={() => testChannelAccount.mutate(row.id)}>测试连接</Button><Button size="small" danger loading={disableChannelAccount.isPending} onClick={() => disableChannelAccount.mutate(row.id)}>停用</Button></Space> },
            ]} />
          </Card>

          <Card title="选题候选" className="panel page-section page-panel page-content">
            <Table rowKey="id" loading={topics.isLoading} dataSource={topics.data} pagination={false} columns={[
              { title: "标题", dataIndex: "title" },
              { title: "评分", dataIndex: "score" },
              { title: "状态", render: (_: unknown, row: Topic) => <TopicStatus status={row.status} /> },
              { title: "操作", render: (_: unknown, row: Topic) => row.status === "candidate" ? <Space><Button size="small" type="primary" loading={decideTopic.isPending} onClick={() => decideTopic.mutate({ id: row.id, decision: "accept" })}>{"\u786E\u8BA4\u9009\u9898"}</Button><Button size="small" danger loading={decideTopic.isPending} onClick={() => decideTopic.mutate({ id: row.id, decision: "reject" })}>{"\u5FFD\u7565"}</Button></Space> : row.status === "accepted" ? <Button size="small" type="primary" loading={startTopicWriting.isPending} onClick={() => startTopicWriting.mutate(row.id)}>{"\u5F00\u59CB\u521B\u4F5C"}</Button> : row.status === "writing" ? <Tag color="purple">{"\u521B\u4F5C\u4E2D"}</Tag> : null },
            ]} />
          </Card>

          <Card
            title={"\u7D20\u6750\u6C60"}
            extra={<Space><Tag color="blue">{materials.data?.filter((item) => item.triage_status === "inbox").length ?? 0}{" \u5F85\u7B5B\u9009"}</Tag><Button onClick={() => selectSection("system")}>{"\u914D\u7F6E\u4FE1\u606F\u6E90"}</Button></Space>}
            className="panel page-section page-panel page-materials material-pool-panel"
          >
            <Typography.Paragraph type="secondary" className="panel-note">{"\u91C7\u96C6\u5B8C\u6210\u540E\uFF0C\u5148\u5728\u6B64\u5904\u9605\u8BFB\u548C\u9009\u5B9A\u5199\u4F5C\u4F9D\u636E\u3002\u7B56\u7565\u53EA\u8D1F\u8D23\u626B\u63CF\u7D20\u6750\uFF0C\u4E0D\u4F1A\u81EA\u52A8\u8BB2\u6700\u65B0\u4E00\u6761\u5199\u6210\u6587\u7AE0\u3002"}</Typography.Paragraph>
            <Table
              rowKey="id"
              loading={materials.isLoading}
              dataSource={materials.data}
              pagination={{ pageSize: 10, showSizeChanger: false }}
              columns={[
                { title: "\u7D20\u6750", dataIndex: "title", width: "34%", render: (_: unknown, row: Material) => <div className="material-title"><strong>{row.title}</strong><span>{row.content_excerpt || row.url}</span></div> },
                { title: "\u6765\u6E90", dataIndex: "source_name", width: "16%" },
                { title: "\u91C7\u96C6\u65F6\u95F4", dataIndex: "created_at", width: "16%", render: (value: string | null) => value ? new Date(value).toLocaleString() : "-" },
                { title: "\u72B6\u6001", width: "12%", render: (_: unknown, row: Material) => <MaterialStatus status={row.triage_status} /> },
                { title: "\u64CD\u4F5C", width: "22%", render: (_: unknown, row: Material) => <Space wrap>
                  <Button size="small" onClick={() => setMaterialPreviewId(row.id)}>{"\u67E5\u770B"}</Button>
                  {row.triage_status === "inbox" && <Button size="small" type="primary" onClick={() => setTopicMaterial(row)}>{"\u9009\u4F5C\u4F9D\u636E"}</Button>}
                  {row.triage_status === "inbox" && <Button size="small" danger loading={triageMaterial.isPending} onClick={() => triageMaterial.mutate({ id: row.id, decision: "ignore" })}>{"\u5FFD\u7565"}</Button>}
                  {row.triage_status === "ignored" && <Button size="small" loading={triageMaterial.isPending} onClick={() => triageMaterial.mutate({ id: row.id, decision: "reopen" })}>{"\u6062\u590D"}</Button>}
                  {row.triage_status === "selected" && <Button size="small" onClick={() => selectSection("content")}>{"\u67E5\u770B\u9009\u9898"}</Button>}
                </Space> },
              ]}
            />
          </Card>
          <Card title="信息源" extra={<Button type="primary" onClick={() => setSourceOpen(true)}>添加来源</Button>} className="panel page-section page-panel page-system">
            <Table rowKey="id" loading={sources.isLoading} dataSource={sources.data} pagination={false} columns={[
              { title: "名称", dataIndex: "name" },
              { title: "类型", dataIndex: "source_type" },
              { title: "地址", dataIndex: "url" },
              { title: "状态", render: (_: unknown, row: Source) => row.enabled ? <Tag color="green">启用</Tag> : <Tag>停用</Tag> },
              { title: "操作", render: (_: unknown, row: Source) => <Space><Button size="small" loading={collectSource.isPending} onClick={() => collectSource.mutate(row.id)}>立即采集</Button><Button size="small" danger loading={disableSource.isPending} onClick={() => disableSource.mutate(row.id)}>停用</Button></Space> },
            ]} />
          </Card>

          <Card title="文章草稿" id="content-management" className="panel page-section page-panel page-content page-publish">
            <Typography.Paragraph type="secondary" className="panel-note">
              当前封面素材：{thumbMediaId || "尚未上传"}
            </Typography.Paragraph>
            <Table rowKey="id" loading={articles.isLoading} dataSource={articles.data} pagination={false} columns={[
              { title: "标题", dataIndex: "title" },
              { title: "状态", render: (_: unknown, row: Article) => <ArticleStatus status={row.status} /> },
              { title: "操作", render: (_: unknown, row: Article) => {
                const revision = row.revisions[row.revisions.length - 1];
                return <Space wrap>
                  {revision && <Button onClick={() => { setEditingArticle(row); setSelectedThemeId(themes.data?.[0]?.id ?? ""); }}>编辑文章</Button>}
                  {revision && <Button onClick={() => setEvidenceArticleId(row.id)}>查看事实包</Button>}
                  {row.review?.status === "pending" && revision && <><Button loading={reviewArticle.isPending} onClick={() => reviewArticle.mutate({ articleId: row.id, revisionId: revision.id, decision: "approve" })}>审核通过</Button><Button danger loading={reviewArticle.isPending} onClick={() => reviewArticle.mutate({ articleId: row.id, revisionId: revision.id, decision: "request_changes" })}>退回修改</Button></>}
                  <Button title={!revision ? "文章没有可用版本" : !thumbMediaId ? "点击后选择 JPG 封面" : undefined} disabled={!revision} loading={createWechatDraft.isPending} onClick={() => { if (!revision) return; if (!thumbMediaId) { message.info("请先选择一张 JPG 封面"); openCoverPicker(); return; } createWechatDraft.mutate({ articleId: row.id, revisionId: revision.id }); }}>{thumbMediaId ? "创建微信草稿" : "先上传封面"}</Button>
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
