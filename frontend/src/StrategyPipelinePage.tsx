import { useEffect, useMemo, useRef, useState } from "react";

import {
  type ChannelAccount,
  type Job,
  type Model,
  type Skill,
  type MaterialCategory,
  type Strategy,
  type StrategyCombination,
  type StrategyConfig,
  type StrategyPayload,
  type StrategySelectionMode,
  type Theme,
} from "./api";
import { Icon } from "./design";
import { applyWechatAutoPublishTemplate } from "./wechatPublishTemplate";

const TEXT = {
  title: "\u81ea\u52a8\u5316\u751f\u4ea7\u7ebf",
  subtitle: "\u4e00\u6761\u751f\u4ea7\u7ebf\u53ef\u4ee5\u7f16\u6392\u591a\u5957\u5185\u5bb9\u7b56\u7565\u7ec4\u5408\uff0c\u5e76\u6309\u56fa\u5b9a\u6216\u8f6e\u6362\u89c4\u5219\u81ea\u52a8\u9009\u62e9\u3002",
  newPipeline: "\u65b0\u5efa\u751f\u4ea7\u7ebf",
  pipelines: "\u751f\u4ea7\u7ebf",
  pipelineName: "\u751f\u4ea7\u7ebf\u540d\u79f0",
  objective: "\u5185\u5bb9\u76ee\u6807",
  schedule: "\u8fd0\u884c\u9891\u7387",
  manual: "\u624b\u52a8\u6267\u884c",
  hourly: "\u6bcf\u5c0f\u65f6",
  daily: "\u6bcf\u5929",
  dailyAt: "\u56fa\u5b9a\u65f6\u523b\uff08\u5317\u4eac\u65f6\u95f4\uff09",
  dailyAtHelp: "\u6bcf\u5929\u4ec5\u4f1a\u5165\u961f 1 \u6b21\uff1b\u670d\u52a1\u91cd\u542f\u540e\u5f53\u5929\u6700\u591a\u8865\u8dd1 1 \u6b21\u3002",
  selectionMode: "\u81ea\u52a8\u8fd0\u884c\u65b9\u5f0f",
  fixed: "\u59cb\u7ec8\u4f7f\u7528\u9ed8\u8ba4\u7ec4\u5408",
  roundRobin: "\u6bcf\u6b21\u4f9d\u6b21\u8f6e\u6362\u7ec4\u5408",
  selectionModeHelp: "\u56fa\u5b9a\uff1a\u6bcf\u6b21\u90fd\u4f7f\u7528\u9ed8\u8ba4\u7ec4\u5408\u3002\u8f6e\u6362\uff1a\u81ea\u52a8\u4efb\u52a1\u6309\u542f\u7528\u7ec4\u5408\u7684\u987a\u5e8f\u4f9d\u6b21\u4f7f\u7528\uff1b\u8bd5\u8dd1\u5f53\u524d\u7ec4\u5408\u4e0d\u4f1a\u6539\u53d8\u8fd9\u4e2a\u987a\u5e8f\u3002",
  translation: "\u5916\u6587\u7d20\u6750\u7ffb\u8bd1",
  translationHelp: "\u975e\u4e2d\u6587\u7d20\u6750\u5728\u5199\u5165\u7d20\u6750\u5e93\u524d\uff0c\u4f7f\u7528\u5df2\u542f\u7528\u7684\u7ffb\u8bd1\u6a21\u578b\u8bd1\u4e3a\u4e2d\u6587\u5e76\u4fdd\u7559\u539f\u6587\u3002",
  enabled: "\u542f\u7528\u81ea\u52a8\u8c03\u5ea6",
  combinations: "\u7ec4\u5408\u7f16\u6392",
  snapshot: "\u7cfb\u7edf\u6bcf\u6b21\u8fd0\u884c\u90fd\u4f1a\u51bb\u7ed3\u6700\u7ec8\u9009\u62e9\u548c\u914d\u7f6e\u5feb\u7167\u3002",
  addCombination: "\u65b0\u589e\u7ec4\u5408",
  default: "\u9ed8\u8ba4",
  disabled: "\u5df2\u505c\u7528",
  systemDefault: "\u4f7f\u7528\u7cfb\u7edf\u9ed8\u8ba4",
  combinationName: "\u7ec4\u5408\u540d\u79f0",
  materialPool: "\u7d20\u6750\u6c60\u8303\u56f4",
  allCategories: "\u7559\u7a7a\u8868\u793a\u4ece\u7d20\u6750\u6c60\u7684\u5168\u90e8\u542f\u7528\u5206\u7c7b\u4e2d\u81ea\u52a8\u9009\u6750",
  writingSkill: "\u5199\u4f5c Skill",
  writingModel: "\u5199\u4f5c\u6a21\u578b",
  theme: "\u6392\u7248\u6a21\u677f",
  review: "\u4eba\u5de5\u5ba1\u6838\u95e8",
  on: "\u5f00\u542f",
  off: "\u5173\u95ed",
  humanization: "\u81ea\u7136\u5ea6",
  wechatPublishTemplate: "\u5e94\u7528\u516c\u4f17\u53f7\u6b63\u5f0f\u53d1\u5e03\u6a21\u677f",
  remove: "\u5220\u9664\u7ec4\u5408",
  duplicate: "\u590d\u5236\u7ec4\u5408",
  save: "\u4fdd\u5b58\u751f\u4ea7\u7ebf",
  runAuto: "\u4fdd\u5b58\u5e76\u6309\u81ea\u52a8\u89c4\u5219\u8bd5\u8dd1",
  runCurrent: "\u4fdd\u5b58\u5e76\u8bd5\u8dd1\u5f53\u524d\u7ec4\u5408",
  keepOne: "\u81f3\u5c11\u4fdd\u7559\u4e00\u4e2a\u7b56\u7565\u7ec4\u5408",
  enableOne: "\u81f3\u5c11\u542f\u7528\u4e00\u4e2a\u7b56\u7565\u7ec4\u5408",
  unnamed: "\u672a\u547d\u540d\u7ec4\u5408",
  newName: "\u65b0\u751f\u4ea7\u7ebf",
  defaultObjective: "\u56f4\u7ed5\u70ed\u70b9\u4e0e\u7528\u6237\u573a\u666f\u751f\u6210\u9ad8\u8d28\u91cf\u516c\u4f17\u53f7\u5185\u5bb9",
  selectPipeline: "\u9009\u62e9\u4e00\u6761\u751f\u4ea7\u7ebf\u6216\u65b0\u5efa\u751f\u4ea7\u7ebf",
  emptyHelp: "\u5de6\u4fa7\u7ba1\u7406\u81ea\u52a8\u5316\u751f\u4ea7\u7ebf\uff0c\u53f3\u4fa7\u7f16\u6392\u8fd9\u6761\u751f\u4ea7\u7ebf\u53ef\u9009\u62e9\u7684\u5185\u5bb9\u6253\u6cd5\u3002",
  unsaved: "\u5c1a\u672a\u4fdd\u5b58\u7684\u751f\u4ea7\u7ebf\u9700\u5148\u4fdd\u5b58\u540e\u624d\u80fd\u8fd0\u884c",
  combinationEnabled: "\u542f\u7528\u7ec4\u5408",
  copySuffix: "\u526f\u672c",
  all: "\u5168\u90e8",
  saving: "\u4fdd\u5b58\u4e2d...",
  running: "\u8fd0\u884c\u4e2d...",
};

