import { useEffect, useMemo, useState } from "react";
import type { Article, ChannelAccount, Job, Material, MaterialCategory, MaterialDetail, Skill, Source, Strategy, Theme, Topic, TopicAlgorithm, TopicAlgorithmPayload } from "./api";
import { api } from "./api";
import { Icon } from "./design";

function stamp(value?: string | null) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

function excerpt(value: string, length = 96) {
  return value.length > length ? value.slice(0, length) + "…" : value;
}

function previewText(value: string) {
  return value
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>\s*<p>/gi, "\n\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, "\"")
    .replace(/&#39;/gi, "'")
    .trim();
}
function sourceTypeLabel(type: string) {
  if (type === "rss") return "RSS";
  if (type === "url") return "网页";
  if (type === "aihot_api") return "AI HOT";
  if (type === "manual") return "手动";
  return type.toUpperCase();
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="flow-empty"><span><Icon name="spark" size={20} /></span><strong>{title}</strong><p>{detail}</p></div>;
}

type CreatePayload = { materialIds: string[]; strategyId: string; title?: string; skillId: string };

export function MaterialWorkspace({
  materials, categories, sources, skills, strategies, loadError, creating, onCreate, onManageSources, onCollect, collecting, onCurate, curating, curationResult,
  onClassify, classifying, onTriage, onAssignCategory, onAddCategory, onUpdateCategory, onDisableCategory, onRestoreCategory,
}: {
  materials: Material[];
  categories: MaterialCategory[];
  sources: Source[];
  skills: Skill[];
  strategies: Strategy[];
  loadError: string;
  creating: boolean;
  onCreate: (payload: CreatePayload) => void;
  onManageSources: () => void;
  onCollect: (ids: string[]) => void;
  collecting: boolean;
  onCurate: (strategyId: string) => void;
  curating: boolean;
  curationResult?: { candidate_count: number; selected_count: number; message: string } | null;
  onClassify: (ids?: string[]) => void;
  classifying: boolean;
  onTriage: (id: string, decision: "save" | "ignore" | "reopen") => void;
  onAssignCategory: (id: string, categoryId: string | null) => void;
  onAddCategory: (payload: { name: string; description?: string; classification_instructions?: string }) => Promise<MaterialCategory>;
  onUpdateCategory: (id: string, payload: Partial<Pick<MaterialCategory, "name" | "description" | "classification_instructions" | "enabled">>) => Promise<MaterialCategory>;
  onDisableCategory: (id: string) => Promise<MaterialCategory>;
  onRestoreCategory: (id: string) => Promise<MaterialCategory>;
}) {
  const [view, setView] = useState<"inbox" | "retained" | "ignored">("inbox");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [composerOpen, setComposerOpen] = useState(false);
  const [strategyId, setStrategyId] = useState("");
  const [curationStrategyId, setCurationStrategyId] = useState("");
  const [collectOpen, setCollectOpen] = useState(false);
  const [collectIds, setCollectIds] = useState<string[] | null>(null);
  const [draftCollectIds, setDraftCollectIds] = useState<string[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [categoryManagerOpen, setCategoryManagerOpen] = useState(false);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [categoryForm, setCategoryForm] = useState({ name: "", description: "", classification_instructions: "" });
  const [title, setTitle] = useState("");
  const [composerSkillId, setComposerSkillId] = useState("");
  const [previewMaterial, setPreviewMaterial] = useState<Material | null>(null);
  const [previewDetail, setPreviewDetail] = useState<MaterialDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const retained = useMemo(() => materials.filter((item) => item.triage_status === "selected" || item.triage_status === "used"), [materials]);
  const inbox = useMemo(() => materials.filter((item) => item.triage_status === "inbox"), [materials]);
  const ignored = useMemo(() => materials.filter((item) => item.triage_status === "ignored"), [materials]);
  const viewMaterials = view === "inbox" ? inbox : view === "retained" ? retained : ignored;
  const sourceFiltered = viewMaterials.filter((item) =>
    (!sourceId || item.source_id === sourceId) && (!categoryId || item.category_id === categoryId),
  );
  const visible = sourceFiltered.filter((item) =>
    (item.title + " " + item.source_name + " " + item.content_excerpt).toLowerCase().includes(query.trim().toLowerCase()),
  );
  const enabledSourceIds = useMemo(() => sources.filter((source) => source.enabled).map((source) => source.id), [sources]);
  useEffect(() => {
    if (!previewMaterial) {
      setPreviewDetail(null);
      setPreviewError("");
      return;
    }
    let active = true;
    setPreviewDetail(null);
    setPreviewError("");
    setPreviewLoading(true);
    void api.material(previewMaterial.id)
      .then((detail) => { if (active) setPreviewDetail(detail); })
      .catch((error: Error) => { if (active) setPreviewError(error.message); })
      .finally(() => { if (active) setPreviewLoading(false); });
    return () => { active = false; };
  }, [previewMaterial]);  useEffect(() => {
    if (sourceId && !sources.some((source) => source.id === sourceId)) setSourceId("");
  }, [sourceId, sources]);
  useEffect(() => {
    if (view === "inbox" && !inbox.length && retained.length) setView("retained");
  }, [inbox.length, retained.length, view]);
  useEffect(() => {
    const first = strategies.find((item) => item.enabled)?.id || "";
    if (!curationStrategyId || !strategies.some((item) => item.id === curationStrategyId && item.enabled)) setCurationStrategyId(first);
    if (!strategyId && first) setStrategyId(first);
  }, [curationStrategyId, strategies, strategyId]);
  useEffect(() => {
    const strategy = strategies.find((item) => item.id === strategyId);
    const config = strategy?.config as Record<string, unknown> | undefined;
    const byStage = (config?.skill_by_stage ?? {}) as Record<string, string>;
    const ids = (config?.skill_ids ?? []) as string[];
    setComposerSkillId(byStage.writing ?? ids[0] ?? "");
  }, [strategyId, strategies]);
  const toggle = (id: string) => setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length < 12 ? [...current, id] : current);
  const editingCategory = categories.find((category) => category.id === editingCategoryId) ?? null;
  const editCategory = (category: MaterialCategory) => {
    setEditingCategoryId(category.id);
    setCategoryForm({
      name: category.name,
      description: category.description,
      classification_instructions: category.classification_instructions,
    });
  };
  const newCategory = () => {
    setEditingCategoryId(null);
    setCategoryForm({ name: "", description: "", classification_instructions: "" });
  };
  const saveCategory = async () => {
    const payload = {
      name: categoryForm.name.trim(),
      description: categoryForm.description.trim(),
      classification_instructions: categoryForm.classification_instructions.trim(),
    };
    if (!payload.name) return;
    if (editingCategory) await onUpdateCategory(editingCategory.id, payload);
    else {
      const created = await onAddCategory(payload);
      setEditingCategoryId(created.id);
    }
  };
  const submit = () => {
    if (!selectedIds.length || !strategyId) return;
    onCreate({ materialIds: selectedIds, strategyId, title: title.trim() || undefined, skillId: composerSkillId });
  };
  return (
    <main className="figma-page flow-page">
      <header className="flow-heading">
        <div><span className="flow-kicker">RETAINED MATERIALS</span><h1>素材池 <small>{materials.length}</small></h1><p>先采集到待精选区，再让 AI 审核；只有已保留素材会进入创作选择。</p></div>
        <div className="flow-heading-actions"><button className="flow-secondary" type="button" onClick={() => { setCategoryManagerOpen(true); if (!editingCategory) newCategory(); }}><Icon name="database" size={16} /> 管理分类</button><button className="flow-secondary" type="button" onClick={() => { setDraftCollectIds(collectIds ?? enabledSourceIds); setCollectOpen(true); }}><Icon name="link" size={16} /> 采集设置</button><button className="flow-primary" type="button" onClick={() => onCollect(collectIds ?? enabledSourceIds)} disabled={collecting || !enabledSourceIds.length}><Icon name="refresh" size={16} /> {collecting ? "正在采集…" : "立即采集"}</button></div>
      </header>
      {loadError && <div className="flow-load-error" role="alert"><Icon name="alert" size={17} /><div><strong>素材池暂时不可用</strong><span>{loadError}</span></div></div>}
      <section className="flow-toolbar">
        <div className="flow-tabs" role="tablist"><button className={view === "inbox" ? "is-active" : ""} type="button" onClick={() => setView("inbox")}>待 AI 精选 <b>{inbox.length}</b></button><button className={view === "retained" ? "is-active" : ""} type="button" onClick={() => setView("retained")}>已保留 <b>{retained.length}</b></button><button className={view === "ignored" ? "is-active" : ""} type="button" onClick={() => setView("ignored")}>已忽略 <b>{ignored.length}</b></button></div>
        <label className="flow-search"><Icon name="search" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索素材" /></label>
        <select className="flow-select flow-source-select" value={sourceId} onChange={(event) => setSourceId(event.target.value)} aria-label="按信息源筛选"><option value="">全部信息源</option>{sources.filter((source) => source.enabled || materials.some((item) => item.source_id === source.id)).map((source) => <option value={source.id} key={source.id}>{source.name}</option>)}</select>
        <select className="flow-select" value={categoryId} onChange={(event) => setCategoryId(event.target.value)} aria-label="按素材分类筛选"><option value="">全部分类</option>{categories.filter((category) => category.enabled || materials.some((item) => item.category_id === category.id)).map((category) => <option value={category.id} key={category.id}>{category.name}（{category.material_count}）</option>)}</select>
        <span className="flow-filter-count">当前筛选 {sourceFiltered.length} 条</span>
        {view === "inbox" && <><button className="flow-secondary" type="button" disabled={classifying || !materials.some((item) => item.classification_status !== "classified")} onClick={() => onClassify()}><Icon name="magic" size={15} /> {classifying ? "AI 分类中…" : "重试 AI 分类"}</button><select className="flow-select" value={curationStrategyId} onChange={(event) => setCurationStrategyId(event.target.value)} aria-label="AI 精选策略"><option value="">选择精选策略</option>{strategies.filter((item) => item.enabled).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><button className="flow-secondary flow-ai-button" type="button" disabled={!inbox.length || !curationStrategyId || curating} onClick={() => onCurate(curationStrategyId)}><Icon name="spark" size={15} /> {curating ? "AI 审核中…" : "AI 精选素材"}</button></>}

      </section>
      {selectedIds.length > 0 && <div className="flow-selection-bar"><span>已选 <b>{selectedIds.length}</b> 条素材</span><button className="flow-secondary" type="button" onClick={() => setSelectedIds([])}>清空选择</button><button className="flow-primary" type="button" disabled={!strategyId} onClick={() => setComposerOpen(true)}>下一步：创建选题并写作</button></div>}
      {curationResult && <div className="flow-notice" role="status"><Icon name="check" size={17} /><div><strong>AI 精选已完成</strong><span>{curationResult.message}</span></div></div>}
      {visible.length ? <section className="retained-grid">{visible.map((material) => {
        const selected = selectedIds.includes(material.id);
        return <article className={"retained-card" + (selected ? " is-selected" : "")} key={material.id}>
          <button className="retained-select" type="button" aria-pressed={selected} onClick={() => toggle(material.id)}><span className="retained-check">{selected ? "✓" : ""}</span><span className="figma-tag">{material.category_name || (material.classification_status === "failed" ? "分类失败" : "待分类")}</span><span className="figma-tag material-source-tag">{material.source_name}</span><time>{stamp(material.published_at || material.created_at)}</time><h2>{material.title}</h2><p>{excerpt(material.content_excerpt || "暂无摘要")}</p></button>
          <footer><span>{material.triage_status === "used" ? "已用于创作" : material.triage_status === "selected" ? "已保留" : material.triage_status === "ignored" ? "已忽略" : "等待 AI 精选"}</span>{material.triage_status === "inbox" && <><button className="flow-preview-link" type="button" onClick={() => onTriage(material.id, "save")}>保留</button><button className="flow-preview-link" type="button" onClick={() => onTriage(material.id, "ignore")}>忽略</button></>}{material.triage_status === "ignored" && <button className="flow-preview-link" type="button" onClick={() => onTriage(material.id, "reopen")}>恢复到待精选</button>}<select aria-label={`修正 ${material.title} 的分类`} value={material.category_id || ""} onChange={(event) => onAssignCategory(material.id, event.target.value || null)}><option value="">未分类</option>{categories.filter((category) => category.enabled).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select><button className="flow-preview-link" type="button" onClick={() => setPreviewMaterial(material)}><Icon name="eye" size={13} />预览内容</button>{material.url && <a href={material.url} target="_blank" rel="noreferrer">查看原文 <Icon name="external" size={13} /></a>}</footer>
        </article>;
      })}</section> : <EmptyState title={view === "inbox" ? "暂无待精选素材" : view === "retained" ? "还没有已保留素材" : "没有已忽略素材"} detail={view === "inbox" ? "点击右上角立即采集，或检查采集设置。" : view === "retained" ? "在待 AI 精选区保留后，素材会出现在这里。" : "被忽略的素材会保留在这里，并可随时恢复。"} />}
      {previewMaterial && <div className="figma-modal-backdrop" role="presentation" onClick={(event) => { if (event.target === event.currentTarget) setPreviewMaterial(null); }}><article className="figma-modal material-preview-modal" role="dialog" aria-modal="true" aria-label="素材预览"><button className="modal-close" type="button" aria-label="关闭预览" onClick={() => setPreviewMaterial(null)}><Icon name="close" size={18} /></button><span className="eyebrow">MATERIAL PREVIEW</span><h2>{previewDetail?.title || previewMaterial.title}</h2><div className="material-preview-meta"><span>{previewDetail?.source_name || previewMaterial.source_name}</span><time>{stamp(previewDetail?.published_at || previewMaterial.published_at || previewDetail?.created_at || previewMaterial.created_at)}</time></div>{previewLoading ? <div className="material-preview-loading">正在加载素材正文…</div> : previewError ? <div className="material-preview-error">预览加载失败：{previewError}</div> : <div className="material-preview-body"><p>{previewText(previewDetail?.content || previewMaterial.content_excerpt || "暂无可预览内容")}</p></div>}<footer className="material-preview-footer">{previewMaterial.url && <a href={previewMaterial.url} target="_blank" rel="noreferrer">打开原文 <Icon name="external" size={13} /></a>}<button className="flow-secondary" type="button" onClick={() => setPreviewMaterial(null)}>关闭预览</button></footer></article></div>}
      {categoryManagerOpen && <section className="flow-drawer category-drawer" role="dialog" aria-modal="true" aria-label="管理素材分类"><div className="flow-drawer-head"><div><span className="flow-kicker">MATERIAL CATEGORIES</span><h2>管理素材分类</h2></div><button type="button" aria-label="关闭" onClick={() => setCategoryManagerOpen(false)}><Icon name="close" size={18} /></button></div><p>AI 会在外文翻译完成后自动分类；你可以在素材卡片上人工纠正。停用分类不会删除历史素材。</p><div className="category-manager-list">{categories.map((category) => <button type="button" key={category.id} className={editingCategory?.id === category.id ? "is-active" : ""} onClick={() => editCategory(category)}><strong>{category.name}</strong><small>{category.enabled ? `${category.material_count} 条素材` : "已停用"}</small></button>)}<button className="category-new" type="button" onClick={newCategory}>+ 新建分类</button></div><label>分类名称<input value={categoryForm.name} maxLength={100} onChange={(event) => setCategoryForm((value) => ({ ...value, name: event.target.value }))} placeholder="例如：AI 应用案例" /></label><label>分类说明<input value={categoryForm.description} maxLength={500} onChange={(event) => setCategoryForm((value) => ({ ...value, description: event.target.value }))} placeholder="告诉 AI 这个分类包含什么" /></label><label>分类判断补充规则<textarea value={categoryForm.classification_instructions} maxLength={2000} onChange={(event) => setCategoryForm((value) => ({ ...value, classification_instructions: event.target.value }))} placeholder="可选：需要归入或排除的具体条件" /></label><div className="flow-drawer-actions"><button className="flow-secondary" type="button" onClick={() => setCategoryManagerOpen(false)}>完成</button>{editingCategory && (editingCategory.enabled ? <button className="flow-danger" type="button" onClick={() => void onDisableCategory(editingCategory.id)}>停用分类</button> : <button className="flow-secondary" type="button" onClick={() => void onRestoreCategory(editingCategory.id)}>恢复分类</button>)}<button className="flow-primary" type="button" disabled={!categoryForm.name.trim()} onClick={() => void saveCategory()}>{editingCategory ? "保存分类" : "创建分类"}</button></div></section>}
      {collectOpen && <section className="flow-drawer collect-source-drawer" role="dialog" aria-modal="true" aria-label="采集设置"><div className="flow-drawer-head"><div><span className="flow-kicker">COLLECTION</span><h2>采集设置</h2></div><button type="button" aria-label="关闭" onClick={() => setCollectOpen(false)}><Icon name="close" size={18} /></button></div><p>勾选要采集的信息源，点击“确定”后，右上角“立即采集”会按你的选择运行。新增、编辑和停用信息源请到「设置 → 信息源」。</p><div className="collect-source-list">{sources.filter((source) => source.enabled).map((source) => <label key={source.id} className={draftCollectIds.includes(source.id) ? "is-selected" : ""}><input type="checkbox" checked={draftCollectIds.includes(source.id)} onChange={(event) => setDraftCollectIds((current) => event.target.checked ? [...current, source.id] : current.filter((id) => id !== source.id))} /><span><strong>{source.name}</strong><small>{sourceTypeLabel(source.source_typ…949 tokens truncated…ic) => void;
  onSaveMaterials: (topic: Topic) => void;
  onCreateAlgorithm: (payload: TopicAlgorithmPayload) => Promise<TopicAlgorithm>;
  onUpdateAlgorithm: (id: string, payload: TopicAlgorithmPayload) => Promise<TopicAlgorithm>;
  onDeleteAlgorithm: (id: string) => Promise<unknown>;
}) {
  const [strategyId, setStrategyId] = useState(strategies.find((item) => item.enabled)?.id || "");
  const [algorithmId, setAlgorithmId] = useState("");
  const [managerOpen, setManagerOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [algorithmForm, setAlgorithmForm] = useState<AlgorithmForm>(DEFAULT_ALGORITHM_FORM);
  const enabledAlgorithms = algorithms.filter((item) => item.enabled);
  const editingAlgorithm = algorithms.find((item) => item.id === editingId) ?? null;
  const candidates = topics.filter((topic) => topic.status === "candidate");

  useEffect(() => {
    if (!enabledAlgorithms.some((item) => item.id === algorithmId)) {
      setAlgorithmId(enabledAlgorithms[0]?.id ?? "");
    }
  }, [algorithmId, algorithms]);

  const editAlgorithm = (algorithm: TopicAlgorithm) => {
    setEditingId(algorithm.id);
    setAlgorithmForm(formForAlgorithm(algorithm));
  };

  const createAlgorithm = () => {
    setEditingId(null);
    setAlgorithmForm(DEFAULT_ALGORITHM_FORM);
  };

  const saveAlgorithm = async () => {
    const payload: TopicAlgorithmPayload = {
      ...algorithmForm,
      name: algorithmForm.name.trim(),
      instructions: algorithmForm.instructions.trim(),
    };
    if (editingAlgorithm) {
      await onUpdateAlgorithm(editingAlgorithm.id, payload);
    } else {
      const created = await onCreateAlgorithm(payload);
      setAlgorithmId(created.id);
      setEditingId(created.id);
      setAlgorithmForm(formForAlgorithm(created));
    }
  };

  return (
    <main className="figma-page flow-page">
      <header className="flow-heading">
        <div><span className="flow-kicker">AI TOPIC RADAR</span><h1>选题雷达</h1><p>AI 扫描信息源，按你选定的算法推荐选题并给出评分。你只需要判断“值不值得写”。</p></div>
        <div className="radar-scan">
          <label><span>选题算法</span><select value={algorithmId} onChange={(event) => setAlgorithmId(event.target.value)} aria-label="选择选题算法"><option value="">加载算法中</option>{enabledAlgorithms.map((algorithm) => <option value={algorithm.id} key={algorithm.id}>{algorithm.name}</option>)}</select></label>
          <button className="flow-ghost" type="button" onClick={() => { setManagerOpen(true); if (!editingAlgorithm) createAlgorithm(); }}>管理算法</button>
          <label><span>扫描生产线</span><select value={strategyId} onChange={(event) => setStrategyId(event.target.value)} aria-label="选择扫描生产线"><option value="">选择生产线</option>{strategies.filter((item) => item.enabled).map((strategy) => <option value={strategy.id} key={strategy.id}>{strategy.name}</option>)}</select></label>
          <button className="flow-primary" type="button" disabled={!strategyId || !algorithmId || scanning} onClick={() => onScan(strategyId, algorithmId)}><Icon name="refresh" size={15} /> {scanning ? "AI 正在扫描…" : "运行一次扫描"}</button>
        </div>
      </header>
      <section className="radar-summary"><div><strong>{candidates.length}</strong><span>个待判断选题</span></div><p>本次扫描使用「{enabledAlgorithms.find((item) => item.id === algorithmId)?.name || "默认推荐算法"}」；每次任务都会冻结当时的算法配置。</p></section>
      {candidates.length ? <section className="radar-list">{candidates.map((topic) => <article className="radar-card" key={topic.id}>
        <div className="radar-score"><strong>{Math.round(topic.score)}</strong><span>/ 100</span></div>
        <div className="radar-body">
          <div className="radar-card-head"><span className="figma-tag">AI 推荐</span><span>{topic.materials.length} 条依据素材</span></div>
          <h2>{topic.title}</h2><p>{topic.rationale || "暂无推荐说明"}</p>
          {!!topic.scores.length && <div className="score-strip">{topic.scores.map((score) => <span key={score.id}><small>{DIMENSION_LABELS[score.dimension] || score.dimension}</small><b>{Math.round(score.score)}</b></span>)}</div>}
          <div className="topic-material-list">{topic.materials.map((material) => <a href={material.url || undefined} target="_blank" rel="noreferrer" key={material.source_item_id}><span>{material.role === "primary" ? "主" : "辅"}</span><b>{material.title}</b><small>{material.source_name}</small></a>)}</div>
          <div className="topic-write-note">生成文章会锁定选题、关联素材和生产线组合；完成后进入待审核，不会直接发布。</div>
          <footer><button className="flow-ghost" type="button" onClick={() => onDismiss(topic)}>忽略选题</button><button className="flow-secondary" type="button" disabled={!topic.materials.length} onClick={() => onSaveMaterials(topic)}>保留关联素材</button><button className="flow-primary" type="button" disabled={writing} onClick={() => onWrite(topic)}>{writing ? "正在创建任务…" : "生成文章并送审"}</button></footer>
        </div>
      </article>)}</section> : <EmptyState title="还没有待判断选题" detail="选择生产线与选题算法后运行扫描，AI 会返回基于真实素材的推荐。" />}
      {managerOpen && <section className="flow-drawer algorithm-drawer" role="dialog" aria-modal="true" aria-label="管理选题算法">
        <div className="flow-drawer-head"><div><span className="flow-kicker">TOPIC ALGORITHMS</span><h2>管理选题算法</h2></div><button type="button" aria-label="关闭" onClick={() => setManagerOpen(false)}><Icon name="close" size={18} /></button></div>
        <p>默认推荐算法始终可用。你创建的算法会出现在上方下拉框，并影响下一次扫描的选题判断与评分。</p>
        <div className="algorithm-list">{algorithms.map((algorithm) => <button type="button" key={algorithm.id} className={editingAlgorithm?.id === algorithm.id ? "is-active" : ""} onClick={() => editAlgorithm(algorithm)}><strong>{algorithm.name}</strong><small>{algorithm.is_builtin ? "系统默认" : algorithm.enabled ? "自定义算法" : "已停用"}</small></button>)}<button className="algorithm-new" type="button" onClick={createAlgorithm}>+ 新建自定义算法</button></div>
        <label>算法名称<input disabled={editingAlgorithm?.is_builtin} value={algorithmForm.name} placeholder="例如：深度洞察优先" onChange={(event) => setAlgorithmForm((value) => ({ ...value, name: event.target.value }))} /></label>
        <label>选题判断规则<textarea disabled={editingAlgorithm?.is_builtin} value={algorithmForm.instructions} placeholder="例如：优先选择有明确用户冲突、可验证事实和实用建议的 AI 工具选题；排除纯融资通稿。" onChange={(event) => setAlgorithmForm((value) => ({ ...value, instructions: event.target.value }))} /></label>
        <label>每次推荐数量<select disabled={editingAlgorithm?.is_builtin} value={algorithmForm.max_topics} onChange={(event) => setAlgorithmForm((value) => ({ ...value, max_topics: Number(event.target.value) }))}>{[2, 3, 4, 5, 6, 8].map((count) => <option key={count} value={count}>{count}</option>)}</select></label>
        <div className="algorithm-weights">{(["heat", "timeliness", "reader_value", "strategy_fit"] as const).map((dimension) => <label key={dimension}><span>{DIMENSION_LABELS[dimension]}</span><input disabled={editingAlgorithm?.is_builtin} type="number" min="0" max="100" value={algorithmForm.weights[dimension]} onChange={(event) => setAlgorithmForm((value) => ({ ...value, weights: { ...value.weights, [dimension]: Number(event.target.value) } }))} /></label>)}</div>
        <div className="flow-drawer-actions"><button className="flow-secondary" type="button" onClick={() => setManagerOpen(false)}>完成</button>{editingAlgorithm && !editingAlgorithm.is_builtin && <button className="flow-danger" type="button" disabled={managingAlgorithms} onClick={() => { if (window.confirm("删除该自定义算法？已运行的扫描任务不会受影响。")) { void onDeleteAlgorithm(editingAlgorithm.id).then(createAlgorithm); } }}>删除算法</button>}{!editingAlgorithm?.is_builtin && <button className="flow-primary" type="button" disabled={managingAlgorithms || !algorithmForm.name.trim()} onClick={() => void saveAlgorithm()}>{managingAlgorithms ? "正在保存…" : editingAlgorithm ? "保存算法" : "创建算法"}</button>}</div>
      </section>}
    </main>
  );
}

function ArticleBody({ article }: { article: Article }) {
  const revision = article.revisions[article.revisions.length - 1];
  return revision ? <div className="article-reading" dangerouslySetInnerHTML={{ __html: revision.rendered_html }} /> : <EmptyState title="没有正文版本" detail="当前任务尚未生成可阅读的正文。" />;
}

export function hasFinalArticleBody(article: Article) {
  const content = article.revisions[article.revisions.length - 1]?.content_markdown.trim() ?? "";
  return content.length >= 300 && !["这是一份基于已核验来源生成的草稿。", "质检报告", "L1 硬性规则", "L2 风格一致性", "禁用词：", "结构套话"].some((marker) => content.includes(marker));
}

export function isReviewFailureStatus(status: string) {
  return ["failed", "failed_retryable", "failed_terminal"].includes(status);
}

export function ReviewQueue({
  articles, jobs, selectedId, pending, retrying, onSelect, onApprove, onChanges, onEdit, onRetry,
}: {
  articles: Article[];
  jobs: Job[];
  selectedId: string | null;
  pending: boolean;
  retrying: boolean;
  onSelect: (id: string) => void;
  onApprove: (article: Article) => void;
  onChanges: (article: Article) => void;
  onEdit: (id: string) => void;
  onRetry: (id: string) => void;
}) {
  const queue = articles.filter((article) => ["waiting_review", "changes_requested", "edited"].includes(article.status));
  const activeJobs = jobs.filter((job) => ["queued", "running", "retrying"].includes(job.status));
  const failedJobs = jobs.filter((job) => isReviewFailureStatus(job.status));
  const selected = queue.find((article) => article.id === selectedId) || queue[0];
  const stepName = (value: string | null) => ({ collect: "采集素材", normalize: "整理素材", deduplicate: "去重", topic: "AI 选题", evidence: "构建事实依据", outline: "生成大纲", writing: "撰写正文", style: "应用文风", rewrite: "自然化改写", review: "质量审核", render: "排版", draft: "生成草稿" }[value || ""] || "准备中");
  return (
    <main className="figma-page flow-page">
      <header className="flow-heading"><div><span className="flow-kicker">REVIEW QUEUE</span><h1>待审核</h1><p>生成任务的进度也会显示在这里；正文完成后进入审核，通过后自动移入成稿库。</p></div><span className="queue-count">{queue.length} 篇待审核 · {activeJobs.length} 篇生成中</span></header>{activeJobs.length > 0 && <section className="generation-status" aria-label="文章生成进度"><h2>正在生成</h2>{activeJobs.map((job) => <article key={job.id}><span className="generation-spinner" aria-hidden="true" /><div><strong>{String((job.runtime_snapshot.strategy as { name?: unknown } | undefined)?.name || "内容生产任务")}</strong><small>当前步骤：{stepName(job.current_step)} · 第 {job.attempt_count + 1} 次执行</small></div></article>)}</section>}{failedJobs.length > 0 && <section className="generation-status is-error" aria-label="生成失败任务"><h2>需要处理</h2>{failedJobs.map((job) => <article key={job.id}><Icon name="alert" size={17} /><div><strong>文章生成失败</strong><small>{job.last_error || "任务执行失败，可重试"}</small></div><button className="flow-secondary" type="button" disabled={retrying} onClick={() => onRetry(job.id)}>重试</button></article>)}</section>}
      {selected ? <section className="review-workbench">
        <aside className="review-queue-list">{queue.map((article) => <button type="button" className={article.id === selected.id ? "is-active" : ""} key={article.id} onClick={() => onSelect(article.id)}><span>{article.status === "changes_requested" ? "待修改" : article.status === "edited" ? "待重新审核" : "待审核"}</span><strong>{article.title}</strong><small>{article.revisions.length} 个版本</small></button>)}</aside>
        <article className="review-document"><header><div><span className="figma-tag">事实校验后生成</span><h2>{selected.title}</h2></div><button className="flow-secondary" type="button" onClick={() => onEdit(selected.id)}><Icon name="edit" size={14} /> 编辑正文</button></header>{selected.review?.auto_result && <section className={`quality-review-summary ${selected.review.auto_result.status === "fail" ? "is-failed" : ""}`}><strong>AI 质量审核：{selected.review.auto_result.status === "fail" ? "未通过，已拦截自动交付" : "通过"}</strong><span>{String(selected.review.auto_result.summary || "已检查事实可追溯、来源质量、标题一致性和正文完整性")}</span>{typeof selected.review.auto_result.score === "number" && <b>{selected.review.auto_result.score} 分</b>}</section>}<ArticleBody article={selected} /><footer><button className="flow-secondary" type="button" disabled={pending} onClick={() => onChanges(selected)}>退回修改</button><button className="flow-primary" type="button" disabled={pending} onClick={() => onApprove(selected)}>{pending ? "正在处理…" : "审核通过，移入成稿库"}</button></footer></article>
      </section> : activeJobs.length ? <EmptyState title="文章正在生成" detail="无需重复创建任务；页面会自动刷新，生成完成后正文会出现在审核队列。" /> : failedJobs.length ? <EmptyState title="生成任务需要处理" detail="请先查看上方失败原因；补齐素材或配置后再重试。" /> : <EmptyState title="审核队列已清空" detail="新文章生成完成后会自动出现在这里；已通过的文章请到成稿库查看。" />}
    </main>
  );
}

export function ArticleLibrary({
  articles, selectedId, themes, channels, selectedThemeId, selectedChannelId, thumbMediaId,
  coverPreviewUrl, themePreviewHtml, themePreviewLoading, themePreviewError, pending, deliveryError, onSelect, onEdit, onArchive, onThemeChange, onChannelChange, onUpload, onDraft,
}: {
  articles: Article[];
  selectedId: string | null;
  themes: Theme[];
  channels: ChannelAccount[];
  selectedThemeId: string;
  selectedChannelId: string;
  thumbMediaId: string;
  coverPreviewUrl: string;
  themePreviewHtml: string;
  themePreviewLoading: boolean;
  themePreviewError: string;
  pending: boolean;
  deliveryError: string;
  onSelect: (id: string) => void;
  onEdit: (id: string) => void;
  onArchive: (article: Article) => void;
  onThemeChange: (id: string) => void;
  onChannelChange: (id: string) => void;
  onUpload: (file: File) => void;
  onDraft: (article: Article) => void;
}) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const library = articles.filter((article) =>
    ["approved", "drafted", "wechat_draft", "publishing", "published"].includes(article.status) && hasFinalArticleBody(article),
  );
  const selected = library.find((article) => article.id === selectedId) || library[0];
  return (
    <main className="figma-page flow-page">
      <header className="flow-heading"><div><span className="flow-kicker">APPROVED LIBRARY</span><h1>成稿库</h1><p>已审核文章的唯一出口。在这里做排版、封面和渠道配置，再写入微信草稿。</p></div><span className="queue-count">{library.length} 篇成稿</span></header>
      {selected ? <section className="library-workbench">
        <aside className="library-list">{library.map((article) => <button type="button" className={article.id === selected.id ? "is-active" : ""} key={article.id} onClick={() => onSelect(article.id)}><span>{article.status === "wechat_draft" ? "微信草稿" : article.status === "publishing" ? "发布处理中" : article.status === "published" ? "已发布" : article.status === "drafted" ? "本地成稿" : "已通过"}</span><strong>{article.title}</strong></button>)}</aside>
        <article className="library-preview"><header><h2>{selected.title}</h2><div className="library-preview-actions"><button className="flow-ghost" type="button" onClick={() => onEdit(selected.id)}>编辑</button><button className="flow-danger" type="button" onClick={() => setConfirmingId(selected.id)}>归档</button></div></header>{confirmingId === selected.id && <div className="library-delete-confirm" role="alert"><p>将从本地成稿库归档这篇文章。微信端已经创建的草稿或已发布内容不会被删除。</p><div><button className="flow-ghost" type="button" onClick={() => setConfirmingId(null)}>取消</button><button className="flow-danger" type="button" disabled={pending} onClick={() => { onArchive(selected); setConfirmingId(null); }}>确认归档</button></div></div>}{selectedThemeId ? <section className="library-themed-preview" aria-label="已应用的公众号排版主题">{themePreviewLoading ? <div className="wechat-preview-loading">正在应用排版模板…</div> : themePreviewError ? <div className="wechat-preview-error">模板预览失败：{themePreviewError}</div> : <div className="wechat-preview-body" dangerouslySetInnerHTML={{ __html: themePreviewHtml }} />}</section> : <ArticleBody article={selected} />}</article>
        <aside className="delivery-panel"><h2>交付设置</h2>
          {selectedThemeId && <section className="wechat-preview" aria-label="微信公众号文章样式预览"><header className="wechat-preview-header"><span>WECHAT ARTICLE PREVIEW</span><strong>{themes.find((theme) => theme.id === selectedThemeId)?.name || "已选模板"}</strong></header>{themePreviewLoading ? <div className="wechat-preview-loading">正在生成公众号正文预览…</div> : themePreviewError ? <div className="wechat-preview-error">预览生成失败：{themePreviewError}</div> : <div className="wechat-preview-body" dangerouslySetInnerHTML={{ __html: themePreviewHtml }} />}</section>}
          <label>排版模板<select value={selectedThemeId} onChange={(event) => onThemeChange(event.target.value)}><option value="">不使用模板</option>{themes.filter((theme) => theme.enabled).map((theme) => <option key={theme.id} value={theme.id}>{theme.name}</option>)}</select></label>
          <label>微信公众号<select value={selectedChannelId} onChange={(event) => onChannelChange(event.target.value)}><option value="">请选择账号</option>{channels.filter((channel) => channel.enabled).map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></label>
          <label className="cover-uploader"><span>封面图</span><input type="file" accept="image/*" onChange={(event) => { const file = event.target.files?.[0]; if (file) onUpload(file); }} />{coverPreviewUrl ? <img src={coverPreviewUrl} alt="封面预览" /> : <div><Icon name="image" size={20} />选择封面</div>}</label>
          {deliveryError && <div className="delivery-error" role="alert">{deliveryError}</div>}
          <button className="flow-primary" type="button" disabled={pending || !selectedChannelId || !thumbMediaId || selected.status === "published"} onClick={() => onDraft(selected)}>{selected.status === "wechat_draft" ? "重新写入微信草稿" : pending ? "正在写入…" : "写入微信草稿"}</button>
          <small>当前测试阶段只创建草稿，不会自动正式发布。</small>
        </aside>
      </section> : <EmptyState title="成稿库还是空的" detail="在待审核页通过一篇文章后，它会立即出现在这里。" />}
    </main>
  );
}