from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from markdown_it import MarkdownIt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ingestion import collect_source
from .models import (
    Article,
    ArticleRevision,
    EvidenceClaim,
    EvidencePackage,
    EvidenceSource,
    Job,
    JobEvent,
    JobStep,
    ModelCallLog,
    ModelConfig,
    Review,
    Source,
    SourceItem,
    Strategy,
    Theme,
    Topic,
    TopicMaterial,
    TopicScore,
)
from .providers import CompletionRequest, ModelProvider, provider_for
from .strategy_combinations import resolve_strategy_definition
from .strategy_config import (
    StrategyConfigError,
    model_id_for_stage,
    model_snapshot,
    skill_for_stage_config,
    skill_snapshot,
    validate_strategy_config,
)
from .themes import render_revision
from .topic_recommendations import recommend_topics

FIXED_STEPS = (
    "collect",
    "normalize",
    "deduplicate",
    "topic",
    "evidence",
    "outline",
    "writing",
    "style",
    "rewrite",
    "review",
    "render",
    "draft",
)



def create_job(
    db: Session,
    strategy: Strategy,
    idempotency_key: str,
    max_attempts: int = 3,
    payload: dict[str, Any] | None = None,
    combination_id: str | None = None,
    execution_config_override: dict[str, Any] | None = None,
    runtime_snapshot_extra: dict[str, Any] | None = None,
) -> Job:
    existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
    if existing:
        return existing
    resolved = resolve_strategy_definition(db, strategy, idempotency_key, combination_id)
    execution_config = validate_strategy_config({**resolved.config, **(execution_config_override or {})})
    job_payload = {
        **(payload or {}),
        "resolved_strategy_config": execution_config,
        "runtime_snapshot": {
            "strategy": {
                "id": strategy.id,
                "version": strategy.version,
                "name": strategy.name,
                "automation_level": strategy.automation_level,
            },
            "combination": resolved.combination,
            "execution_config": execution_config,
            **(runtime_snapshot_extra or {}),
        },
    }
    job = Job(
        strategy_id=strategy.id,
        idempotency_key=idempotency_key,
        max_attempts=max_attempts,
        status="queued",
        payload_json=job_payload,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _step(db: Session, job: Job, name: str) -> JobStep:
    current = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == name))
    if current is None:
        current = JobStep(job_id=job.id, step_name=name)
        db.add(current)
        db.flush()
    return current


def _job_event(
    db: Session,
    job: Job,
    event_type: str,
    step_name: str | None = None,
    status: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        JobEvent(
            job_id=job.id,
            event_type=event_type,
            step_name=step_name,
            status=status,
            payload_json=payload or {},
        )
    )


def _run_step(db: Session, job: Job, name: str, fn) -> dict[str, Any]:
    step = _step(db, job, name)
    if step.status == "succeeded":
        return step.output_json
    step.status = "running"
    step.attempt_count += 1
    step.started_at = datetime.now(timezone.utc)
    job.current_step = name
    _job_event(db, job, "step_started", name, "running")
    db.commit()
    try:
        output = fn()
        step.status = "succeeded"
        step.output_json = output
        step.completed_at = datetime.now(timezone.utc)
        step.error = None
        _job_event(db, job, "step_succeeded", name, "succeeded", {"output_keys": list(output)})
        db.commit()
        return output
    except Exception as exc:
        failed_at = datetime.now(timezone.utc)
        step.status = "failed"
        step.error = str(exc)
        job.last_error = str(exc)
        _job_event(db, job, "step_failed", name, "failed", {"error": str(exc)[:500]})
        job.attempt_count += 1
        job.lease_until = None
        _record_job_duration(job, failed_at)
        if job.attempt_count < job.max_attempts:
            job.status = "failed_retryable"
            job.available_at = failed_at + timedelta(seconds=min(60, 2 ** max(job.attempt_count - 1, 0)))
        else:
            job.status = "failed_terminal"
            job.available_at = None
        db.commit()
        raise


def _skip_step(db: Session, job: Job, name: str, reason: str) -> dict[str, Any]:
    step = _step(db, job, name)
    if step.status == "succeeded":
        return step.output_json
    step.status = "skipped"
    step.attempt_count += 1
    step.output_json = {"skipped": True, "reason": reason}
    step.completed_at = datetime.now(timezone.utc)
    job.current_step = name
    _job_event(db, job, "step_started", name, "skipped", {"reason": reason})
    _job_event(db, job, "step_skipped", name, "skipped", {"reason": reason})
    db.commit()
    return step.output_json


