import httpx
from sqlalchemy import select

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