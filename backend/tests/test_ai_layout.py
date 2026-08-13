import pytest
from sqlalchemy import select

from content_ops.models import (
    Article,
    ArticleRevision,
    JobEvent,
    ModelConfig,
    Source,
    Strategy,
    Theme,
    ThemeVersion,
)
from content_ops.providers import CompletionRequest, CompletionResponse, FakeProvider
from content_ops.strategy_config import StrategyConfigError, validate_strategy_config
from content_ops.themes import (
    ensure_builtin_themes,
    extract_html,
    layout_instruction,
    validate_gzh_html,
)
from content_ops.workflow import create_job, run_job


class RenderOkProvider(FakeProvider):
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        if "你是微信公众号文章排版专家" in (request.system or ""):
            return CompletionResponse(
                text='<article style="background:#fff;color:#333;"><section style="padding:16px;"><p>AI 排版产物</p></section></article>',  # noqa: E501
                input_tokens=10,
                output_tokens=10,
            )
        return super().complete(request)


class RenderBadProvider(FakeProvider):
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        if "你是微信公众号文章排版专家" in (request.system or ""):
            return CompletionResponse(text='<div class="bad"><p>不合规</p></div>', input_tokens=10, output_tokens=10)
        return super().complete(request)


def _theme(db):
    ensure_builtin_themes(db)
    db.commit()
    return db.query(Theme).filter(Theme.slug == "moyu-green").one()


def _strategy_with_ai_render(db, model_id: str) -> Strategy:
    theme = _theme(db)
    strategy = Strategy(
        name="AI 排版策略",
        objective="测试 AI 装配排版",
        config_json={
            "theme_id": theme.id,
            "render_mode": "ai",
            "review_rules": {"human_review_required": True},
        },
    )
    db.add(strategy)
    db.commit()
    return strategy


def _manual_source(db) -> Source:
    source = Source(
        name="手动资料",
        source_type="manual",
        url="https://example.com/ai-layout",
        config_json={"title": "AI 排版测试", "content": "官方公告确认产品已发布。"},
    )
    db.add(source)
    db.commit()
    return source


def test_validate_gzh_html_catches_forbidden_markup():
    assert validate_gzh_html('<article style="color:#333;"><p>合规</p></article>') == []
    for bad in ('<style>', '<div>', 'class="x"', 'position:fixed', '@media', 'display:grid', 'url('):
        errors = validate_gzh_html(f'<article style="background:#fff;">{bad}</article>')
        assert errors, bad


def test_extract_html_from_fence_and_plain():
    fence = '```html\n<article><p>围栏内容</p></article>\n```\n说明文字'
    assert "<article>" in extract_html(fence)
    plain = "前面的话\n<article style=\"background:#fff;\"><p>直接输出</p></article>\n后面的话"
    assert "<article" in extract_html(plain)
    assert extract_html("no html here") == "no html here"


def test_layout_instruction_contains_theme_and_components(db):
    theme = _theme(db)
    version = db.query(ThemeVersion).filter_by(theme_id=theme.id, version=theme.current_version).one()
    instruction = layout_instruction(theme, version)
    assert "摸鱼绿" in instruction
    assert "cover" in instruction
    assert "section_title" in instruction
    assert "position:fixed" in instruction


def test_render_mode_validation():
    with pytest.raises(StrategyConfigError):
        validate_strategy_config({"render_mode": "magic"})
    with pytest.raises(StrategyConfigError):
        validate_strategy_config({"render_mode": "ai"})
    assert validate_strategy_config({})["render_mode"] == "deterministic"
    assert validate_strategy_config({"render_mode": "ai", "theme_id": "t"})["render_mode"] == "ai"


def test_render_mode_ai_uses_model_html(db):
    _manual_source(db)
    model = ModelConfig(provider="fake", name="render-model", enabled=True)
    db.add(model)
    db.commit()
    strategy = _strategy_with_ai_render(db, model.id)

    job = create_job(db, strategy, "ai-render-ok")
    result = run_job(db, job.id, RenderOkProvider())

    assert result.status == "waiting_review"
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    revision = db.scalar(select(ArticleRevision).where(ArticleRevision.article_id == article.id))
    assert revision is not None
    assert "AI 排版产物" in revision.rendered_html
    fallbacks = db.scalars(
        select(JobEvent).where(JobEvent.job_id == job.id, JobEvent.event_type == "render_fallback")
    ).all()
    assert not fallbacks


def test_render_mode_ai_falls_back_on_invalid_html(db):
    _manual_source(db)
    model = ModelConfig(provider="fake", name="render-model", enabled=True)
    db.add(model)
    db.commit()
    strategy = _strategy_with_ai_render(db, model.id)

    job = create_job(db, strategy, "ai-render-bad")
    result = run_job(db, job.id, RenderBadProvider())

    assert result.status == "waiting_review"
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    revision = db.scalar(select(ArticleRevision).where(ArticleRevision.article_id == article.id))
    assert revision is not None
    assert "<div" not in revision.rendered_html
    fallbacks = db.scalars(
        select(JobEvent).where(JobEvent.job_id == job.id, JobEvent.event_type == "render_fallback")
    ).all()
    assert len(fallbacks) == 1
    assert "不合规" in (fallbacks[0].payload_json or {}).get("reason", "")