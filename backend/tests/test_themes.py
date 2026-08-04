from content_ops.api import add_theme, copy_theme, disable_theme, list_themes, preview_article_theme, update_theme
from content_ops.models import Article, ArticleRevision, Job, RenderedVersion, Strategy, Theme
from content_ops.schemas import ThemeCopy, ThemeCreate, ThemeUpdate
from content_ops.themes import ensure_builtin_themes, render_revision


def make_revision(db):
    strategy = Strategy(name="theme-strategy", objective="test", enabled=True)
    db.add(strategy)
    db.flush()
    job = Job(strategy_id=strategy.id, idempotency_key="theme-job")
    db.add(job)
    db.flush()
    article = Article(job_id=job.id, title="主题测试")
    db.add(article)
    db.flush()
    revision = ArticleRevision(
        article_id=article.id,
        version=1,
        content_markdown="# 标题\n\n正文 **重点**。\n\n<script>alert(1)</script>",
    )
    db.add(revision)
    db.flush()
    return article, revision


def test_builtin_themes_are_seeded_and_rendering_is_idempotent(db):
    _, revision = make_revision(db)
    ensure_builtin_themes(db)
    db.commit()

    themes = db.query(Theme).order_by(Theme.slug).all()
    assert len(themes) == 6
    assert {theme.slug for theme in themes} == {
        "swiss-blue-grid",
        "night-flight",
        "warm-reading",
        "neon-lab",
        "you-sir-column",
        "briefing-paper",
    }

    first = render_revision(db, revision, themes[0])
    first.html = "<style>.legacy{color:red}</style>"
    db.commit()
    second = render_revision(db, revision, themes[0])
    db.commit()

    assert first.id == second.id
    assert f"data-theme=\"{themes[0].slug}\"" in first.html
    assert "<script>" not in first.html
    assert "<style" not in first.html
    assert "style=" in first.html
    assert "&lt;script&gt;" in first.html
    assert db.query(RenderedVersion).count() == 1


def test_switching_theme_preserves_revision_and_creates_separate_rendering(db):
    _, revision = make_revision(db)
    ensure_builtin_themes(db)
    db.commit()
    themes = db.query(Theme).order_by(Theme.slug).all()

    first = render_revision(db, revision, themes[0])
    second = render_revision(db, revision, themes[1])
    db.commit()

    assert first.id != second.id
    assert revision.version == 1
    assert revision.content_markdown.startswith("# 标题")
    assert db.query(RenderedVersion).count() == 2

def test_theme_api_lists_builtins_and_previews_revision(db):
    article, revision = make_revision(db)
    listed = list_themes(None, db)

    preview = preview_article_theme(article.id, revision.id, listed[0].id, None, db)

    assert len(listed) == 6
    assert preview.theme_version == 1
    assert f"data-theme=\"{listed[0].slug}\"" in preview.html

def test_theme_lifecycle_versions_and_copy(db):
    created = add_theme(
        ThemeCreate(name="测试主题", slug="test-theme", description="初始", tokens={"accent": "#123456"}, css=".x{}"),
        None,
        db,
    )
    updated = update_theme(
        created.id,
        ThemeUpdate(description="更新", tokens={"accent": "#654321"}, css=".x{color:red}"),
        None,
        db,
    )
    assert updated.current_version == 2
    copied = copy_theme(
        created.id,
        ThemeCopy(name="测试主题副本", slug="test-theme-copy"),
        None,
        db,
    )
    assert copied.current_version == 1
    assert copied.tokens["accent"] == "#654321"
    disabled = disable_theme(created.id, None, db)
    assert disabled.enabled is False