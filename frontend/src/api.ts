import { buildChannelTestPath, buildWechatThumbPath, type WechatDraftPayload } from "./contracts";
export type User = {
  id: string;
  email: string;
  role: "admin" | "operator" | "reviewer" | string;
};
export type Source = {
  id: string;
  name: string;
  source_type: "rss" | "url" | "manual" | "aihot_api";
  url: string;
  group_name: string;
  group_id: string | null;
  enabled: boolean;
  requires_review: boolean;
  config: Record<string, unknown>;
  last_error: string | null;
};

export type MaterialCategory = {
  id: string;
  name: string;
  description: string;
  classification_instructions: string;
  enabled: boolean;
  is_builtin: boolean;
  material_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type Material = {
  id: string;
  source_id: string;
  source_name: string;
  title: string;
  url: string;
  content_excerpt: string;
  published_at: string | null;
  created_at: string | null;
  triage_status: "inbox" | "selected" | "ignored" | "used";
  category_id: string | null;
  category_name: string | null;
  classification_status: "pending" | "classified" | "failed" | "unclassified";
  classification_source: "ai" | "manual" | null;
  classification_confidence: number | null;
  classification_reason: string | null;
  classification_error: string | null;
  ai_score?: number | null;
};

export type MaterialDetail = Material & { content: string };

export type TopicAlgorithm = {
  id: string;
  name: string;
  instructions: string;
  max_topics: number;
  weights: Record<"heat" | "timeliness" | "reader_value" | "strategy_fit", number>;
  is_builtin: boolean;
  enabled: boolean;
};

export type TopicAlgorithmPayload = {
  name: string;
  instructions: string;
  max_topics: number;
  weights: Record<"heat" | "timeliness" | "reader_value" | "strategy_fit", number>;
};

export type StrategySelectionMode = "fixed" | "round_robin";

export type StrategyCombination = {
  id: string;
  name: string;
  enabled: boolean;
  config: StrategyConfig;
};

export type StrategyConfig = {
  source_ids?: string[];
  material_category_ids?: string[];
  translate_foreign_sources?: boolean;
  channel_account_id?: string;
  delivery_mode?: "local_draft" | "wechat_draft" | "auto_publish";
  wechat_thumb_media_id?: string;
  wechat_author?: string;
  wechat_digest?: string;
  content_source_url?: string;
  need_open_comment?: boolean;
  only_fans_can_comment?: boolean;
  theme_id?: string;
  theme_version?: number;
  theme_selection_mode?: "auto" | "manual";
  model_by_stage?: Record<string, string>;
  skill_by_stage?: Record<string, string>;
  skill_ids?: string[];
  disabled_steps?: string[];
  review_rules?: { human_review_required?: boolean };
  topic_algorithm?: {
    instructions?: string;
    max_topics?: number;
    weights?: Partial<Record<"heat" | "timeliness" | "reader_value" | "strategy_fit", number>>;
  };
  selection_mode?: StrategySelectionMode;
  default_combination_id?: string | null;
  strategy_combinations?: StrategyCombination[];
  [key: string]: unknown;
};

export type StrategyPayload = {
  name: string;
  objective: string;
  schedule: string;
  automation_level: string;
  enabled?: boolean;
  config?: StrategyConfig;
};

export type Strategy = StrategyPayload & {
  id: string;
  version: number;
  config: StrategyConfig;
};

export type Job = {
  id: string;
  strategy_id: string;
  status: string;
  current_step: string | null;
  attempt_count: number;
  max_attempts: number;
  available_at: string | null;
  lease_until: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number;
  runtime_snapshot: Record<string, unknown>;
  idempotency_key: string;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type CalendarItem = {
  job_id: string;
  strategy_id: string;
  article_id: string | null;
  title: string;
  status: string;
  scheduled_at: string | null;
};

export type WechatConnection = {
  configured: boolean;
  connected: boolean;
  message: string;
};

export type WechatMaterial = {
  media_id: string;
  url: string | null;
};

export type ArticleRevision = {
  id: string;
  article_id: string;
  version: number;
  content_markdown: string;
  rendered_html: string;
  created_by: string | null;
};

export type Review = {
  id: string;
  article_revision_id: string;
  status: string;
  auto_result: Record<string, unknown>;
  reviewer_id: string | null;
  comment: string | null;
};

export type Article = {
  id: string;
  job_id: string;
  title: string;
  status: string;
  evidence: Record<string, unknown>;
  runtime_snapshot: Record<string, unknown>;
  revisions: ArticleRevision[];
  review: Review | null;
};

export type Publication = {
  id: string;
  article_revision_id: string;
  channel_account_id: string;
  action: string;
  status: string;
  remote_id: string | null;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AuditLog = {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  payload: Record<string, unknown>;
  ip_address: string | null;
  created_at: string | null;
};

export type Theme = {
  id: string;
  name: string;
  slug: string;
  description: string;
  enabled: boolean;
  is_builtin: boolean;
  current_version: number;
  tokens: Record<string, string>;
};

export type ThemePreview = {
  theme: Theme;
  theme_version: number;
  html: string;
};

export type TopicScore = {
  id: string;
  topic_id: string;
  dimension: string;
  score: number;
  rationale: string;
};

export type TopicMaterial = {
  source_item_id: string;
  source_name: string;
  title: string;
  url: string;
  role: string;
  relevance_score: number;
};


export type Topic = {
  id: string;
  strategy_id: string;
  job_id: string | null;
  source_item_id: string | null;
  title: string;
  status: string;
  score: number;
  rationale: string;
  scores: TopicScore[];
  materials: TopicMaterial[];
};

export type EvidencePackage = {
  id: string;
  article_id: string;
  status: string;
  version: number;
  summary: string;
  sources: Array<{ id: string; source_item_id: string | null; title: string; url: string; snapshot_hash: string; credibility: number }>;
  claims: Array<{ id: string; source_id: string | null; claim_type: string; statement: string; status: string }>;
};

export type JobEvent = {
  id: string;
  job_id: string;
  event_type: string;
  step_name: string | null;
  status: string | null;
  payload: Record<string, unknown>;
  created_at: string | null;
};

export type ChannelAccount = {
  id: string;
  channel_type: string;
  name: string;
  enabled: boolean;
  config: Record<string, unknown>;
  capabilities: Record<string, unknown>;
  has_credentials: boolean;
};

export type Skill = {
  id: string;
  name: string;
  skill_type: string;
  version: string;
  status: string;
  manifest: Record<string, unknown>;
};

export type Model = {
  id: string;
  provider: string;
  name: string;
  api_base_url: string | null;
  enabled: boolean;
  config: Record<string, unknown>;
  has_api_key: boolean;
};

export type Dashboard = {
  sources: number;
  strategies: number;
  jobs: number;
  articles: number;
};

export class ApiRequestError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(path: string, status: number, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.path = path;
  }
}

function formatApiDetail(detail: unknown): string | undefined {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (!Array.isArray(detail)) return undefined;
  const messages = detail
    .map((item) => (item && typeof item === "object" && "msg" in item ? (item as { msg?: unknown }).msg : undefined))
    .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    .map((item) => item.trim());
  return messages.length ? messages.join("；") : undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const statusMessage = `请求失败（HTTP ${response.status}）`;
    let detail: string | undefined;
    try {
      const raw = await response.text();
      const body = JSON.parse(raw) as { detail?: unknown };
      detail = formatApiDetail(body.detail);
    } catch {
      // Non-JSON proxy errors still expose the HTTP status to the operator.
    }
    throw new ApiRequestError(path, response.status, detail ? `${statusMessage}：${detail}` : statusMessage);
  }
  return response.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    request<User>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<User>("/api/v1/auth/me"),
  logout: () => request<{ ok: boolean }>("/api/v1/auth/logout", { method: "POST" }),
  changePassword: (payload: { current_password: string; new_password: string; confirm_password: string }) =>
    request<{ ok: boolean }>("/api/v1/auth/password", { method: "POST", body: JSON.stringify(payload) }),
  dashboard: () => request<Dashboard>("/api/v1/dashboard"),
  users: () => request<User[]>("/api/v1/users"),
  addUser: (payload: { email: string; password: string; role: string }) =>
    request<User>("/api/v1/users", { method: "POST", body: JSON.stringify(payload) }),
  sources: () => request<Source[]>("/api/v1/sources"),
  materials: (triageStatus?: string, sourceId?: string, categoryId?: string) => {
    const params = new URLSearchParams();
    if (triageStatus) params.set("triage_status", triageStatus);
    if (sourceId) params.set("source_id", sourceId);
    if (categoryId) params.set("category_id", categoryId);
    const query = params.toString();
    return request<Material[]>(`/api/v1/materials${query ? `?${query}` : ""}`);
  },
  materialCategories: (includeDisabled = true) => request<MaterialCategory[]>(`/api/v1/material-categories?include_disabled=${includeDisabled}`),
  addMaterialCategory: (payload: { name: string; description?: string; classification_instructions?: string; enabled?: boolean }) =>
    request<MaterialCategory>("/api/v1/material-categories", { method: "POST", body: JSON.stringify(payload) }),
  updateMaterialCategory: (id: string, payload: Partial<Pick<MaterialCategory, "name" | "description" | "classification_instructions" | "enabled">>) =>
    request<MaterialCategory>(`/api/v1/material-categories/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  disableMaterialCategory: (id: string) => request<MaterialCategory>(`/api/v1/material-categories/${id}`, { method: "DELETE" }),
  restoreMaterialCategory: (id: string) => request<MaterialCategory>(`/api/v1/material-categories/${id}/restore`, { method: "POST" }),
  classifyMaterials: (payload: { material_ids?: string[]; retry_failed?: boolean } = {}) =>
    request<{ candidate_count: number; classified_count: number; failed_count: number; message: string }>("/api/v1/materials/classify", { method: "POST", body: JSON.stringify(payload) }),
  assignMaterialCategory: (id: string, categoryId: string | null) =>
    request<Material>(`/api/v1/materials/${id}/category`, { method: "PUT", body: JSON.stringify({ category_id: categoryId }) }),
  material: (id: string) => request<MaterialDetail>(`/api/v1/materials/${id}`),
  triageMaterial: (id: string, decision: "save" | "ignore" | "reopen") =>
    request<Material>(`/api/v1/materials/${id}/triage`, { method: "POST", body: JSON.stringify({ decision }) }),
  curateMaterials: (payload: { strategy_id: string; material_ids?: string[]; limit?: number }) =>
    request<{ candidate_count: number; selected_count: number; selected_ids: string[]; selected_titles: string[]; message: string }>("/api/v1/materials/curate", { method: "POST", body: JSON.stringify(payload) }),
  createTopicFromMaterial: (id: string, payload: { strategy_id: string; title?: string }) =>
    request<Topic>(`/api/v1/materials/${id}/topics`, { method: "POST", body: JSON.stringify(payload) }),
  createTopicFromMaterials: (payload: { strategy_id: string; material_ids: string[]; title?: string }) =>
    request<Topic>("/api/v1/topics/from-materials", { method: "POST", body: JSON.stringify(payload) }),
  startTopicWriting: (id: string, payload?: { writing_skill_id?: string; disable_writing_skill?: boolean }) => request<Job>(`/api/v1/topics/${id}/start-writing`, { method: "POST", body: JSON.stringify(payload || {}) }),
  addSource: (payload: Partial<Source>) => request<Source>("/api/v1/sources", { method: "POST", body: JSON.stringify(payload) }),
  addManualMaterial: (payload: { title: string; content: string; source_name?: string }) =>
    request<Material>("/api/v1/materials/manual", { method: "POST", body: JSON.stringify(payload) }),
  collectSource: (id: string) => request<{ source_id: string; count: number; item_ids: string[]; classified_count: number; classification_failed_count: number }>(`/api/v1/sources/${id}/collect`, { method: "POST" }),
  updateSource: (id: string, payload: Source) => request<Source>(`/api/v1/sources/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  disableSource: (id: string) => request<Source>(`/api/v1/sources/${id}`, { method: "DELETE" }),
  strategies: () => request<Strategy[]>("/api/v1/strategies"),
  addStrategy: (payload: StrategyPayload) =>
    request<Strategy>("/api/v1/strategies", { method: "POST", body: JSON.stringify(payload) }),
  updateStrategy: (id: string, payload: StrategyPayload) =>
    request<Strategy>(`/api/v1/strategies/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  scanStrategy: (id: string, topicAlgorithmId?: string) =>
    request<Job>(`/api/v1/strategies/${id}/scan`, {
      method: "POST",
      body: topicAlgorithmId ? JSON.stringify({ topic_algorithm_id: topicAlgorithmId }) : undefined,
    }),
  jobs: () => request<Job[]>("/api/v1/jobs"),
  calendar: () => request<CalendarItem[]>("/api/v1/calendar"),
  articles: () => request<Article[]>("/api/v1/articles"),
  article: (id: string) => request<Article>(`/api/v1/articles/${id}`),
  archiveArticle: (id: string) => request<Article>(`/api/v1/articles/${id}`, { method: "DELETE" }),
  publications: () => request<Publication[]>("/api/v1/publications"),
  auditLogs: () => request<AuditLog[]>("/api/v1/audit-logs"),
  themes: () => request<Theme[]>("/api/v1/themes"),
  addTheme: (payload: { name: string; slug: string; description?: string; enabled?: boolean; tokens?: Record<string, unknown>; css?: string }) =>
    request<Theme>("/api/v1/themes", { method: "POST", body: JSON.stringify(payload) }),
  updateTheme: (id: string, payload: { name?: string; description?: string; enabled?: boolean; tokens?: Record<string, unknown>; css?: string }) =>
    request<Theme>(`/api/v1/themes/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  copyTheme: (id: string, payload: { name: string; slug: string }) =>
    request<Theme>(`/api/v1/themes/${id}/copy`, { method: "POST", body: JSON.stringify(payload) }),
  disableTheme: (id: string) => request<Theme>(`/api/v1/themes/${id}`, { method: "DELETE" }),
  previewTheme: (articleId: string, revisionId: string, themeId: string, mode: "deterministic" | "ai" = "deterministic") =>
    request<ThemePreview>(`/api/v1/articles/${articleId}/revisions/${revisionId}/themes/${themeId}/preview?mode=${mode}`, { method: "POST" }),
  topicAlgorithms: () => request<TopicAlgorithm[]>("/api/v1/topic-algorithms"),
  addTopicAlgorithm: (payload: TopicAlgorithmPayload) =>
    request<TopicAlgorithm>("/api/v1/topic-algorithms", { method: "POST", body: JSON.stringify(payload) }),
  updateTopicAlgorithm: (id: string, payload: Partial<TopicAlgorithmPayload & { enabled: boolean }>) =>
    request<TopicAlgorithm>(`/api/v1/topic-algorithms/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteTopicAlgorithm: (id: string) =>
    request<TopicAlgorithm>(`/api/v1/topic-algorithms/${id}`, { method: "DELETE" }),
  topics: () => request<Topic[]>("/api/v1/topics"),
  addTopic: (payload: { strategy_id: string; title: string; rationale?: string; score?: number }) =>
    request<Topic>("/api/v1/topics", { method: "POST", body: JSON.stringify(payload) }),
  decideTopic: (id: string, decision: "accept" | "reject" | "merge") =>
    request<Topic>(`/api/v1/topics/${id}/decision`, { method: "POST", body: JSON.stringify({ decision }) }),
  articleEvidence: (articleId: string) => request<EvidencePackage>(`/api/v1/articles/${articleId}/evidence`),
  jobEvents: (jobId: string) => request<JobEvent[]>(`/api/v1/jobs/${jobId}/events`),
  channelAccounts: () => request<ChannelAccount[]>("/api/v1/channels"),
  updateChannelAccount: (id: string, payload: { name?: string; app_id?: string; app_secret?: string; enabled?: boolean }) =>
    request<ChannelAccount>(`/api/v1/channels/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  disableChannelAccount: (id: string) => request<ChannelAccount>(`/api/v1/channels/${id}`, { method: "DELETE" }),
  addChannelAccount: (payload: { name: string; app_id: string; app_secret: string; publish_enabled?: boolean }) =>
    request<ChannelAccount>("/api/v1/channels", {
      method: "POST",
      body: JSON.stringify({
        channel_type: "wechat",
        name: payload.name,
        app_id: payload.app_id,
        app_secret: payload.app_secret,
        config: { publish_enabled: Boolean(payload.publish_enabled) },
      }),
    }),
  testChannelAccount: (id: string) => request<WechatConnection>(buildChannelTestPath(id), { method: "POST" }),
  models: () => request<Model[]>("/api/v1/models"),
  updateModel: (id: string, payload: { provider?: string; name?: string; api_base_url?: string; api_key?: string; enabled?: boolean }) =>
    request<Model>(`/api/v1/models/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  disableModel: (id: string) => request<Model>(`/api/v1/models/${id}`, { method: "PUT", body: JSON.stringify({ enabled: false }) }),
  deleteModel: (id: string) => request<{ deleted: boolean }>(`/api/v1/models/${id}`, { method: "DELETE" }),
  addModel: (payload: { provider: string; name: string; api_base_url?: string; api_key?: string }) =>
    request<Model>("/api/v1/models", { method: "POST", body: JSON.stringify(payload) }),
  importSkill: async (file: File): Promise<Skill> => {
    const form = new FormData();
    form.append("package", file);
    const response = await fetch("/api/v1/skills/import", { method: "POST", credentials: "include", body: form });
    if (!response.ok) throw new Error((await response.json()).detail ?? "Skill 导入失败");
    return response.json() as Promise<Skill>;
  },
  testModel: (id: string) => request<{ ok: boolean; message: string }>(`/api/v1/models/${id}/test`, { method: "POST" }),
  skills: () => request<Skill[]>("/api/v1/skills"),
  publishSkill: (id: string) => request<Skill>(`/api/v1/skills/${id}/publish`, { method: "POST" }),
  disableSkill: (id: string) => request<Skill>(`/api/v1/skills/${id}/disable`, { method: "POST" }),
  rollbackSkill: (id: string, version: string) => request<Skill>(`/api/v1/skills/${id}/rollback/${encodeURIComponent(version)}`, { method: "POST" }),
  runStrategy: (id: string, combinationId?: string) => request<Job>(`/api/v1/strategies/${id}/run`, { method: "POST", body: combinationId ? JSON.stringify({ combination_id: combinationId }) : undefined }),
  retryJob: (id: string) => request<Job>(`/api/v1/jobs/${id}/retry`, { method: "POST" }),
  cancelJob: (id: string) => request<Job>(`/api/v1/jobs/${id}/cancel`, { method: "POST" }),
  testWechatConnection: () => request<WechatConnection>("/api/v1/channels/wechat/test", { method: "POST" }),
  getWechatPublishStatus: (publishId: string, accountId: string) =>
    request<Record<string, unknown>>(`/api/v1/channels/wechat/publish/${encodeURIComponent(publishId)}?account_id=${encodeURIComponent(accountId)}`),  getWechatDraft: (mediaId: string, accountId?: string) =>
    request<Record<string, unknown>>(`/api/v1/channels/wechat/drafts/${encodeURIComponent(mediaId)}${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ""}`),
  uploadWechatThumb: async (file: File, accountId?: string): Promise<WechatMaterial> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(buildWechatThumbPath(accountId), { method: "POST", credentials: "include", body: form });
if (!response.ok) {
      let detail = "封面上传失败";
      try {
        const body = await response.json() as { detail?: string };
        detail = body.detail || detail;
      } catch {
        // Keep the stable fallback for non-JSON proxy errors.
      }
      throw new Error(detail);
    }
    return response.json() as Promise<WechatMaterial>;
  },
  createWechatDraft: (articleId: string, revisionId: string, payload: WechatDraftPayload) =>
    request<Publication>(`/api/v1/articles/${articleId}/revisions/${revisionId}/wechat-draft`, { method: "POST", body: JSON.stringify(payload) }),
  updateWechatDraft: (articleId: string, revisionId: string, payload: WechatDraftPayload) =>
    request<Publication>(`/api/v1/articles/${articleId}/revisions/${revisionId}/wechat-draft/update`, { method: "POST", body: JSON.stringify(payload) }),
  publishWechatDraft: (articleId: string, revisionId: string, channelAccountId: string) =>
    request<Publication>(`/api/v1/articles/${articleId}/revisions/${revisionId}/wechat-publish`, { method: "POST", body: JSON.stringify({ channel_account_id: channelAccountId }) }),
  addRevision: (articleId: string, content_markdown: string, title?: string) =>
    request<ArticleRevision>(`/api/v1/articles/${articleId}/revisions`, { method: "POST", body: JSON.stringify({ content_markdown, title }) }),
  reviewArticle: (articleId: string, revisionId: string, decision: "approve" | "reject" | "request_changes", comment = "") =>
    request<Review>(`/api/v1/articles/${articleId}/revisions/${revisionId}/review`, { method: "POST", body: JSON.stringify({ decision, comment }) }),
};
