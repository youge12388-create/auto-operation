from __future__ import annotations

import json
from typing import Any

import httpx

from .providers import CompletionRequest, ModelProvider
from .settings import get_settings


def _json_object(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _extract_claims(provider: ModelProvider, title: str, sources: list[dict[str, str]], limit: int) -> list[str]:
    response = provider.complete(
        CompletionRequest(
            system=(
                "Extract only independently checkable factual claims. "
                "Return JSON with a claims array of short strings. "
                "Do not include opinions, predictions, or claims not present in the supplied sources."
            ),
            user="FACT_CLAIMS_JSON\n"
            + json.dumps({"title": title, "sources": sources, "limit": limit}, ensure_ascii=False),
            max_tokens=1200,
        )
    )
    payload = _json_object(response.text)
    claims = payload.get("claims") if payload else None
    if not isinstance(claims, list):
        return []
    return [str(claim).strip()[:800] for claim in claims if isinstance(claim, str) and claim.strip()][:limit]


def _search(query: str) -> list[dict[str, str]]:
    settings = get_settings()
    if not settings.tavily_api_key:
        raise RuntimeError("Tavily API key is not configured")
    response = httpx.post(
        f"{settings.tavily_api_base_url.rstrip('/')}/search",
        headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
        json={"query": query, "search_depth": "advanced", "max_results": 4, "include_raw_content": "text"},
        timeout=settings.tavily_timeout_seconds,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not isinstance(results, list):
        return []
    return [
        {
            "title": str(item.get("title") or "")[:500],
            "url": str(item.get("url") or "")[:2000],
            "excerpt": str(item.get("raw_content") or item.get("content") or "")[:5000],
        }
        for item in results
        if isinstance(item, dict) and item.get("url")
    ]


def _evaluate_claims(provider: ModelProvider, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    response = provider.complete(
        CompletionRequest(
            system=(
                "You are a fact checker. For each claim, classify it as supported, partially_supported, "
                "conflicting, unsupported, or unverifiable using only the supplied source excerpts. Return JSON "
                "with a claims array; each item must have statement, status, summary, and citation_urls."
            ),
            user="FACT_VERDICTS_JSON\n" + json.dumps({"claims": claims}, ensure_ascii=False),
            max_tokens=1600,
        )
    )
    payload = _json_object(response.text)
    result = payload.get("claims") if payload else None
    if not isinstance(result, list):
        return []
    allowed = {"supported", "partially_supported", "conflicting", "unsupported", "unverifiable"}
    return [
        {
            "statement": str(item.get("statement") or "")[:800],
            "status": str(item.get("status") or "unverifiable"),
            "summary": str(item.get("summary") or "")[:1000],
            "citation_urls": [str(url)[:2000] for url in item.get("citation_urls", []) if isinstance(url, str)][:4],
        }
        for item in result
        if isinstance(item, dict) and str(item.get("status") or "") in allowed
    ]


def verify_evidence(provider: ModelProvider, title: str, sources: list[dict[str, str]]) -> dict[str, Any]:
    """Create an auditable, fail-closed verification report from external web evidence."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return {
            "verification_status": "unavailable",
            "summary": "Tavily API key is not configured; automatic publication requires human review.",
            "claims": [],
            "sources": [],
        }
    try:
        claims = _extract_claims(provider, title, sources, settings.fact_verification_max_claims)
    except Exception as exc:
        return {
            "verification_status": "unavailable",
            "summary": f"Claim extraction was unavailable: {exc}",
            "claims": [],
            "sources": [],
        }
    if not claims:
        return {
            "verification_status": "unavailable",
            "summary": "No atomic factual claims could be extracted; automatic publication requires human review.",
            "claims": [],
            "sources": [],
        }
    try:
        candidates = [{"statement": claim, "sources": _search(claim)} for claim in claims]
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "verification_status": "unavailable",
            "summary": f"Online verification was unavailable: {exc}",
            "claims": [],
            "sources": [],
        }
    try:
        verdicts = _evaluate_claims(provider, candidates)
    except Exception as exc:
        return {
            "verification_status": "unavailable",
            "summary": f"Claim evaluation was unavailable: {exc}",
            "claims": [],
            "sources": candidates,
        }
    if not verdicts:
        return {
            "verification_status": "unavailable",
            "summary": "Verification model did not return a valid claim report.",
            "claims": [],
            "sources": candidates,
        }
    status = "verified" if all(item["status"] == "supported" for item in verdicts) else "needs_review"
    return {
        "verification_status": status,
        "summary": (
            "All factual claims are supported."
            if status == "verified"
            else "One or more factual claims need editorial review."
        ),
        "claims": verdicts,
        "sources": candidates,
    }
