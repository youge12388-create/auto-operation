from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urldefrag, urlsplit, urlunsplit

import feedparser
import httpx
import trafilatura
from sqlalchemy import select
from sqlalchemy.orm import Session

from .material_classification import classify_materials
from .models import Job, MaterialCategory, ModelConfig, Source, SourceItem
from .providers import ModelProvider, provider_for
from .translations import needs_chinese_translation, translate_source_items


def normalize_url(value: str) -> str:
    parts = urlsplit(urldefrag(value.strip())[0])
    scheme = parts.scheme.lower()
    host = parts.netloc.lower()
    return urlunsplit((scheme, host, parts.path.rstrip("/"), parts.query, ""))


def content_hash(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


AIHOT_API_ITEMS_URL = "https://aihot.virxact.com/api/v1/items"

_AIHOT_CATEGORY_NAMES = {
    "ai-models": "AI 前沿",
    "ai-products": "产品与商业",
    "industry": "行业观察",
    "paper": "AI 前沿",
    "tip": "技术与工具",
}


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _aihot_category(db: Session, slug: str | None) -> MaterialCategory | None:
    name = _AIHOT_CATEGORY_NAMES.get(slug or "")
    if not name:
        return None
    category = db.scalar(select(MaterialCategory).where(MaterialCategory.name == name))
    if category is None:
        category = MaterialCategory(
            name=name,
            description=f"来自 AI HOT 官方分类（{slug}）",
            enabled=True,
            is_builtin=False,
        )
        db.add(category)
        db.flush()
    return category


def _upsert_item(db: Session, source: Source, title: str, url: str, content: str) -> SourceItem:
    canonical = normalize_url(url or source.url)
    digest = content_hash(content or title)
    item = db.scalar(select(SourceItem).where(SourceItem.canonical_url == canonical))
    if item is None and content.strip():
        item = db.scalar(select(SourceItem).where(SourceItem.content_hash == digest))
    if item is None:
        item = SourceItem(
            source_id=source.id,
            title=title.strip() or canonical,
            url=url or source.url,
            canonical_url=canonical,
            content=content.strip(),
            content_hash=digest,
            status="verified" if (content.strip() or title.strip()) else "insufficient",
            classification_status="pending",
        )
        db.add(item)
    elif item.content_hash != digest:
        # A changed upstream item needs a fresh translation; unchanged items retain their
        # persisted Chinese rendition instead of paying for the same model call again.
        item.title = title.strip() or item.title
        item.content = content.strip() or item.content
        item.content_hash = digest
        item.status = "verified" if item.content else "insufficient"
        item.category_id = None
        item.classification_status = "pending"
        item.classification_source = None
        item.classification_confidence = None
        item.classification_reason = None
        item.classification_error = None
    return item


def collect_source(
    db: Session,
    source: Source,
    translation_provider: ModelProvider | None = None,
    translation_model: ModelConfig | None = None,
    translation_job: Job | None = None,
    translate_foreign_sources: bool = True,
) -> list[SourceItem]:
    if not source.enabled or (source.group is not None and not source.group.enabled):
        return []
    try:
        if source.source_type == "manual":
            item = _upsert_item(
                db,
                source,
                source.config_json.get("title", source.name),
                source.url,
                source.config_json.get("content", ""),
            )
            items = [item]
        elif source.source_type == "aihot_api":
            config = source.config_json or {}
            params = {
                "mode": "selected",
                "window": str(config.get("window", "24h")),
                "limit": max(1, min(int(config.get("limit", 100)), 100)),
            }
            category_slug = config.get("category")
            if category_slug:
                params["category"] = str(category_slug)
            api_response = httpx.get(AIHOT_API_ITEMS_URL, params=params, timeout=30)
            api_response.raise_for_status()
            payload = api_response.json()
            items = []
            for entry in payload.get("items") or []:
                links = entry.get("links") or {}
                title = entry.get("title") or entry.get("originalTitle") or ""
                url = links.get("original") or links.get("aihot") or source.url
                summary = entry.get("summary") or ""
                item = _upsert_item(db, source, title, url, summary)
                item.published_at = _parse_iso_datetime(entry.get("publishedAt"))
                category = _aihot_category(db, entry.get("category"))
                if category is not None:
                    item.category_id = category.id
                    item.classification_status = "classified"
                    item.classification_source = "ai"
                    item.classification_confidence = 90.0
                    item.classification_reason = "来自 AI HOT 官方分类"
                items.append(item)
        else:
            response = httpx.get(source.url, timeout=30, follow_redirects=True)
            response.raise_for_status()
            if source.source_type == "rss":
                items = [
                    _upsert_item(
                        db,
                        source,
                        entry.get("title", ""),
                        entry.get("link", source.url),
                        entry.get("summary") or entry.get("description") or entry.get("title", ""),
                    )
                    for entry in feedparser.parse(response.content).entries
                ]
            else:
                content = trafilatura.extract(response.text) or response.text[:4000]
                items = [_upsert_item(db, source, source.name, str(response.url), content)]
        if translate_foreign_sources and any(needs_chinese_translation(item) for item in items):
            if translation_provider is None:
                translation_model = translation_model or db.scalar(
                    select(ModelConfig).where(ModelConfig.enabled.is_(True)).order_by(ModelConfig.created_at.desc())
                )
                translation_provider = provider_for(translation_model) if translation_model else None
            if translation_provider is None:
                raise ValueError("外文信息源需要先配置一个启用的翻译模型")
            translate_source_items(db, translation_job, items, translation_provider, translation_model)
        classification_candidates = [
            item
            for item in items
            if item.status == "verified" and item.classification_status in {"pending", "failed"}
        ]
        if classification_candidates:
            classification_model = translation_model or db.scalar(
                select(ModelConfig).where(ModelConfig.enabled.is_(True)).order_by(ModelConfig.created_at.desc())
            )
            classification_provider = (
                translation_provider
                if classification_model is not None and classification_model is translation_model
                else (provider_for(classification_model) if classification_model is not None else None)
            )
            categories = db.scalars(
                select(MaterialCategory).where(MaterialCategory.enabled.is_(True)).order_by(MaterialCategory.name)
            ).all()
            classify_materials(
                db,
                translation_job,
                classification_candidates,
                categories,
                classification_provider,
                classification_model,
            )
        source.last_success_at = datetime.now(timezone.utc)
        source.last_error = None
        db.flush()
        return items
    except Exception as exc:
        source.last_error = str(exc)
        db.flush()
        raise
