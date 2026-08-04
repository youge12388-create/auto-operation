from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urldefrag, urlsplit, urlunsplit

import feedparser
import httpx
import trafilatura
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Source, SourceItem


def normalize_url(value: str) -> str:
    parts = urlsplit(urldefrag(value.strip())[0])
    scheme = parts.scheme.lower()
    host = parts.netloc.lower()
    return urlunsplit((scheme, host, parts.path.rstrip("/"), parts.query, ""))


def content_hash(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


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
            status="verified" if content.strip() else "insufficient",
        )
        db.add(item)
    else:
        item.title = title.strip() or item.title
        item.content = content.strip() or item.content
        item.content_hash = digest
        item.status = "verified" if item.content else "insufficient"
    return item


def collect_source(db: Session, source: Source) -> list[SourceItem]:
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
                        entry.get("summary", ""),
                    )
                    for entry in feedparser.parse(response.content).entries
                ]
            else:
                content = trafilatura.extract(response.text) or ""
                items = [_upsert_item(db, source, source.name, str(response.url), content)]
        source.last_success_at = datetime.now(timezone.utc)
        source.last_error = None
        db.flush()
        return items
    except Exception as exc:
        source.last_error = str(exc)
        db.flush()
        raise
