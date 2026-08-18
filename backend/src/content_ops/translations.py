from __future__ import annotations

import json
import re
import time
from typing import Iterable

from sqlalchemy.orm import Session

from .models import Job, ModelCallLog, ModelConfig, SourceItem
from .providers import CompletionRequest, ModelProvider

_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_LATIN = re.compile(r"[A-Za-z]")
_TRANSLATED_PREFIX = "\u3010\u4e2d\u6587\u8bd1\u6587\u3011"
_ORIGINAL_PREFIX = "\u3010\u539f\u6587\u3011"


def needs_chinese_translation(item: SourceItem) -> bool:
    """Return whether a newly collected item needs a Chinese rendition."""
    content = item.content.strip()
    if not content or content.startswith(_TRANSLATED_PREFIX):
        return False
    text = f"{item.title}\n{content}"
    latin_count = len(_LATIN.findall(text))
    cjk_count = len(_CJK.findall(text))
    return latin_count >= 12 and cjk_count * 5 < latin_count


def _translated_payload(text: str) -> tuple[str, str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Translation model did not return valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Translation model returned an invalid payload")
    title = str(parsed.get("title") or "").strip()
    content = str(parsed.get("content") or "").strip()
    if not title or not content:
        raise ValueError("Translation model did not return both title and content")
    return title[:500], content


def translate_source_items(
    db: Session,
    job: Job | None,
    items: Iterable[SourceItem],
    provider: ModelProvider,
    model: ModelConfig | None,
) -> int:
    """Translate source items before they are exposed through the material pool."""
    translated_count = 0
    for item in items:
        if not needs_chinese_translation(item):
            continue
        original_title = item.title.strip()
        original_content = item.content.strip()
        request = CompletionRequest(
            system=(
                "You are a precise translator for a Chinese editorial team. Translate the title and body into "
                "natural Simplified Chinese. Preserve facts, dates, names, numbers, qualifiers, and links. Do not "
                "add analysis. Return only JSON with string fields title and content."
            ),
            user=f"MATERIAL_TRANSLATION_JSON\nTITLE: {original_title}\nCONTENT:\n{original_content[:12000]}",
            max_tokens=4000,
        )
        started = time.perf_counter()
        log = ModelCallLog(
            job_id=job.id if job else None,
            stage="translation",
            provider=model.provider if model else provider.__class__.__name__,
            model_name=model.name if model else provider.__class__.__name__,
            status="running",
            input_summary=f"Material translation: {original_title[:160]}",
        )
        # Keep the write transaction closed while the network call is in flight.
        # SQLite allows only one writer; holding the lock across a slow model
        # call blocks the API/worker process pair with `database is locked`.
        db.add(log)
        try:
            response = provider.complete(request)
            translated_title, translated_content = _translated_payload(response.text)
            item.title = translated_title
            item.content = (
                f"{_TRANSLATED_PREFIX}\n{translated_content}\n\n{_ORIGINAL_PREFIX}\n{original_content}"
            )
            log.status = "succeeded"
            log.duration_ms = int((time.perf_counter() - started) * 1000)
            log.input_tokens = response.input_tokens
            log.output_tokens = response.output_tokens
            log.cost = response.cost
            log.output_summary = f"Translated: {translated_title[:160]}"
            translated_count += 1
        except Exception as exc:
            log.status = "failed"
            log.duration_ms = int((time.perf_counter() - started) * 1000)
            log.error = str(exc)
            try:
                db.flush()
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
            raise
        # Commit each item so a later failure does not discard already translated
        # material (and the paid model call behind it), and failed calls stay
        # observable in model_call_logs.
        try:
            db.flush()
            db.commit()
        except Exception:
            # A failed flush leaves the session in a pending-rollback state;
            # using it again would raise PendingRollbackError and hide the
            # original database error. Recover first, then surface the real one.
            try:
                db.rollback()
            except Exception:
                pass
            raise
    return translated_count