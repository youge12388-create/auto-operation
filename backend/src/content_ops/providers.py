from __future__ import annotations

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
        if "CURRENT_CONTENT:" in request.user and "END_CURRENT_CONTENT" in request.user:
            text = request.user.split("CURRENT_CONTENT:", 1)[1].split("END_CURRENT_CONTENT", 1)[0].strip()
            return CompletionResponse(text=text, input_tokens=80, output_tokens=len(text))
        title = request.user.splitlines()[0][:80] or "每日 AI 干货"
        text = (
            f"# {title}\n\n"
            "这是一份基于已核验来源生成的草稿。\n\n"
            "## 发生了什么\n\n"
            f"当前主题为：{title}。正文仍需人工审核事实、语气和发布范围。\n\n"
            "## 需要注意\n\n"
            "本文不新增未在事实包中确认的事实。"
        )
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
