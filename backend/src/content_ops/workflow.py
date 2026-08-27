from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from markdown_it import MarkdownIt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .delivery import deliver_article
from .fact_verification import verify_evidence
from .ingestion import collect_source
from .material_curation import curate_materials
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
    ThemeVersion,
    Topic,
)
from .providers import CompletionRequest, ModelProvider, provider_for
from .redaction import redact_error, redact_event_payload
from .settings import get_settings
from .strategy_combinations import resolve_strategy_definition
from .strategy_config import (
    StrategyConfigError,
    model_id_for_stage,
    model_snapshot,
    skill_for_stage_config,
    skill_snapshot,
    validate_strategy_config,
)
from .themes import extract_html, layout_instruction, recommend_editorial_theme, render_revision, validate_gzh_html
from .topic_recommendations import recommend_topics

REQUIRED_AI_REVIEW_CHECKS = frozenset(
    {"fact_traceability", "source_quality", "title_alignment", "content_complete"}
)

_MAX_JOB_ERROR_LENGTH = 2000
_MAX_EVENT_ERROR_LENGTH = 500
_REDACTED_ERROR_ATTR = "_content_ops_redacted_error"


class JobCanceled(Exception):
    pass


def _remember_redacted_error(exc: Exception, error: str) -> None:
    """Retain a provider-aware rendering while re-raising the original exception."""
    try:
        setattr(exc, _REDACTED_ERROR_ATTR, error)
    except (AttributeError, TypeError):
        # Some exception implementations do not allow custom attributes. The
        # generic redactor in _persisted_error still protects those failures.
        pass


def _persisted_error(exc: Exception, *, max_length: int) -> str:
    remembered = getattr(exc, _REDACTED_ERROR_ATTR, None)
    return redact_error(remembered if isinstance(remembered, str) else exc, max_length=max_length)


def _assert_job_active(db: Session, job: Job) -> None:
    db.refresh(job, attribute_names=["status"])
    if job.status == "canceled":
        raise JobCanceled("Job was canceled")


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
    try:
        db.commit()
    except IntegrityError:
        # A concurrent enqueue may have committed the same idempotency key
        # between our existence check and this commit; return the winner.
        db.rollback()
        existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
        raise
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
    event_payload = dict(payload or {})
    for key in ("error", "reason"):
        if key in event_payload:
            event_payload[key] = redact_error(event_payload[key], max_length=_MAX_EVENT_ERROR_LENGTH)
    event_payload = redact_event_payload(event_payload)
    db.add(
        JobEvent(
            job_id=job.id,
            event_type=event_type,
            step_name=step_name,
            status=status,
            payload_json=event_payload,
        )
    )


def _run_step(db: Session, job: Job, name: str, fn) -> dict[str, Any]:
    _assert_job_active(db, job)
    step = _step(db, job, name)
    if step.status == "succeeded":
        return step.output_json
    step.status = "running"
    step.attempt_count += 1
    step.started_at = datetime.now(timezone.utc)
    job.current_step = name
    if job.lease_until is not None:
        job.lease_until = datetime.now(timezone.utc) + timedelta(seconds=get_settings().job_lease_seconds)
    _job_event(db, job, "step_started", name, "running")
    db.commit()
    try:
        output = fn()
        _assert_job_active(db, job)
        step.status = "succeeded"
        step.output_json = output
        step.completed_at = datetime.now(timezone.utc)
        step.error = None
        _job_event(db, job, "step_succeeded", name, "succeeded", {"output_keys": list(output)})
        db.commit()
        return output
    except JobCanceled:
        canceled_at = datetime.now(timezone.utc)
        step.status = "canceled"
        step.completed_at = canceled_at
        step.error = "Job was canceled"
        job.status = "canceled"
        job.available_at = None
        job.lease_until = None
        job.completed_at = canceled_at
        _record_job_duration(job, canceled_at)
        _job_event(db, job, "job_canceled", name, "canceled")
        db.commit()
        raise
    except Exception as exc:
        failed_at = datetime.now(timezone.utc)
        error = _persisted_error(exc, max_length=_MAX_JOB_ERROR_LENGTH)
        step.status = "failed"
        step.error = error
        job.last_error = error
        _job_event(db, job, "step_failed", name, "failed", {"error": error})
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
    if stage in {"writing", "style", "rewrite"}:
        request = CompletionRequest(
            system=request.system + _GENERATION_GUIDANCE,
            user=request.user,
            json_schema=request.json_schema,
            max_tokens=request.max_tokens,
        )
    started = time.perf_counter()
    snapshot = article.model_snapshot or {}
    stage_snapshot = (snapshot.get("stages") or {}).get(stage) or snapshot
    provider_name = str(stage_snapshot.get("provider") or provider.__class__.__name__)
    model_name = str(stage_snapshot.get("name") or provider.__class__.__name__)
    api_key = str(getattr(provider, "api_key", "") or "")
    try:
        response = provider.complete(request)
    except Exception as exc:
        error = redact_error(exc, secret_values=(api_key,), max_length=_MAX_JOB_ERROR_LENGTH)
        _remember_redacted_error(exc, error)
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
                error=error,
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


