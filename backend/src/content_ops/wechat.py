from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from .settings import Settings


class WeChatAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        retryable: bool = False,
        result_unknown: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.result_unknown = result_unknown


@dataclass(frozen=True)
class WeChatDraftResult:
    media_id: str


@dataclass(frozen=True)
class WeChatMaterialResult:
    media_id: str
    url: str | None = None


@dataclass(frozen=True)
class WeChatPublishResult:
    publish_id: str


class WeChatClient:
    """Synchronous client for the Official Account token, material and draft APIs."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        *,
        base_url: str = "https://api.weixin.qq.com",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not app_id or not app_secret:
            raise ValueError("微信公众账号凭证未配置")
        self._app_id = app_id
        self._app_secret = app_secret
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    @classmethod
    def from_settings(cls, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> "WeChatClient":
        if not settings.wechat_app_id or not settings.wechat_app_secret:
            raise ValueError("微信公众账号凭证未配置")
        return cls(
            settings.wechat_app_id,
            settings.wechat_app_secret,
            base_url=settings.wechat_api_base_url,
            timeout=settings.wechat_timeout_seconds,
            transport=transport,
        )

    def __enter__(self) -> "WeChatClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _parse_json(self, response: httpx.Response, *, result_unknown: bool = False) -> dict[str, Any]:
        if response.status_code >= 500:
            raise WeChatAPIError(
                "微信接口暂时不可用",
                retryable=True,
                result_unknown=result_unknown,
            )
        if response.status_code >= 400:
            raise WeChatAPIError(f"微信接口 HTTP 错误：{response.status_code}", retryable=False)
        try:
            data = response.json()
        except ValueError as exc:
            raise WeChatAPIError("微信接口返回了无效响应", retryable=True, result_unknown=result_unknown) from exc
        if not isinstance(data, dict):
            raise WeChatAPIError("微信接口返回格式错误", retryable=True, result_unknown=result_unknown)
        errcode = data.get("errcode")
        if errcode not in (None, 0):
            errmsg = str(data.get("errmsg") or "未知错误")[:200]
            raise WeChatAPIError(
                f"微信接口错误 {errcode}：{errmsg}",
                code=int(errcode),
                retryable=int(errcode) in {42001, 45009},
            )
        return data

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        result_unknown: bool = False,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, params=params, json=json)
        except httpx.RequestError as exc:
            raise WeChatAPIError(
                "微信接口网络请求失败",
                retryable=True,
                result_unknown=result_unknown,
            ) from exc
        return self._parse_json(response, result_unknown=result_unknown)

    def _request_multipart(
        self,
        path: str,
        *,
        params: dict[str, str],
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        try:
            response = self._client.post(
                path,
                params=params,
                files={"media": (filename, content, content_type)},
            )
        except httpx.RequestError as exc:
            raise WeChatAPIError("微信接口网络请求失败", retryable=True, result_unknown=True) from exc
        return self._parse_json(response, result_unknown=True)

    def get_access_token(self) -> str:
        if self._access_token and monotonic() < self._access_token_expires_at:
            return self._access_token
        data = self._request_json(
            "GET",
            "/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": self._app_id, "secret": self._app_secret},
        )
        token = data.get("access_token")
        expires_in = int(data.get("expires_in") or 7200)
        if not isinstance(token, str) or not token:
            raise WeChatAPIError("微信接口未返回 access_token", retryable=True)
        self._access_token = token
        self._access_token_expires_at = monotonic() + max(expires_in - 120, 1)
        return token

    def test_connection(self) -> None:
        self.get_access_token()

    def upload_permanent_material(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str = "image/jpeg",
        material_type: str = "thumb",
    ) -> WeChatMaterialResult:
        if not content:
            raise ValueError("素材文件不能为空")
        if material_type not in {"image", "voice", "video", "thumb"}:
            raise ValueError("不支持的微信素材类型")
        if material_type == "thumb" and len(content) > 64 * 1024:
            raise ValueError("微信公众号封面缩略图不能超过 64KB")
        data = self._request_multipart(
            "/cgi-bin/material/add_material",
            params={"access_token": self.get_access_token(), "type": material_type},
            filename=filename,
            content=content,
            content_type=content_type,
        )
        media_id = data.get("media_id")
        if not isinstance(media_id, str) or not media_id:
            raise WeChatAPIError("微信接口未返回素材 media_id", retryable=True, result_unknown=True)
        url = data.get("url")
        return WeChatMaterialResult(media_id=media_id, url=url if isinstance(url, str) else None)

    def upload_article_image(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str = "image/jpeg",
    ) -> str:
        if not content:
            raise ValueError("正文图片不能为空")
        data = self._request_multipart(
            "/cgi-bin/media/uploadimg",
            params={"access_token": self.get_access_token()},
            filename=filename,
            content=content,
            content_type=content_type,
        )
        url = data.get("url")
        if not isinstance(url, str) or not url:
            raise WeChatAPIError("微信接口未返回正文图片 URL", retryable=True, result_unknown=True)
        return url

    @staticmethod
    def _article_payload(
        *,
        title: str,
        content_html: str,
        thumb_media_id: str,
        author: str = "",
        digest: str = "",
        content_source_url: str = "",
        need_open_comment: bool = False,
        only_fans_can_comment: bool = False,
    ) -> dict[str, Any]:
        if not title.strip():
            raise ValueError("微信文章标题不能为空")
        if len(title.strip()) > 64:
            raise ValueError("微信文章标题不能超过 64 个字符")
        if not content_html.strip():
            raise ValueError("微信文章正文不能为空")
        if "<style" in content_html.lower():
            raise ValueError("微信正文必须使用内嵌 style，禁止外部样式标签")
        if "javascript:" in content_html.lower():
            raise ValueError("微信正文不允许使用 javascript 方案")
        if not thumb_media_id.strip():
            raise ValueError("微信公众号草稿必须提供封面素材 ID")
        return {
            "title": title,
            "author": author,
            "digest": digest,
            "content": content_html,
            "content_source_url": content_source_url,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1 if need_open_comment else 0,
            "only_fans_can_comment": 1 if only_fans_can_comment else 0,
        }

    def create_draft(self, **article: Any) -> WeChatDraftResult:
        data = self._request_json(
            "POST",
            "/cgi-bin/draft/add",
            params={"access_token": self.get_access_token()},
            json={"articles": [self._article_payload(**article)]},
            result_unknown=True,
        )
        media_id = data.get("media_id")
        if not isinstance(media_id, str) or not media_id:
            raise WeChatAPIError("微信接口未返回草稿 media_id", retryable=True, result_unknown=True)
        return WeChatDraftResult(media_id=media_id)

    def get_draft(self, media_id: str) -> dict[str, Any]:
        if not media_id.strip():
            raise ValueError("草稿 media_id 不能为空")
        return self._request_json(
            "POST",
            "/cgi-bin/draft/get",
            params={"access_token": self.get_access_token()},
            json={"media_id": media_id},
        )

    def update_draft(self, *, media_id: str, article: dict[str, Any], index: int = 0) -> None:
        if not media_id.strip():
            raise ValueError("草稿 media_id 不能为空")
        self._request_json(
            "POST",
            "/cgi-bin/draft/update",
            params={"access_token": self.get_access_token()},
            json={"media_id": media_id, "index": index, "articles": article},
            result_unknown=True,
        )

    def submit_publish(self, media_id: str) -> WeChatPublishResult:
        if not media_id.strip():
            raise ValueError("草稿 media_id 不能为空")
        data = self._request_json(
            "POST",
            "/cgi-bin/freepublish/submit",
            params={"access_token": self.get_access_token()},
            json={"media_id": media_id},
            result_unknown=True,
        )
        publish_id = data.get("publish_id")
        if not isinstance(publish_id, str) or not publish_id:
            raise WeChatAPIError("微信接口未返回发布 ID", retryable=True, result_unknown=True)
        return WeChatPublishResult(publish_id=publish_id)

    def get_publish_status(self, publish_id: str) -> dict[str, Any]:
        if not publish_id.strip():
            raise ValueError("发布 ID 不能为空")
        return self._request_json(
            "POST",
            "/cgi-bin/freepublish/get",
            params={"access_token": self.get_access_token()},
            json={"publish_id": publish_id},
        )

    def count_drafts(self) -> int:
        data = self._request_json(
            "GET",
            "/cgi-bin/draft/count",
            params={"access_token": self.get_access_token()},
        )
        total_count = data.get("total_count")
        if not isinstance(total_count, int):
            raise WeChatAPIError("微信接口未返回草稿数量", retryable=True)
        return total_count

    def batch_get_drafts(self, *, offset: int = 0, count: int = 20, no_content: bool = True) -> dict[str, Any]:
        if offset < 0 or count < 1 or count > 20:
            raise ValueError("草稿列表分页参数无效")
        return self._request_json(
            "POST",
            "/cgi-bin/draft/batchget",
            params={"access_token": self.get_access_token()},
            json={"offset": offset, "count": count, "no_content": 1 if no_content else 0},
        )
