import { useEffect, useMemo, useState } from "react";
import type { Article, ChannelAccount, Job, Material, MaterialCategory, MaterialDetail, Skill, Source, Strategy, Theme, Topic, TopicAlgorithm, TopicAlgorithmPayload } from "./api";
import { api } from "./api";
import { Icon } from "./design";

function stamp(value?: string | null) {
  if (!value) return "æ—¶é—´æœªçŸ¥";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "æ—¶é—´æœªçŸ¥";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

function excerpt(value: string, length = 96) {
  return value.length > length ? value.slice(0, length) + "â€¦" : value;
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
  if (type === "url") return "ç½‘é¡µ";
  if (type === "aihot_api") return "AI HOT";
  if (type === "manual") return "æ‰‹åŠ¨";
  return type.toUpperCase();
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="flow-empty"><span><Icon name="spark" size={20} /></span><strong>{title}</strong><p>{detail}</p></div>;
}

type CreatePayload = { materialIds: string[]; strategyId: string; title?: string; skillId: string };

export function MaterialWorkspace({
  materials, categories, sources, skills, strategies, loadError, creating, onCreate, onManageSources, onCollect, collecting, onCurate, curating, curationResult,
  onClassify, classifying, onTriage, onAssignCategory, onAddCategory, onUpdateCategory, onDisableCategory, onRestoreCategory,
  onManageStrategies,
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
  onManageStrategies: () => void;
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
  const hasEnabledStrategy = strategies.some((item) => item.enabled);
  const selectedInboxCount = materials.filter((item) => selectedIds.includes(item.id) && item.triage_status === "inbox").length;
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
        <div><span className="flow-kicker">RETAINED MATERIALS</span><h1>ç´ ææ±  <small>{materials.length}</small></h1><p>å…ˆé‡‡é›†åˆ°å¾…ç²¾é€‰åŒºï¼Œå†è®© AI å®¡æ ¸ï¼›åªæœ‰å·²ä¿ç•™ç´ æä¼šè¿›å…¥åˆ›ä½œé€‰æ‹©ã€‚</p></div>
        <div className="flow-heading-actions"><button className="flow-secondary" type="button" onClick={() => { setCategoryManagerOpen(true); if (!editingCategory) newCategory(); }}><Icon name="database" size={16} /> ç®¡ç†åˆ†ç±»</button><button className="flow-secondary" type="button" onClick={() => { setDraftCollectIds(collectIds ?? enabledSourceIds); setCollectOpen(true); }}><Icon name="link" size={16} /> é‡‡é›†è®¾ç½®</button><button className="flow-primary" type="button" onClick={() => onCollect(collectIds ?? enabledSourceIds)} disabled={collecting || !enabledSourceIds.length}><Icon name="refresh" size={16} /> {collecting ? "æ­£åœ¨é‡‡é›†â€¦" : "ç«‹å³é‡‡é›†"}</button></div>
      </header>
      {loadError && <div className="flow-load-error" role="alert"><Icon name="alert" size={17} /><div><strong>ç´ ææ± æš‚æ—¶ä¸å¯ç”¨</strong><span>{loadError}</span></div></div>}
      <section className="flow-toolbar">
        <div className="flow-tabs" role="tablist"><button className={view === "inbox" ? "is-active" : ""} type="button" onClick={() => setView("inbox")}>å¾… AI ç²¾é€‰ <b>{inbox.length}</b></button><button className={view === "retained" ? "is-active" : ""} type="button" onClick={() => setView("retained")}>å·²ä¿ç•™ <b>{retained.length}</b></button><button className={view === "ignored" ? "is-active" : ""} type="button" onClick={() => setView("ignored")}>å·²å¿½ç•¥ <b>{ignored.length}</b></button></div>
        <label className="flow-search"><Icon name="search" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="æœç´¢ç´ æ" /></label>
        <select className="flow-select flow-source-select" value={sourceId} onChange={(event) => setSourceId(event.target.value)} aria-label="æŒ‰ä¿¡æ¯æºç­›é€‰"><option value="">å…¨éƒ¨ä¿¡æ¯æº</option>{sources.filter((source) => source.enabled || materials.some((item) => item.source_id === source.id)).map((source) => <option value={source.id} key={source.id}>{source.name}</option>)}</select>
        <select className="flow-select" value={categoryId} onChange={(event) => setCategoryId(event.target.value)} aria-label="æŒ‰ç´ æåˆ†ç±»ç­›é€‰"><option value="">å…¨éƒ¨åˆ†ç±»</option>{categories.filter((category) => category.enabled || materials.some((item) => item.category_id === category.id)).map((category) => <option value={category.id} key={category.id}>{category.name}ï¼ˆ{category.material_count}ï¼‰</option>)}</select>
        <span className="flow-filter-count">å½“å‰ç­›é€‰ {sourceFiltered.length} æ¡</span>
        {view === "inbox" && <><button className="flow-secondary" type="button" disabled={classifying || !materials.some((item) => item.classification_status !== "classified")} onClick={() => onClassify()}><Icon name="magic" size={15} /> {classifying ? "AI åˆ†ç±»ä¸­â€¦" : "é‡è¯• AI åˆ†ç±»"}</button><select className="flow-select" value={curationStrategyId} onChange={(event) => setCurationStrategyId(event.target.value)} aria-label="AI ç²¾é€‰ç­–ç•¥"><option value="">é€‰æ‹©ç²¾é€‰ç­–ç•¥</option>{strategies.filter((item) => item.enabled).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><button className="flow-secondary flow-ai-button" type="button" disabled={!inbox.length || !curationStrategyId || curating} onClick={() => onCurate(curationStrategyId)}><Icon name="spark" size={15} /> {curating ? "AI å®¡æ ¸ä¸­â€¦" : "AI ç²¾é€‰ç´ æ"}</button></>}

      </section>
      {selectedIds.length > 0 && <div className="flow-selection-bar"><span>å·²é€‰ <b>{selectedIds.length}</b> æ¡ç´ æ</span><button className="flow-secondary" type="button" onClick={() => setSelectedIds([])}>æ¸…ç©ºé€‰æ‹©</button><button className="flow-primary" type="button" disabled={creating || (hasEnabledStrategy && selectedInboxCount > 0)} onClick={() => { if (!hasEnabledStrategy) { onManageStrategies(); return; } if (selectedInboxCount === 0) setComposerOpen(true); }}>{hasEnabledStrategy ? "ä¸‹ä¸€æ­¥ï¼šåˆ›å»ºé€‰é¢˜å¹¶å†™ä½œ" : "å…ˆåˆ›å»ºç”Ÿäº§çº¿"}</button>{!hasEnabledStrategy && <small className="flow-selection-hint">è¯·å…ˆåˆ°â€œè‡ªåŠ¨åŒ–â€ä¿å­˜å¹¶å¯ç”¨ä¸€æ¡ç”Ÿäº§çº¿ã€‚</small>}{hasEnabledStrategy && selectedInboxCount > 0 && <small className="flow-selection-hint">å·²é€‰çš„ {selectedInboxCount} æ¡ç´ æè¿˜åœ¨â€œå¾… AI ç²¾é€‰â€åŒºï¼Œè¯·å…ˆç‚¹å‡»å¡ç‰‡åº•éƒ¨çš„â€œä¿ç•™â€ã€‚</small>}</div>}
      {curationResult && <div className="flow-notice" role="status"><Icon name="check" size={17} /><div><strong>AI ç²¾é€‰å·²å®Œæˆ</strong><span>{curationResult.message}</span></div></div>}
      {visible.length ? <section className="retained-grid">{visible.map((material) => {
        const selected = selectedIds.includes(material.id);
        return <article className={"retained-card" + (selected ? " is-selected" : "")} key={material.id}>
          <button className="retained-select" type="button" aria-pressed={selected} onClick={() => toggle(material.id)}><span className="retained-check">{selected ? "âœ“" : ""}</span><span className="figma-tag">{material.category_name || (material.classification_status === "failed" ? "åˆ†ç±»å¤±è´¥" : "å¾…åˆ†ç±»")}</span><span className="figma-tag material-source-tag">{material.source_name}</span><time>{stamp(material.published_at || material.created_at)}</time><h2>{material.title}</h2><p>{excerpt(material.content_excerpt || "æš‚æ— æ‘˜è¦")}</p></button>
          <footer><span>{material.triage_status === "used" ? "å·²ç”¨äºåˆ›ä½œ" : material.triage_status === "selected" ? "å·²ä¿ç•™" : material.triage_status === "ignored" ? "å·²å¿½ç•¥" : "ç­‰å¾… AI ç²¾é€‰"}</span>{material.triage_status === "inbox" && <><button className="flow-preview-link" type="button" onClick={() => onTriage(material.id, "save")}>ä¿ç•™</button><button className="flow-preview-link" type="button" onClick={() => onTriage(material.id, "ignore")}>å¿½ç•¥</button></>}{material.triage_status === "ignored" && <button className="flow-preview-link" type="button" onClick={() => onTriage(material.id, "rç]ü¶‰Ëkºwµçtµ‘É…İ•ÈˆÉ½±”ô‰‘¥…±½œˆ…É¥„µµ½‘…°ô‰ÑÉÕ”ˆ…É¥„µ±…‰•°ô‹º‡B¦'¦Šcº_šÎTˆø4(€€€€€€€€ñ‘¥Ø±…ÍÍ9…µ”ô‰™±½Üµ‘É…İ•Èµ¡•…ˆøñ‘¥ØøñÍÁ…¸±…ÍÍ9…µ”ô‰™±½Üµ­¥­•ÈˆùQ=A%1=I%Q!5Lğ½ÍÁ…¸øñ Èûº‡B¦'¦Šcº_šÎTğ½ Èøğ½‘¥Øøñ‰ÕÑÑ½¸ÑåÁ”ô‰‰ÕÑÑ½¸ˆ…É¥„µ±…‰•°ô‹–Ï¦^´ˆ½¹±¥¬õì ¤€ôøÍ•Ñ5…¹…•É=Á•¸¡™…±Í”¥ôøñ%½¸¹…µ”ô‰±½Í”ˆÍ¥é”õìÄáô€¼øğ½‰ÕÑÑ½¸øğ½‘¥Øø4(€€€€€€€€ñÀû¦îc¢º“š:£¢6Cº_šÎW–/î#–>¿R£’öƒ–"o–îëjº_šÎW’òk–ë:Ã–r£’â+šZç’â/š.'š†¾ò3–æÛ–öÇ–N7’â/’âš²‡š&¯š>?j¦'¦Šc–"“šZ·’â;¢¾–"ğ½Àø4(€€€€€€€€ñ‘¥Ø±…ÍÍ9…µ”ô‰…±½É¥Ñ¡´µ±¥ÍĞˆùí…±½É¥Ñ¡µÌ¹µ…À ¡…±½É¥Ñ¡´¤€ôø€ñ‰ÕÑÑ½¸ÑåÁ”ô‰‰ÕÑÑ½¸ˆ­•äõí…±½É¥Ñ¡´¹¥‘ô±…ÍÍ9…µ”õí•‘¥Ñ¥¹±½É¥Ñ¡´ü¹¥€ôôô…±½É¥Ñ¡´¹¥€ü€‰¥Ìµ…Ñ¥Ù”ˆ€è€ˆ‰ô½¹±¥¬õì ¤€ôø•‘¥Ñ±½É¥Ñ¡´¡…±½É¥Ñ¡´¥ôøñÍÑÉ½¹œùí…±½É¥Ñ¡´¹¹…µ•ôğ½ÍÑÉ½¹œøñÍµ…±°ùí…±½É¥Ñ¡´¹¥Í}‰Õ¥±Ñ¥¸€ü€‹Îïî¦îc¢ºˆ€è…±½É¥Ñ¡´¹•¹…‰±•€ü€‹¢«–ºk’æ'º_šÎTˆ€è€‹–ŞË–sR ‰ôğ½Íµ…±°øğ½‰ÕÑÑ½¸ø¥ôñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰…±½É¥Ñ¡´µ¹•ÜˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ½¹±¥¬õíÉ•…Ñ•±½É¥Ñ¡µôø¬ƒšZÃ–îë¢«–ºk’æ'º_šÎTğ½‰ÕÑÑ½¸øğ½‘¥Øø4(€€€€€€€€ñ±…‰•°ûº_šÎW–B7Àñ¥¹ÁÕĞ‘¥Í…‰±•õí•‘¥Ñ¥¹±½É¥Ñ¡´ü¹¥Í}‰Õ¥±Ñ¥¹ôÙ…±Õ”õí…±½É¥Ñ¡µ½É´¹¹…µ•ôÁ±…•¡½±‘•Èô‹’ú/–š¾òkšŞÇ–ê›šÒ{–¾’òc– ˆ½¹¡…¹”õì¡•Ù•¹Ğ¤€ôøÍ•Ñ±½É¥Ñ¡µ½É´ ¡Ù…±Õ”¤€ôø€¡ì€¸¸¹Ù…±Õ”°¹…µ”è•Ù•¹Ğ¹Ñ…É•Ğ¹Ù…±Õ”ô¤¥ô€¼øğ½±…‰•°ø4(€€€€€€€€ñ±…‰•°û¦'¦Šc–"“šZ·¢–"dñÑ•áÑ…É•„‘¥Í…‰±•õí•‘¥Ñ¥¹±½É¥Ñ¡´ü¹¥Í}‰Õ¥±Ñ¥¹ôÙ…±Õ”õí…±½É¥Ñ¡µ½É´¹¥¹ÍÑÉÕÑ¥½¹ÍôÁ±…•¡½±‘•Èô‹’ú/–š¾òk’òc–#¦'š.§šr'šb;†»R£š"ß–Ëª–>¿¦ª3¢¾’ê/–º{–J3–º{R£–îë¢º»j$ƒ–Ş—–ß¦'¦Šc¾òoš:K¦f“ê¿¢z7¢Ö¦k¢ÿˆ½¹¡…¹”õì¡•Ù•¹Ğ¤€ôøÍ•Ñ±½É¥Ñ¡µ½É´ ¡Ù…±Õ”¤€ôø€¡ì€¸¸¹Ù…±Õ”°¥¹ÍÑÉÕÑ¥½¹Ìè•Ù•¹Ğ¹Ñ…É•Ğ¹Ù…±Õ”ô¤¥ô€¼øğ½±…‰•°ø4(€€€€€€€€ñ±…‰•°ûš¾?š²‡š:£¢6CšVÃ¦<ñÍ•±•Ğ‘¥Í…‰±•õí•‘¥Ñ¥¹±½É¥Ñ¡´ü¹¥Í}‰Õ¥±Ñ¥¹ôÙ…±Õ”õí…±½É¥Ñ¡µ½É´¹µ…á}Ñ½Á¥Íô½¹¡…¹”õì¡•Ù•¹Ğ¤€ôøÍ•Ñ±½É¥Ñ¡µ½É´ ¡Ù…±Õ”¤€ôø€¡ì€¸¸¹Ù…±Õ”°µ…á}Ñ½Á¥Ìè9Õµ‰•È¡•Ù•¹Ğ¹Ñ…É•Ğ¹Ù…±Õ”¤ô¤¥ôùílÈ°€Ì°€Ğ°€Ô°€Ø°€át¹µ…À ¡½Õ¹Ğ¤€ôø€ñ½ÁÑ¥½¸­•äõí½Õ¹ÑôÙ…±Õ”õí½Õ¹Ñôùí½Õ¹Ñôğ½½ÁÑ¥½¸ø¥ôğ½Í•±•Ğøğ½±…‰•°ø4(€€€€€€€€ñ‘¥Ø±…ÍÍ9…µ”ô‰…±½É¥Ñ¡´µİ•¥¡ÑÌˆùì¡l‰¡•…Ğˆ°€‰Ñ¥µ•±¥¹•ÍÌˆ°€‰É•…‘•É}Ù…±Õ”ˆ°€‰ÍÑÉ…Ñ•å}™¥Ğ‰t…Ì½¹ÍĞ¤¹µ…À ¡‘¥µ•¹Í¥½¸¤€ôø€ñ±…‰•°­•äõí‘¥µ•¹Í¥½¹ôøñÍÁ…¸ùí%59M%=9}1	1Mm‘¥µ•¹Í¥½¹uôğ½ÍÁ…¸øñ¥¹ÁÕĞ‘¥Í…‰±•õí•‘¥Ñ¥¹±½É¥Ñ¡´ü¹¥Í}‰Õ¥±Ñ¥¹ôÑåÁ”ô‰¹Õµ‰•Èˆµ¥¸ôˆÀˆµ…àôˆÄÀÀˆÙ…±Õ”õí…±½É¥Ñ¡µ½É´¹İ•¥¡ÑÍm‘¥µ•¹Í¥½¹uô½¹¡…¹”õì¡•Ù•¹Ğ¤€ôøÍ•Ñ±½É¥Ñ¡µ½É´ ¡Ù…±Õ”¤€ôø€¡ì€¸¸¹Ù…±Õ”°İ•¥¡ÑÌèì€¸¸¹Ù…±Õ”¹İ•¥¡ÑÌ°m‘¥µ•¹Í¥½¹tè9Õµ‰•È¡•Ù•¹Ğ¹Ñ…É•Ğ¹Ù…±Õ”¤ôô¤¥ô€¼øğ½±…‰•°ø¥ôğ½‘¥Øø4(€€€€€€€€ñ‘¥Ø±…ÍÍ9…µ”ô‰™±½Üµ‘É…İ•Èµ…Ñ¥½¹Ìˆøñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½ÜµÍ•½¹‘…ÉäˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ½¹±¥¬õì ¤€ôøÍ•Ñ5…¹…•É=Á•¸¡™…±Í”¥ôû–º3š"@ğ½‰ÕÑÑ½¸ùí•‘¥Ñ¥¹±½É¥Ñ¡´€˜˜€…•‘¥Ñ¥¹±½É¥Ñ¡´¹¥Í}‰Õ¥±Ñ¥¸€˜˜€ñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½Üµ‘…¹•ÈˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ‘¥Í…‰±•õíµ…¹…¥¹±½É¥Ñ¡µÍô½¹±¥¬õì ¤€ôøì¥˜€¡İ¥¹‘½Ü¹½¹™¥É´ ‹–"ƒ¦f“¢¾—¢«–ºk’æ'º_šÎW¾ò–ŞË¢şC¢†3jš&¯š>?’îï–*‡’â7’òk–>_–öÇ–N7ˆ¤¤ìÙ½¥½¹•±•Ñ•±½É¥Ñ¡´¡•‘¥Ñ¥¹±½É¥Ñ¡´¹¥¤¹Ñ¡•¸¡É•…Ñ•±½É¥Ñ¡´¤ìôõôû–"ƒ¦f“º_šÎTğ½‰ÕÑÑ½¸ùõì…•‘¥Ñ¥¹±½É¥Ñ¡´ü¹¥Í}‰Õ¥±Ñ¥¸€˜˜€ñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½ÜµÁÉ¥µ…ÉäˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ‘¥Í…‰±•õíµ…¹…¥¹±½É¥Ñ¡µÌñğ€……±½É¥Ñ¡µ½É´¹¹…µ”¹ÑÉ¥´ ¥ô½¹±¥¬õì ¤€ôøÙ½¥Í…Ù•±½É¥Ñ¡´ ¥ôùíµ…¹…¥¹±½É¥Ñ¡µÌ€ü€‹š¶–r£’şw–¶cŠ˜ˆ€è•‘¥Ñ¥¹±½É¥Ñ¡´€ü€‹’şw–¶cº_šÎTˆ€è€‹–"o–îëº_šÎT‰ôğ½‰ÕÑÑ½¸ùôğ½‘¥Øø4(€€€€€€ğ½Í•Ñ¥½¸ùô4(€€€€ğ½µ…¥¸ø4(€€¤ì4)ô4(4)™Õ¹Ñ¥½¸ÉÑ¥±•	½‘ä¡ì…ÉÑ¥±”ôèì…ÉÑ¥±”èÉÑ¥±”ô¤ì4(€½¹ÍĞÉ•Ù¥Í¥½¸€ô…ÉÑ¥±”¹É•Ù¥Í¥½¹Ím…ÉÑ¥±”¹É•Ù¥Í¥½¹Ì¹±•¹Ñ €´€Åtì4(€É•ÑÕÉ¸É•Ù¥Í¥½¸€ü€ñ‘¥Ø±…ÍÍ9…µ”ô‰…ÉÑ¥±”µÉ•…‘¥¹œˆ‘…¹•É½ÕÍ±åM•Ñ%¹¹•É!Q50õíì}}¡Ñµ°èÉ•Ù¥Í¥½¸¹É•¹‘•É•‘}¡Ñµ°õô€¼ø€è€ñµÁÑåMÑ…Ñ”Ñ¥Ñ±”ô‹šÊ‡šr'š¶šZ&#šr°ˆ‘•Ñ…¥°ô‹–öO–&7’îï–*‡–Âkšr«Rš"C–>¿¦b¢¾ïjš¶šZˆ€¼øì4)ô4(4)•áÁ½ÉĞ™Õ¹Ñ¥½¸¡…Í¥¹…±ÉÑ¥±•	½‘ä¡…ÉÑ¥±”èÉÑ¥±”¤ì4(€½¹ÍĞ½¹Ñ•¹Ğ€ô…ÉÑ¥±”¹É•Ù¥Í¥½¹Ím…ÉÑ¥±”¹É•Ù¥Í¥½¹Ì¹±•¹Ñ €´€Åtü¹½¹Ñ•¹Ñ}µ…É­‘½İ¸¹ÑÉ¥´ ¤€üü€ˆˆì4(€É•ÑÕÉ¸½¹Ñ•¹Ğ¹±•¹Ñ €øô€ÌÀÀ€˜˜€…l‹¢şgšb¿’â’î÷–~ë’ê;–ŞËš‚ã¦ª3šv—šêCRš"Cj¢6'¢ÿˆ°€‹¢Ò£šš*—–F(ˆ°€‰0Äƒ†³šŸ¢–"dˆ°€‰0Èƒ¦;š‚ó’â¢Óšœˆ°€‹šR£¢¾7¾òhˆ°€‹îOšz––_¢¾t‰t¹Í½µ” ¡µ…É­•È¤€ôø½¹Ñ•¹Ğ¹¥¹±Õ‘•Ì¡µ…É­•È¤¤ì4)ô4(4)•áÁ½ÉĞ™Õ¹Ñ¥½¸¥ÍI•Ù¥•İ…¥±ÕÉ•MÑ…ÑÕÌ¡ÍÑ…ÑÕÌèÍÑÉ¥¹œ¤ì4(€É•ÑÕÉ¸l‰™…¥±•ˆ°€‰™…¥±•‘}É•ÑÉå…‰±”ˆ°€‰™…¥±•‘}Ñ•Éµ¥¹…°‰t¹¥¹±Õ‘•Ì¡ÍÑ…ÑÕÌ¤ì4)ô4(4)•áÁ½ÉĞ™Õ¹Ñ¥½¸I•Ù¥•İEÕ•Õ”¡ì4(€…ÉÑ¥±•Ì°©½‰Ì°Í•±•Ñ•‘%°Á•¹‘¥¹œ°É•ÑÉå¥¹œ°½¹M•±•Ğ°½¹ÁÁÉ½Ù”°½¹¡…¹•Ì°½¹‘¥Ğ°½¹I•ÑÉä°4)ôèì4(€…ÉÑ¥±•ÌèÉÑ¥±•mtì4(€©½‰Ìè)½‰mtì4(€Í•±•Ñ•‘%èÍÑÉ¥¹œğ¹Õ±°ì4(€Á•¹‘¥¹œè‰½½±•…¸ì4(€É•ÑÉå¥¹œè‰½½±•…¸ì4(€½¹M•±•Ğè€¡¥èÍÑÉ¥¹œ¤€ôøÙ½¥ì4(€½¹ÁÁÉ½Ù”è€¡…ÉÑ¥±”èÉÑ¥±”¤€ôøÙ½¥ì4(€½¹¡…¹•Ìè€¡…ÉÑ¥±”èÉÑ¥±”¤€ôøÙ½¥ì4(€½¹‘¥Ğè€¡¥èÍÑÉ¥¹œ¤€ôøÙ½¥ì4(€½¹I•ÑÉäè€¡¥èÍÑÉ¥¹œ¤€ôøÙ½¥ì4)ô¤ì4(€½¹ÍĞÅÕ•Õ”€ô…ÉÑ¥±•Ì¹™¥±Ñ•È ¡…ÉÑ¥±”¤€ôøl‰İ…¥Ñ¥¹}É•Ù¥•Üˆ°€‰¡…¹•Í}É•ÅÕ•ÍÑ•ˆ°€‰•‘¥Ñ•‰t¹¥¹±Õ‘•Ì¡…ÉÑ¥±”¹ÍÑ…ÑÕÌ¤¤ì4(€½¹ÍĞ…Ñ¥Ù•)½‰Ì€ô©½‰Ì¹™¥±Ñ•È ¡©½ˆ¤€ôøl‰ÅÕ•Õ•ˆ°€‰ÉÕ¹¹¥¹œˆ°€‰É•ÑÉå¥¹œ‰t¹¥¹±Õ‘•Ì¡©½ˆ¹ÍÑ…ÑÕÌ¤¤ì4(€½¹ÍĞ™…¥±•‘)½‰Ì€ô©½‰Ì¹™¥±Ñ•È ¡©½ˆ¤€ôø¥ÍI•Ù¥•İ…¥±ÕÉ•MÑ…ÑÕÌ¡©½ˆ¹ÍÑ…ÑÕÌ¤¤ì4(€½¹ÍĞÍ•±•Ñ•€ôÅÕ•Õ”¹™¥¹ ¡…ÉÑ¥±”¤€ôø…ÉÑ¥±”¹¥€ôôôÍ•±•Ñ•‘%¤ñğÅÕ•Õ•lÁtì4(€½¹ÍĞÍÑ•Á9…µ”€ô€¡Ù…±Õ”èÍÑÉ¥¹œğ¹Õ±°¤€ôø€¡ì½±±•Ğè€‹¦¦nÒƒšv@ˆ°¹½Éµ…±¥é”è€‹šVÓBÒƒšv@ˆ°‘•‘ÕÁ±¥…Ñ”è€‹–:ï¦4ˆ°Ñ½Á¥Œè€‰$ƒ¦'¦Š`ˆ°•Ù¥‘•¹”è€‹šz–îë’ê/–º{’úwš6¸ˆ°½ÕÑ±¥¹”è€‹Rš"C–’ŸêÈˆ°İÉ¥Ñ¥¹œè€‹šJÃ–gš¶šZˆ°ÍÑå±”è€‹–êSR£šZ¦8ˆ°É•İÉ¥Ñ”è€‹¢«Û–2[šRç–dˆ°É•Ù¥•Üè€‹¢Ò£¦?–º‡š‚àˆ°É•¹‘•Èè€‹š:K& ˆ°‘É…™Ğè€‹Rš"C¢6'¢üˆõmÙ…±Õ”ñğ€ˆ‰tñğ€‹––’’â´ˆ¤ì4(€É•ÑÕÉ¸€ 4(€€€€ñµ…¥¸±…ÍÍ9…µ”ô‰™¥µ„µÁ…”™±½ÜµÁ…”ˆø4(€€€€€€ñ¡•…‘•È±…ÍÍ9…µ”ô‰™±½Üµ¡•…‘¥¹œˆøñ‘¥ØøñÍÁ…¸±…ÍÍ9…µ”ô‰™±½Üµ­¥­•ÈˆùIY%\EUUğ½ÍÁ…¸øñ Äû–ú–º‡š‚àğ½ ÄøñÀûRš"C’îï–*‡j¢şo–ê›’æ’òkšbû’ë–r£¢şg¦3¾òoš¶šZ–º3š"C–B;¢şo–—–º‡š‚ã¾ò3¦k¢ş–B;¢«–*£ï–—š"C¢ÿ–êOğ½Àøğ½‘¥ØøñÍÁ…¸±…ÍÍ9…µ”ô‰ÅÕ•Õ”µ½Õ¹ĞˆùíÅÕ•Õ”¹±•¹Ñ¡ôƒ¾–ú–º‡š‚àƒ
Üí…Ñ¥Ù•)½‰Ì¹±•¹Ñ¡ôƒ¾Rš"C’â´ğ½ÍÁ…¸øğ½¡•…‘•Èùí…Ñ¥Ù•)½‰Ì¹±•¹Ñ €ø€À€˜˜€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰•¹•É…Ñ¥½¸µÍÑ…ÑÕÌˆ…É¥„µ±…‰•°ô‹šZ®ƒRš"C¢şo–ê˜ˆøñ Èûš¶–r£Rš"@ğ½ Èùí…Ñ¥Ù•)½‰Ì¹µ…À ¡©½ˆ¤€ôø€ñ…ÉÑ¥±”­•äõí©½ˆ¹¥‘ôøñÍÁ…¸±…ÍÍ9…µ”ô‰•¹•É…Ñ¥½¸µÍÁ¥¹¹•Èˆ…É¥„µ¡¥‘‘•¸ô‰ÑÉÕ”ˆ€¼øñ‘¥ØøñÍÑÉ½¹œùíMÑÉ¥¹œ ¡©½ˆ¹ÉÕ¹Ñ¥µ•}Í¹…ÁÍ¡½Ğ¹ÍÑÉ…Ñ•ä…Ìì¹…µ”üèÕ¹­¹½İ¸ôğÕ¹‘•™¥¹•¤ü¹¹…µ”ñğ€‹––ºçR’êŸ’îï–*„ˆ¥ôğ½ÍÑÉ½¹œøñÍµ…±°û–öO–&7š¶—¦ª“¾òiíÍÑ•Á9…µ”¡©½ˆ¹ÕÉÉ•¹Ñ}ÍÑ•À¥ôƒ
Üƒ²°í©½ˆ¹…ÑÑ•µÁÑ}½Õ¹Ğ€¬€Åôƒš²‡š&Ÿ¢†0ğ½Íµ…±°øğ½‘¥Øøğ½…ÉÑ¥±”ø¥ôğ½Í•Ñ¥½¸ùõí™…¥±•‘)½‰Ì¹±•¹Ñ €ø€À€˜˜€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰•¹•É…Ñ¥½¸µÍÑ…ÑÕÌ¥Ìµ•ÉÉ½Èˆ…É¥„µ±…‰•°ô‹Rš"C–’Ç¢Ò—’îï–*„ˆøñ Èû¦r¢š–’Bğ½ Èùí™…¥±•‘)½‰Ì¹µ…À ¡©½ˆ¤€ôø€ñ…ÉÑ¥±”­•äõí©½ˆ¹¥‘ôøñ%½¸¹…µ”ô‰…±•ÉĞˆÍ¥é”õìÄİô€¼øñ‘¥ØøñÍÑÉ½¹œûšZ®ƒRš"C–’Ç¢Ò”ğ½ÍÑÉ½¹œøñÍµ…±°ùí©½ˆ¹±…ÍÑ}•ÉÉ½Èñğ€‹’îï–*‡š&Ÿ¢†3–’Ç¢Ò—¾ò3–>¿¦7¢¾T‰ôğ½Íµ…±°øğ½‘¥Øøñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½ÜµÍ•½¹‘…ÉäˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ‘¥Í…‰±•õíÉ•ÑÉå¥¹ô½¹±¥¬õì ¤€ôø½¹I•ÑÉä¡©½ˆ¹¥¥ôû¦7¢¾Tğ½‰ÕÑÑ½¸øğ½…ÉÑ¥±”ø¥ôğ½Í•Ñ¥½¸ùô4(€€€€€íÍ•±•Ñ•€ü€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰É•Ù¥•Üµİ½É­‰•¹ ˆø4(€€€€€€€€ñ…Í¥‘”±…ÍÍ9…µ”ô‰É•Ù¥•ÜµÅÕ•Õ”µ±¥ÍĞˆùíÅÕ•Õ”¹µ…À ¡…ÉÑ¥±”¤€ôø€ñ‰ÕÑÑ½¸ÑåÁ”ô‰‰ÕÑÑ½¸ˆ±…ÍÍ9…µ”õí…ÉÑ¥±”¹¥€ôôôÍ•±•Ñ•¹¥€ü€‰¥Ìµ…Ñ¥Ù”ˆ€è€ˆ‰ô­•äõí…ÉÑ¥±”¹¥‘ô½¹±¥¬õì ¤€ôø½¹M•±•Ğ¡…ÉÑ¥±”¹¥¥ôøñÍÁ…¸ùí…ÉÑ¥±”¹ÍÑ…ÑÕÌ€ôôô€‰¡…¹•Í}É•ÅÕ•ÍÑ•ˆ€ü€‹–ú’ş»šRäˆ€è…ÉÑ¥±”¹ÍÑ…ÑÕÌ€ôôô€‰•‘¥Ñ•ˆ€ü€‹–ú¦7šZÃ–º‡š‚àˆ€è€‹–ú–º‡š‚à‰ôğ½ÍÁ…¸øñÍÑÉ½¹œùí…ÉÑ¥±”¹Ñ¥Ñ±•ôğ½ÍÑÉ½¹œøñÍµ…±°ùí…ÉÑ¥±”¹É•Ù¥Í¥½¹Ì¹±•¹Ñ¡ôƒ’â«&#šr°ğ½Íµ…±°øğ½‰ÕÑÑ½¸ø¥ôğ½…Í¥‘”ø4(€€€€€€€€ñ…ÉÑ¥±”±…ÍÍ9…µ”ô‰É•Ù¥•Üµ‘½Õµ•¹Ğˆøñ¡•…‘•Èøñ‘¥ØøñÍÁ…¸±…ÍÍ9…µ”ô‰™¥µ„µÑ…œˆû’ê/–º{š‚‡¦ª3–B;Rš"@ğ½ÍÁ…¸øñ ÈùíÍ•±•Ñ•¹Ñ¥Ñ±•ôğ½ Èøğ½‘¥Øøñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½ÜµÍ•½¹‘…ÉäˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ½¹±¥¬õì ¤€ôø½¹‘¥Ğ¡Í•±•Ñ•¹¥¥ôøñ%½¸¹…µ”ô‰•‘¥ĞˆÍ¥é”õìÄÑô€¼øƒò[¢úGš¶šZğ½‰ÕÑÑ½¸øğ½¡•…‘•ÈùíÍ•±•Ñ•¹É•Ù¥•Üü¹…ÕÑ½}É•ÍÕ±Ğ€˜˜€ñÍ•Ñ¥½¸±…ÍÍ9…µ”õíÅÕ…±¥ÑäµÉ•Ù¥•ÜµÍÕµµ…Éä€‘íÍ•±•Ñ•¹É•Ù¥•Ü¹…ÕÑ½}É•ÍÕ±Ğ¹ÍÑ…ÑÕÌ€ôôô€‰™…¥°ˆ€ü€‰¥Ìµ™…¥±•ˆ€è€ˆ‰õôøñÍÑÉ½¹œù$ƒ¢Ò£¦?–º‡š‚ã¾òiíÍ•±•Ñ•¹É•Ù¥•Ü¹…ÕÑ½}É•ÍÕ±Ğ¹ÍÑ…ÑÕÌ€ôôô€‰™…¥°ˆ€ü€‹šr«¦k¢ş¾ò3–ŞËš.›š"«¢«–*£’ê“’î`ˆ€è€‹¦k¢ş‰ôğ½ÍÑÉ½¹œøñÍÁ…¸ùíMÑÉ¥¹œ¡Í•±•Ñ•¹É•Ù¥•Ü¹…ÕÑ½}É•ÍÕ±Ğ¹ÍÕµµ…Éäñğ€‹–ŞËšš~—’ê/–º{–>¿¢ş÷šê¿šv—šêC¢Ò£¦?š‚¦Šc’â¢ÓšŸ–J3š¶šZ–º3šVÓšœˆ¥ôğ½ÍÁ…¸ùíÑåÁ•½˜Í•±•Ñ•¹É•Ù¥•Ü¹…ÕÑ½}É•ÍÕ±Ğ¹Í½É”€ôôô€‰¹Õµ‰•Èˆ€˜˜€ñˆùíÍ•±•Ñ•¹É•Ù¥•Ü¹…ÕÑ½}É•ÍÕ±Ğ¹Í½É•ôƒ–"ğ½ˆùôğ½Í•Ñ¥½¸ùõíÑåÁ•½˜Í•±•Ñ•¹•Ù¥‘•¹”¹Ù•É¥™¥…Ñ¥½¸€ôôô€‰½‰©•Ğˆ€˜˜Í•±•Ñ•¹•Ù¥‘•¹”¹Ù•É¥™¥…Ñ¥½¸€„ôô¹Õ±°€˜˜€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰ÅÕ…±¥ÑäµÉ•Ù¥•ÜµÍÕµµ…ÉäˆøñÍÑÉ½¹œû¢SöG’ê/–º{š‚ã¦ª3¾òiíMÑÉ¥¹œ ¡Í•±•Ñ•¹•Ù¥‘•¹”¹Ù•É¥™¥…Ñ¥½¸…ÌìÙ•É¥™¥…Ñ¥½¹}ÍÑ…ÑÕÌüèÕ¹­¹½İ¸ô¤¹Ù•É¥™¥…Ñ¥½¹}ÍÑ…ÑÕÌñğ€‰Õ¹­¹½İ¸ˆ¥ôğ½ÍÑÉ½¹œøñÍÁ…¸ùíMÑÉ¥¹œ ¡Í•±•Ñ•¹•Ù¥‘•¹”¹Ù•É¥™¥…Ñ¥½¸…ÌìÍÕµµ…ÉäüèÕ¹­¹½İ¸ô¤¹ÍÕµµ…Éäñğ€‹šjš^ƒš‚ã¦ª3¢¾Óšb8ˆ¥ôğ½ÍÁ…¸øğ½Í•Ñ¥½¸ùôñÉÑ¥±•	½‘ä…ÉÑ¥±”õíÍ•±•Ñ•‘ô€¼øñ™½½Ñ•Èøñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½ÜµÍ•½¹‘…ÉäˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ‘¥Í…‰±•õíÁ•¹‘¥¹ô½¹±¥¬õì ¤€ôø½¹¡…¹•Ì¡Í•±•Ñ•¥ôû¦–n{’ş»šRäğ½‰ÕÑÑ½¸øñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½ÜµÁÉ¥µ…ÉäˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ‘¥Í…‰±•õíÁ•¹‘¥¹ô½¹±¥¬õì ¤€ôø½¹ÁÁÉ½Ù”¡Í•±•Ñ•¥ôùíÁ•¹‘¥¹œ€ü€‹š¶–r£–’BŠ˜ˆ€è€‹–º‡š‚ã¦k¢ş¾ò3ï–—š"C¢ÿ–êL‰ôğ½‰ÕÑÑ½¸øğ½™½½Ñ•Èøğ½…ÉÑ¥±”ø4(€€€€€€ğ½Í•Ñ¥½¸ø€è…Ñ¥Ù•)½‰Ì¹±•¹Ñ €ü€ñµÁÑåMÑ…Ñ”Ñ¥Ñ±”ô‹šZ®ƒš¶–r£Rš"@ˆ‘•Ñ…¥°ô‹š^ƒ¦r¦7–’7–"o–îë’îï–*‡¾òo¦†×¦v‹’òk¢«–*£–"ßšZÃ¾ò3Rš"C–º3š"C–B;š¶šZ’òk–ë:Ã–r£–º‡š‚ã¦b–"_ˆ€¼ø€è™…¥±•‘)½‰Ì¹±•¹Ñ €ü€ñµÁÑåMÑ…Ñ”Ñ¥Ñ±”ô‹Rš"C’îï–*‡¦r¢š–’Bˆ‘•Ñ…¥°ô‹¢¾ß–#š~—r/’â+šZç–’Ç¢Ò—–:–nƒ¾òo¢†—¦öCÒƒšvCš"[¦7ö»–B;–7¦7¢¾Wˆ€¼ø€è€ñµÁÑåMÑ…Ñ”Ñ¥Ñ±”ô‹–º‡š‚ã¦b–"_–ŞËšâ¦èˆ‘•Ñ…¥°ô‹šZÃšZ®ƒRš"C–º3š"C–B;’òk¢«–*£–ë:Ã–r£¢şg¦3¾òo–ŞË¦k¢şjšZ®ƒ¢¾ß–"Ãš"C¢ÿ–êOš~—r/ˆ€¼ùô4(€€€€ğ½µ…¥¸ø4(€€¤ì4)ô4(4)•áÁ½ÉĞ™Õ¹Ñ¥½¸ÉÑ¥±•1¥‰É…Éä¡ì4(€…ÉÑ¥±•Ì°Í•±•Ñ•‘%°Ñ¡•µ•Ì°¡…¹¹•±Ì°Í•±•Ñ•‘Q¡•µ•%°Í•±•Ñ•‘¡…¹¹•±%°Ñ¡Õµ‰5•‘¥…%°4(€½Ù•ÉAÉ•Ù¥•İUÉ°°Ñ¡•µ•AÉ•Ù¥•İ!Ñµ°°Ñ¡•µ•AÉ•Ù¥•İ1½…‘¥¹œ°Ñ¡•µ•AÉ•Ù¥•İÉÉ½È°Á•¹‘¥¹œ°‘•±¥Ù•ÉåÉÉ½È°½¹M•±•Ğ°½¹‘¥Ğ°½¹É¡¥Ù”°½¹Q¡•µ•¡…¹”°½¹¡…¹¹•±¡…¹”°½¹UÁ±½…°½¹É…™Ğ°4)ôèì4(€…ÉÑ¥±•ÌèÉÑ¥±•mtì4(€Í•±•Ñ•‘%èÍÑÉ¥¹œğ¹Õ±°ì4(€Ñ¡•µ•ÌèQ¡•µ•mtì4(€¡…¹¹•±Ìè¡…¹¹•±½Õ¹Ñmtì4(€Í•±•Ñ•‘Q¡•µ•%èÍÑÉ¥¹œì4(€Í•±•Ñ•‘¡…¹¹•±%èÍÑÉ¥¹œì4(€Ñ¡Õµ‰5•‘¥…%èÍÑÉ¥¹œì4(€½Ù•ÉAÉ•Ù¥•İUÉ°èÍÑÉ¥¹œì4(€Ñ¡•µ•AÉ•Ù¥•İ!Ñµ°èÍÑÉ¥¹œì4(€Ñ¡•µ•AÉ•Ù¥•İ1½…‘¥¹œè‰½½±•…¸ì4(€Ñ¡•µ•AÉ•Ù¥•İÉÉ½ÈèÍÑÉ¥¹œì4(€Á•¹‘¥¹œè‰½½±•…¸ì4(€‘•±¥Ù•ÉåÉÉ½ÈèÍÑÉ¥¹œì4(€½¹M•±•Ğè€¡¥èÍÑÉ¥¹œ¤€ôøÙ½¥ì4(€½¹‘¥Ğè€¡¥èÍÑÉ¥¹œ¤€ôøÙ½¥ì4(€½¹É¡¥Ù”è€¡…ÉÑ¥±”èÉÑ¥±”¤€ôøÙ½¥ì4(€½¹Q¡•µ•¡…¹”è€¡¥èÍÑÉ¥¹œ¤€ôøÙ½¥ì4(€½¹¡…¹¹•±¡…¹”è€¡¥èÍÑÉ¥¹œ¤€ôøÙ½¥ì4(€½¹UÁ±½…è€¡™¥±”è¥±”¤€ôøÙ½¥ì4(€½¹É…™Ğè€¡…ÉÑ¥±”èÉÑ¥±”¤€ôøÙ½¥ì4)ô¤ì4(€½¹ÍĞm½¹™¥Éµ¥¹%°Í•Ñ½¹™¥Éµ¥¹%‘t€ôÕÍ•MÑ…Ñ”ñÍÑÉ¥¹œğ¹Õ±°ø¡¹Õ±°¤ì4(€½¹ÍĞ±¥‰É…Éä€ô…ÉÑ¥±•Ì¹™¥±Ñ•È ¡…ÉÑ¥±”¤€ôø4(€€€l‰…ÁÁÉ½Ù•ˆ°€‰‘É…™Ñ•ˆ°€‰İ•¡…Ñ}‘É…™Ğˆ°€‰ÁÕ‰±¥Í¡¥¹œˆ°€‰ÁÕ‰±¥Í¡•‰t¹¥¹±Õ‘•Ì¡…ÉÑ¥±”¹ÍÑ…ÑÕÌ¤€˜˜¡…Í¥¹…±ÉÑ¥±•	½‘ä¡…ÉÑ¥±”¤°4(€€¤ì4(€½¹ÍĞÍ•±•Ñ•€ô±¥‰É…Éä¹™¥¹ ¡…ÉÑ¥±”¤€ôø…ÉÑ¥±”¹¥€ôôôÍ•±•Ñ•‘%¤ñğ±¥‰É…ÉålÁtì4(€É•ÑÕÉ¸€ 4(€€€€ñµ…¥¸±…ÍÍ9…µ”ô‰™¥µ„µÁ…”™±½ÜµÁ…”ˆø4(€€€€€€ñ¡•…‘•È±…ÍÍ9…µ”ô‰™±½Üµ¡•…‘¥¹œˆøñ‘¥ØøñÍÁ…¸±…ÍÍ9…µ”ô‰™±½Üµ­¥­•ÈˆùAAI=Y1%	IIdğ½ÍÁ…¸øñ Äûš"C¢ÿ–êLğ½ ÄøñÀû–ŞË–º‡š‚ãšZ®ƒj–R¿’â–ë–>–r£¢şg¦3–kš:K&#–Â¦v‹–J3šâƒ¦O¦7ö»¾ò3–7–g–—–ú»’ş‡¢6'¢ÿğ½Àøğ½‘¥ØøñÍÁ…¸±…ÍÍ9…µ”ô‰ÅÕ•Õ”µ½Õ¹Ğˆùí±¥‰É…Éä¹±•¹Ñ¡ôƒ¾š"C¢üğ½ÍÁ…¸øğ½¡•…‘•Èø4(€€€€€íÍ•±•Ñ•€ü€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰±¥‰É…Éäµİ½É­‰•¹ ˆø4(€€€€€€€€ñ…Í¥‘”±…ÍÍ9…µ”ô‰±¥‰É…Éäµ±¥ÍĞˆùí±¥‰É…Éä¹µ…À ¡…ÉÑ¥±”¤€ôø€ñ‰ÕÑÑ½¸ÑåÁ”ô‰‰ÕÑÑ½¸ˆ±…ÍÍ9…µ”õí…ÉÑ¥±”¹¥€ôôôÍ•±•Ñ•¹¥€ü€‰¥Ìµ…Ñ¥Ù”ˆ€è€ˆ‰ô­•äõí…ÉÑ¥±”¹¥‘ô½¹±¥¬õì ¤€ôø½¹M•±•Ğ¡…ÉÑ¥±”¹¥¥ôøñÍÁ…¸ùí…ÉÑ¥±”¹ÍÑ…ÑÕÌ€ôôô€‰İ•¡…Ñ}‘É…™Ğˆ€ü€‹–ú»’ş‡¢6'¢üˆ€è…ÉÑ¥±”¹ÍÑ…ÑÕÌ€ôôô€‰ÁÕ‰±¥Í¡¥¹œˆ€ü€‹–>G–â–’B’â´ˆ€è…ÉÑ¥±”¹ÍÑ…ÑÕÌ€ôôô€‰ÁÕ‰±¥Í¡•ˆ€ü€‹–ŞË–>G–âˆ€è…ÉÑ¥±”¹ÍÑ…ÑÕÌ€ôôô€‰‘É…™Ñ•ˆ€ü€‹šr³–rÃš"C¢üˆ€è€‹–ŞË¦k¢ş‰ôğ½ÍÁ…¸øñÍÑÉ½¹œùí…ÉÑ¥±”¹Ñ¥Ñ±•ôğ½ÍÑÉ½¹œøğ½‰ÕÑÑ½¸ø¥ôğ½…Í¥‘”ø4(€€€€€€€€ñ…ÉÑ¥±”±…ÍÍ9…µ”ô‰±¥‰É…ÉäµÁÉ•Ù¥•Üˆøñ¡•…‘•Èøñ ÈùíÍ•±•Ñ•¹Ñ¥Ñ±•ôğ½ Èøñ‘¥Ø±…ÍÍ9…µ”ô‰±¥‰É…ÉäµÁÉ•Ù¥•Üµ…Ñ¥½¹Ìˆøñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½Üµ¡½ÍĞˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ½¹±¥¬õì ¤€ôø½¹‘¥Ğ¡Í•±•Ñ•¹¥¥ôûò[¢úDğ½‰ÕÑÑ½¸øñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½Üµ‘…¹•ÈˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ½¹±¥¬õì ¤€ôøÍ•Ñ½¹™¥Éµ¥¹%¡Í•±•Ñ•¹¥¥ôû–öKš†Œğ½‰ÕÑÑ½¸øğ½‘¥Øøğ½¡•…‘•Èùí½¹™¥Éµ¥¹%€ôôôÍ•±•Ñ•¹¥€˜˜€ñ‘¥Ø±…ÍÍ9…µ”ô‰±¥‰É…Éäµ‘•±•Ñ”µ½¹™¥É´ˆÉ½±”ô‰…±•ÉĞˆøñÀû–Â’î;šr³–rÃš"C¢ÿ–êO–öKš†¢şg¾šZ®ƒ–ú»’ş‡®¿–ŞËî?–"o–îëj¢6'¢ÿš"[–ŞË–>G–â––ºç’â7’òk¢Š¯–"ƒ¦f“ğ½Àøñ‘¥Øøñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½Üµ¡½ÍĞˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ½¹±¥¬õì ¤€ôøÍ•Ñ½¹™¥Éµ¥¹%¡¹Õ±°¥ôû–>[šÚ ğ½‰ÕÑÑ½¸øñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½Üµ‘…¹•ÈˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ‘¥Í…‰±•õíÁ•¹‘¥¹ô½¹±¥¬õì ¤€ôøì½¹É¡¥Ù”¡Í•±•Ñ•¤ìÍ•Ñ½¹™¥Éµ¥¹%¡¹Õ±°¤ìõôû†»¢º“–öKš†Œğ½‰ÕÑÑ½¸øğ½‘¥Øøğ½‘¥ØùõíÍ•±•Ñ•‘Q¡•µ•%€ü€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰±¥‰É…ÉäµÑ¡•µ•µÁÉ•Ù¥•Üˆ…É¥„µ±…‰•°ô‹–ŞË–êSR£j–³’ò_–>ßš:K&#’âï¦Š`ˆùíÑ¡•µ•AÉ•Ù¥•İ1½…‘¥¹œ€ü€ñ‘¥Ø±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üµ±½…‘¥¹œˆûš¶–r£–êSR£š:K&#š¢‡švÿŠ˜ğ½‘¥Øø€èÑ¡•µ•AÉ•Ù¥•İÉÉ½È€ü€ñ‘¥Ø±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üµ•ÉÉ½Èˆûš¢‡švÿ¦Š¢#–’Ç¢Ò—¾òiíÑ¡•µ•AÉ•Ù¥•İÉÉ½Éôğ½‘¥Øø€è€ñ‘¥Ø±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üµ‰½‘äˆ‘…¹•É½ÕÍ±åM•Ñ%¹¹•É!Q50õíì}}¡Ñµ°èÑ¡•µ•AÉ•Ù¥•İ!Ñµ°õô€¼ùôğ½Í•Ñ¥½¸ø€è€ñÉÑ¥±•	½‘ä…ÉÑ¥±”õíÍ•±•Ñ•‘ô€¼ùôğ½…ÉÑ¥±”ø4(€€€€€€€€ñ…Í¥‘”±…ÍÍ9…µ”ô‰‘•±¥Ù•ÉäµÁ…¹•°ˆøñ Èû’ê“’îc¢ºûö¸ğ½ Èø4(€€€€€€€€€íÍ•±•Ñ•‘Q¡•µ•%€˜˜€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üˆ…É¥„µ±…‰•°ô‹–ú»’ş‡–³’ò_–>ßšZ®ƒš‚ß–ò?¦Š¢ ˆøñ¡•…‘•È±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üµ¡•…‘•ÈˆøñÍÁ…¸ù]!PIQ%1AIY%\ğ½ÍÁ…¸øñÍÑÉ½¹œùíÑ¡•µ•Ì¹™¥¹ ¡Ñ¡•µ”¤€ôøÑ¡•µ”¹¥€ôôôÍ•±•Ñ•‘Q¡•µ•%¤ü¹¹…µ”ñğ€‹–ŞË¦'š¢‡švü‰ôğ½ÍÑÉ½¹œøğ½¡•…‘•ÈùíÑ¡•µ•AÉ•Ù¥•İ1½…‘¥¹œ€ü€ñ‘¥Ø±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üµ±½…‘¥¹œˆûš¶–r£Rš"C–³’ò_–>ßš¶šZ¦Š¢#Š˜ğ½‘¥Øø€èÑ¡•µ•AÉ•Ù¥•İÉÉ½È€ü€ñ‘¥Ø±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üµ•ÉÉ½Èˆû¦Š¢#Rš"C–’Ç¢Ò—¾òiíÑ¡•µ•AÉ•Ù¥•İÉÉ½Éôğ½‘¥Øø€è€ñ‘¥Ø±…ÍÍ9…µ”ô‰İ•¡…ĞµÁÉ•Ù¥•Üµ‰½‘äˆ‘…¹•É½ÕÍ±åM•Ñ%¹¹•É!Q50õíì}}¡Ñµ°èÑ¡•µ•AÉ•Ù¥•İ!Ñµ°õô€¼ùôğ½Í•Ñ¥½¸ùô4(€€€€€€€€€€ñ±…‰•°ûš:K&#š¢‡švüñÍ•±•ĞÙ…±Õ”õíÍ•±•Ñ•‘Q¡•µ•%‘ô½¹¡…¹”õì¡•Ù•¹Ğ¤€ôø½¹Q¡•µ•¡…¹”¡•Ù•¹Ğ¹Ñ…É•Ğ¹Ù…±Õ”¥ôøñ½ÁÑ¥½¸Ù…±Õ”ôˆˆû’â7’öÿR£š¢‡švüğ½½ÁÑ¥½¸ùíÑ¡•µ•Ì¹™¥±Ñ•È ¡Ñ¡•µ”¤€ôøÑ¡•µ”¹•¹…‰±•¤¹µ…À ¡Ñ¡•µ”¤€ôø€ñ½ÁÑ¥½¸­•äõíÑ¡•µ”¹¥‘ôÙ…±Õ”õíÑ¡•µ”¹¥‘ôùíÑ¡•µ”¹¹…µ•ôğ½½ÁÑ¥½¸ø¥ôğ½Í•±•Ğøğ½±…‰•°ø4(€€€€€€€€€€ñ±…‰•°û–ú»’ş‡–³’ò_–>ÜñÍ•±•ĞÙ…±Õ”õíÍ•±•Ñ•‘¡…¹¹•±%‘ô½¹¡…¹”õì¡•Ù•¹Ğ¤€ôø½¹¡…¹¹•±¡…¹”¡•Ù•¹Ğ¹Ñ…É•Ğ¹Ù…±Õ”¥ôøñ½ÁÑ¥½¸Ù…±Õ”ôˆˆû¢¾ß¦'š.§¢Ò›–>Üğ½½ÁÑ¥½¸ùí¡…¹¹•±Ì¹™¥±Ñ•È ¡¡…¹¹•°¤€ôø¡…¹¹•°¹•¹…‰±•¤¹µ…À ¡¡…¹¹•°¤€ôø€ñ½ÁÑ¥½¸­•äõí¡…¹¹•°¹¥‘ôÙ…±Õ”õí¡…¹¹•°¹¥‘ôùí¡…¹¹•°¹¹…µ•ôğ½½ÁÑ¥½¸ø¥ôğ½Í•±•Ğøğ½±…‰•°ø4(€€€€€€€€€€ñ±…‰•°±…ÍÍ9…µ”ô‰½Ù•ÈµÕÁ±½…‘•ÈˆøñÍÁ…¸û–Â¦v‹–nøğ½ÍÁ…¸øñ¥¹ÁÕĞÑåÁ”ô‰™¥±”ˆ…•ÁĞô‰¥µ…”¼¨ˆ½¹¡…¹”õì¡•Ù•¹Ğ¤€ôøì½¹ÍĞ™¥±”€ô•Ù•¹Ğ¹Ñ…É•Ğ¹™¥±•Ìü¹lÁtì¥˜€¡™¥±”¤½¹UÁ±½…¡™¥±”¤ìõô€¼ùí½Ù•ÉAÉ•Ù¥•İUÉ°€ü€ñ¥µœÍÉŒõí½Ù•ÉAÉ•Ù¥•İUÉ±ô…±Ğô‹–Â¦v‹¦Š¢ ˆ€¼ø€è€ñ‘¥Øøñ%½¸¹…µ”ô‰¥µ…”ˆÍ¥é”õìÈÁô€¼û¦'š.§–Â¦vˆğ½‘¥Øùôğ½±…‰•°ø4(€€€€€€€€€í‘•±¥Ù•ÉåÉÉ½È€˜˜€ñ‘¥Ø±…ÍÍ9…µ”ô‰‘•±¥Ù•Éäµ•ÉÉ½ÈˆÉ½±”ô‰…±•ÉĞˆùí‘•±¥Ù•ÉåÉÉ½Éôğ½‘¥Øùô4(€€€€€€€€€€ñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰™±½ÜµÁÉ¥µ…ÉäˆÑåÁ”ô‰‰ÕÑÑ½¸ˆ‘¥Í…‰±•õíÁ•¹‘¥¹œñğ€…Í•±•Ñ•‘¡…¹¹•±%ñğ€…Ñ¡Õµ‰5•‘¥…%ñğÍ•±•Ñ•¹ÍÑ…ÑÕÌ€ôôô€‰ÁÕ‰±¥Í¡•‰ô½¹±¥¬õì ¤€ôø½¹É…™Ğ¡Í•±•Ñ•¥ôùíÍ•±•Ñ•¹ÍÑ…ÑÕÌ€ôôô€‰İ•¡…Ñ}‘É…™Ğˆ€ü€‹¦7šZÃ–g–—–ú»’ş‡¢6'¢üˆ€èÁ•¹‘¥¹œ€ü€‹š¶–r£–g–—Š˜ˆ€è€‹–g–—–ú»’ş‡¢6'¢ü‰ôğ½‰ÕÑÑ½¸ø4(€€€€€€€€€€ñÍµ…±°û–öO–&7šÖ/¢¾W¦bÛšº×–>«–"o–îë¢6'¢ÿ¾ò3’â7’òk¢«–*£š¶–ò?–>G–âğ½Íµ…±°ø4(€€€€€€€€ğ½…Í¥‘”ø4(€€€€€€ğ½Í•Ñ¥½¸ø€è€ñµÁÑåMÑ…Ñ”Ñ¥Ñ±”ô‹š"C¢ÿ–êO¢şcšb¿¦ëjˆ‘•Ñ…¥°ô‹–r£–ú–º‡š‚ã¦†×¦k¢ş’â¾šZ®ƒ–B;¾ò3–º’òk®/–6Ï–ë:Ã–r£¢şg¦3ˆ€¼ùô4(€€€€ğ½µ…¥¸ø4(€€¤ì4)ô4(4