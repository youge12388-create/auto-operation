from content_ops.api import (
    add_source,
    add_source_group,
    app,
    disable_source,
    disable_source_group,
    list_source_groups,
    source_read,
    update_source,
    update_source_group,
)
from content_ops.ingestion import collect_source
from content_ops.models import Source
from content_ops.schemas import SourceCreate, SourceGroupCreate, SourceGroupUpdate


def test_source_group_update_route_is_registered():
    route = next(item for item in app.routes if item.path == "/api/v1/sources/groups/{group_id}")

    assert "PUT" in route.methods

def test_source_read_normalizes_legacy_website_type(db):
    source = Source(
        name="Legacy website",
        source_type="website",
        url="https://example.com",
        group_name="default",
        config_json={},
    )
    db.add(source)
    db.flush()

    assert source_read(source).source_type == "url"


def test_source_group_and_source_crud_preserve_group_scope(db):
    group = add_source_group(SourceGroupCreate(name="AI 研究"), None, db)
    source = add_source(
        SourceCreate(
            name="官方 RSS",
            source_type="rss",
            url="https://example.com/feed.xml",
            group_name="AI 研究",
            group_id=group.id,
        ),
        None,
        db,
    )
    assert source.group_id == group.id
    assert list_source_groups(None, db)[0].name == "AI 研究"

    updated = update_source(
        source.id,
        SourceCreate(
            name="官方 RSS（更新）",
            source_type="rss",
            url="https://example.com/feed-v2.xml",
            group_name="AI 研究",
            group_id=group.id,
        ),
        None,
        db,
    )
    assert updated.name.endswith("更新）")
    assert updated.group_id == group.id

    disabled = disable_source(source.id, None, db)
    assert disabled.enabled is False

def test_source_group_can_be_disabled_and_stops_collection(db):
    group = add_source_group(SourceGroupCreate(name="停用分组"), None, db)
    source = add_source(
        SourceCreate(
            name="分组手动源",
            source_type="manual",
            url="https://example.com/grouped",
            group_id=group.id,
            config={"title": "不应采集", "content": "不应采集的内容"},
        ),
        None,
        db,
    )
    renamed = update_source_group(group.id, SourceGroupUpdate(name="停用分组（更新）"), None, db)
    assert renamed.name.endswith("更新）")
    disabled = disable_source_group(group.id, None, db)
    assert disabled.enabled is False
    assert collect_source(db, db.get(Source, source.id)) == []