def _complete_advisory_with_log(
    db: Session,
    job: Job,
    article: Article,
    provider: ModelProvider,
    request: CompletionRequest,
    stage: str,
) -> str:
    try:
        return _complete_with_log(db, job, article, provider, request, stage)
    except Exception as exc:
        _job_event(
            db,
            job,
            "advisory_review_unavailable",
            stage,
            "warning",
            {"reason": str(exc)[:500]},
        )
        return json.dumps(
            {
                "status": "unavailable",
                "score": 0,
                "summary": "AI advisory review was unavailable; delivery continued.",
                "checks": {},
            }
        )


def _normalize_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if 0 < score <= 1:
        score *= 100
    elif 1 < score <= 10:
        score *= 10
    return max(0.0, min(100.0, score))


_NON_ARTICLE_MARKERS = (
    "这是一份基于已核验来源生成的草稿。",
    "质检报告",
    "L1 硬性规则",
    "L2 风格一致性",
    "禁用词：",
    "结构套话",
)

# A writing skill can include an author's personal sign-off as part of its
# example output. That information belongs to the skill author, not to every
# article generated in this workspace, so never carry it into a draft.
_TRAILING_BYLINE_AND_CONTACT = re.compile(
    r"(?:\n|\A)[ \t>]*[/\uff0f][ \t]*(?:\u4f5c\u8005|author)[\uff1a:][^\n]+"
    r"(?:\n[ \t>]*(?:[/\uff0f][ \t]*)?(?:(?:\u6295\u7a3f|\u7206\u6599|\u5408\u4f5c|\u5546\u52a1|\u8054\u7cfb).*"
    r"|(?:\u90ae\u7bb1|email)[\uff1a:].*))*\s*\Z",
    re.IGNORECASE,
)


def _parse_quality_review(content: str) -> dict[str, Any]:
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI 质量审核没有返回可解析结果")
    try:
        payload = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("AI 质量审核结果不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI 质量审核结果缺少 pass/fail 状态")
    # Some OpenAI-compatible models mirror the requested schema in a wrapper.
    # Accept it only when the direct result does not already declare a status.
    if "status" not in payload and isinstance(payload.get("response_schema"), dict):
        payload = payload["response_schema"]
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"pass", "fail"}:
        raise ValueError("AI 质量审核结果缺少 pass/fail 状态")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        checks = {}
    return {
        "status": status,
        "score": _normalize_score(payload.get("score")),
        "summary": str(payload.get("summary") or "").strip()[:1000],
        "checks": checks,
    }


def _parse_advisory_quality_review(content: str) -> dict[str, Any]:
    try:
        return _parse_quality_review(content)
    except (TypeError, ValueError):
        return {
            "status": "unavailable",
            "score": 0.0,
            "summary": "AI review was unavailable; automatic publication requires human review.",
            "checks": {},
        }


