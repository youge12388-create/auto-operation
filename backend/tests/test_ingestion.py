from sqlalchemy import select

from content_ops.ingestion import collect_source, content_hash, normalize_url
from content_ops.models import Source, SourceItem


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