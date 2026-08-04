import httpx
import pytest

from content_ops.api import wechat_error_detail
from content_ops.wechat import WeChatAPIError, WeChatClient


def test_wechat_client_caches_token_and_creates_draft():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/cgi-bin/token":
            assert request.url.params["appid"] == "wx-test"
            assert request.url.params["secret"] == "secret-test"
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 7200}, request=request)
        assert request.url.path == "/cgi-bin/draft/add"
        assert request.url.params["access_token"] == "token-1"
        body = httpx.Request("POST", request.url, content=request.content).read()
        assert b'"thumb_media_id":"thumb-1"' in body
        return httpx.Response(200, json={"media_id": "draft-1"}, request=request)

    with WeChatClient("wx-test", "secret-test", transport=httpx.MockTransport(handler)) as client:
        first = client.create_draft(title="标题", content_html="<p>正文</p>", thumb_media_id="thumb-1")
        second = client.create_draft(title="标题2", content_html="<p>正文2</p>", thumb_media_id="thumb-1")

    assert first.media_id == "draft-1"
    assert second.media_id == "draft-1"
    assert [request.url.path for request in calls] == ["/cgi-bin/token", "/cgi-bin/draft/add", "/cgi-bin/draft/add"]


def test_wechat_client_rejects_api_error_without_exposing_secret():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errcode": 40001, "errmsg": "invalid credential"},
            request=request,
        )

    with WeChatClient("wx-test", "secret-test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WeChatAPIError) as error:
            client.get_access_token()

    assert "secret-test" not in str(error.value)
    assert "40001" in str(error.value)


def test_wechat_ip_whitelist_error_has_actionable_recovery():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errcode": 40164, "errmsg": "invalid ip 116.30.103.251 ipv6 ::ffff:116.30.103.251"},
            request=request,
        )

    with WeChatClient("wx-test", "secret-test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(WeChatAPIError) as error:
            client.get_access_token()

    assert error.value.code == 40164
    detail = wechat_error_detail(error.value)
    assert "116.30.103.251" in detail
    assert "IP 白名单" in detail
    assert "无需重复添加" in detail


def test_wechat_client_uploads_material_and_updates_draft():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/cgi-bin/token":
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 7200}, request=request)
        if request.url.path == "/cgi-bin/material/add_material":
            assert request.url.params["type"] == "thumb"
            assert b"cover-bytes" in request.content
            return httpx.Response(200, json={"media_id": "thumb-1"}, request=request)
        if request.url.path == "/cgi-bin/draft/get":
            assert b"draft-1" in request.content
            return httpx.Response(200, json={"news_item": []}, request=request)
        if request.url.path == "/cgi-bin/draft/update":
            assert b"draft-1" in request.content
            return httpx.Response(200, json={}, request=request)
        raise AssertionError(request.url.path)

    with WeChatClient("wx-test", "secret-test", transport=httpx.MockTransport(handler)) as client:
        material = client.upload_permanent_material(
            content=b"cover-bytes",
            filename="cover.jpg",
            content_type="image/jpeg",
            material_type="thumb",
        )
        draft = client.get_draft("draft-1")
        client.update_draft(
            media_id="draft-1",
            article={
                "title": "标题",
                "content": "<p>正文</p>",
                "thumb_media_id": material.media_id,
            },
        )

    assert material.media_id == "thumb-1"
    assert draft == {"news_item": []}
    assert paths == [
        "/cgi-bin/token",
        "/cgi-bin/material/add_material",
        "/cgi-bin/draft/get",
        "/cgi-bin/draft/update",
    ]


def test_wechat_client_rejects_external_style_tags():
    from pytest import raises

    with raises(ValueError, match="内嵌"):
        WeChatClient._article_payload(
            title="标题",
            content_html="<style>.x{color:red}</style>",
            thumb_media_id="thumb-1",
        )


def test_wechat_client_submits_publish():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/cgi-bin/token":
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 7200}, request=request)
        assert request.url.path == "/cgi-bin/freepublish/submit"
        assert b'"media_id":"draft-1"' in request.content
        return httpx.Response(200, json={"publish_id": "publish-1"}, request=request)

    with WeChatClient("wx-test", "secret-test", transport=httpx.MockTransport(handler)) as client:
        result = client.submit_publish("draft-1")

    assert result.publish_id == "publish-1"
    assert paths == ["/cgi-bin/token", "/cgi-bin/freepublish/submit"]


def test_wechat_client_reads_publish_status():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/token":
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 7200}, request=request)
        assert request.url.path == "/cgi-bin/freepublish/get"
        assert b'"publish_id":"publish-1"' in request.content
        return httpx.Response(200, json={"publish_id": "publish-1", "publish_status": 0}, request=request)

    with WeChatClient("wx-test", "secret-test", transport=httpx.MockTransport(handler)) as client:
        status = client.get_publish_status("publish-1")

    assert status["publish_status"] == 0
