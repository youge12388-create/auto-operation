from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from markdown_it import MarkdownIt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ArticleRevision, RenderedVersion, Theme, ThemeVersion


@dataclass(frozen=True)
class ThemeSpec:
    name: str
    slug: str
    description: str
    tokens: dict[str, str]
    css: str


BUILTIN_THEME_SPECS = (
    ThemeSpec(
        name="瑞士蓝格",
        slug="swiss-blue-grid",
        description="白底、细网格和蓝色标题条，适合信息密度高的公众号文章。",
        tokens={"surface": "#FFFFFF", "text": "#182230", "accent": "#1456D8", "muted": "#667085"},
        css="""
.wx-theme-swiss-blue-grid {
  color: #182230;
  background: #FFFFFF;
  font-family: Arial, Helvetica, sans-serif;
  line-height: 1.8;
  padding: 28px 24px;
  border-left: 4px solid #1456D8;
}
.wx-theme-swiss-blue-grid h1,
.wx-theme-swiss-blue-grid h2,
.wx-theme-swiss-blue-grid h3 {
  color: #1456D8;
  line-height: 1.35;
  margin: 1.2em 0 .55em;
}
.wx-theme-swiss-blue-grid h1 {
  border-top: 1px solid #D8E0ED;
  padding-top: 18px;
}
.wx-theme-swiss-blue-grid p { margin: .9em 0; }
.wx-theme-swiss-blue-grid blockquote {
  border-left: 3px solid #1456D8;
  color: #667085;
  margin: 1em 0;
  padding: .2em 1em;
  background: #F4F7FB;
}
.wx-theme-swiss-blue-grid code { background: #F4F7FB; padding: .12em .35em; }
.wx-theme-swiss-blue-grid a { color: #1456D8; }
""",
    ),
    ThemeSpec(
        name="夜航黑金",
        slug="night-flight",
        description="深色背景、金色标题和窄栏正文，适合观点型和复盘型文章。",
        tokens={"surface": "#0B0C0A", "text": "#F4F1EA", "accent": "#FFB800", "muted": "#B8B4AA"},
        css="""
.wx-theme-night-flight {
  color: #F4F1EA;
  background: #0B0C0A;
  font-family: Georgia, 'Times New Roman', serif;
  line-height: 1.85;
  padding: 30px 24px;
}
.wx-theme-night-flight h1,
.wx-theme-night-flight h2,
.wx-theme-night-flight h3 {
  color: #FFB800;
  line-height: 1.35;
  margin: 1.2em 0 .55em;
}
.wx-theme-night-flight p,
.wx-theme-night-flight ul,
.wx-theme-night-flight ol {
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}
.wx-theme-night-flight blockquote { border-left: 3px solid #FFB800; color: #B8B4AA; padding-left: 1em; }
.wx-theme-night-flight code { color: #FFB800; }
.wx-theme-night-flight a { color: #FFB800; }
""",
    ),
    ThemeSpec(
        name="阅读暖页",
        slug="warm-reading",
        description="米白底、棕色正文和宽松段落，适合教程与长文阅读。",
        tokens={"surface": "#E8DCC7", "text": "#3A3028", "accent": "#C66B3D", "muted": "#76695E"},
        css="""
.wx-theme-warm-reading {
  color: #3A3028;
  background: #E8DCC7;
  font-family: Georgia, 'Times New Roman', serif;
  line-height: 1.9;
  padding: 30px 25px;
}
.wx-theme-warm-reading h1,
.wx-theme-warm-reading h2,
.wx-theme-warm-reading h3 {
  color: #C66B3D;
  line-height: 1.35;
  margin: 1.25em 0 .55em;
}
.wx-theme-warm-reading p { margin: 1em 0; }
.wx-theme-warm-reading blockquote { border-left: 3px solid #C66B3D; color: #76695E; padding-left: 1em; }
.wx-theme-warm-reading code { background: #D4B895; padding: .12em .35em; }
.wx-theme-warm-reading a { color: #C66B3D; }
""",
    ),
)