def _automatic_review_passed(result: dict[str, Any], review_rules: dict[str, Any]) -> bool:
    threshold = float(review_rules.get("ai_review_min_score", 75))
    checks = result.get("checks")
    return (
        result.get("status") == "pass"
        and float(result.get("score") or 0) >= threshold
        and isinstance(checks, dict)
        and all(checks.get(name) is True for name in REQUIRED_AI_REVIEW_CHECKS)
    )


def _require_article_body(content: str, stage: str) -> str:
    body = content.strip()
    if len(body) < 300:
        raise ValueError(f"{stage} 阶段没有生成足够完整的文章正文")
    marker = next((item for item in _NON_ARTICLE_MARKERS if item in body), None)
    if marker is not None:
        # Some writing skills (e.g. khazix-writer) instruct the model to append a
        # self-check report after the article. Keep the article and drop the report.
        cut = body.find(marker)
        line_start = body.rfind("\n", 0, cut) + 1
        body = body[:line_start].rstrip()
        if len(body) < 300:
            raise ValueError(f"{stage} 阶段返回了质检内容（{marker}），不是文章正文")
    return _TRAILING_BYLINE_AND_CONTACT.sub("", body).rstrip()

def _require_outline(content: str) -> str:
    outline = content.strip()
    if len(outline) < 80:
        raise ValueError("大纲阶段没有生成足够完整的文章蓝图")
    return outline


