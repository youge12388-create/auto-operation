from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .models import ModelConfig
from .security import decrypt_secret


@dataclass(frozen=True)
class CompletionRequest:
    system: str
    user: str
    json_schema: dict[str, Any] | None = None
    max_tokens: int = 2000


@dataclass(frozen=True)
class CompletionResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


class ModelProvider(Protocol):
    def complete(self, request: CompletionRequest) -> CompletionResponse: ...


class FakeProvider:
    """Deterministic provider for tests and the first vertical slice."""

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        if request.user.startswith("MATERIAL_TRANSLATION_JSON"):
            title = request.user.split("TITLE:", 1)[1].split("\nCONTENT:", 1)[0].strip()
            content = request.user.split("\nCONTENT:\n", 1)[1].strip()
            return CompletionResponse(
                text=json.dumps(
                    {
                        "title": f"\u4e2d\u6587\u8bd1\u6587\uff1a{title}",
                        "content": f"\u4e2d\u6587\u8bd1\u6587\uff1a{content}",
                    },
                    ensure_ascii=False,
                ),
                input_tokens=80,
                output_tokens=len(content),
            )
        if "CURRENT_CONTENT:" in request.user and "END_CURRENT_CONTENT" in request.user:
            text = request.user.split("CURRENT_CONTENT:", 1)[1].split("END_CURRENT_CONTENT", 1)[0].strip()
            return CompletionResponse(text=text, input_tokens=80, output_tokens=len(text))
        title = request.user.splitlines()[0][:80] or "每日 AI 干货"
        text = f"""# {title}

围绕「{title}」，这篇文章只整理事实包中已经确认的信息，并把它放回读者真正关心的问题里：这件事改变了什么，为什么值得现在关注，以及下一步该如何判断。

## 发生了什么

来源显示，这个主题并不是孤立的新闻点，而是一次值得持续观察的变化。我们先保留可以追溯的事实，再区分已经发生的结果和仍需验证的推断，避免把不确定的信息写成结论。

## 对读者有什么影响

如果你正在跟进相关产品、技术或行业趋势，重点不在于追逐每一个新名词，而在于理解它是否解决了真实问题、需要什么条件，以及现有使用方式会不会因此变化。这也是后续创作时最值得补充的一线观察。

## 还需要关注什么

本文不新增未在事实包中确认的事实。发布前仍需要人工核对来源、语气和适用范围，并补充作者自己的判断或经历，让文章成为一篇完整、可读且负责任的内容。"""
        return CompletionResponse(text=text, input_tokens=80, output_tokens=len(text))


class OpenAICompatibleProvider:
    def __init__(self, model: ModelConfig):
        self.model = model
        self.api_key = decrypt_secret(model.encrypted_api_key)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self.api_key:
            raise ValueError("模型未配置 API Key")
        base_url = (self.model.api_base_url or "https://api.openai.com/v1").rstrip("/")
        payload = {
            "model": self.model.name,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_tokens,
        }
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") or {}
        return CompletionResponse(
            text=data["choices"][0]["message"]["content"],
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


class AnthropicProvider:
    def __init__(self, model: ModelConfig):
        self.model = model
        self.api_key = decrypt_secret(model.encrypted_api_key)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        if not self.api_key:
            raise ValueError("模型未配置 API Key")
        base_url = (self.model.api_base_url or "https://api.anthropic.com/v1").rstrip("/")
        response = httpx.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model.name,
                "system": request.system,
                "max_tokens": request.max_tokens,
                "messages": [{"role": "user", "content": request.user}],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") or {}
        return CompletionResponse(
            text=data["content"][0]["text"],
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


def provider_for(model: ModelConfig | None) -> ModelProvider:
    if model is None or model.provider == "fake":
        return FakeProvider()
    if model.provider == "anthropic":
        return AnthropicProvider(model)
    if model.provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider(model)
    raise ValueError(f"不支持的模型供应商：{model.provider}")