# 微信正文不可靠地支持 style 标签和 class 选择器，内置主题使用标签级内联样式。
INLINE_STYLE_PRESETS: dict[str, dict[str, str]] = {
    "swiss-blue-grid": {
        "article": "background:#FFFFFF;color:#182230;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;font-size:16px;line-height:1.9;padding:28px 22px;",  # noqa: E501
        "h1": "color:#1456D8;font-size:26px;line-height:1.35;margin:0 0 24px;padding-bottom:16px;border-bottom:2px solid #1456D8;",  # noqa: E501
        "h2": "color:#1456D8;font-size:21px;line-height:1.45;margin:34px 0 12px;padding-left:12px;border-left:4px solid #1456D8;",  # noqa: E501
        "h3": "color:#182230;font-size:18px;line-height:1.5;margin:26px 0 10px;",
        "p": "margin:0 0 18px;",
        "blockquote": "margin:22px 0;padding:14px 16px;border-left:4px solid #1456D8;background:#F4F7FB;color:#667085;",
        "code": "padding:2px 5px;background:#F4F7FB;color:#1456D8;",
        "a": "color:#1456D8;text-decoration:none;",
        "img": "display:block;max-width:100%;height:auto;margin:18px auto;",
        "hr": "border:0;border-top:1px solid #D8E0ED;margin:28px 0;",
    },
    "night-flight": {
        "article": "background:#0B0C0A;color:#F4F1EA;font-family:Georgia,'Times New Roman',serif;font-size:16px;line-height:1.9;padding:30px 22px;",  # noqa: E501
        "h1": "color:#FFB800;font-size:26px;line-height:1.35;margin:0 0 26px;padding-bottom:16px;border-bottom:1px solid #5B5137;",  # noqa: E501
        "h2": "color:#FFB800;font-size:21px;line-height:1.45;margin:34px 0 12px;",
        "h3": "color:#F4F1EA;font-size:18px;line-height:1.5;margin:26px 0 10px;",
        "p": "margin:0 0 18px;",
        "blockquote": "margin:22px 0;padding:14px 16px;border-left:4px solid #FFB800;background:#171811;color:#B8B4AA;",
        "code": "padding:2px 5px;background:#171811;color:#FFB800;",
        "a": "color:#FFB800;text-decoration:none;",
        "img": "display:block;max-width:100%;height:auto;margin:18px auto;",
        "hr": "border:0;border-top:1px solid #5B5137;margin:28px 0;",
    },
    "warm-reading": {
        "article": "background:#E8DCC7;color:#3A3028;font-family:Georgia,'Times New Roman',serif;font-size:16px;line-height:1.95;padding:30px 23px;",  # noqa: E501
        "h1": "color:#C66B3D;font-size:26px;line-height:1.35;margin:0 0 26px;padding-bottom:16px;border-bottom:2px solid #C66B3D;",  # noqa: E501
        "h2": "color:#C66B3D;font-size:21px;line-height:1.45;margin:34px 0 12px;",
        "h3": "color:#3A3028;font-size:18px;line-height:1.5;margin:26px 0 10px;",
        "p": "margin:0 0 19px;",
        "blockquote": "margin:22px 0;padding:14px 16px;border-left:4px solid #C66B3D;background:#D8C5A9;color:#76695E;",
        "code": "padding:2px 5px;background:#D8C5A9;color:#8B4729;",
        "a": "color:#A74D2C;text-decoration:none;",
        "img": "display:block;max-width:100%;height:auto;margin:18px auto;",
        "hr": "border:0;border-top:1px solid #C9AA84;margin:28px 0;",
    },
    "neon-lab": {
        "article": "background:#101827;color:#E6EDF7;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;font-size:16px;line-height:1.85;padding:28px 22px;",  # noqa: E501
        "h1": "color:#A3E635;font-size:26px;line-height:1.35;margin:0 0 24px;padding-bottom:16px;border-bottom:1px solid #31445D;",  # noqa: E501
        "h2": "color:#A3E635;font-size:21px;line-height:1.45;margin:34px 0 12px;padding:12px 14px;background:#17253A;",
        "h3": "color:#E6EDF7;font-size:18px;line-height:1.5;margin:26px 0 10px;",
        "p": "margin:0 0 18px;",
        "blockquote": "margin:22px 0;padding:14px 16px;border-left:4px solid #A3E635;background:#17253A;color:#91A4BD;",
        "code": "padding:2px 5px;background:#17253A;color:#A3E635;",
        "a": "color:#A3E635;text-decoration:none;",
        "img": "display:block;max-width:100%;height:auto;margin:18px auto;",
        "hr": "border:0;border-top:1px solid #31445D;margin:28px 0;",
    },
    "you-sir-column": {
        "article": "background:#FAF9F6;color:#202124;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;font-size:16px;line-height:1.9;padding:30px 22px;",  # noqa: E501
        "h1": "color:#202124;font-size:27px;line-height:1.3;margin:0 0 24px;padding-bottom:16px;border-bottom:4px solid #F26B38;",  # noqa: E501
        "h2": "color:#202124;font-size:21px;line-height:1.45;margin:34px 0 12px;padding-left:12px;border-left:4px solid #F26B38;",  # noqa: E501
        "h3": "color:#F26B38;font-size:18px;line-height:1.5;margin:26px 0 10px;",
        "p": "margin:0 0 18px;",
        "blockquote": "margin:22px 0;padding:14px 16px;border-left:4px solid #F26B38;background:#FFF0E9;color:#72757A;",
        "code": "padding:2px 5px;background:#F2E8E1;color:#C14B1E;",
        "a": "color:#C14B1E;text-decoration:none;",
        "img": "display:block;max-width:100%;height:auto;margin:18px auto;",
        "hr": "border:0;border-top:1px solid #E5D8D0;margin:28px 0;",
    },
    "briefing-paper": {
        "article": "background:#F7F5EF;color:#1D1D1B;font-family:Georgia,'Times New Roman',serif;font-size:16px;line-height:1.8;padding:28px 22px;",  # noqa: E501
        "h1": "color:#1D1D1B;font-size:27px;line-height:1.3;margin:0 0 22px;padding-bottom:14px;border-bottom:4px double #1D1D1B;",  # noqa: E501
        "h2": "color:#C53030;font-size:20px;line-height:1.4;margin:30px 0 10px;padding-top:10px;border-top:1px solid #A6A196;",  # noqa: E501
        "h3": "color:#1D1D1B;font-size:18px;line-height:1.45;margin:24px 0 8px;",
        "p": "margin:0 0 16px;",
        "blockquote": "margin:20px 0;padding:12px 14px;border-left:4px solid #C53030;background:#ECE8DE;color:#77736B;",
        "code": "padding:2px 5px;background:#ECE8DE;color:#C53030;",
        "a": "color:#C53030;text-decoration:none;",
        "img": "display:block;max-width:100%;height:auto;margin:18px auto;",
        "hr": "border:0;border-top:1px solid #A6A196;margin:26px 0;",
    },
}

