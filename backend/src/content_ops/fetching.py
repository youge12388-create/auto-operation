from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlsplit

from crawlee import Request
from crawlee.crawlers import HttpCrawler, HttpCrawlingContext
from crawlee.request_loaders import ThrottlingRequestManager
from crawlee.storage_clients import MemoryStorageClient
from crawlee.storages import RequestQueue


class SourceFetchError(RuntimeError):
    """Raised when Crawlee cannot fetch a source response."""


@dataclass(frozen=True, slots=True)
class FetchedResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes

    @property
    def text(self) -> str:
        content_type = self.headers.get("content-type", "")
        match = re.search(r"charset=\s*[\"']?([^;\s\"']+)", content_type, re.IGNORECASE)
        encoding = match.group(1) if match else "utf-8"
        try:
            return self.content.decode(encoding, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


_DEFAULT_HEADERS = {
    "Accept": "text/html, application/xhtml+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_url(
    url: str,
    *,
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
    headers: dict[str, str] | None = None,
    respect_robots_txt: bool = True,
) -> FetchedResponse:
    """Fetch one source URL with Crawlee's HTTP crawler.

    Content-ops still owns source scheduling and persistence. Crawlee is
    limited to one URL here so it provides reliable HTTP fetching, retries,
    headers and robots.txt handling without creating a second crawler queue.
    Browser crawling is intentionally not enabled by this module.
    """

    request_headers = {**_DEFAULT_HEADERS, **(headers or {})}

    async def run() -> FetchedResponse:
        result: FetchedResponse | None = None
        failure: Exception | None = None
        storage_client = MemoryStorageClient()
        request_queue = await RequestQueue.open(storage_client=storage_client)

        async def open_domain_queue(**kwargs):  # type: ignore[no-untyped-def]
            kwargs["storage_client"] = storage_client
            return await RequestQueue.open(**kwargs)

        domain = urlsplit(url).hostname or ""
        request_manager = ThrottlingRequestManager(
            request_queue,
            domains=[domain] if domain else [],
            request_manager_opener=open_domain_queue,
        )
        crawler = HttpCrawler(
            max_request_retries=max(0, max_retries),
            max_requests_per_crawl=1,
            request_handler_timeout=timedelta(seconds=timeout_seconds),
            storage_client=storage_client,
            request_manager=request_manager,
            respect_robots_txt_file=respect_robots_txt,
            configure_logging=False,
        )

        @crawler.router.default_handler
        async def request_handler(context: HttpCrawlingContext) -> None:
            nonlocal result
            response = context.http_response
            body = await response.read()
            response_headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            result = FetchedResponse(
                url=getattr(context.request, "loaded_url", None) or context.request.url,
                status_code=response.status_code,
                headers=response_headers,
                content=body,
            )

        @crawler.failed_request_handler
        async def failed_request(_context, error: Exception) -> None:  # type: ignore[no-untyped-def]
            nonlocal failure
            failure = error

        request = Request.from_url(
            url,
            headers=request_headers,
            max_retries=max(0, max_retries),
        )
        await crawler.run([request])
        if result is not None:
            return result
        if failure is not None:
            raise SourceFetchError(f"{type(failure).__name__}: {failure}") from failure
        raise SourceFetchError("Crawlee 未返回有效响应，可能被 robots.txt 或站点策略拒绝")

    try:
        return asyncio.run(run())
    except SourceFetchError:
        raise
    except Exception as exc:
        raise SourceFetchError(f"{type(exc).__name__}: {exc}") from exc