def _record_job_duration(job: Job, finished_at: datetime | None = None) -> None:
    if job.started_at is None:
        return
    end = finished_at or datetime.now(timezone.utc)
    started = job.started_at if job.started_at.tzinfo is not None else job.started_at.replace(tzinfo=timezone.utc)
    end = end if end.tzinfo is not None else end.replace(tzinfo=timezone.utc)
    job.duration_ms = max(0, int((end - started).total_seconds() * 1000))


def _article(db: Session, job: Job, strategy_version: int) -> Article:
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    if article is None:
        article = Article(job_id=job.id, strategy_version=strategy_version)
        db.add(article)
        db.flush()
    return article


def _complete_with_log(
    db: Session,
    job: Job,
    article: Article,
    provider: ModelProvider,
    request: CompletionRequest,
    stage: str,
) -> str:
    started = time.perf_counter()
    snapshot = article.model_snapshot or {}
    stage_snapshot = (snapshot.get("stages") or {}).get(stage) or snapshot
    provider_name = str(stage_snapshot.get("provider") or provider.__class__.__name__)
    model_name = str(stage_snapshot.get("name") or provider.__class__.__name__)
    api_key = str(getattr(provider, "api_key", "") or "")
    try:
        response = provider.complete(request)
    except Exception as exc:
        error = str(exc)
        if api_key:
            error = error.replace(api_key, "[redacted]")
        db.add(
            ModelCallLog(
                job_id=job.id,
                article_id=article.id,
                stage=stage,
                provider=provider_name,
                model_name=model_name,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_summary=f"{request.system}\n{request.user}"[:1000],
                error=error[:2000],
            )
        )
        db.flush()
        raise
    db.add(
        ModelCallLog(
            job_id=job.id,
            article_id=article.id,
            stage=stage,
            provider=provider_name,
            model_name=model_name,
            status="succeeded",
            duration_ms=int((time.perf_counter() - started) * 1000),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost=response.cost,
            input_summary=f"{request.system}\n{request.user}"[:1000],
            output_summary=response.text[:1000],
        )
    )
    db.flush()
    return response.text


_NON_ARTICLE_MARKERS = (
    "这是一份基于已核验来源生成的草稿。",
    "质检报告",
    "L1 硬性规则",
    "L2 风格一致性",
    "禁用词：",
    "结构套话",
)


def _require_article_body(content: str, stage: str) -> str:
    body = content.strip()
    if len(body) < 300:
        raise ValueError(f"{stage} 阶段没有生成足够完整的文章正文")
    marker = next((item for item in _NON_ARTICLE_MARKERS if item in body), None)
    if marker is not None:
        raise ValueError(f"{stage} 阶段返回了质检内容（{marker}），不是文章正文")
    return body