const DAILY_AT_PATTERN = /^daily@(([01]\d|2[0-3]):[0-5]\d)$/;

export function scheduleMode(schedule: string): "manual" | "hourly" | "daily" {
  return schedule === "hourly" ? "hourly" : schedule.startsWith("daily") ? "daily" : "manual";
}

export function dailyTime(schedule: string): string {
  const match = DAILY_AT_PATTERN.exec(schedule);
  return match?.[1] ?? "";
}

export function validatedSchedule(schedule: string): string {
  if (scheduleMode(schedule) === "daily" && !DAILY_AT_PATTERN.test(schedule)) {
    throw new Error("每日运行必须设置固定时刻（HH:MM）。");
  }
  return schedule;
}

type SavePayload = StrategyPayload & { enabled: boolean; config: StrategyConfig };

type Props = {
  strategies: Strategy[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  categories: MaterialCategory[];
  skills: Skill[];
  themes: Theme[];
  models: Model[];
  channels: ChannelAccount[];
  onSave: (id: string | undefined, payload: SavePayload) => Promise<Strategy>;
  onRun: (id: string, combinationId?: string) => Promise<Job>;
  onManageMaterials: () => void;
  onUploadThumb: (file: File, channelId: string) => Promise<string>;
  onImportSkill: (file: File) => Promise<void>;
  importingSkill: boolean;
};

type PipelineDraft = {
  name: string;
  objective: string;
  schedule: string;
  automationLevel: string;
  enabled: boolean;
  selectionMode: StrategySelectionMode;
  defaultCombinationId: string;
  combinations: StrategyCombination[];
};

function id(): string {
  return globalThis.crypto?.randomUUID?.() ?? `combination-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function defaultCombination(categories: MaterialCategory[], skills: Skill[], models: Model[], themes: Theme[], _channels: ChannelAccount[]): StrategyCombination {
  return {
    id: id(),
    name: TEXT.unnamed,
    enabled: true,
    config: {
      material_category_ids: [],
      skill_ids: [],
      model_by_stage: models.find((item) => item.enabled) ? { writing: models.find((item) => item.enabled)!.id } : {},
      theme_id: themes.find((item) => item.enabled)?.id,
      humanization: 75,
      review_rules: { human_review_required: false },
      delivery_mode: "local_draft",
      material_scope: categories.length ? "category" : "all",
    },
  };
}

function strategyBaseConfig(config: StrategyConfig): StrategyConfig {
  const base = { ...config };
  delete base.selection_mode;
  delete base.default_combination_id;
  delete base.strategy_combinations;
  return base;
}

export function mergeCombinationConfig(base: StrategyConfig, override: StrategyConfig): StrategyConfig {
  return {
    ...base,
    ...override,
    model_by_stage: { ...(base.model_by_stage ?? {}), ...(override.model_by_stage ?? {}) },
    skill_by_stage: { ...(base.skill_by_stage ?? {}), ...(override.skill_by_stage ?? {}) },
    review_rules: { ...(base.review_rules ?? {}), ...(override.review_rules ?? {}) },
  };
}
function CategorySelector({ categories, value, onChange }: { categories: MaterialCategory[]; value: string[]; onChange: (ids: string[]) => void }) {
  const enabledCategories = categories.filter((category) => category.enabled);
  const selected = value.filter((id) => enabledCategories.some((category) => category.id === id));
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);
  return <details className="source-selector">
    <summary><span>{selected.length ? `已选择 ${selected.length} 个素材分类` : "全部启用的素材分类"}</span><small>点击选择</small></summary>
    <div className="source-selector-menu">
      <label className="source-selector-all"><input type="checkbox" checked={!selected.length} onChange={() => onChange([])} />使用素材池全部启用分类</label>
      {enabledCategories.map((category) => <label key={category.id}><input type="checkbox" checked={selected.includes(category.id)} onChange={() => toggle(category.id)} />{category.name}<small>{category.material_count} 条</small></label>)}
    </div>
  </details>;
}

function initialDraft(strategy: Strategy | null, categories: MaterialCategory[], skills: Skill[], models: Model[], themes: Theme[], channels: ChannelAccount[]): PipelineDraft {
  if (!strategy) {
    const combination = defaultCombination(categories, skills, models, themes, channels);
    return {
      name: TEXT.newName,
      objective: TEXT.defaultObjective,
      schedule: "manual",
      automationLevel: "L2",
      enabled: false,
      selectionMode: "fixed",
      defaultCombinationId: combination.id,
      combinations: [combination],
    };
  }
  const baseConfig = strategyBaseConfig(strategy.config);
  const configured = strategy.config.strategy_combinations?.filter((item) => item && typeof item.id === "string") ?? [];
  const combinations = configured.length
    ? configured.map((item) => ({ ...item, config: mergeCombinationConfig(baseConfig, item.config) }))
    : [{ id: "default", name: strategy.name, enabled: true, config: baseConfig }];
  const enabledDefault = combinations.find((item) => item.enabled)?.id ?? combinations[0].id;
  return {
    name: strategy.name,
    objective: strategy.objective,
    schedule: strategy.schedule,
    automationLevel: strategy.automation_level,
    enabled: strategy.enabled ?? false,
    selectionMode: strategy.config.selection_mode ?? "fixed",
    defaultCombinationId: strategy.config.default_combination_id ?? enabledDefault,
    combinations,
  };
}

function stripCombinationFields(config: StrategyConfig): StrategyConfig {
  const copy = { ...config };
  for (const key of ["source_ids", "material_category_ids", "skill_ids", "skill_by_stage", "model_by_stage", "theme_id", "humanization", "review_rules", "delivery_mode", "channel_account_id", "wechat_thumb_media_id", "source_mode", "material_ids", "topic_algorithm", "selection_mode", "default_combination_id", "strategy_combinations"]) {
    delete copy[key];
  }
  return copy;
}

export function sanitizeCombinationConfig(config: StrategyConfig): StrategyConfig {
  const copy = { ...config };
  delete copy.topic_algorithm;
  if ((copy.delivery_mode ?? "local_draft") === "local_draft") {
    delete copy.channel_account_id;
    delete copy.wechat_thumb_media_id;
  }
  return copy;
}

export function StrategyPipelinePage(props: Props) {
  const current = props.strategies.find((item) => item.id === props.selectedId) ?? null;
  const [draft, setDraft] = useState(() => initialDraft(current, props.categories, props.skills, props.models, props.themes, props.channels));
  const [activeCombinationId, setActiveCombinationId] = useState(draft.combinations[0]?.id ?? "");
  const [busy, setBusy] = useState<"save" | "auto" | "current" | null>(null);
  const [error, setError] = useState("");
  const skillFileRef = useRef<HTMLInputElement | null>(null);
  const thumbFileRef = useRef<HTMLInputElement | null>(null);
  const [thumbUploading, setThumbUploading] = useState(false);

  useEffect(() => {
    const next = initialDraft(current, props.categories, props.skills, props.models, props.themes, props.channels);
    setDraft(next);
    setActiveCombinationId(next.defaultCombinationId || next.combinations[0]?.id || "");
    setError("");
  }, [current?.id, current?.version, props.selectedId]);

  const active = draft.combinations.find((item) => item.id === activeCombinationId) ?? draft.combinations[0];
  const enabledSkills = props.skills.filter((item) => item.status === "published");
  const enabledModels = props.models.filter((item) => item.enabled);
  const enabledThemes = props.themes.filter((item) => item.enabled);
  const enabledChannels = props.channels.filter((item) => item.enabled);
  const enabledCount = draft.combinations.filter((item) => item.enabled).length;
  const resourceNames = useMemo(() => ({
    skills: new Map(props.skills.map((item) => [item.id, item.name])),
    models: new Map(props.models.map((item) => [item.id, item.name])),
    themes: new Map(props.themes.map((item) => [item.id, item.name])),
    channels: new Map(props.channels.map((item) => [item.id, item.name])),
  }), [props.channels, props.models, props.skills, props.themes]);

  const updateActive = (update: (item: StrategyCombination) => StrategyCombination) => {
    setDraft((value) => ({ ...value, combinations: value.combinations.map((item) => item.id === active.id ? update(item) : item) }));
  };

  const addCombination = () => {
    const combination = defaultCombination(props.categories, props.skills, props.models, props.themes, props.channels);
    setDraft((value) => ({ ...value, combinations: [...value.combinations, combination] }));
    setActiveCombinationId(combination.id);
  };

  const duplicateCombination = () => {
    if (!active) return;
    const duplicate = { ...active, id: id(), name: `${active.name} ${TEXT.copySuffix}`, config: { ...active.config } };
    setDraft((value) => ({ ...value, combinations: [...value.combinations, duplicate] }));
    setActiveCombinationId(duplicate.id);
  };

  const removeCombination = () => {
    if (!active || draft.combinations.length === 1) {
      setError(TEXT.keepOne);
      return;
    }
    const remaining = draft.combinations.filter((item) => item.id !== active.id);
    const nextDefault = remaining.some((item) => item.id === draft.defaultCombinationId && item.enabled)
      ? draft.defaultCombinationId
      : remaining.find((item) => item.enabled)?.id ?? remaining[0].id;
    setDraft((value) => ({ ...value, combinations: remaining, defaultCombinationId: nextDefault }));
    setActiveCombinationId(remaining[0].id);
  };

  const setActiveEnabled = (enabled: boolean) => {
    if (!active) return;
    setDraft((value) => {
      const combinations = value.combinations.map((item) => item.id === active.id ? { ...item, enabled } : item);
      const defaultCombinationId = !enabled && value.defaultCombinationId === active.id
        ? combinations.find((item) => item.enabled)?.id ?? value.defaultCombinationId
        : value.defaultCombinationId;
      return { ...value, combinations, defaultCombinationId };
    });
  };

  const payload = (): SavePayload => {
    if (!draft.combinations.length) throw new Error(TEXT.keepOne);
    if (!draft.combinations.some((item) => item.enabled)) throw new Error(TEXT.enableOne);
    const defaultId = draft.combinations.some((item) => item.id === draft.defaultCombinationId && item.enabled)
      ? draft.defaultCombinationId
      : draft.combinations.find((item) => item.enabled)!.id;
    return {
      name: draft.name.trim() || TEXT.newName,
      objective: draft.objective.trim() || TEXT.defaultObjective,
      schedule: validatedSchedule(draft.schedule),
      automation_level: draft.automationLevel,
      enabled: draft.enabled,
      config: {
        ...stripCombinationFields(current?.config ?? {}),
        selection_mode: draft.selectionMode,
        default_combination_id: defaultId,
        strategy_combinations: draft.combinations.map((item) => ({
          ...item,
          name: item.name.trim() || TEXT.unnamed,
          config: sanitizeCombinationConfig(item.config),
        })),
      },
    };
  };

  const uploadThumb = async (file: File) => {
    const channelId = active?.config.channel_account_id;
    if (!channelId) {
      setError("请先选择微信公众号账号！");
      return;
    }
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      setError("封面只支持 JPG 或 PNG 图片");
      return;
    }
    setError("");
    setThumbUploading(true);
    try {
      const mediaId = await props.onUploadThumb(file, channelId);
      updateActive((item) => ({ ...item, config: { ...item.config, wechat_thumb_media_id: mediaId } }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "封面上传失败");
    } finally {
      setThumbUploading(false);
    }
  };

  const save = async (run: "auto" | "current" | null = null) => {
    setError("");
    setBusy(run ?? "save");
    try {
      const saved = await props.onSave(current?.id, payload());
      if (run) await props.onRun(saved.id, run === "current" ? active?.id : undefined);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : TEXT.unsaved);
    } finally {
      setBusy(null);
    }
  };

  return <main className="figma-page pipeline-page">
    <div className="figma-page-heading strategy-heading">
      <div><h1><span className="title-icon"><Icon name="settings" size={22} /></span>{TEXT.title}</h1><p>{TEXT.subtitle}</p></div>
      <button className="strategy-source-link" type="button" onClick={props.onManageMaterials}><Icon name="database" size={16} />{TEXT.materialPool}<span>{props.categories.filter((item) => item.enabled).length}</span></button>
      <button className="strategy-source-link" type="button" disabled={props.importingSkill} onClick={() => skillFileRef.current?.click()}>{props.importingSkill ? "导入中…" : "导入 Skill（ZIP）"}</button>
      <input ref={skillFileRef} type="file" accept=".zip,application/zip" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) void props.onImportSkill(file); event.target.value = ""; }} />
    </div>
    <section className="pipeline-layout">
      <aside className="pipeline-list-panel">
        <div className="strategy-list-head"><h2>{TEXT.pipelines}<small> ({props.strategies.length})</small></h2><button className="figma-link-button" type="button" onClick={props.onNew}>+ {TEXT.newPipeline}</button></div>
        <div className="pipeline-list">
          {props.strategies.map((strategy) => {
            const count = strategy.config.strategy_combinations?.length ?? 1;
            return <button key={strategy.id} type="button" className={`pipeline-list-item ${strategy.id === props.selectedId ? "is-selected" : ""}`} onClick={() => props.onSelect(strategy.id)}>
              <span><strong>{strategy.name}</strong><i className={strategy.enabled ? "is-on" : ""} /></span>
              <small>{count} {TEXT.combinations}{" \u00b7 "}{strategy.config.selection_mode === "round_robin" ? TEXT.roundRobin : TEXT.fixed}</small>
            </button>;
          })}
          {!props.strategies.length && <div className="strategy-empty-hint">{TEXT.emptyHelp}</div>}
        </div>
      </aside>
      <div className="pipeline-editor">
        <section className="strategy-section pipeline-meta">
          <div className="strategy-meta-grid">
            <label className="strategy-meta-field"><small>{TEXT.pipelineName}</small><input value={draft.name} onChange={(event) => setDraft((value) => ({ ...value, name: event.target.value }))} /></label>
            <label className="strategy-meta-field"><small>{TEXT.objective}</small><input value={draft.objective} onChange={(event) => setDraft((value) => ({ ...value, objective: event.target.value }))} /></label>
            <label className="strategy-meta-field"><small>{TEXT.schedule}</small><select value={scheduleMode(draft.schedule)} onChange={(event) => setDraft((value) => ({ ...value, schedule: event.target.value === "daily" ? (DAILY_AT_PATTERN.test(value.schedule) ? value.schedule : "daily@") : event.target.value }))}><option value="manual">{TEXT.manual}</option><option value="hourly">{TEXT.hourly}</option><option value="daily">{TEXT.daily}</option></select></label>
            {scheduleMode(draft.schedule) === "daily" && <label className="strategy-meta-field"><small>{TEXT.dailyAt}</small><input type="time" value={dailyTime(draft.schedule)} onChange={(event) => setDraft((value) => ({ ...value, schedule: `daily@${event.target.value}` }))} required /><span>{TEXT.dailyAtHelp}</span></label>}
            <label className="strategy-meta-field"><small>{TEXT.selectionMode}</small><select value={draft.selectionMode} onChange={(event) => setDraft((value) => ({ ...value, selectionMode: event.target.value as StrategySelectionMode }))}><option value="fixed">{TEXT.fixed}</option><option value="round_robin">{TEXT.roundRobin}</option></select><span>{TEXT.selectionModeHelp}</span></label>
          </div>
          <label className="strategy-enabled-toggle"><input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft((value) => ({ ...value, enabled: event.target.checked }))} />{TEXT.enabled}</label>
        </section>
        <section className="strategy-section pipeline-combinations">
          <div className="pipeline-section-head"><div><h2>{TEXT.combinations}</h2><p>{TEXT.snapshot}</p></div><button className="figma-link-button" type="button" onClick={addCombination}>+ {TEXT.addCombination}</button></div>
          <div className="combination-tabs">
            {draft.combinations.map((item) => <button key={item.id} type="button" className={item.id === active?.id ? "is-active" : ""} onClick={() => setActiveCombinationId(item.id)}><span>{item.name || TEXT.unnamed}</span>{item.id === draft.defaultCombinationId && <b>{TEXT.default}</b>}{!item.enabled && <em>{TEXT.disabled}</em>}</button>)}
          </div>
          {active && <div className="combination-editor">
            <div className="combination-toolbar">
              <label className="combination-name"><small>{TEXT.combinationName}</small><input maxLength={100} value={active.name} onChange={(event) => updateActive((item) => ({ ...item, name: event.target.value }))} /></label>
              <label className="strategy-enabled-toggle"><input type="checkbox" checked={active.enabled} disabled={active.enabled && enabledCount === 1} onChange={(event) => setActiveEnabled(event.target.checked)} />{TEXT.combinationEnabled}</label>
              <button type="button" className={`combination-default ${active.id === draft.defaultCombinationId ? "is-default" : ""}`} disabled={!active.enabled} onClick={() => setDraft((value) => ({ ...value, defaultCombinationId: active.id }))}>{TEXT.default}</button>
              <button type="button" onClick={() => updateActive((item) => ({ ...item, config: applyWechatAutoPublishTemplate(item.config) }))}>{TEXT.wechatPublishTemplate}</button>
            </div>
            <div className="combination-fields">
              <label><small>{TEXT.materialPool}</small><CategorySelector categories={props.categories} value={active.config.material_category_ids ?? []} onChange={(categoryIds) => updateActive((item) => ({ ...item, config: { ...item.config, material_category_ids: categoryIds } }))} /><span>{TEXT.allCategories}</span></label>
              <label><small>{TEXT.writingSkill}</small><select value={(active.config.skill_by_stage ?? {}).writing ?? active.config.skill_ids?.[0] ?? ""} onChange={(event) => updateActive((item) => {
                const skillByStage = { ...(item.config.skill_by_stage ?? {}) };
                if (event.target.value) skillByStage.writing = event.target.value;
                else delete skillByStage.writing;
                return { ...item, config: { ...item.config, skill_ids: [], skill_by_stage: skillByStage } };
              })}><option value="">通用写作（不套用 Skill）</option>{enabledSkills.map((item) => <option key={item.id} value={item.id}>{item.name}{" \u00b7 v"}{item.version}</option>)}</select></label>
              <label><small>{TEXT.writingModel}</small><select value={(active.config.model_by_stage ?? {}).writing ?? ""} onChange={(event) => updateActive((item) => {
                const modelByStage = { ...(item.config.model_by_stage ?? {}) };
                if (event.target.value) modelByStage.writing = event.target.value;
                else delete modelByStage.writing;
                return { ...item, config: { ...item.config, model_by_stage: modelByStage } };
              })}><option value="">{TEXT.systemDefault}</option>{enabledModels.map((item) => <option key={item.id} value={item.id}>{item.provider} / {item.name}</option>)}</select></label>
              <label className="combination-review"><small>{TEXT.translation}</small><button type="button" className={active.config.translate_foreign_sources !== false ? "is-on" : ""} onClick={() => updateActive((item) => ({ ...item, config: { ...item.config, translate_foreign_sources: item.config.translate_foreign_sources === false } }))}>{active.config.translate_foreign_sources !== false ? TEXT.on : TEXT.off}</button><span>{TEXT.translationHelp}</span></label><label><small>{TEXT.theme}</small><select value={active.config.theme_id ?? ""} onChange={(event) => updateActive((item) => ({ ...item, config: { ...item.config, theme_id: event.target.value || undefined } }))}><option value="">{TEXT.disabled}</option>{enabledThemes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label className="combination-review"><small>{TEXT.review}</small><button type="button" disabled={active.config.delivery_mode === "auto_publish"} className={(active.config.review_rules?.human_review_required ?? false) ? "is-on" : ""} onClick={() => updateActive((item) => ({ ...item, config: { ...item.config, review_rules: { ...(item.config.review_rules ?? {}), human_review_required: !(item.config.review_rules?.human_review_required ?? false) } } }))}>{(active.config.review_rules?.human_review_required ?? false) ? TEXT.on : TEXT.off}</button><span>{active.config.delivery_mode === "auto_publish" ? "AI 审核须通过 75 分且联网事实核验完整；否则进入人工审核" : "默认关闭；开启后文章必须由你通过后才能交付"}</span></label>
              <label><small>交付模式</small><select value={active.config.delivery_mode ?? "local_draft"} onChange={(event) => updateActive((item) => { const deliveryMode = event.target.value as "local_draft" | "wechat_draft" | "auto_publish"; return { ...item, config: { ...item.config, delivery_mode: deliveryMode, review_rules: { ...(item.config.review_rules ?? {}), human_review_required: deliveryMode === "auto_publish" ? false : (item.config.review_rules?.human_review_required ?? false) } } }; })}><option value="local_draft">本地成稿（不调用微信）</option><option value="wechat_draft">微信草稿测试</option><option value="auto_publish">自动正式发布</option></select><span>{active.config.delivery_mode === "auto_publish" ? "会先创建草稿；默认开启评论；只有服务器全局发布开关开启且账号有权限时才提交正式发布" : active.config.delivery_mode === "wechat_draft" ? "自动写入微信草稿，不会正式发布" : "生成后进入本系统成稿库"}</span></label>
              {(active.config.delivery_mode === "wechat_draft" || active.config.delivery_mode === "auto_publish") && <><label><small>微信公众号</small><select value={active.config.channel_account_id ?? ""} onChange={(event) => updateActive((item) => ({ ...item, config: { ...item.config, channel_account_id: event.target.value || undefined, wechat_thumb_media_id: event.target.value === item.config.channel_account_id ? item.config.wechat_thumb_media_id : undefined } }))}><option value="">请选择账号</option>{enabledChannels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}{channel.capabilities.publish ? " · 可发布" : " · 仅草稿"}</option>)}</select></label><label><small>默认封面素材 ID</small><input value={active.config.wechat_thumb_media_id ?? ""} onChange={(event) => updateActive((item) => ({ ...item, config: { ...item.config, wechat_thumb_media_id: event.target.value.trim() || undefined } }))} placeholder="微信永久素材 media_id" /><button type="button" className="flow-secondary" disabled={!active.config.channel_account_id || thumbUploading} onClick={() => thumbFileRef.current?.click()}>{thumbUploading ? "上传中…" : "上传 JPG/PNG 封面"}</button><span>{active.config.wechat_thumb_media_id ? "封面已上传并回填 media_id" : "自动交付必须使用已经上传到该公众号的永久封面素材"}</span></label><input ref={thumbFileRef} type="file" accept="image/jpeg,image/png" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadThumb(file); event.target.value = ""; }} /></>}
              <label className="combination-range"><small>{TEXT.humanization} <b>{Number(active.config.humanization ?? 75)}%</b></small><input type="range" min="0" max="100" value={Number(active.config.humanization ?? 75)} onChange={(event) => updateActive((item) => ({ ...item, config: { ...item.config, humanization: Number(event.target.value) } }))} /></label>
            </div>
            <div className="combination-summary"><span><Icon name="database" size={15} />{active.config.material_category_ids?.length || TEXT.all}</span><b>{"\u2192"}</b><span><Icon name="magic" size={15} />{resourceNames.skills.get((active.config.skill_by_stage ?? {}).writing ?? active.config.skill_ids?.[0] ?? "") ?? TEXT.default}</span><b>{"\u2192"}</b><span><Icon name="robot" size={15} />{resourceNames.models.get((active.config.model_by_stage ?? {}).writing ?? "") ?? TEXT.default}</span><b>{"\u2192"}</b><span><Icon name="image" size={15} />{resourceNames.themes.get(active.config.theme_id ?? "") ?? TEXT.default}</span><b>{"→"}</b><span><Icon name="mail" size={15} />{active.config.delivery_mode === "auto_publish" ? "自动发布" : active.config.delivery_mode === "wechat_draft" ? (resourceNames.channels.get(active.config.channel_account_id ?? "") ?? "微信草稿") : "本地成稿"}</span></div>
            <div className="combination-actions"><button type="button" onClick={duplicateCombination}>{TEXT.duplicate}</button><button type="button" className="danger" onClick={removeCombination}>{TEXT.remove}</button></div>
          </div>}
        </section>
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="pipeline-save-bar">
          <button type="button" disabled={busy !== null} onClick={() => void save()}>{busy === "save" ? TEXT.saving : TEXT.save}</button>
          <button type="button" disabled={busy !== null} onClick={() => void save("auto")}>{busy === "auto" ? TEXT.running : TEXT.runAuto}</button>
          <button type="button" className="primary" disabled={busy !== null || !active?.enabled} onClick={() => void save("current")}>{busy === "current" ? TEXT.running : TEXT.runCurrent}</button>
        </div>
      </div>
    </section>
  </main>;
}
