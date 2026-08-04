import httpx

from content_ops.models import ModelConfig
from content_ops.providers import AnthropicProvider, CompletionRequest, OpenAICompatibleProvider
from content_ops.security import encrypt_secret


def test_openai_compatible_provider_maps_response_and_usage(monkeypatch):
    requests: list[dict] = []

    def fake_post(url, headers, json, timeout):
        requests.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    model = ModelConfig(
        provider="openai-compatible",
        name="test-model",
        api_base_url="https://model.example/v1",
        encrypted_api_key=encrypt_secret("secret-value"),
    )
    response = OpenAICompatibleProvider(model).complete(CompletionRequest(system="s", user="u"))

    assert response.text == "ok"
    assert response.input_tokens == 4
    assert response.output_tokens == 3
    assert requests[0]["url"] == "https://model.example/v1/chat/completions"
    assert requests[0]["headers"]["Authorization"] == "Bearer secret-value"
    assert requests[0]["json"]["model"] == "test-model"


def test_anthropic_provider_maps_response(monkeypatch):
    def fake_post(url, headers, json, timeout):
        assert url == "https://anthropic.example/v1/messages"
        assert headers["x-api-key"] == "secret-value"
        assert json["messages"][0]["content"] == "u"
        return httpx.Response(
            200,
            json={"content": [{"text": "anthropic result"}], "usage": {"input_tokens": 5, "output_tokens": 6}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    model = ModelConfig(
        provider="anthropic",
        name="claude-test",
        api_base_url="https://anthropic.example/v1",
        encrypted_api_key=encrypt_secret("secret-value"),
    )
    response = AnthropicProvider(model).complete(CompletionRequest(system="s", user="u"))

    assert response.text == "anthropic result"
    assert response.input_tokens == 5
    assert response.output_tokens == 6