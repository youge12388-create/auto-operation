import httpx
import pytest
from sqlalchemy import select

from content_ops.fetching import FetchedResponse
from content_ops.ingestion import collect_source, content_hash, normalize_url
from content_ops.models import MaterialCategory, ModelConfig, Source, SourceItem
from content_ops.providers import FakeProvider


def test_normalize_url_removes_fragment_and_trailing_slash():
    assert normalize_url("HTTPS://Example.COM/path/#section") == "https://example.com/path"


def test_content_hash_is_stable():
    assert content_hash("  same content  ") == content_hash("same content")


def test_manual_collection_is_idempotent(db):
    source = Source(
        name="manual",
        source_type="manual",
        url="https://example.com/source",
        config_json={"title": "标题", "content": "正文"},
    )
    db.add(source)
    db.commit()

    first = collect_source(db, source)
    second = collect_source(db, source)
    db.commit()

    assert first[0].id == second[0].id
    item = db.scalar(select(SourceItem).where(SourceItem.source_id == source.id))
    assert item is not None
    assert item.content == "正文"
    assert source.last_error is None
    assert source.last_success_at is not None


def test_collection_deduplicates_same_url_or_content_across_sources(db):
    first_source = Source(
        name="first",
        source_type="manual",
        url="https://example.com/shared#one",
        config_json={"title": "共享内容", "content": "跨来源相同事实"},
    )
    second_source = Source(
        name="second",
        source_type="manual",
        url="https://example.com/shared#two",
        config_json={"title": "另一个标题", "content": "跨来源相同事实"},
    )
    db.add_all([first_source, second_source])
    db.commit()

    first = collect_source(db, first_source)
    second = collect_source(db, second_source)
    db.commit()

    assert first[0].id == second[0].id
    assert db.query(SourceItem).count() == 1


def test_manual_collection_translates_foreign_material_before_returning_it(db):
    original = "A research team released a detailed workflow for evaluating AI agents across real tool-use tasks."
    source = Source(
        name="English source",
        source_type="manual",
        url="https://example.com/foreign-material",
        config_json={"title": "Agent evaluation workflow", "content": original},
    )
    model = ModelConfig(name="translation-model", provider="fake", enabled=True)
    db.add_all([source, model])
    db.commit()

    items = collect_source(db, source, FakeProvider(), model)

    assert items[0].title.startswith("\u4e2d\u6587\u8bd1\u6587\uff1a")
    assert items[0].content.startswith("\u3010\u4e2d\u6587\u8bd1\u6587\u3011")
    assert items[0].content.endswith(original)

def test_aihot_api_collection_maps_category_without_model_calls(monkeypatch, db):
    def fake_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            request=httpx.Request("GET", str(url)),
            json={
                "items": [
                    {
                        "id": "item-1",
                        "title": "NVIDIA 发布新模型",
                        "originalTitle": "NVIDIA Alpamayo",
                        "summary": "NVIDIA 发布面向 Robotaxi 的开源视觉语言动作模型。",
                        "category": "ai-models",
                        "publishedAt": "2026-08-05T01:00:00Z",
                        "links": {
                            "original": "https://example.com/nvidia",
                            "aihot": "https://aihot.virxact.com/items/abc",
                        },
                    },
                    {
                        "id": "item-2",
                        "title": "某产品发布",
                        "summary": "某公司发布新产品。",
                        "category": "ai-products",
                        "publishedAt": "2026-08-05T02:00:00Z",
                        "links": {"original": "https://example.com/product"},
                    },
                ]
            },
        )

    monkeypatch.setattr("content_ops.ingestion.httpx.get", fake_get)
    source = Source(
        name="AI HOT",
        source_type="aihot_api",
        url="https://aihot.virxact.com/api/v1/items",
        config_json={"window": "24h", "limit": 100},
    )
    db.add(source)
    db.commit()

    items = collect_source(db, source)
    db.commit()

    assert len(items) == 2
    assert items[0].title == "NVIDIA 发布新模型"
    assert items[0].content == "NVIDIA 发布面向 Robotaxi 的开源视觉语言动作模型。"
    assert items[0].published_at is not None
    frontier = db.scalar(select(MaterialCategory).where(MaterialCategory.name == "AI 前沿"))
    assert frontier is not None
    assert items[0].category_id == frontier.id
    assert items[0].classification_source == "ai"
    products = db.scalar(select(MaterialCategory).where(MaterialCategory.name == "产品与商业"))
    assert products is not None
    assert items[1].category_id == products.id
    assert source.last_error is None
    assert source.last_success_at is not None


def test_rss_entries_without_links_do_not_overwrite_each_other(monkeypatch, db):
    rss_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>测试</title>'
        "<item><title>第一</title><description>内容一</description></item>"
        "<item><title>第二</title><description>内容二</description></item>"
        "</channel></rss>"
    ).encode("utf-8")

    def fake_fetch(url, **kwargs):
        return FetchedResponse(
            url=str(url),
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=rss_xml,
        )

    monkeypatch.setattr("content_ops.ingestion.fetch_url", fake_fetch)
    source = Source(name="无链接 RSS", source_type="rss", url="https://example.com/feed")
    db.add(source)
    db.commit()

    items = collect_source(db, source)
    db.commit()

    # Both entries lack a link; they must be kept as separate items instead of
    # the second one overwriting the first via the shared source-URL canonical.
    assert len(items) == 2
    assert {item.title for item in items} == {"第一", "第二"}


def test_empty_rss_is_reported_as_collection_failure(monkeypatch, db):
    def fake_fetch(url, **kwargs):
        return FetchedResponse(
            url=str(url),
            status_code=200,
            headers={"content-type": "application/rss+xml"},
            content=b"<rss><channel><title>empty</title></channel></rss>",
        )

    monkeypatch.setattr("content_ops.ingestion.fetch_url", fake_fetch)
    source = Source(name="empty RSS", source_type="rss", url="https://example.com/empty-feed")
    db.add(source)
    db.commit()

    with pytest.raises(ValueError, match="RSS 信息源没有可用条目"):
        collect_source(db, source)

    db.refresh(source)
    assert source.last_error == "RSS 信息源没有可用条目"
    assert source.last_success_at is None


def test_aihot_items_without_links_do_not_overwrite_each_other(monkeypatch, db):
    def fake_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            request=httpx.Request("GET", str(url)),
            json={
                "items": [
                    {
                        "id": "item-1",
                        "title": "条目一",
                        "summary": "内容一",
                        "category": None,
                        "publishedAt": "2026-08-05T01:00:00Z",
                        "links": {},
                    },
                    {
                        "id": "item-2",
                        "title": "条目二",
                        "summary": "内容二",
                        "category": None,
                        "publishedAt": "2026-08-05T02:00:00Z",
                        "links": {},
                    },
                ]
            },
        )

    monkeypatch.setattr("content_ops.ingestion.httpx.get", fake_get)
    source = Source(
        name="AI HOT",
        source_type="aihot_api",
        url="https://aihot.virxact.com/api/v1/items",
        config_json={"window": "24h", "limit": 100},
    )
    db.add(source)
    db.commit()

    items = collect_source(db, source)
    db.commit()

    assert len(items) == 2
    assert {item.title for item in items} == {"条目一", "条目二"}