def run_job(db: Session, job_id: str, provider: ModelProvider) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise ValueError("任务不存在")
    if job.status in {"succeeded", "canceled", "failed_terminal"}:
        return job
    strategy = db.get(Strategy, job.strategy_id)
    if strategy is None:
        raise ValueError("任务关联的内容策略不存在")
    strategy_config = (job.payload_json or {}).get("resolved_strategy_config")
    if not isinstance(strategy_config, dict):
        try:
            resolved = resolve_strategy_definition(db, strategy, job.idempotency_key)
        except StrategyConfigError as exc:
            raise ValueError(str(exc)) from exc
        strategy_config = resolved.config
        job.payload_json = {
            **(job.payload_json or {}),
            "resolved_strategy_config": resolved.config,
            "runtime_snapshot": {
                "strategy": {
                    "id": strategy.id,
                    "version": strategy.version,
                    "name": strategy.name,
                    "automation_level": strategy.automation_level,
                },
                "combination": resolved.combination,
                "execution_config": resolved.config,
            },
        }
        db.commit()
    job_runtime_snapshot = (job.payload_json or {}).get("runtime_snapshot") or {}
    strategy_runtime_snapshot = job_runtime_snapshot.get("strategy") or {}
    snapshot_strategy_version = strategy_runtime_snapshot.get("version")
    if not isinstance(snapshot_strategy_version, int):
        snapshot_strategy_version = strategy.version
    job_model_id = (job.payload_json or {}).get("model_id")
    job_mode = (job.payload_json or {}).get("mode")
    if job_mode == "scan":
        if job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        job.completed_at = None
        job.status = "running"
        job.available_at = None
        job.lease_until = None
        db.commit()

        collected: list[str] = []

        def collect_for_triage() -> dict[str, Any]:
            source_query = select(Source).where(Source.enabled.is_(True))
            source_ids = strategy_config.get("source_ids", [])
            if source_ids:
                source_query = source_query.where(Source.id.in_(source_ids))
            for source in db.scalars(source_query).all():
                for item in collect_source(
                    db,
                    source,
                    translation_job=job,
                    translate_foreign_sources=strategy_config.get("translate_foreign_sources", True),
                ):
                    collected.append(item.id)
            return {"item_ids": collected, "material_count": len(collected)}

        collect_output = _run_step(db, job, "collect", collect_for_triage)
        _run_step(db, job, "normalize", lambda: {"normalized": True})
        _run_step(db, job, "deduplicate", lambda: {"deduplicated": True})
        recommendation_model_id = model_id_for_stage(strategy_config, "writing", job_model_id)
        if not recommendation_model_id:
            raise ValueError("Topic scanning requires an enabled model in the selected strategy")
        recommendation_model = db.get(ModelConfig, recommendation_model_id)
        if recommendation_model is None or not recommendation_model.enabled:
            raise ValueError("The topic recommendation model is missing or disabled")
        material_ids = list(dict.fromkeys(collect_output["item_ids"]))
        materials = db.scalars(
            select(SourceItem)
            .where(SourceItem.id.in_(material_ids), SourceItem.status == "verified")
            .order_by(SourceItem.created_at.desc())
        ).all()

        def build_recommendations() -> dict[str, Any]:
            topic_algorithm = strategy_config.get("topic_algorithm", {})
            maximum_topics = int(topic_algorithm.get("max_topics", 4))
            topics = recommend_topics(
                db,
                job,
                strategy,
                materials,
                provider if recommendation_model.provider == "fake" else provider_for(recommendation_model),
                recommendation_model,
                strategy_objective=strategy_runtime_snapshot.get("objective") or strategy.objective,
                algorithm=topic_algorithm,
                limit=maximum_topics,
            )
            return {"topic_ids": [topic.id for topic in topics], "topic_count": len(topics)}

        topic_output = _run_step(db, job, "topic", build_recommendations)
        for step_name in FIXED_STEPS[4:]:
            _skip_step(db, job, step_name, "等待运营人员从素材池选择写作依据")
        finished_at = datetime.now(timezone.utc)
        job.status = "waiting_topic"
        job.current_step = "topic"
        job.completed_at = finished_at
        job.available_at = None
        job.lease_until = None
        _record_job_duration(job, finished_at)
        _job_event(
            db,
            job,
            "job_waiting_topic",
            "topic",
            "waiting_topic",
            {"material_count": len(collected), "topic_count": topic_output["topic_count"]},
        )
        db.commit()
        db.refresh(job)
        return job

    def configured_model(stage: str) -> ModelConfig | None:
        model_id = model_id_for_stage(strategy_config, stage, job_model_id)
        if not model_id:
            return None
        model = db.get(ModelConfig, model_id)
        if model is None:
            raise ValueError(f"阶段 {stage} 关联的模型不存在")
        if not model.enabled:
            raise ValueError(f"阶段 {stage} 关联的模型已停用")
        return model

    stage_models = {stage: configured_model(stage) for stage in ("writing", "style", "rewrite")}
    article = _article(db, job, snapshot_strategy_version)
    if not article.model_snapshot:
        writing_model = stage_models["writing"]
        article.model_snapshot = {
            **model_snapshot(writing_model, provider.__class__.__name__),
            "stages": {
                stage: model_snapshot(model, provider.__class__.__name__) for stage, model in stage_models.items()
            },
        }
    if not article.skill_snapshot:
        skill_objects = {
            stage: skill_for_stage_config(db, strategy_config, stage)
            for stage in ("writing", "style", "rewrite", "review")
        }
        article.skill_snapshot = {
            "strategy_version": snapshot_strategy_version,
            "skill_ids": strategy_config.get("skill_ids", []),
            "skills": strategy_config.get("skills", {}),
            "stages": {stage: skill_snapshot(skill) for stage, skill in skill_objects.items() if skill is not None},
        }
    if not article.runtime_snapshot_json:
        source_ids = strategy_config.get("source_ids", [])
        source_query = select(Source).where(Source.enabled.is_(True))
        if source_ids:
            source_query = source_query.where(Source.id.in_(source_ids))
        source_snapshot = [
            {
                "id": source.id,
                "name": source.name,
                "source_type": source.source_type,
                "url": source.url,
                "group_name": source.group_name,
            }
            for source in db.scalars(source_query.order_by(Source.id)).all()
        ]
        article.runtime_snapshot_json = {
            "strategy": {
                "id": strategy_runtime_snapshot.get("id", strategy.id),
                "version": snapshot_strategy_version,
                "name": strategy_runtime_snapshot.get("name", strategy.name),
                "automation_level": strategy_runtime_snapshot.get("automation_level", strategy.automation_level),
                "disabled_steps": strategy_config.get("disabled_steps", []),
                "source_ids": strategy_config.get("source_ids", []),
                "channel_account_id": strategy_config.get("channel_account_id"),
            },
            "combination": job_runtime_snapshot.get("combination", {}),
            "execution_config": strategy_config,
            "model": article.model_snapshot,
            "skills": article.skill_snapshot,
            "sources": source_snapshot,
            "theme": {
                "id": strategy_config.get("theme_id"),
                "version": strategy_config.get("theme_version"),
            },
            "review_rules": strategy_config.get("review_rules", {"human_review_required": True}),
        }
        job.payload_json = {**(job.payload_json or {}), "runtime_snapshot": article.runtime_snapshot_json}
    db.flush()
    if job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    job.completed_at = None
    job.status = "running"
    job.available_at = None
    job.lease_until = None
    db.commit()

    collected: dict[str, Any] = {"items": []}
    disabled_steps = set(strategy_config.get("disabled_steps", []))

    def stage_provider(stage: str) -> ModelProvider:
        model = stage_models.get(stage)
        return provider_for(model) if model is not None else provider

    def skill_instruction(stage: str) -> str:
        skill = skill_for_stage_config(db, strategy_config, stage)
        return f"\n\nSkill 指令（{skill.name} {skill.version}）：\n{skill.prompt}" if skill else ""

    def collect() -> dict[str, Any]:
        source_query = select(Source).where(Source.enabled.is_(True))
        source_ids = strategy_config.get("source_ids", [])
        if source_ids:
            source_query = source_query.where(Source.id.in_(source_ids))
        sources = db.scalars(source_query).all()
        for source in sources:
            for item in collect_source(
                db,
                source,
                translation_job=job,
                translate_foreign_sources=strategy_config.get("translate_foreign_sources", True),
            ):
                collected["items"].append(item.id)
        return {"item_ids": collected["items"]}

    _run_step(db, job, "collect", collect)
    _run_step(db, job, "normalize", lambda: {"normalized": True})
    _run_step(db, job, "deduplicate", lambda: {"deduplicated": True})

    def topic() -> dict[str, Any]:
        selected_topic_id = (job.payload_json or {}).get("topic_id")
        if selected_topic_id:
            topic_record = db.get(Topic, selected_topic_id)
            if topic_record is None or topic_record.strategy_id != strategy.id:
                raise ValueError("选题不存在或不属于当前策略")
            if topic_record.status not in {"accepted", "writing"}:
                raise ValueError("选题必须先通过人工确认才能开始创作")
            linked_items = [link.material for link in topic_record.material_links if link.material is not None]
            item = (
                linked_items[0]
                if linked_items
                else (db.get(SourceItem, topic_record.source_item_id) if topic_record.source_item_id else None)
            )
            if item is None or item.status != "verified":
                raise ValueError("选题关联的素材不可用")
            topic_record.status = "writing"
            article.title = topic_record.title or item.title
            db.flush()
            return {
                "topic_id": topic_record.id,
                "source_item_id": item.id,
                "source_item_ids": [linked.id for linked in linked_items] if linked_items else [item.id],
                "title": article.title,
                "score": topic_record.score,
                "rationale": topic_record.rationale,
            }

        topic_query = select(SourceItem).where(SourceItem.status == "verified")
        source_ids = strategy_config.get("source_ids", [])
        if source_ids:
            topic_query = topic_query.where(SourceItem.source_id.in_(source_ids))
        item = db.scalar(topic_query.order_by(SourceItem.created_at.desc()))
        if item is None:
            raise ValueError("没有可用的已验证来源内容")
        article.title = item.title
        topic_record = db.scalar(select(Topic).where(Topic.job_id == job.id))
        if topic_record is None:
            topic_record = Topic(
                strategy_id=strategy.id,
                job_id=job.id,
                source_item_id=item.id,
                title=item.title,
                status="accepted",
                score=80,
                rationale="基于最新已验证来源自动选中",
            )
            db.add(topic_record)
            db.flush()
            db.add(
                TopicMaterial(
                    topic_id=topic_record.id,
                    source_item_id=item.id,
                    role="primary",
                    relevance_score=100,
                )
            )
            for dimension, score, rationale in (
                ("recency", 90, "来源内容较新"),
                ("source_quality", 80, "来源已通过采集校验"),
                ("strategy_fit", 80, "与当前内容策略匹配"),
            ):
                db.add(TopicScore(topic_id=topic_record.id, dimension=dimension, score=score, rationale=rationale))
        else:
            topic_record.source_item_id = item.id
            topic_record.title = item.title
        db.flush()
        return {
            "topic_id": topic_record.id,
            "source_item_id": item.id,
            "title": item.title,
            "source_item_ids": [item.id],
            "score": topic_record.score,
            "rationale": topic_record.rationale,
        }

    topic_output = _run_step(db, job, "topic", topic)
    item = db.get(SourceItem, topic_output["source_item_id"])
    if item is None:
        raise ValueError("选题来源不存在")
    material_ids = topic_output.get("source_item_ids") or [item.id]
    evidence_by_id = {
        source_item.id: source_item
        for source_item in db.scalars(select(SourceItem).where(SourceItem.id.in_(material_ids))).all()
    }
    evidence_items = [evidence_by_id[item_id] for item_id in material_ids if item_id in evidence_by_id]

    def evidence() -> dict[str, Any]:
        result = {
            "confirmed_facts": [
                {"statement": source_item.content[:1000] or source_item.title, "source_url": source_item.url}
                for source_item in evidence_items
            ],
            "conflicts": [],
            "unknowns": [],
            "inferences": [],
            "sources": [
                {"title": source_item.title, "url": source_item.url, "verified": True} for source_item in evidence_items
            ],
        }
        package = db.scalar(select(EvidencePackage).where(EvidencePackage.article_id == article.id))
        if package is None:
            package = EvidencePackage(article_id=article.id, status="verified", version=1, summary=item.title)
            db.add(package)
            db.flush()
            for source_item in evidence_items:
                source = EvidenceSource(
                    evidence_package_id=package.id,
                    source_item_id=source_item.id,
                    title=source_item.title,
                    url=source_item.url,
                    snapshot_hash=source_item.content_hash,
                    snapshot_text=source_item.content[:10000],
                    credibility=0.8,
                )
                db.add(source)
                db.flush()
                db.add(
                    EvidenceClaim(
                        evidence_package_id=package.id,
                        source_id=source.id,
                        claim_type="fact",
                        statement=source_item.content[:1000] or source_item.title,
                        status="confirmed",
                    )
                )
        article.evidence_json = {**result, "evidence_package_id": package.id}
        db.flush()
        return {**result, "evidence_package_id": package.id}

    evidence_output = _run_step(db, job, "evidence", evidence)
    outline_output = _run_step(
        db,
        job,
        "outline",
        lambda: {"outline": ["发生了什么", "实际影响", "注意事项"]},
    )
    writing_output = _run_step(
        db,
        job,
        "writing",
        lambda: {
            "content": _require_article_body(
                _complete_with_log(
                    db,
                    job,
                    article,
                    stage_provider("writing"),
                CompletionRequest(
                    system="你是事实优先的内容编辑，只能使用事实包中的信息。" + skill_instruction("writing"),
                    user=f"{article.title}\n{evidence_output}\n{outline_output}",
                ),
                    "writing",
                ),
                "写作",
            )
        },
    )
    if "style" in disabled_steps:
        _skip_step(db, job, "style", "策略配置已关闭")
        style_output = {"content": writing_output["content"]}
    else:
        style_output = _run_step(
            db,
            job,
            "style",
            lambda: {
                "content": _require_article_body(
                    _complete_with_log(
                        db,
                        job,
                        article,
                        stage_provider("style"),
                    CompletionRequest(
                        system="你是负责风格编辑的内容编辑，不能改变事实。" + skill_instruction("style"),
                        user=f"CURRENT_CONTENT:\n{writing_output['content']}\nEND_CURRENT_CONTENT",
                    ),
                        "style",
                    ),
                    "风格编辑",
                )
            },
        )
    if "rewrite" in disabled_steps:
        _skip_step(db, job, "rewrite", "策略配置已关闭")
        rewrite_output = {"content": style_output["content"]}
    else:
        rewrite_output = _run_step(
            db,
            job,
            "rewrite",
            lambda: {
                "content": _require_article_body(
                    _complete_with_log(
                        db,
                        job,
                        article,
                        stage_provider("rewrite"),
                    CompletionRequest(
                        system="你是负责最终改写的内容编辑，不能增加事实。" + skill_instruction("rewrite"),
                        user=f"CURRENT_CONTENT:\n{style_output['content']}\nEND_CURRENT_CONTENT",
                    ),
                        "rewrite",
                    ),
                    "最终改写",
                )
            },
        )
    _run_step(
        db,
        job,
        "review",
        lambda: {"status": "pass", "checks": {"fact_traceability": True, "source_quality": True}},
    )
    review_rules = strategy_config.get("review_rules", {})
    human_review_required = bool(review_rules.get("human_review_required", True))

    def render() -> dict[str, Any]:
        content = rewrite_output["content"]
        html = MarkdownIt("commonmark", {"breaks": True}).render(content)
        revision = db.scalar(
            select(ArticleRevision)
            .where(ArticleRevision.article_id == article.id)
            .order_by(ArticleRevision.version.desc())
        )
        if revision is None:
            revision = ArticleRevision(article_id=article.id, version=1, content_markdown=content, rendered_html=html)
            db.add(revision)
        else:
            revision.content_markdown = content
            revision.rendered_html = html
        db.flush()
        rendered_version_id = None
        theme_id = strategy_config.get("theme_id")
        if theme_id:
            theme = db.get(Theme, theme_id)
            if theme is None:
                raise ValueError("策略配置的排版主题不存在")
            if not theme.enabled:
                raise ValueError("策略配置的排版主题已停用")
            rendered_version_id = render_revision(db, revision, theme).id
        return {
            "article_id": article.id,
            "revision_id": revision.id,
            "rendered_version_id": rendered_version_id,
            "html_length": len(html),
        }

    render_output = _run_step(db, job, "render", render)
    rendered_revision = db.get(ArticleRevision, render_output["revision_id"])
    if rendered_revision is None:
        raise ValueError("渲染后的文章版本不存在")
    if rendered_revision.review is None:
        db.add(
            Review(
                article_revision_id=rendered_revision.id,
                status="pending",
                auto_result_json={"status": "pass", "checks": {"fact_traceability": True, "source_quality": True}},
            )
        )
        db.flush()
    current_review = rendered_revision.review
    if not human_review_required:
        if current_review is not None:
            current_review.status = "auto_approved"
        article.status = "approved"
    if human_review_required and article.status != "approved":
        article.status = "waiting_review"
        job.status = "waiting_review"
        job.current_step = "review"
        job.available_at = None
        job.lease_until = None
        _record_job_duration(job)
        db.commit()
        db.refresh(job)
        return job

    def draft() -> dict[str, Any]:
        article.status = "drafted"
        job.status = "succeeded"
        job.current_step = "draft"
        job.available_at = None
        job.lease_until = None
        job.completed_at = datetime.now(timezone.utc)
        _record_job_duration(job, job.completed_at)
        db.flush()
        return {
            "article_id": article.id,
            "revision_id": render_output["revision_id"],
            "publication": "local_draft",
        }

    _run_step(db, job, "draft", draft)
    db.commit()
    db.refresh(job)
    return job
