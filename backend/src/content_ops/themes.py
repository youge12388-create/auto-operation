# ruff: noqa: E501 - inline WeChat HTML/CSS templates are intentionally kept readable as complete fragments.
from __future__ import annotations

import html as html_lib
from dataclasses import dataclass
from typing import Any

from lxml import html as lxml_html
from markdown_it import MarkdownIt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, ArticleRevision, RenderedVersion, Theme, ThemeVersion

# 内置排版主题移植自 https://github.com/crossoverJie/gzh-design-skill
# （gzh-design-skill · 公众号排版技能，甲木 × 摸鱼小李，AGPL-3.0）
# 组件化设计语言同时参考 https://github.com/iniwap/AIWriteX 的模板结构。
# 每套主题由 HTML 组件（封面、编号章节、金句卡、列表卡、数据表、代码块、图片、结语）装配而成，
# 样式全内联、不使用 class/style/div/position:fixed 等微信会过滤的写法。


@dataclass(frozen=True)
class ThemeSpec:
    name: str
    slug: str
    description: str
    tokens: dict[str, str]
    css: str


_SANS = "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif"
_SERIF = "'Noto Serif SC',Georgia,'Times New Roman',serif"

BUILTIN_THEME_SPECS = (
    ThemeSpec(
        name="摸鱼绿",
        slug="moyu-green",
        description="绿色杂志风：渐变封面、胶囊标签、信息密度高，适合教程、测评、清单、工具盘点。",
        tokens={
            "surface": "#FFFFFF",
            "text": "#374151",
            "accent": "#059669",
            "muted": "#9CA3AF",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-moyu-green{background:#ffffff;color:#374151;}",
    ),
    ThemeSpec(
        name="红白色系",
        slug="red-white",
        description="经典编辑风：红底白字引言卡、编号章节、红色克制点睛，适合观点、深度分析、盘点。",
        tokens={
            "surface": "#FFFFFF",
            "text": "#1C1917",
            "accent": "#DC2626",
            "muted": "#9CA3AF",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-red-white{background:#ffffff;color:#374151;}",
    ),
    ThemeSpec(
        name="石墨极简",
        slug="graphite-minimal",
        description="现代极简：超大水印编号、上下细线引言卡、全灰阶，适合设计、科技评论、高端品牌。",
        tokens={
            "surface": "#FFFFFF",
            "text": "#52525B",
            "accent": "#52525B",
            "muted": "#A1A1AA",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-graphite-minimal{background:#ffffff;color:#52525B;}",
    ),
    ThemeSpec(
        name="留白禅意",
        slug="zen-whitespace",
        description="纯白留白：衬线大字引言、小号墨绿英文章节标签、呼吸感最强，适合禅意随笔。",
        tokens={
            "surface": "#FFFFFF",
            "text": "#525252",
            "accent": "#4A5D52",
            "muted": "#A3A3A3",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-zen-whitespace{background:#FFFFFF;color:#525252;}",
    ),
    ThemeSpec(
        name="摸鱼票据",
        slug="moyu-ticket",
        description="票据/门票隐喻：硬阴影黑边卡片、绿色撕票线、星级编号，适合测评与工具对比。",
        tokens={
            "surface": "#FFFEF8",
            "text": "#555555",
            "accent": "#059669",
            "muted": "#999999",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-moyu-ticket{background:#ffffff;color:#555;}",
    ),
    ThemeSpec(
        name="橄榄手记",
        slug="olive-journal",
        description="编辑部内刊：米白纸感、深色摘要条、橙色点睛，适合内刊手记、深度评测、案例复盘。",
        tokens={
            "surface": "#FDFDF8",
            "text": "#4D4F46",
            "accent": "#ED7B2F",
            "muted": "#9EA096",
            "font": "'IBM Plex Sans',-apple-system,system-ui,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif",  # noqa: E501
            "serif": _SERIF,
        },
        css=".wx-theme-olive-journal{background:#fdfdf8;color:#4d4f46;}",
    ),
    # 下面四套样式移植自 aiworkskills/wechat-article-skills（Apache-2.0）。
    ThemeSpec(
        name="经典蓝（AI Work Skills）",
        slug="aws-classic-blue",
        description="经典蓝编辑风：蓝色标题条和渐变分隔线，适合科技、商业类公众号。",
        tokens={
            "surface": "#FFFFFF", "text": "#3A3A3A", "accent": "#1A6DB5", "muted": "#999999", "font": _SANS, "serif": _SERIF,
        },
        css=".wx-theme-aws-classic-blue{background:#fff;color:#3a3a3a;}",
    ),
    ThemeSpec(
        name="优雅紫（AI Work Skills）",
        slug="aws-elegant-purple",
        description="优雅紫圆润风：淡紫描边、较宽字距，适合文化、美学类公众号。",
        tokens={
            "surface": "#FFFFFF", "text": "#595959", "accent": "#664D9D", "muted": "#DEC6FB", "font": _SANS, "serif": _SERIF,
        },
        css=".wx-theme-aws-elegant-purple{background:#fff;color:#595959;}",
    ),
    ThemeSpec(
        name="暖橙（AI Work Skills）",
        slug="aws-warm-orange",
        description="暖橙活力风：橙色标题条与短分隔线，适合自媒体、创业类公众号。",
        tokens={
            "surface": "#FFFFFF", "text": "#3E3E3E", "accent": "#EF7060", "muted": "#999999", "font": _SANS, "serif": _SERIF,
        },
        css=".wx-theme-aws-warm-orange{background:#fff;color:#3e3e3e;}",
    ),
    ThemeSpec(
        name="极简黑（AI Work Skills）",
        slug="aws-minimal-black",
        description="极简黑留白风：轻字重、大字距和居中引言，适合思想深度类公众号。",
        tokens={
            "surface": "#FFFFFF", "text": "#333333", "accent": "#18181B", "muted": "#BBBBBB", "font": _SANS, "serif": _SERIF,
        },
        css=".wx-theme-aws-minimal-black{background:#fff;color:#333;}",
    ),
    ThemeSpec(
        name="编辑留白",
        slug="editorial-notes",
        description="编辑式长文：首段导语、舒展正文、无营销标签的章节锚点，适合观点、叙事和深度复盘。",
        tokens={
            "surface": "#FFFEFA",
            "text": "#2D2A26",
            "accent": "#B34A31",
            "muted": "#A89F94",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-editorial-notes{background:#fffefa;color:#2d2a26;}",
    ),
    ThemeSpec(
        name="编辑留白 · 案例复盘",
        slug="editorial-casebook",
        description="案例复盘版：强调观察、转折和结论的层次，适合项目实践、增长复盘与经验沉淀。",
        tokens={
            "surface": "#FFFDF9",
            "text": "#302C28",
            "accent": "#8E4A3C",
            "muted": "#A99E94",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-editorial-casebook{background:#fffdf9;color:#302c28;}",
    ),
    ThemeSpec(
        name="编辑留白 · 方法清单",
        slug="editorial-playbook",
        description="方法清单版：用真实步骤锚点组织阅读，适合教程、指南、流程与工具方法。",
        tokens={
            "surface": "#FCFDFC",
            "text": "#263542",
            "accent": "#315B71",
            "muted": "#AAB7BD",
            "font": _SANS,
            "serif": _SERIF,
        },
        css=".wx-theme-editorial-playbook{background:#fcfdfc;color:#263542;}",
    ),
)


# 行内元素样式（正文段落内部出现 strong/code/a/em 时注入）。
INLINE_STYLE_PRESETS: dict[str, dict[str, str]] = {
    "moyu-green": {
        "article": f"background:#ffffff;color:#374151;font-family:{_SANS};font-size:15px;line-height:1.9;letter-spacing:0.5px;max-width:677px;margin:0 auto;padding:0 18px;",  # noqa: E501
        "strong": "color:#059669;font-weight:700;",
        "code": "padding:1px 6px;border-radius:4px;background:#F1F5F9;color:#059669;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;",  # noqa: E501
        "a": "color:#059669;text-decoration:none;",
        "em": "color:#374151;font-style:italic;",
    },
    "red-white": {
        "article": f"background:#ffffff;color:#374151;font-family:{_SANS};font-size:15px;line-height:1.8;letter-spacing:0.5px;max-width:677px;margin:0 auto;padding:0 10px;",  # noqa: E501
        "strong": "color:#991B1B;font-weight:700;",
        "code": "padding:1px 6px;border-radius:4px;background:#FEE2E2;color:#991B1B;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:14px;",  # noqa: E501
        "a": "color:#DC2626;text-decoration:none;",
        "em": "color:#374151;font-style:italic;",
    },
    "graphite-minimal": {
        "article": f"background:#ffffff;color:#52525B;font-family:{_SANS};font-size:15px;line-height:1.8;letter-spacing:0.3px;max-width:677px;margin:0 auto;padding:0 10px;",  # noqa: E501
        "strong": "color:#27272A;font-weight:700;",
        "code": "padding:2px 6px;border-radius:4px;background:#F4F4F5;color:#27272A;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:14px;",  # noqa: E501
        "a": "color:#52525B;text-decoration:none;",
        "em": "color:#52525B;font-style:italic;",
    },
    "zen-whitespace": {
        "article": f"background:#FFFFFF;color:#525252;font-family:{_SANS};font-size:15px;line-height:1.9;letter-spacing:0.3px;max-width:677px;margin:0 auto;padding:0 16px;",  # noqa: E501
        "strong": "color:#2B2B2B;font-weight:600;",
        "code": "padding:1px 6px;border-radius:4px;background:#EEF3F0;color:#3D5046;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:14px;",  # noqa: E501
        "a": "color:#4A5D52;text-decoration:none;",
        "em": "color:#525252;font-style:italic;",
    },
    "moyu-ticket": {
        "article": f"background:#ffffff;color:#555;font-family:{_SANS};font-size:14px;line-height:1.9;letter-spacing:0.5px;max-width:677px;margin:0 auto;padding:0 18px;",  # noqa: E501
        "strong": "color:#059669;font-weight:700;",
        "code": "padding:2px 6px;border-radius:4px;background:#F3F4F6;color:#1F2937;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;font-weight:600;",  # noqa: E501
        "a": "color:#059669;text-decoration:none;",
        "em": "color:#555;font-style:italic;",
    },
    "olive-journal": {
        "article": f"background:#fdfdf8;color:#4d4f46;font-family:{_SANS};font-size:14px;line-height:1.9;max-width:677px;margin:0 auto;padding:8px 10px;",  # noqa: E501
        "strong": "color:#23251d;font-weight:700;",
        "code": "padding:2px 6px;border-radius:4px;background:#eeefe9;color:#23251d;border:1px solid #b6b7af;font-family:ui-monospace,Menlo,Monaco,Consolas,monospace;font-size:13px;",  # noqa: E501
        "a": "color:#ed7b2f;text-decoration:none;",
        "em": "color:#4d4f46;font-style:italic;",
    },
    "aws-classic-blue": {
        "article": f"background:#fff;color:#3a3a3a;font-family:{_SANS};font-size:16px;line-height:1.8;letter-spacing:0.5px;max-width:677px;margin:0 auto;padding:0 18px;",
        "strong": "color:#1A6DB5;font-weight:bold;",
        "code": "color:#1A6DB5;background:#EBF5FF;padding:2px 6px;border-radius:3px;font-size:90%;",
        "a": "color:#1A6DB5;text-decoration:none;border-bottom:1px solid #1A6DB5;",
        "em": "font-style:italic;color:#555;",
    },
    "aws-elegant-purple": {
        "article": f"background:#fff;color:#595959;font-family:{_SANS};font-size:16px;line-height:1.75;letter-spacing:2px;max-width:677px;margin:0 auto;padding:0 18px;",
        "strong": "color:#595959;font-weight:bold;",
        "code": "color:#664D9D;background:#F6EEFF;padding:2px 8px;border-radius:10px;font-size:90%;",
        "a": "color:#664D9D;font-weight:normal;border-bottom:1px solid #664D9D;",
        "em": "font-style:normal;color:#595959;background:#F6EEFF;",
    },
    "aws-warm-orange": {
        "article": f"background:#fff;color:#3e3e3e;font-family:{_SANS};font-size:16px;line-height:1.8;max-width:677px;margin:0 auto;padding:0 18px;",
        "strong": "color:#EF7060;font-weight:bold;",
        "code": "color:#E96900;background:#F3F3F3;padding:2px 6px;border-radius:4px;font-size:90%;",
        "a": "color:#EF7060;text-decoration:none;border-bottom:1px solid #EF7060;",
        "em": "font-style:italic;color:#555;",
    },
    "aws-minimal-black": {
        "article": f"background:#fff;color:#333;font-family:{_SANS};font-size:16px;line-height:2;letter-spacing:0.5px;max-width:677px;margin:0 auto;padding:0 18px;",
        "strong": "color:#18181B;font-weight:700;",
        "code": "color:#18181B;background:#F4F4F5;padding:2px 6px;border-radius:2px;font-size:90%;",
        "a": "color:#18181B;text-decoration:underline;text-underline-offset:3px;",
        "em": "font-style:italic;color:#666;",
    },
    "editorial-notes": {
        "article": f"background:#FFFEFA;color:#2D2A26;font-family:{_SANS};font-size:16px;line-height:1.95;letter-spacing:0.45px;max-width:677px;margin:0 auto;padding:8px 20px 34px;",
        "strong": "color:#2D2A26;font-weight:700;background:linear-gradient(transparent 64%,#F3DDD1 0);",
        "code": "padding:1px 5px;background:#F3EEE8;color:#7D3828;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;",
        "a": "color:#8E3E2B;text-decoration:none;border-bottom:1px solid #D8AD9F;",
        "em": "color:#6B625A;font-style:italic;",
    },
    "editorial-casebook": {
        "article": f"background:#FFFDF9;color:#302C28;font-family:{_SANS};font-size:16px;line-height:1.95;letter-spacing:0.4px;max-width:677px;margin:0 auto;padding:10px 20px 34px;",
        "strong": "color:#5F3027;font-weight:700;background:linear-gradient(transparent 66%,#F0D8CF 0);",
        "code": "padding:1px 5px;background:#F5EEEA;color:#6B3429;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;",
        "a": "color:#7D4033;text-decoration:none;border-bottom:1px solid #D8B7AC;",
        "em": "color:#6D625B;font-style:italic;",
    },
    "editorial-playbook": {
        "article": f"background:#FCFDFC;color:#263542;font-family:{_SANS};font-size:16px;line-height:1.9;letter-spacing:0.35px;max-width:677px;margin:0 auto;padding:10px 20px 34px;",
        "strong": "color:#263542;font-weight:700;background:linear-gradient(transparent 66%,#D6E7ED 0);",
        "code": "padding:1px 5px;background:#EEF4F5;color:#284E60;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;",
        "a": "color:#315B71;text-decoration:none;border-bottom:1px solid #A9C6D1;",
        "em": "color:#52636C;font-style:italic;",
    },
}


# 组件模板：{surface}/{text}/{accent}/{muted}/{font}/{serif} 由主题 tokens 注入，
# {title}/{num}/{content}/{items}/{lang}/{code}/{src}/{alt} 由渲染逻辑注入。
DEFAULT_COMPONENTS: dict[str, str] = {
    "paragraph": '<p style="margin:0 0 16px;font-size:15px;line-height:1.9;text-align:justify;color:{text};">{content}</p>',  # noqa: E501
    "bullet_list": '<ul style="margin:0 0 18px;padding-left:22px;">{items}</ul>',
    "bullet_item": '<li style="font-size:15px;line-height:1.9;color:{text};margin-bottom:8px;">{content}</li>',
    "ordered_list": '<ol style="margin:0 0 18px;padding-left:22px;">{items}</ol>',
    "ordered_item": '<li style="font-size:15px;line-height:1.9;color:{text};margin-bottom:8px;">{content}</li>',
    "code_block": '<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#1E293B;box-shadow:0 4px 16px -8px rgba(15,23,42,0.4);"><section style="display:flex;align-items:center;padding:9px 14px;background:#0F172A;"><span style="width:10px;height:10px;border-radius:50%;background:#FF5F56;margin-right:7px;"><br></span><span style="width:10px;height:10px;border-radius:50%;background:#FFBD2E;margin-right:7px;"><br></span><span style="width:10px;height:10px;border-radius:50%;background:#27C93F;margin-right:7px;"><br></span><span style="margin-left:12px;font-size:12px;color:#64748B;font-family:Consolas,Monaco,monospace;letter-spacing:1px;">{lang}</span></section><section style="padding:11px 14px;">{code}</section></section>',  # noqa: E501
    "image": '<section style="margin:0 0 10px;background:#fff;border-radius:12px;padding:6px;border:1px solid #E5E7EB;box-shadow:0 4px 12px -2px rgba(0,0,0,0.08);"><img src="{src}" alt="{alt}" style="max-width:100%;height:auto;display:block;margin:0 auto;border-radius:8px;"></section>',  # noqa: E501
    "divider": '<section style="margin:24px 0;border-top:1px solid #E5E7EB;"><br></section>',
    "cover": '<section style="margin:0 0 24px;padding:26px 20px 22px;border-radius:16px;background:{accent};"><p style="margin:0 0 8px;font-size:11px;font-weight:700;letter-spacing:3px;color:rgba(255,255,255,0.85);">公众号精选</p><h1 style="margin:0;font-size:26px;font-weight:900;line-height:1.3;color:#fff;">{title}</h1></section>',  # noqa: E501
    "section_title": '<section style="margin:32px 0 16px;"><section style="display:flex;align-items:center;gap:14px;"><section style="text-align:center;flex-shrink:0;"><p style="margin:0;font-size:26px;font-weight:900;color:{accent};line-height:1;letter-spacing:-1px;">{num}</p><p style="margin:0;font-size:8px;font-weight:700;color:{muted};letter-spacing:2px;">PART</p></section><span style="width:1px;height:32px;background:#E5E7EB;"><br></span><section><p style="margin:0;font-size:17px;font-weight:900;color:{text};letter-spacing:0.3px;">{title}</p></section></section></section>',  # noqa: E501
    "subsection_title": '<p style="margin:26px 0 12px;font-size:16px;font-weight:800;color:{text};line-height:1.5;padding-left:12px;border-left:4px solid {accent};">{title}</p>',  # noqa: E501
    "minor_title": '<p style="margin:20px 0 10px;font-size:15px;font-weight:700;color:{text};line-height:1.5;">{title}</p>',
    "quote": '<section style="margin:0 0 22px;background:{surface};border:1px dashed {muted};border-radius:8px;padding:14px 16px;">{content}</section>',  # noqa: E501
    "code_line": '<p style="margin:0;font-family:\'SF Mono\',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#E2E8F0;">{code}</p>',  # noqa: E501
    "ending": '<section style="margin:28px 0 0;padding:14px 0;border-top:1px solid {muted};text-align:center;"><p style="margin:0;font-size:12px;font-weight:700;letter-spacing:4px;color:{muted};">THE END</p></section>',  # noqa: E501
}

COMPONENT_PRESETS: dict[str, dict[str, str]] = {
    "moyu-green": {
        "cover": '<section style="margin:0 0 24px;background:#fff;border:1.5px solid rgba(5,150,105,0.15);border-radius:20px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);"><section style="padding:26px 24px 22px;"><section style="display:flex;align-items:center;gap:8px;margin-bottom:18px;"><span style="width:6px;height:6px;background:#059669;border-radius:50%;"><br></span><span style="font-size:11px;font-weight:700;letter-spacing:3px;color:#059669;">公众号精选</span><span style="flex:1;height:1px;background:linear-gradient(to right,rgba(5,150,105,0.12),transparent);"><br></span></section><h1 style="margin:0;font-size:24px;font-weight:900;color:#111827;line-height:1.25;letter-spacing:-1px;">{title}</h1></section><section style="background:linear-gradient(135deg,#059669,#10B981);padding:10px 24px;"><p style="margin:0;font-size:12px;color:rgba(255,255,255,0.9);font-weight:600;letter-spacing:1px;">MOYU · 绿色杂志风</p></section></section>',  # noqa: E501
        "section_title": '<section style="margin:36px 0 18px;"><section style="display:flex;align-items:center;gap:16px;"><section style="text-align:center;flex-shrink:0;"><p style="margin:0;font-size:28px;font-weight:900;color:#059669;line-height:1;letter-spacing:-2px;">{num}</p><p style="margin:0;font-size:8px;font-weight:700;color:#D1D5DB;letter-spacing:2px;">PART</p></section><span style="width:1px;height:36px;background:#E5E7EB;"><br></span><section><p style="margin:0;font-size:17px;font-weight:900;color:#111827;letter-spacing:0.3px;">{title}</p><p style="margin:0;font-size:11px;font-weight:600;color:#9CA3AF;letter-spacing:1.5px;">MOYU CHAPTER</p></section></section></section>',  # noqa: E501
        "subsection_title": '<p style="margin:28px 0 14px;font-size:16px;font-weight:900;color:#111827;line-height:1.5;"><span style="background:linear-gradient(180deg,transparent 65%,#FDE68A 65%);padding:0 4px;">{title}</span></p>',  # noqa: E501
        "quote": '<section style="margin:0 0 22px;background:#F9FAFB;border:1px dashed #D1D5DB;border-radius:8px;padding:12px 16px;text-align:justify;">{content}</section>',  # noqa: E501
        "ending": '<section style="margin:28px 0 0;background:linear-gradient(135deg,#059669,#10B981);border-radius:12px;padding:14px 16px;text-align:center;"><p style="margin:0;font-size:12px;font-weight:700;letter-spacing:4px;color:#fff;">THE END · 感谢阅读</p></section>',  # noqa: E501
    },
    "red-white": {
        "cover": '<section style="margin:0 0 26px;background:#ffffff;border-radius:12px;box-shadow:0 4px 24px -4px rgba(220,38,38,0.15);padding:26px 22px 22px;overflow:hidden;"><p style="margin:0;font-size:42px;color:#DC2626;font-weight:900;line-height:0.6;">"</p><h1 style="margin:14px 0 0;font-size:23px;font-weight:800;color:#1C1917;line-height:1.4;">{title}</h1></section>',  # noqa: E501
        "section_title": '<section style="margin:36px 0 14px;"><p style="margin:0 0 8px;font-size:12px;font-weight:800;color:#DC2626;letter-spacing:2px;">PART {num}</p><h2 style="margin:0;font-size:21px;font-weight:800;color:#1C1917;line-height:1.4;padding-bottom:10px;border-bottom:2px solid #FEE2E2;">{title}</h2></section>',  # noqa: E501
        "subsection_title": '<p style="margin:26px 0 12px;font-size:16px;font-weight:800;color:#1C1917;line-height:1.5;padding-left:12px;border-left:4px solid #DC2626;">{title}</p>',  # noqa: E501
        "quote": '<section style="margin:0 0 22px;background:#FEF2F2;border-radius:0 10px 10px 0;border-left:4px solid #DC2626;padding:14px 18px;">{content}</section>',  # noqa: E501
        "ending": '<section style="margin:28px 0 0;border-top:1px solid #FEE2E2;padding:16px 0 6px;text-align:center;"><p style="margin:0;font-size:11px;font-weight:800;letter-spacing:4px;color:#DC2626;">END · RED &amp; WHITE</p></section>',  # noqa: E501
    },
    "graphite-minimal": {
        "cover": '<section style="margin:0 0 32px;padding:36px 18px;border-top:1px solid #E4E4E7;border-bottom:1px solid #E4E4E7;text-align:center;"><p style="margin:0 0 14px;font-size:10px;font-weight:600;letter-spacing:4px;color:#A1A1AA;">GRAPHITE · 现代极简</p><h1 style="margin:0;font-size:24px;font-weight:800;color:#27272A;line-height:1.4;letter-spacing:-0.5px;">{title}</h1></section>',  # noqa: E501
        "section_title": '<section style="margin:40px 0 16px;"><p style="margin:0 0 2px;font-size:52px;font-weight:900;color:#E4E4E7;line-height:0.9;letter-spacing:-2px;">{num}</p><h2 style="margin:8px 0 0;font-size:20px;font-weight:800;color:#27272A;line-height:1.4;padding-bottom:10px;border-bottom:1px solid #E4E4E7;">{title}</h2></section>',  # noqa: E501
        "subsection_title": '<p style="margin:28px 0 14px;font-size:15px;font-weight:800;color:#27272A;line-height:1.4;padding-left:12px;border-left:3px solid #52525B;">{title}</p>',  # noqa: E501
        "quote": '<section style="margin:0 0 26px;border-left:3px solid #52525B;padding:14px 0 14px 22px;">{content}</section>',  # noqa: E501
        "ending": '<section style="margin:32px 0 0;text-align:center;"><span style="display:inline-block;width:40px;height:1px;background:#E4E4E7;"><br></span><p style="margin:12px 0 0;font-size:10px;font-weight:600;letter-spacing:4px;color:#A1A1AA;">END</p></section>',  # noqa: E501
    },
    "zen-whitespace": {
        "cover": '<section style="margin:0 0 36px;padding:36px 18px;border-top:1px solid #E8E8E8;border-bottom:1px solid #E8E8E8;text-align:center;"><p style="margin:0 0 14px;font-size:10px;font-weight:600;letter-spacing:4px;color:#4A5D52;">ZEN · 留白禅意</p><h1 style="margin:0;font-family:\'Noto Serif SC\',Georgia,\'Times New Roman\',serif;font-size:22px;font-weight:600;color:#2B2B2B;line-height:1.5;letter-spacing:0.8px;">{title}</h1></section>',  # noqa: E501
        "section_title": '<section style="margin:48px 0 18px;"><p style="margin:0 0 10px;font-size:10px;color:#4A5D52;font-weight:600;letter-spacing:4px;">{num} · CHAPTER</p><h2 style="margin:0 0 14px;font-family:\'Noto Serif SC\',Georgia,\'Times New Roman\',serif;font-size:21px;font-weight:700;color:#2B2B2B;line-height:1.4;letter-spacing:0.5px;">{title}</h2><span style="display:inline-block;width:40px;height:2px;background:#4A5D52;"><br></span></section>',  # noqa: E501
        "subsection_title": '<p style="margin:32px 0 12px;font-size:16px;font-weight:600;color:#2B2B2B;line-height:1.5;letter-spacing:0.3px;">{title}</p>',  # noqa: E501
        "quote": '<section style="margin:36px 0;padding:32px 18px;border-top:1px solid #E8E8E8;border-bottom:1px solid #E8E8E8;text-align:center;">{content}</section>',  # noqa: E501
        "ending": '<section style="margin:40px 0 0;border-top:1px solid #E8E8E8;padding:16px 0 4px;text-align:center;"><p style="margin:0;font-size:10px;font-weight:500;letter-spacing:5px;color:#A3A3A3;">FIN</p></section>',  # noqa: E501
    },
    "moyu-ticket": {
        "cover": '<section style="margin:0 0 28px;background:#fffef8;border:2px solid #1a1a1a;box-shadow:4px 4px 0 #1a1a1a;overflow:hidden;"><section style="background:#059669;padding:10px 18px;display:flex;justify-content:space-between;align-items:center;"><span style="font-size:10px;font-weight:700;letter-spacing:2px;color:#fff;">TICKET · 深度测评</span><span style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.85);">001</span></section><section style="padding:22px 18px 20px;"><h1 style="margin:0 0 10px;font-size:23px;font-weight:900;color:#1a1a1a;line-height:1.3;">{title}</h1><span style="display:inline-block;width:36px;height:3px;background:#059669;"><br></span></section></section>',  # noqa: E501
        "section_title": '<section style="margin:32px 0 14px;"><section style="display:flex;align-items:center;gap:12px;"><span style="background:#1a1a1a;color:#fff;font-size:12px;font-weight:800;padding:4px 10px;border-radius:4px;">{num}</span><h2 style="margin:0;font-size:20px;font-weight:800;color:#1a1a1a;line-height:1.4;">{title}</h2></section></section>',  # noqa: E501
        "subsection_title": '<p style="margin:24px 0 10px;font-size:16px;font-weight:800;color:#1a1a1a;line-height:1.5;"><span style="border-bottom:2px solid #A7F3D0;padding-bottom:2px;">{title}</span></p>',  # noqa: E501
        "quote": '<section style="margin:0 0 22px;background:#F0FDF4;border:1px dashed #A7F3D0;border-radius:8px;padding:12px 16px;">{content}</section>',  # noqa: E501
        "ending": '<section style="margin:28px 0 0;border-top:2px dashed #A7F3D0;padding:14px 0 4px;text-align:center;"><p style="margin:0;font-size:11px;font-weight:800;letter-spacing:4px;color:#1a1a1a;">- END OF TICKET -</p></section>',  # noqa: E501
    },
    "olive-journal": {
        "cover": '<section style="margin:0 0 26px;background:#fdfdf8;border:1px solid #bfc1b7;border-radius:6px;overflow:hidden;"><section style="padding:24px 20px 18px;"><section style="display:flex;align-items:center;gap:8px;margin-bottom:18px;"><span style="width:8px;height:8px;background:#1e1f23;border-radius:50%;"><br></span><span style="font-size:10px;font-weight:700;letter-spacing:3px;color:#65675e;">内刊手记</span><span style="flex:1;height:1px;background:#bfc1b7;"><br></span></section><h1 style="margin:0;font-size:23px;font-weight:800;color:#23251d;line-height:1.35;">{title}</h1></section><section style="background:#1e1f23;padding:10px 20px;"><p style="margin:0;font-size:11px;font-weight:700;letter-spacing:2px;color:#fff;">OLIVE JOURNAL · 编辑部内刊</p></section></section>',  # noqa: E501
        "section_title": '<section style="margin:32px 0 14px;"><section style="display:flex;align-items:center;gap:14px;"><section style="text-align:center;flex-shrink:0;"><p style="margin:0;font-size:24px;font-weight:800;color:#23251d;line-height:1;letter-spacing:-2px;">{num}</p><p style="margin:0;font-size:8px;font-weight:700;color:#9ea096;letter-spacing:2px;">PART</p></section><span style="width:1px;height:32px;background:#bfc1b7;"><br></span><section><p style="margin:0;font-size:17px;font-weight:800;color:#23251d;letter-spacing:0.2px;">{title}</p><p style="margin:0;font-size:11px;font-weight:600;color:#65675e;letter-spacing:1.2px;">OLIVE JOURNAL</p></section></section></section>',  # noqa: E501
        "subsection_title": '<p style="margin:24px 0 10px;font-size:16px;font-weight:800;color:#23251d;line-height:1.5;padding-left:10px;border-left:3px solid #ed7b2f;">{title}</p>',  # noqa: E501
        "quote": '<section style="margin:0 0 22px;background:#fdfdf8;border-radius:6px;padding:14px 16px;border:1px solid #bfc1b7;">{content}</section>',  # noqa: E501
        "ending": '<section style="margin:28px 0 0;background:#1e1f23;border-radius:6px;padding:16px 18px;text-align:center;"><p style="margin:0;font-size:12px;font-weight:800;letter-spacing:3px;color:#fff;">FIN · 编辑部</p></section>',  # noqa: E501
    },
    "aws-classic-blue": {
        "cover": '<section style="margin:0 0 24px;text-align:center;"><h1 style="margin:0;font-size:22px;font-weight:bold;color:#1A6DB5;border-bottom:2px solid #1A6DB5;padding-bottom:10px;line-height:1.4;">{title}</h1></section>',
        "section_title": '<section style="margin:2em 0 0;"><h2 style="display:inline-block;margin:0;font-size:17px;font-weight:bold;color:#fff;background:#1A6DB5;padding:5px 14px 4px;border-top-left-radius:3px;border-top-right-radius:3px;border-bottom:2px solid #14527D;line-height:1.4;">{title}</h2></section>',
        "subsection_title": '<h3 style="margin:1.5em 0 0.8em;font-size:16px;font-weight:bold;color:#1A6DB5;padding-left:10px;border-left:3px solid #1A6DB5;line-height:1.5;">{title}</h3>',
        "minor_title": '<h4 style="margin:1.2em 0 0.6em;font-size:15px;font-weight:bold;color:#444;line-height:1.5;">{title}</h4>',
        "paragraph": '<p style="margin:10px 0;font-size:16px;line-height:1.8;text-align:justify;color:#3A3A3A;letter-spacing:0.5px;">{content}</p>',
        "bullet_list": '<ul style="padding-left:20px;margin:0.6em 0;">{items}</ul>',
        "bullet_item": '<li style="margin-bottom:6px;line-height:1.75;color:#3A3A3A;">{content}</li>',
        "ordered_list": '<ol style="padding-left:20px;margin:0.6em 0;">{items}</ol>',
        "ordered_item": '<li style="margin-bottom:6px;line-height:1.75;color:#3A3A3A;">{content}</li>',
        "quote": '<blockquote style="margin:1.2em 0;border-left:4px solid #1A6DB5;background:#F7FBFF;padding:14px 16px;color:#555;">{content}</blockquote>',
        "code_block": '<section style="margin:1em 0;background:#0F2A44;color:#93C5FD;padding:16px;border-radius:10px;font-size:13px;line-height:1.8;overflow-x:auto;box-shadow:0 8px 24px rgba(0,0,0,0.2);">{code}</section>',
        "code_line": '<p style="margin:0;font-family:\'SF Mono\',Consolas,Monaco,monospace;font-size:13px;line-height:1.8;color:#93C5FD;">{code}</p>',
        "image": '<img src="{src}" alt="{alt}" style="max-width:100%;border-radius:5px;display:block;margin:0 auto;box-shadow:#84A1A8 0 6px 12px;">',
        "divider": '<section style="margin:2em 0;height:1px;background:linear-gradient(to right,rgba(26,109,181,0),rgba(26,109,181,0.6),rgba(26,109,181,0));"><br></section>',
        "ending": '',
    },
    "aws-elegant-purple": {
        "cover": '<section style="margin:0 0 24px;text-align:center;"><h1 style="margin:0;font-size:22px;font-weight:bold;color:#595959;line-height:1.4;">{title}</h1></section>',
        "section_title": '<h2 style="margin:2em 0 1em;font-size:18px;font-weight:bold;color:#595959;padding-left:10px;border-left:5px solid #DEC6FB;line-height:1.4;">{title}</h2>',
        "subsection_title": '<section style="margin:1.5em 0 0.8em;text-align:center;"><h3 style="display:inline-block;margin:0;font-size:16px;font-weight:bold;color:#595959;border-bottom:2px solid #DEC6FB;padding-bottom:4px;line-height:1.5;">{title}</h3></section>',
        "minor_title": '<h4 style="margin:1.2em 0 0.6em;font-size:15px;font-weight:bold;color:#595959;line-height:1.5;">{title}</h4>',
        "paragraph": '<p style="margin:10px 0;font-size:16px;line-height:1.75;text-align:justify;color:#595959;letter-spacing:2px;">{content}</p>',
        "bullet_list": '<ul style="padding-left:20px;margin:0.6em 0;list-style-type:circle;">{items}</ul>',
        "bullet_item": '<li style="margin-bottom:6px;line-height:1.75;color:#595959;font-size:16px;">{content}</li>',
        "ordered_list": '<ol style="padding-left:20px;margin:0.6em 0;">{items}</ol>',
        "ordered_item": '<li style="margin-bottom:6px;line-height:1.75;color:#595959;font-size:16px;">{content}</li>',
        "quote": '<blockquote style="margin:1.2em 0;border:1px solid #DEC6FB;background:#F6EEFF;padding:15px 20px;border-radius:6px;color:#595959;">{content}</blockquote>',
        "code_block": '<section style="margin:1em 0;background:#F9F5FF;padding:16px;border-radius:10px;border:1px solid #E9D5FF;font-size:13px;line-height:1.8;overflow-x:auto;color:#5B3A8C;">{code}</section>',
        "code_line": '<p style="margin:0;font-family:\'SF Mono\',Consolas,Monaco,monospace;font-size:13px;line-height:1.8;color:#5B3A8C;">{code}</p>',
        "image": '<img src="{src}" alt="{alt}" style="max-width:100%;border-radius:6px;display:block;margin:20px auto;">',
        "divider": '<section style="margin:2em 0;border-top:2px solid #DEC6FB;"><br></section>',
        "ending": '',
    },
    "aws-warm-orange": {
        "cover": '<section style="margin:0 0 24px;text-align:center;"><h1 style="margin:0;font-size:22px;font-weight:bold;color:#EF7060;border-bottom:2px solid #EF7060;padding-bottom:10px;line-height:1.4;">{title}</h1></section>',
        "section_title": '<section style="margin:2em 0 0;"><h2 style="display:inline-block;margin:0;font-size:17px;font-weight:bold;color:#fff;background:#EF7060;padding:4px 12px 2px;border-top-left-radius:3px;border-top-right-radius:3px;border-bottom:2px solid #EFEBE9;line-height:1.4;">{title}</h2></section>',
        "subsection_title": '<h3 style="margin:1.5em 0 0.8em;font-size:16px;font-weight:bold;color:#EF7060;line-height:1.5;">{title}</h3>',
        "minor_title": '<h4 style="margin:1.2em 0 0.6em;font-size:15px;font-weight:bold;color:#C0392B;line-height:1.5;">{title}</h4>',
        "paragraph": '<p style="margin:10px 0;font-size:16px;line-height:1.8;text-align:justify;color:#3E3E3E;">{content}</p>',
        "bullet_list": '<ul style="padding-left:20px;margin:0.6em 0;">{items}</ul>',
        "bullet_item": '<li style="margin-bottom:6px;line-height:1.75;color:#3E3E3E;">{content}</li>',
        "ordered_list": '<ol style="padding-left:20px;margin:0.6em 0;">{items}</ol>',
        "ordered_item": '<li style="margin-bottom:6px;line-height:1.75;color:#3E3E3E;">{content}</li>',
        "quote": '<blockquote style="margin:1.2em 0;border-left:4px solid #EF7060;background:#FFF9F9;padding:12px 16px;color:#555;">{content}</blockquote>',
        "code_block": '<section style="margin:1em 0;background:#1C1917;color:#FDBA74;padding:16px;border-radius:10px;font-size:13px;line-height:1.8;overflow-x:auto;box-shadow:0 8px 24px rgba(0,0,0,0.2);">{code}</section>',
        "code_line": '<p style="margin:0;font-family:\'SF Mono\',Consolas,Monaco,monospace;font-size:13px;line-height:1.8;color:#FDBA74;">{code}</p>',
        "image": '<img src="{src}" alt="{alt}" style="max-width:100%;border-radius:5px;display:block;margin:15px auto;">',
        "divider": '<section style="width:40px;height:3px;background:#EF7060;margin:2em 0;border-radius:2px;"><br></section>',
        "ending": '',
    },
    "aws-minimal-black": {
        "cover": '<section style="margin:0 0 32px;text-align:center;"><h1 style="margin:0;font-size:24px;font-weight:300;color:#18181B;letter-spacing:4px;line-height:1.4;">{title}</h1></section>',
        "section_title": '<h2 style="margin:2.5em 0 1em;font-size:18px;font-weight:400;color:#18181B;letter-spacing:2px;line-height:1.4;">{title}</h2>',
        "subsection_title": '<h3 style="margin:2em 0 0.8em;font-size:16px;font-weight:600;color:#333;line-height:1.5;">{title}</h3>',
        "minor_title": '<h4 style="margin:1.5em 0 0.6em;font-size:15px;font-weight:500;color:#555;line-height:1.5;">{title}</h4>',
        "paragraph": '<p style="margin:1em 0;font-size:16px;line-height:2;text-align:justify;color:#333;letter-spacing:0.5px;">{content}</p>',
        "bullet_list": '<ul style="padding-left:20px;margin:0.8em 0;">{items}</ul>',
        "bullet_item": '<li style="margin-bottom:8px;line-height:1.8;color:#444;">{content}</li>',
        "ordered_list": '<ol style="padding-left:20px;margin:0.8em 0;">{items}</ol>',
        "ordered_item": '<li style="margin-bottom:8px;line-height:1.8;color:#444;">{content}</li>',
        "quote": '<blockquote style="margin:1.5em 2em;border:none;padding:16px 24px;color:#666;font-style:italic;font-size:16px;line-height:2;text-align:center;">{content}</blockquote>',
        "code_block": '<section style="margin:1em 0;background:#FAFAFA;padding:20px;border-radius:4px;border:1px solid #E5E5E5;font-size:13px;line-height:1.8;overflow-x:auto;color:#333;">{code}</section>',
        "code_line": '<p style="margin:0;font-family:\'SF Mono\',Consolas,Monaco,monospace;font-size:13px;line-height:1.8;color:#333;">{code}</p>',
        "image": '<img src="{src}" alt="{alt}" style="max-width:100%;display:block;margin:0 auto;">',
        "divider": '<section style="width:24px;height:1px;background:#18181B;margin:2.5em auto;"><br></section>',
        "ending": '',
    },
    "editorial-notes": {
        "cover": '<section style="margin:0 0 30px;padding:8px 0 22px;border-bottom:1px solid #D8CDC1;"><section style="width:34px;height:3px;background:#B34A31;margin:0 0 18px;"><span><br></span></section><h1 style="margin:0;font-family:{serif};font-size:27px;font-weight:700;line-height:1.42;letter-spacing:0.3px;color:#2D2A26;">{title}</h1></section>',
        "opening": '<p style="margin:0 0 28px;font-family:{serif};font-size:18px;line-height:1.92;letter-spacing:0.35px;color:#514942;">{content}</p>',
        "section_title": '<section style="margin:42px 0 18px;padding:0 0 11px;border-bottom:1px solid #E5DDD4;"><h2 style="margin:0;padding-left:11px;border-left:3px solid #B34A31;font-size:19px;font-weight:700;line-height:1.55;letter-spacing:0.2px;color:#2D2A26;">{title}</h2></section>',
        "subsection_title": '<h3 style="margin:30px 0 12px;font-size:16px;font-weight:700;line-height:1.65;color:#403A35;">{title}</h3>',
        "minor_title": '<h4 style="margin:22px 0 8px;font-size:15px;font-weight:700;line-height:1.6;color:#514942;">{title}</h4>',
        "paragraph": '<p style="margin:0 0 18px;font-size:16px;line-height:1.95;letter-spacing:0.45px;text-align:justify;text-indent:2em;color:#2D2A26;">{content}</p>',
        "bullet_list": '<section style="margin:0 0 22px;padding:2px 0 2px 16px;border-left:1px solid #D8CDC1;"><ul style="margin:0;padding-left:19px;">{items}</ul></section>',
        "bullet_item": '<li style="margin:0 0 9px;font-size:16px;line-height:1.85;color:#2D2A26;">{content}</li>',
        "ordered_list": '<ol style="margin:0 0 22px;padding-left:25px;">{items}</ol>',
        "ordered_item": '<li style="margin:0 0 9px;padding-left:3px;font-size:16px;line-height:1.85;color:#2D2A26;">{content}</li>',
        "quote": '<blockquote style="margin:28px 0;padding:3px 0 3px 16px;border-left:3px solid #C77B65;color:#635A53;font-family:{serif};font-size:17px;line-height:1.9;letter-spacing:0.2px;">{content}</blockquote>',
        "code_block": '<section style="margin:0 0 22px;padding:14px 16px;background:#2D2A26;overflow-x:auto;"><section style="margin:0 0 8px;font-size:11px;letter-spacing:1.5px;color:#DAB4A7;">{lang}</section>{code}</section>',
        "code_line": '<p style="margin:0;font-family:\'SF Mono\',Consolas,Monaco,monospace;font-size:13px;line-height:1.7;color:#F8F2EB;">{code}</p>',
        "image": '<section style="margin:0 0 22px;"><img src="{src}" alt="{alt}" style="max-width:100%;height:auto;display:block;margin:0 auto;"></section>',
        "divider": '<section style="width:32px;height:1px;background:#B34A31;margin:34px auto;"><span><br></span></section>',
        "ending": '',
    },
    "editorial-casebook": {
        "cover": '<section style="margin:0 0 28px;padding:10px 0 21px;border-top:4px solid #8E4A3C;border-bottom:1px solid #DDD2C8;"><h1 style="margin:0;font-family:{serif};font-size:26px;font-weight:700;line-height:1.45;color:#302C28;">{title}</h1></section>',
        "opening": '<p style="margin:0 0 28px;padding-left:14px;border-left:2px solid #C89586;font-family:{serif};font-size:18px;line-height:1.9;color:#554C46;">{content}</p>',
        "section_title": '<section style="margin:40px 0 17px;padding:0 0 10px;border-bottom:1px solid #E7DDD5;"><h2 style="margin:0;font-size:19px;font-weight:700;line-height:1.55;color:#302C28;">{title}</h2></section>',
        "subsection_title": '<h3 style="margin:28px 0 11px;padding-left:10px;border-left:2px solid #C89586;font-size:16px;font-weight:700;line-height:1.65;color:#473D37;">{title}</h3>',
        "paragraph": '<p style="margin:0 0 18px;font-size:16px;line-height:1.95;text-align:justify;text-indent:2em;color:#302C28;">{content}</p>',
        "bullet_list": '<ul style="margin:0 0 22px;padding-left:23px;">{items}</ul>',
        "bullet_item": '<li style="margin:0 0 9px;font-size:16px;line-height:1.85;color:#302C28;">{content}</li>',
        "ordered_list": '<ol style="margin:0 0 22px;padding-left:25px;">{items}</ol>',
        "ordered_item": '<li style="margin:0 0 9px;font-size:16px;line-height:1.85;color:#302C28;">{content}</li>',
        "quote": '<blockquote style="margin:28px 0;padding:14px 16px;background:#F5EEEA;border-left:3px solid #8E4A3C;color:#635851;font-family:{serif};font-size:17px;line-height:1.85;">{content}</blockquote>',
        "divider": '<section style="width:100%;height:1px;background:#E0D4CB;margin:32px 0;"><span><br></span></section>',
        "ending": '',
    },
    "editorial-playbook": {
        "cover": '<section style="margin:0 0 30px;padding:8px 0 21px;border-bottom:1px solid #C9D5D9;"><section style="width:30px;height:3px;background:#315B71;margin:0 0 17px;"><span><br></span></section><h1 style="margin:0;font-family:{serif};font-size:26px;font-weight:700;line-height:1.42;color:#263542;">{title}</h1></section>',
        "opening": '<p style="margin:0 0 27px;font-family:{serif};font-size:18px;line-height:1.9;color:#425661;">{content}</p>',
        "section_title": '<section style="display:flex;align-items:baseline;margin:38px 0 17px;padding:0 0 11px;border-bottom:1px solid #D7E0E3;"><span style="margin-right:10px;font-size:12px;font-weight:700;letter-spacing:1px;color:#315B71;">{num}</span><h2 style="margin:0;font-size:19px;font-weight:700;line-height:1.55;color:#263542;">{title}</h2></section>',
        "subsection_title": '<h3 style="margin:28px 0 11px;font-size:16px;font-weight:700;line-height:1.65;color:#2C4958;">{title}</h3>',
        "paragraph": '<p style="margin:0 0 17px;font-size:16px;line-height:1.9;text-align:justify;color:#263542;">{content}</p>',
        "bullet_list": '<section style="margin:0 0 22px;padding:3px 0 3px 15px;border-left:2px solid #B7CCD4;"><ul style="margin:0;padding-left:18px;">{items}</ul></section>',
        "bullet_item": '<li style="margin:0 0 9px;font-size:16px;line-height:1.82;color:#263542;">{content}</li>',
        "ordered_list": '<ol style="margin:0 0 22px;padding-left:25px;">{items}</ol>',
        "ordered_item": '<li style="margin:0 0 9px;padding-left:3px;font-size:16px;font-weight:600;line-height:1.82;color:#263542;">{content}</li>',
        "quote": '<blockquote style="margin:28px 0;padding:3px 0 3px 15px;border-left:3px solid #315B71;color:#4C626C;font-family:{serif};font-size:17px;line-height:1.85;">{content}</blockquote>',
        "divider": '<section style="width:30px;height:2px;background:#315B71;margin:32px 0;"><span><br></span></section>',
        "ending": '',
    },
}


def _fill(template: str, vars_: dict[str, str], **values: str) -> str:
    merged = {**vars_, **values}
    for key, value in merged.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def _inner_html(el, inline: dict[str, str], p_style: str = "") -> str:
    for tag, style in (
        ("strong", inline.get("strong")),
        ("code", inline.get("code")),
        ("a", inline.get("a")),
        ("em", inline.get("em")),
    ):
        if not style:
            continue
        for node in el.iter(tag):
            existing = node.get("style", "")
            node.set("style", f"{style}{existing}" if existing else style)
    if p_style:
        for node in el.iter("p"):
            existing = node.get("style", "")
            node.set("style", f"{p_style}{existing}" if existing else p_style)
    parts = [html_lib.escape(el.text or "", quote=False)]
    for child in el:
        parts.append(lxml_html.tostring(child, encoding="unicode", method="html", with_tail=False))
        parts.append(html_lib.escape(child.tail or "", quote=False))
    return "".join(parts)


def _table_html(el, vars_: dict[str, str]) -> str:
    head = ""
    rows: list[str] = []
    for tr in el.findall(".//tr"):
        if tr.find("th") is not None:
            head = "".join(
                f'<th style="background:{vars_["accent"]};color:#fff;font-weight:700;padding:8px 12px;text-align:left;border:1px solid rgba(255,255,255,0.15);">{th.text or ""}</th>'  # noqa: E501
                for th in tr.findall("th")
            )
        else:
            cells = "".join(
                f'<td style="padding:8px 12px;border:1px solid #E5E7EB;color:{vars_["text"]};">{td.text or ""}</td>'
                for td in tr.findall("td")
            )
            if cells:
                rows.append(f"<tr>{cells}</tr>")
    thead = f"<thead><tr>{head}</tr></thead>" if head else ""
    tbody = f"<tbody>{''.join(rows)}</tbody>" if rows else ""
    return f'<table style="width:100%;border-collapse:collapse;margin:0 0 20px;font-size:14px;">{thead}{tbody}</table>'


def recommend_editorial_theme(title: str, outline: Any, content_markdown: str) -> tuple[str, str]:
    """Choose an editorial layout from explicit content signals; never randomize a published article."""
    title_text = title or ""
    body_text = f"{outline or ''}\n{content_markdown or ''}"
    playbook_terms = ("如何", "怎么", "步骤", "方法", "教程", "指南", "清单", "流程", "操作", "工具")
    casebook_terms = ("案例", "复盘", "项目", "实践", "客户", "增长", "结果", "问题", "踩坑", "实验")
    playbook_score = 2 * sum(title_text.count(term) for term in playbook_terms) + sum(
        body_text.count(term) for term in playbook_terms
    )
    casebook_score = 2 * sum(title_text.count(term) for term in casebook_terms) + sum(
        body_text.count(term) for term in casebook_terms
    )
    section_count = content_markdown.count("\n## ")
    if playbook_score >= 3 or (playbook_score >= 2 and section_count >= 3):
        return "editorial-playbook", "检测到步骤、方法或清单结构"
    if casebook_score >= 3 or (casebook_score >= 2 and section_count >= 3):
        return "editorial-casebook", "检测到案例、复盘或结果结构"
    return "editorial-notes", "默认使用观点长文结构"

def _components_for(theme: Theme, version: ThemeVersion) -> dict[str, str]:
    tokens = version.tokens_json or {}
    comps = tokens.get("components")
    if isinstance(comps, dict) and comps:
        return comps
    return COMPONENT_PRESETS.get(theme.slug) or DEFAULT_COMPONENTS


def _tokens_for(theme: Theme, version: ThemeVersion) -> dict[str, str]:
    tokens = version.tokens_json or {}
    return {
        "surface": str(tokens.get("surface") or "#FFFFFF"),
        "text": str(tokens.get("text") or "#1F2937"),
        "accent": str(tokens.get("accent") or "#2563EB"),
        "muted": str(tokens.get("muted") or "#6B7280"),
        "font": str(tokens.get("font") or _SANS),
        "serif": str(tokens.get("serif") or _SERIF),
    }


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
            db.add(
                ThemeVersion(
                    theme_id=theme.id,
                    version=1,
                    tokens_json={
                        **spec.tokens,
                        "inline_styles": INLINE_STYLE_PRESETS.get(spec.slug, {}),
                        "components": COMPONENT_PRESETS.get(spec.slug, {}),
                    },
                    css_text=spec.css,
                )
            )
        elif theme.is_builtin and "components" not in (version.tokens_json or {}):
            # 旧种子升级：为已存在的内置主题补上组件模板，渲染时自动刷新缓存。
            version.tokens_json = {
                **spec.tokens,
                "inline_styles": INLINE_STYLE_PRESETS.get(spec.slug, {}),
                "components": COMPONENT_PRESETS.get(spec.slug, {}),
            }
            version.css_text = spec.css
    db.flush()


def render_markdown(content_markdown: str) -> str:
    return MarkdownIt("commonmark", {"breaks": True, "html": False}).enable("table").render(content_markdown)


def inline_styles_for_theme(theme: Theme, version: ThemeVersion) -> dict[str, str]:
    tokens = version.tokens_json or {}
    preset = tokens.get("inline_styles") or INLINE_STYLE_PRESETS.get(theme.slug)
    if preset:
        return preset
    surface = str(tokens.get("surface") or "#FFFFFF")
    text = str(tokens.get("text") or "#1F2937")
    accent = str(tokens.get("accent") or "#2563EB")
    return {
        "article": f"background:{surface};color:{text};font-size:16px;line-height:1.9;padding:28px 22px;",
        "strong": f"color:{accent};font-weight:700;",
        "code": f"color:{accent};",
        "a": f"color:{accent};text-decoration:none;",
    }


def render_with_theme(content_markdown: str, theme: Theme, version: ThemeVersion, title: str = "") -> str:
    body_html = render_markdown(content_markdown)
    root = lxml_html.fromstring(f"<body>{body_html}</body>")
    inline = inline_styles_for_theme(theme, version)
    comps = _components_for(theme, version)
    vars_ = _tokens_for(theme, version)
    parts: list[str] = []
    section_no = 0
    opening_available = True
    has_h1 = any(el.tag == "h1" for el in root)
    if title and not has_h1:
        parts.append(_fill(comps.get("cover", DEFAULT_COMPONENTS["cover"]), vars_, title=html_lib.escape(title, quote=False)))  # noqa: E501
    for el in list(root):
        tag = el.tag
        if tag in {"h2", "h3", "h4", "blockquote", "ul", "ol", "pre", "table", "img", "hr"}:
            opening_available = False
        if tag == "h1":
            parts.append(_fill(comps.get("cover", DEFAULT_COMPONENTS["cover"]), vars_, title=_inner_html(el, inline)))
        elif tag == "h2":
            section_no += 1
            parts.append(
                _fill(
                    comps.get("section_title", DEFAULT_COMPONENTS["section_title"]),
                    vars_,
                    num=f"{section_no:02d}",
                    title=_inner_html(el, inline),
                )
            )
        elif tag == "h3":
            parts.append(_fill(comps.get("subsection_title", DEFAULT_COMPONENTS["subsection_title"]), vars_, title=_inner_html(el, inline)))  # noqa: E501
        elif tag == "h4":
            parts.append(_fill(comps.get("minor_title", DEFAULT_COMPONENTS["minor_title"]), vars_, title=_inner_html(el, inline)))  # noqa: E501
        elif tag == "blockquote":
            parts.append(_fill(comps.get("quote", DEFAULT_COMPONENTS["quote"]), vars_, content=_inner_html(el, inline, "margin:0;")))  # noqa: E501
        elif tag == "ul":
            items = "".join(
                _fill(comps.get("bullet_item", DEFAULT_COMPONENTS["bullet_item"]), vars_, content=_inner_html(li, inline))  # noqa: E501
                for li in el.iterchildren("li")
            )
            parts.append(_fill(comps.get("bullet_list", DEFAULT_COMPONENTS["bullet_list"]), vars_, items=items))
        elif tag == "ol":
            items = "".join(
                _fill(
                    comps.get("ordered_item", DEFAULT_COMPONENTS["ordered_item"]),
                    vars_,
                    num=str(i + 1),
                    content=_inner_html(li, inline),
                )
                for i, li in enumerate(el.iterchildren("li"))
            )
            parts.append(_fill(comps.get("ordered_list", DEFAULT_COMPONENTS["ordered_list"]), vars_, items=items))
        elif tag == "pre":
            code_el = el.find("code")
            code_text = (code_el.text if code_el is not None else el.text) or ""
            lang = ""
            if code_el is not None:
                for cls in (code_el.get("class") or "").split():
                    if cls.startswith("language-"):
                        lang = cls[len("language-"):]
                        break
            lines = "".join(
                _fill(
                    comps.get("code_line", DEFAULT_COMPONENTS["code_line"]),
                    vars_,
                    code=line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") or "&nbsp;",
                )
                for line in code_text.split("\n")
            )
            parts.append(_fill(comps.get("code_block", DEFAULT_COMPONENTS["code_block"]), vars_, lang=lang, code=lines))
        elif tag == "table":
            parts.append(_table_html(el, vars_))
        elif tag == "img":
            parts.append(_fill(comps.get("image", DEFAULT_COMPONENTS["image"]), vars_, src=el.get("src", ""), alt=el.get("alt", "")))  # noqa: E501
        elif tag == "hr":
            parts.append(_fill(comps.get("divider", DEFAULT_COMPONENTS["divider"]), vars_))
        elif tag == "p":
            imgs = el.findall("img")
            only_image = len(imgs) == 1 and not (el.text or "").strip() and not [x for x in el if x is not imgs[0]]
            if only_image:
                parts.append(
                    _fill(comps.get("image", DEFAULT_COMPONENTS["image"]), vars_, src=imgs[0].get("src", ""), alt=imgs[0].get("alt", ""))  # noqa: E501
                )
            else:
                component_name = "opening" if opening_available and comps.get("opening") else "paragraph"
                parts.append(_fill(comps.get(component_name, DEFAULT_COMPONENTS["paragraph"]), vars_, content=_inner_html(el, inline)))  # noqa: E501
                opening_available = False
        else:
            parts.append(lxml_html.tostring(el, encoding="unicode", method="html"))
    ending = comps.get("ending", DEFAULT_COMPONENTS["ending"])
    if ending:
        parts.append(_fill(ending, vars_))
    body = "".join(parts)
    wrapper = lxml_html.fragment_fromstring(
        f'<article data-theme="{theme.slug}" data-theme-version="{version.version}" style="{inline.get("article", "")}">{body}</article>',  # noqa: E501
        create_parent=False,
    )
    return lxml_html.tostring(wrapper, encoding="unicode", method="html")


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
    article = db.get(Article, revision.article_id)
    article_title = article.title if article is not None else ""
    fresh_html = render_with_theme(revision.content_markdown, theme, version, article_title)
    if rendered is None:
        rendered = RenderedVersion(
            article_revision_id=revision.id,
            theme_version_id=version.id,
            html=fresh_html,
        )
        db.add(rendered)
        db.flush()
    elif rendered.html != fresh_html:
        # Refresh cached previews when inline color tokens or the rendering logic changes
        # without changing the revision or theme version identity.
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




# ---------------------------------------------------------------------------
# AI 装配排版：把主题组件模板交给模型，生成完整微信 HTML。
# ---------------------------------------------------------------------------

_WECHAT_FORBIDDEN_MARKERS = (
    "<style",
    "<script",
    "<div",
    "<link",
    "<iframe",
    "class=",
    "id=",
    "position:fixed",
    "position:absolute",
    "position:sticky",
    "float:",
    "@media",
    "@keyframes",
    "display:grid",
    "url(",
)


def validate_gzh_html(html: str) -> list[str]:
    """返回微信不兼容的写法列表；空列表表示合规。"""
    errors: list[str] = []
    lowered = html.lower()
    for marker in _WECHAT_FORBIDDEN_MARKERS:
        if marker in lowered:
            errors.append(marker)
    return errors


def extract_html(text: str) -> str:
    """从模型回复中提取 HTML：优先 ```html 围栏，其次取首尾标签之间的内容。"""
    content = (text or "").strip()
    fence = content.find("```")
    if fence >= 0:
        block = content[fence + 3 :]
        end_fence = block.find("```")
        if end_fence >= 0:
            block = block[:end_fence]
        else:
            block = content[fence + 3 :]
        first_lt = block.find("<")
        return block[first_lt:] if first_lt >= 0 else block.strip()
    first_lt = content.find("<")
    last_gt = content.rfind(">")
    if first_lt >= 0 and last_gt > first_lt:
        return content[first_lt : last_gt + 1]
    return content


def layout_instruction(theme: Theme, version: ThemeVersion) -> str:
    """把主题组件模板整理成给排版模型的指令。"""
    comps = _components_for(theme, version)
    tokens = _tokens_for(theme, version)
    lines = [
        f"你是微信公众号文章排版专家。请把用户提供的 Markdown 文章排版成「{theme.name}」主题的完整 HTML。",
        f"主题定位：{theme.description}",
        "",
        "必须遵守的微信平台红线（违反任何一条都算失败）：",
        "1. 禁止 <style>/<script>/<div>/<link>/<iframe> 标签，禁止 class、id 属性。",
        "2. 禁止 position:fixed/absolute/sticky、float、display:grid、@media、@keyframes、CSS 变量、外部字体、背景图 url()。",  # noqa: E501
        "3. 所有样式必须内联在 style 属性中；文字节点尽量用 <span> 包裹。",
        "4. 装饰性空元素（圆点、分割线、短横）内部必须放 <span><br></span> 占位，否则微信会剥掉样式。",
        "5. 输出必须是纯 HTML（不要 Markdown、不要解释），以 <article> 为根，文章标题作为封面标题。",
        "",
        "排版规则：",
        "1. 文章标题放入封面组件；一级标题（# ）如果存在就用它，否则用文章标题。",
        "2. 每个二级标题（## ）是一个章节，必须使用章节标题组件并编号 01/02/03…。",
        "3. 引用（> ）使用金句引用组件；列表使用要点列表组件；表格保持为数据表；图片用图片组件；代码块用代码块组件。",
        "4. 正文段落直接使用正文段落组件，不要自创未在组件库中的结构；组件可组合但不能违背微信红线。",
        "5. 结尾追加结语组件。",
        "",
        "主题组件模板（{placeholder} 为待填充内容，直接替换成真实内容）：",
    ]
    for name, template in comps.items():
        lines.append(f"--- {name} ---")
        lines.append(template)
    lines.append("")
    lines.append("配色参考：")
    for key in ("surface", "text", "accent", "muted"):
        lines.append(f"{key}: {tokens.get(key)}")
    return "\n".join(lines)
