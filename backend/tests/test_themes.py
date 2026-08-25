from sqlalchemy import select

from content_ops.api import add_theme, copy_theme, disable_theme, list_themes, preview_article_theme, update_theme
from content_ops.models import Article, ArticleRevision, Job, RenderedVersion, Strategy, Theme
from content_ops.schemas import ThemeCopy, ThemeCreate, ThemeUpdate
from content_ops.themes import ensure_builtin_themes, recommend_editorial_theme, render_revision, validate_gzh_html


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
    assert len(themes) == 13
    assert {theme.slug for theme in themes} == {
        "moyu-green",
        "red-white",
        "graphite-minimal",
        "zen-whitespace",
        "moyu-ticket",
        "olive-journal",
        "aws-classic-blue",
        "aws-elegant-purple",
        "aws-warm-orange",
        "aws-minimal-black",
        "editorial-notes",
        "editorial-casebook",
        "editorial-playbook",
    }

    first = render_revision(db, revision, themes[0])
    first.html = "<style>.legacy{color:red}</style>"
    db.commit()
    second = render_revision(db, revision, themes[0])
    db.commit()

    assert first.id == second.id
    assert f'data-theme="{themes[0].slug}"' in first.html
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

    assert len(listed) == 13
    assert preview.theme_version == 1
    assert f'data-theme="{listed[0].slug}"' in preview.html


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


def test_custom_theme_tokens_are_inlined_for_wechat_rendering(db):
    _, revision = make_revision(db)
    theme = add_theme(
        ThemeCreate(
            name="Custom color",
            slug="custom-color",
            tokens={"surface": "#112233", "text": "#EEF0F2", "accent": "#FF3366", "muted": "#AABBCC"},
        ),
        None,
        db,
    )

    rendered = render_revision(db, revision, db.get(Theme, theme.id))

    assert "background:#112233" in rendered.html
    assert "color:#FF3366" in rendered.html


def test_aiworkskills_themes_keep_their_distinctive_inline_styles(db):
    _, revision = make_revision(db)
    revision.content_markdown = """# 标题

## 章节

### 小节

#### 四级标题

正文 **重点**。

> 引言

- 列表

```python
print('hello')
```

---
"""
    ensure_builtin_themes(db)
    db.commit()

    expected_fragments = {
        "aws-classic-blue": "background:#0F2A44",
        "aws-elegant-purple": "border-left:5px solid #DEC6FB",
        "aws-warm-orange": "color:#FDBA74",
        "aws-minimal-black": "letter-spacing:4px",
        "editorial-casebook": "border-top:4px solid #8E4A3C",
        "editorial-playbook": "border-left:3px solid #315B71",
    }
    for slug, fragment in expected_fragments.items():
        theme = db.scalar(select(Theme).where(Theme.slug == slug))
        assert theme is not None
        rendered = render_revision(db, revision, theme)
        assert fragment in rendered.html


def test_editorial_notes_uses_a_lede_and_quiet_section_anchors(db):
    _, revision = make_revision(db)
    revision.content_markdown = """# 不把文章写成模板，是编辑的基本功

真正的阅读感，不来自更多颜色和卡片，而来自内容在页面里有自己的呼吸。

## 先把首段留给读者

第二段回到正常正文，强调 **关键信息**，但不抢走叙事本身。

> 好的排版不是替文字说话，而是让文字更容易被听见。
"""
    ensure_builtin_themes(db)
    db.commit()
    theme = db.scalar(select(Theme).where(Theme.slug == "editorial-notes"))

    assert theme is not None
    rendered = render_revision(db, revision, theme)

    assert 'font-size:18px' in rendered.html
    assert 'text-indent:2em' in rendered.html
    assert 'border-left:3px solid #B34A31' in rendered.html
    assert 'PART' not in rendered.html
    assert 'THE END' not in rendered.html
    assert rendered.html.count('但不抢走叙事本身') == 1
    assert validate_gzh_html(rendered.html) == []

def test_editorial_theme_recommendation_matches_article_structure():
    playbook_slug, playbook_reason = recommend_editorial_theme(
        "\u5982\u4f55\u642d\u5efa\u5185\u5bb9\u5de5\u4f5c\u6d41",
        ["\u51c6\u5907", "\u6b65\u9aa4", "\u8fd0\u884c\u6e05\u5355"],
        (
            "## \u7b2c\u4e00\u6b65\n\u5148\u62c6\u89e3\u95ee\u9898\n\n"
            "## \u7b2c\u4e8c\u6b65\n\u5efa\u7acb\u6e05\u5355\n\n"
            "## \u7b2c\u4e09\u6b65\n\u590d\u76d8"
        ),
    )
    casebook_slug, casebook_reason = recommend_editorial_theme(
        "\u4e00\u6b21\u9879\u76ee\u590d\u76d8",
        ["\u6848\u4f8b\u80cc\u666f", "\u95ee\u9898", "\u7ed3\u679c"],
        (
            "## \u6848\u4f8b\u80cc\u666f\n\u9879\u76ee\u5b9e\u8df5\n\n"
            "## \u95ee\u9898\n\u4e00\u6b21\u8df5\u5751\n\n"
            "## \u7ed3\u679c\n\u589e\u957f\u7ed3\u8bba"
        ),
    )
    notes_slug, notes_reason = recommend_editorial_theme(
        "\u4e00\u4e2a\u89c2\u70b9",
        [],
        "## \u5f00\u573a\n\u8bb2\u4e00\u4e2a\u6545\u4e8b",
    )

    assert (playbook_slug, playbook_reason) == ("editorial-playbook", "检测到步骤、方法或清单结构")
    assert (casebook_slug, casebook_reason) == ("editorial-casebook", "检测到案例、复盘或结果结构")
    assert (notes_slug, notes_reason) == ("editorial-notes", "默认使用观点长文结构")