def _ensure_wechat_structure(content: str) -> str:
    body = content.strip()
    if len(re.findall(r"(?m)^##\s+\S+", body)) >= 2:
        return body

    blocks = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
    title = ""
    if blocks and blocks[0].startswith("# ") and not blocks[0].startswith("## "):
        title = blocks.pop(0)
    prose = "\n\n".join(blocks)
    parts = [part.strip() for part in re.split(r"(?<=[???.!?])\s*", prose) if part.strip()]
    if len(parts) < 3:
        parts = blocks
    if len(parts) < 2:
        return body

    headings = (
        "????????",
        "???????",
        "??????",
    )
    chunk_size = max(1, (len(parts) + len(headings) - 1) // len(headings))
    sections: list[str] = []
    for index, heading in enumerate(headings):
        start = index * chunk_size
        if start >= len(parts):
            break
        end = len(parts) if index == len(headings) - 1 else min(len(parts), start + chunk_size)
        section = " ".join(parts[start:end]).strip()
        if section:
            sections.append(f"## {heading}\n\n{section}")
    if len(sections) < 2:
        return body
    return "\n\n".join(([title] if title else []) + sections)


_GENERATION_GUIDANCE = (
    " Produce a WeChat-ready Markdown article with 3-5 meaningful level-2 headings."
    " Use exact numbers only when they appear in the evidence; otherwise use qualitative wording."
    " Separate confirmed facts from inference, preserve the title's meaning, and do not invent sources."
    " Never append an author byline, email address, submission notice, or quality-review report."
)


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
        db.commit()

        collected: list[str] = []
        source_failures: dict[str, str] = {}

        def collect_for_triage() -> dict[str, Any]:
            source_query = select(Source).where(Source.enabled.is_(True))
            source_ids = strategy_config.get("source_ids", [])
            if source_ids:
                source_query = source_query.where(Source.id.in_(source_ids))
            sources = db.scalars(source_query).all()
            for source in sources:
                try:
                    for item in collect_source(
                        db,
                        source,
                        translation_job=job,
                        translate_foreign_sources=strategy_config.get("translate_foreign_sources", True),
                    ):
                        collected.append(item.id)
                except Exception as exc:
                    # Isolate a failing source so one bad feed cannot fail the
                    # whole scan, mirroring the automation collect step.
                    source_failures[source.name] = redact_error(exc, max_length=_MAX_EVENT_ERROR_LENGTH)
                    _job_event(
                        db,
                        job,
                        "source_failed",
                        "collect",
                        "failed",
                        {"source": source.name, "error": source_failures[source.name]},
                    )
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
            return {
                "item_ids": collected,
                "material_count": len(collected),
                "succeeded_sources": len(sources) - len(source_failures),
                "failed_sources": source_failures,
            }

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
        material_query = select(SourceItem).where(
            SourceItem.id.in_(material_ids),
            SourceItem.status == "verified",
        )
        material_category_ids = strategy_config.get("material_category_ids", [])
        if material_category_ids:
            material_query = material_query.where(SourceItem.category_id.in_(material_category_ids))
        materials = db.scalars(material_query.order_by(SourceItem.created_at.desc())).all()

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

    stage_models = {
        stage: configured_model(stage)
        for stage in ("outline", "writing", "style", "rewrite", "review", "render")
    }
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
            for stage in ("outline", "writing", "style", "rewrite", "review", "render")
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
            "review_rules": strategy_config.get("review_rules", {"human_review_required": False}),
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
        collected_items: list[str] = []
        source_failures: dict[str, str] = {}
        for source in sources:
            try:
                for item in collect_source(
                    db,
                    source,
                    translation_job=job,
                    translate_foreign_sources=strategy_config.get("translate_foreign_sources", True),
                ):
                    collected_items.append(item.id)
            except Exception as exc:
                source_failures[source.name] = redact_error(exc, max_length=_MAX_EVENT_ERROR_LENGTH)
                _job_event(
                    db,
                    job,
                    "source_failed",
                    "collect",
                    "failed",
                    {"source": source.name, "error": source_failures[source.name]},
                )
                try:
                    # Persist the failure event right away: a later source's
                    # collect_source may roll back the shared session, which
                    # would otherwise discard this pending event.
                    db.commit()
                except Exception:
                    db.rollback()
        db.commit()
        return {
            "item_ids": collected_items,
            "source_count": len(sources),
            "succeeded_sources": len(sources) - len(source_failures),
            "failed_sources": source_failures,
        }

    collect_output = _run_step(db, job, "collect", collect)
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

        candidate_query = select(SourceItem).where(
            SourceItem.status == "verified",
            SourceItem.triage_status.in_(("inbox", "selected")),
        )
        source_ids = strategy_config.get("source_ids", [])
        if source_ids:
            candidate_query = candidate_query.where(SourceItem.source_id.in_(source_ids))
        material_category_ids = strategy_config.get("material_category_ids", [])
        if material_category_ids:
            candidate_query = candidate_query.where(SourceItem.category_id.in_(material_category_ids))
        collected_ids = list(dict.fromkeys(collect_output.get("item_ids", [])))
        if collected_ids:
            candidate_query = candidate_query.where(SourceItem.id.in_(collected_ids))
        candidates = db.scalars(candidate_query.order_by(SourceItem.created_at.desc()).limit(50)).all()
        if not candidates and collected_ids:
            fallback_query = select(SourceItem).where(
                SourceItem.status == "verified",
                SourceItem.triage_status.in_(("inbox", "selected")),
            )
            if source_ids:
                fallback_query = fallback_query.where(SourceItem.source_id.in_(source_ids))
            if material_category_ids:
                fallback_query = fallback_query.where(SourceItem.category_id.in_(material_category_ids))
            candidates = db.scalars(fallback_query.order_by(SourceItem.created_at.desc()).limit(50)).all()
        if not candidates:
            raise ValueError("素材池范围内没有可用于自动创作的素材")

        writing_model = stage_models["writing"]
        curation = curate_materials(
            db,
            job,
            strategy,
            candidates,
            stage_provider("writing"),
            writing_model,
            limit=12,
        )
        selected_ids = [decision["id"] for decision in curation]
        if not selected_ids:
            raise ValueError("AI 精选后没有达到创作标准的素材")
        selected_by_id = {item.id: item for item in candidates}
        selected_materials = [selected_by_id[item_id] for item_id in selected_ids if item_id in selected_by_id]
        algorithm = strategy_config.get("topic_algorithm", {})
        recommendations = recommend_topics(
            db,
            job,
            strategy,
            selected_materials,
            stage_provider("writing"),
            writing_model,
            strategy_objective=strategy_runtime_snapshot.get("objective") or strategy.objective,
            algorithm=algorithm,
            limit=int(algorithm.get("max_topics", 4)),
        )
        topic_record = max(recommendations, key=lambda candidate: candidate.score)
        for recommendation in recommendations:
            recommendation.status = "writing" if recommendation.id == topic_record.id else "rejected_auto"
        linked_items = [link.material for link in topic_record.material_links if link.material is not None]
        if not linked_items:
            raise ValueError("AI 选题没有关联可用素材")
        item = linked_items[0]
        article.title = topic_record.title
        db.flush()
        return {
            "topic_id": topic_record.id,
            "source_item_id": item.id,
            "title": topic_record.title,
            "source_item_ids": [linked.id for linked in linked_items],
            "score": topic_record.score,
            "rationale": topic_record.rationale,
            "selection_mode": "ai_automatic",
        }

    topic_output = _run_step(db, job, "topic", topic)
    runtime_snapshot = dict((job.payload_json or {}).get("runtime_snapshot") or {})
    if "material_selection" not in runtime_snapshot:
        runtime_snapshot["material_selection"] = {
            "category_ids": list(strategy_config.get("material_category_ids", [])),
            "material_ids": list(topic_output.get("source_item_ids") or [topic_output["source_item_id"]]),
            "topic_id": topic_output["topic_id"],
            "topic_title": topic_output["title"],
            "selection_mode": topic_output.get("selection_mode", "manual"),
        }
        job.payload_json = {**(job.payload_json or {}), "runtime_snapshot": runtime_snapshot}
        article.runtime_snapshot_json = runtime_snapshot
        db.flush()
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
        verification = verify_evidence(
            stage_provider("review"),
            article.title,
            [
                {"title": source_item.title, "url": source_item.url, "text": source_item.content[:4000]}
                for source_item in evidence_items
            ],
        )
        result = {
            "confirmed_facts": [
                {"statement": source_item.content[:1000] or source_item.title, "source_url": source_item.url}
                for source_item in evidence_items
            ],
            "conflicts": [],
            "unknowns": [],
            "inferences": [],
            "sources": [
                {
                    "title": source_item.title,
                    "url": source_item.url,
                    "verified": verification["verification_status"] == "verified",
                }
                for source_item in evidence_items
            ],
            "verification": verification,
        }
        package = db.scalar(select(EvidencePackage).where(EvidencePackage.article_id == article.id))
        if package is None:
            package = EvidencePackage(article_id=article.id, status="draft", version=1, summary=item.title)
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
                        status="source_snapshot",
                    )
                )
        package.status = str(verification["verification_status"])
        package.summary = str(verification["summary"])
        for claim in verification["claims"]:
            db.add(
                EvidenceClaim(
                    evidence_package_id=package.id,
                    source_id=None,
                    claim_type="fact",
                    statement=claim["statement"],
                    status=claim["status"],
                )
            )
        article.evidence_json = {**result, "evidence_package_id": package.id}
        db.flush()
        return {**result, "evidence_package_id": package.id}

    evidence_output = _run_step(db, job, "evidence", evidence)
    outline_skill = skill_for_stage_config(db, strategy_config, "outline")
    if outline_skill is None:
        outline_output = _run_step(
            db,
            job,
            "outline",
            lambda: {"outline": ["发生了什么", "实际影响", "注意事项"]},
        )
    else:
        outline_output = _run_step(
            db,
            job,
            "outline",
            lambda: {
                "outline": _require_outline(
                    _complete_with_log(
                        db,
                        job,
                        article,
                        stage_provider("outline"),
                        CompletionRequest(
                            system=(
                                "你是事实优先的公众号选题策划编辑。只能使用事实包中的信息，"
                                "为已选主题输出可直接交给写作阶段的 Markdown 大纲。大纲必须包含开头钩子，"
                                "3-5 个二级标题、每节的核心论点与事实依据、结尾行动建议和各节建议字数。"
                                "不要虚构读者反馈、数据、案例或来源。"
                                + skill_instruction("outline")
                            ),
                            user=json.dumps(
                                {
                                    "title": article.title,
                                    "strategy_objective": strategy_runtime_snapshot.get("objective")
                                    or strategy.objective,
                                    "evidence": evidence_output,
                                },
                                ensure_ascii=False,
                            ),
                        ),
                        "outline",
                    )
                )
            },
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
    rewrite_output = {
        **rewrite_output,
        "content": _ensure_wechat_structure(rewrite_output["content"]),
    }
    review_rules = strategy_config.get("review_rules", {})
    quality_review_output = _run_step(
        db,
        job,
        "review",
        lambda: _parse_advisory_quality_review(
            _complete_advisory_with_log(
                db,
                job,
                article,
                stage_provider("review"),
                CompletionRequest(
                    system=(
                        "你是发布前质量审核员。只根据文章和事实包检查事实可追溯、来源质量、"
                        "标题与正文一致性、完整性和明显风险。不要重写文章。只返回一个 JSON 对象，"
                        "根层必须包含 status（仅 pass 或 fail）、score、summary 和 checks；"
                        "不要返回 response_schema、markdown 或其他包装字段。"
                        + skill_instruction("review")
                    ),
                    user="QUALITY_REVIEW_JSON\n"
                    + json.dumps(
                        {
                            "required_output": {
                                "status": "pass or fail",
                                "score": 0,
                                "summary": "审核结论",
                                "checks": {
                                    "fact_traceability": True,
                                    "source_quality": True,
                                    "title_alignment": True,
                                    "content_complete": True,
                                },
                            },
                            "title": article.title,
                            "article": rewrite_output["content"],
                            "evidence": evidence_output,
                        },
                        ensure_ascii=False,
                    ),
                    max_tokens=1000,
                ),
                "review",
            )
        ),
    )
    verification = evidence_output.get("verification", {})
    if verification.get("verification_status") != "verified":
        quality_review_output = {
            "status": "fail",
            "score": 0.0,
            "summary": str(verification.get("summary") or "Fact verification requires human review."),
            "checks": {
                "fact_traceability": False,
                "source_quality": False,
                "title_alignment": True,
                "content_complete": True,
            },
        }
    human_review_required = bool(review_rules.get("human_review_required", False))
    automatic_review_passed = _automatic_review_passed(quality_review_output, review_rules)
    requires_human_review = human_review_required or (
        strategy_config.get("delivery_mode") == "auto_publish" and not automatic_review_passed
    )

    approved_revision_id = (job.payload_json or {}).get("approved_revision_id")
    approved_revision = db.get(ArticleRevision, approved_revision_id) if approved_revision_id else None
    if approved_revision is not None and approved_revision.article_id != article.id:
        approved_revision = None

    def render() -> dict[str, Any]:
        content = (
            approved_revision.content_markdown if approved_revision is not None else rewrite_output["content"]
        )
        theme_id = strategy_config.get("theme_id")
        render_mode = strategy_config.get("render_mode", "deterministic")
        theme_selection = {"mode": strategy_config.get("theme_selection_mode", "manual")}
        if theme_selection["mode"] == "auto":
            recommended_slug, reason = recommend_editorial_theme(article.title, outline_output, content)
            recommended_theme = db.scalar(
                select(Theme).where(Theme.slug == recommended_slug, Theme.enabled.is_(True))
            )
            if recommended_theme is not None:
                theme_id = recommended_theme.id
                theme_selection.update(
                    {"recommended_slug": recommended_slug, "theme_id": recommended_theme.id, "reason": reason}
                )
                _job_event(db, job, "theme_recommendation", "render", "info", theme_selection)
            else:
                theme_selection.update(
                    {"recommended_slug": recommended_slug, "reason": f"{reason}；推荐主题不可用，保留当前主题"}
                )
        runtime_snapshot = dict(article.runtime_snapshot_json or {})
        runtime_snapshot["theme"] = {"id": theme_id, "version": strategy_config.get("theme_version")}
        runtime_snapshot["theme_selection"] = theme_selection
        article.runtime_snapshot_json = runtime_snapshot
        job.payload_json = {**(job.payload_json or {}), "runtime_snapshot": runtime_snapshot}
        revision = approved_revision or db.scalar(
            select(ArticleRevision)
            .where(ArticleRevision.article_id == article.id)
            .order_by(ArticleRevision.version.desc())
        )
        if revision is None:
            revision = ArticleRevision(article_id=article.id, version=1, content_markdown=content)
            db.add(revision)
        elif approved_revision is None:
            revision.content_markdown = content
        db.flush()
        rendered_version_id = None
        fallback_reason = ""
        if render_mode == "ai":
            if not theme_id:
                raise ValueError("AI 排版必须配置排版主题")
            theme = db.get(Theme, theme_id)
            if theme is None or not theme.enabled:
                raise ValueError("策略配置的排版主题不存在或已停用")
            version = db.scalar(
                select(ThemeVersion).where(
                    ThemeVersion.theme_id == theme.id,
                    ThemeVersion.version == theme.current_version,
                )
            )
            if version is None:
                raise ValueError("排版主题版本缺失")
            try:
                raw = _complete_with_log(
                    db,
                    job,
                    article,
                    stage_provider("render"),
                    CompletionRequest(
                        system=layout_instruction(theme, version) + skill_instruction("render"),
                        user=f"文章标题：{article.title}\n\n文章正文（Markdown）：\n{content}",
                        max_tokens=8000,
                    ),
                    "render",
                )
                html = extract_html(raw)
                errors = validate_gzh_html(html)
                if errors:
                    raise ValueError(f"AI 排版输出不合规：{', '.join(errors[:4])}")
                revision.rendered_html = html
            except Exception as exc:
                fallback_reason = str(exc)[:500]
                _job_event(db, job, "render_fallback", "render", "warning", {"reason": fallback_reason})
        if render_mode == "deterministic" or fallback_reason:
            html = MarkdownIt("commonmark", {"breaks": True}).render(content)
            revision.rendered_html = html
            if theme_id:
                theme = db.get(Theme, theme_id)
                if theme is None:
                    raise ValueError("策略配置的排版主题不存在")
                if not theme.enabled:
                    raise ValueError("策略配置的排版主题已停用")
                rendered_version_id = render_revision(db, revision, theme).id
        db.flush()
        return {
            "article_id": article.id,
            "revision_id": revision.id,
            "rendered_version_id": rendered_version_id,
            "theme_id": theme_id,
            "theme_selection": theme_selection,
            "html_length": len(revision.rendered_html or ""),
        }


    render_output = _run_step(db, job, "render", render)
    rendered_revision = db.get(ArticleRevision, render_output["revision_id"])
    if rendered_revision is None:
        raise ValueError("渲染后的文章版本不存在")
    if rendered_revision.review is None:
        current_review = Review(
            article_revision_id=rendered_revision.id,
            status="pending",
            auto_result_json=quality_review_output,
        )
        db.add(current_review)
        db.flush()
    else:
        current_review = rendered_revision.review
    if not requires_human_review:
        if current_review is not None:
            current_review.status = "auto_approved"
        article.status = "approved"
    if requires_human_review and article.status != "approved":
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
        _assert_job_active(db, job)
        delivery = deliver_article(
            db,
            article,
            rendered_revision,
            strategy_config,
            ensure_active=lambda: _assert_job_active(db, job),
        )
        job.status = "succeeded"
        job.current_step = "draft"
        job.available_at = None
        job.lease_until = None
        job.completed_at = datetime.now(timezone.utc)
        _record_job_duration(job, job.completed_at)
        if delivery.publish_blocked:
            _job_event(
                db,
                job,
                "auto_publish_blocked",
                "draft",
                "succeeded",
                {"reason": delivery.publish_blocked, "publication_id": delivery.publication_id},
            )
        db.flush()
        return {
            "article_id": article.id,
            "revision_id": render_output["revision_id"],
            "publication": delivery.mode,
            "delivery_status": delivery.status,
            "publication_id": delivery.publication_id,
            "remote_id": delivery.remote_id,
            "publish_blocked": delivery.publish_blocked,
        }

    _run_step(db, job, "draft", draft)
    db.commit()
    db.refresh(job)
    return job