BUILTIN_THEME_SPECS = BUILTIN_THEME_SPECS + (
    ThemeSpec(name="Neon Lab", slug="neon-lab", description="Deep blue and fluorescent green for AI product updates.", tokens={"surface":"#101827","text":"#E6EDF7","accent":"#A3E635","muted":"#91A4BD"}, css=".wx-theme-neon-lab{background:#101827;color:#E6EDF7;}"),  # noqa: E501
    ThemeSpec(name="You Sir Column", slug="you-sir-column", description="A warm editorial column for 游sir brand content.", tokens={"surface":"#FAF9F6","text":"#202124","accent":"#F26B38","muted":"#72757A"}, css=".wx-theme-you-sir-column{background:#FAF9F6;color:#202124;}"),  # noqa: E501
    ThemeSpec(name="Briefing Paper", slug="briefing-paper", description="A newspaper-like briefing layout for daily AI news.", tokens={"surface":"#F7F5EF","text":"#1D1D1B","accent":"#C53030","muted":"#77736B"}, css=".wx-theme-briefing-paper{background:#F7F5EF;color:#1D1D1B;}"),  # noqa: E501
)
def ensure_builtin_themes(db: Session) -> None:
    for spec in BUILTIN_THEME_SPECS:
        theme = db.scalar(select(Theme).where(Theme.slug == spec.slug))
        if theme is None:
            theme = Theme(
                name=spec.name,
                slug=spec.slug,
                description=spec.description,
                enabled=True,
                is_builtin=True,
                current_version=1,
            )
            db.add(theme)
            db.flush()
        version = db.scalar(select(ThemeVersion).where(ThemeVersion.theme_id == theme.id, ThemeVersion.version == 1))
        if version is None:
            db.add(ThemeVersion(theme_id=theme.id, version=1, tokens_json={**spec.tokens, "inline_styles": INLINE_STYLE_PRESETS.get(spec.slug, {})}, css_text=spec.css))  # noqa: E501
    db.flush()


def render_markdown(content_markdown: str) -> str:
    return MarkdownIt("commonmark", {"breaks": True, "html": False}).render(content_markdown)


def render_with_theme(content_markdown: str, theme: Theme, version: ThemeVersion) -> str:
    body = render_markdown(content_markdown)
    from lxml import html

    wrapper = html.fragment_fromstring(
        f'<article data-theme="{theme.slug}" data-theme-version="{version.version}">{body}</article>',
        create_parent=False,
    )
    inline_styles = (version.tokens_json or {}).get("inline_styles") or INLINE_STYLE_PRESETS.get(theme.slug, {})
    wrapper.set("style", inline_styles.get("article", ""))
    for tag, style in inline_styles.items():
        if tag == "article":
            continue
        for element in wrapper.iter(tag):
            existing = element.get("style", "")
            element.set("style", f"{style}{existing}" if existing else style)
    return html.tostring(wrapper, encoding="unicode", method="html")

def render_revision(db: Session, revision: ArticleRevision, theme: Theme) -> RenderedVersion:
    if not theme.enabled:
        raise ValueError("theme is disabled")
    version = db.scalar(
        select(ThemeVersion).where(
            ThemeVersion.theme_id == theme.id,
            ThemeVersion.version == theme.current_version,
        )
    )
    if version is None:
        raise ValueError("theme version is missing")
    rendered = db.scalar(
        select(RenderedVersion).where(
            RenderedVersion.article_revision_id == revision.id,
            RenderedVersion.theme_version_id == version.id,
        )
    )
    fresh_html = render_with_theme(revision.content_markdown, theme, version)
    if rendered is None:
        rendered = RenderedVersion(
            article_revision_id=revision.id,
            theme_version_id=version.id,
            html=fresh_html,
        )
        db.add(rendered)
        db.flush()
    elif "<style" in rendered.html or "data-theme=" not in rendered.html:
        # Refresh renders created by the pre-inline-style renderer without changing
        # the revision or theme version identity.
        rendered.html = fresh_html
        db.flush()
    return rendered


def theme_tokens(theme: Theme, version: ThemeVersion) -> dict[str, Any]:
    return {
        "theme_id": theme.id,
        "slug": theme.slug,
        "version": version.version,
        "tokens": version.tokens_json,
    }
