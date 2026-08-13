import pytest

from content_ops.api import (
    add_manual_material,
    create_topic_algorithm,
    delete_topic_algorithm,
    list_topic_algorithms,
    update_topic_algorithm,
)
from content_ops.models import Source, SourceItem
from content_ops.schemas import ManualMaterialCreate, TopicAlgorithmCreate, TopicAlgorithmUpdate
from content_ops.workflow import _require_article_body


def test_custom_topic_algorithm_can_be_created_updated_and_deleted(db):
    defaults = list_topic_algorithms(None, db)
    assert len(defaults) == 1
    assert defaults[0].is_builtin is True

    created = create_topic_algorithm(
        TopicAlgorithmCreate(
            name="读者价值优先",
            instructions="优先选择能解决具体问题的选题。",
            max_topics=5,
            weights={"reader_value": 60, "heat": 20, "timeliness": 10, "strategy_fit": 10},
        ),
        None,
        db,
    )
    assert created.name == "读者价值优先"
    assert created.weights["reader_value"] == 60

    updated = update_topic_algorithm(
        created.id,
        TopicAlgorithmUpdate(instructions="优先选择有证据且能落地的选题。", max_topics=3),
        None,
        db,
    )
    assert updated.max_topics == 3
    assert updated.instructions.startswith("优先选择")

    deleted = delete_topic_algorithm(created.id, None, db)
    assert deleted.id == created.id
    assert [item.id for item in list_topic_algorithms(None, db)] == [defaults[0].id]


def test_manual_material_is_saved_directly_to_retained_pool(db):
    material = add_manual_material(
        ManualMaterialCreate(
            title="我的一条观察",
            content="这是手动粘贴的完整素材正文。",
            source_name="我的观察",
        ),
        None,
        db,
    )

    source = db.get(Source, material.source_id)
    saved = db.get(SourceItem, material.id)
    assert source is not None and source.source_type == "manual"
    assert source.name == "我的观察"
    assert saved is not None and saved.triage_status == "selected"
    assert saved.content == "这是手动粘贴的完整素材正文。"


def test_quality_report_is_stripped_from_article_body():
    with pytest.raises(ValueError, match="不是文章正文"):
        _require_article_body("## 质检报告\n\nL1 硬性规则\n" + "说明" * 200, "最终改写")

    article = "# 可读文章\n\n" + "这是经过事实核验后形成的完整文章段落。 " * 40
    report = "\n\n## 质检报告\n\n**L1 硬性规则** ✅"
    assert _require_article_body(article + report, "最终改写") == article.strip()