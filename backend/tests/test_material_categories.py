import pytest

from content_ops.api import (
    assign_material_category,
    create_material_category,
    disable_material_category,
    list_material_categories,
    list_materials,
    restore_material_category,
    update_material_category,
)
from content_ops.ingestion import collect_source
from content_ops.material_categories import ensure_builtin_material_categories
from content_ops.models import Article, MaterialCategory, ModelConfig, Source, SourceItem, Strategy
from content_ops.providers import FakeProvider
from content_ops.schemas import MaterialCategoryAssign, MaterialCategoryCreate, MaterialCategoryUpdate
from content_ops.strategy_config import StrategyConfigError, validate_strategy_references
from content_ops.workflow import create_job, run_job


def test_collection_classifies_material_with_configured_model(db):
    category = MaterialCategory(name="AI 前沿", description="AI 模型和研究")
    model = ModelConfig(provider="fake", name="classification-model", enabled=True)
    source = Source(
        name="classification source",
        source_type="manual",
        url="https://example.com/classification",
        config_json={"title": "新的 AI 模型", "content": "这是一条已经翻译为中文的 AI 进展。"},
    )
    db.add_all([category, model, source])
    db.commit()

    item = collect_source(db, source)[0]

    assert item.status == "verified"
    assert item.category_id == category.id
    assert item.classification_status == "classified"
    assert item.classification_source == "ai"
    assert item.classification_confidence == 86


def test_material_is_retained_when_classification_model_is_missing(db):
    category = MaterialCategory(name="行业观察")
    source = Source(
        name="no model source",
        source_type="manual",
        url="https://example.com/no-model",
        config_json={"title": "行业变化", "content": "这条中文素材仍然需要进入素材池。"},
    )
    db.add_all([category, source])
    db.commit()

    item = collect_source(db, source)[0]

    assert item.status == "verified"
    assert item.classification_status == "failed"
    assert item.classification_error == "没有可用的 AI 分类模型"


def test_category_management_and_manual_correction_are_reversible(db):
    created = create_material_category(
        MaterialCategoryCreate(name="产品发布", description="产品动态"),
        None,
        db,
    )
    source = Source(name="manual correction source", source_type="manual", url="")
    db.add(source)
    db.flush()
    material = SourceItem(
        source_id=source.id,
        title="一条素材",
        url="",
        canonical_url="manual://category-correction",
        content="中文素材内容",
        content_hash="f" * 64,
        status="verified",
    )
    db.add(material)
    db.commit()

    assigned = assign_material_category(
        material.id,
        MaterialCategoryAssign(category_id=created.id),
        None,
        db,
    )
    assert assigned.category_id == created.id
    assert assigned.category_name == "产品发布"
    assert assigned.classification_source == "manual"

    disabled = disable_material_category(created.id, None, db)
    assert disabled.enabled is False
    assert disabled.material_count == 1
    with pytest.raises(StrategyConfigError, match="素材分类已停用"):
        validate_strategy_references(db, {"material_category_ids": [created.id]})

    restored = restore_material_category(created.id, None, db)
    assert restored.enabled is True
    renamed = update_material_category(
        created.id,
        MaterialCategoryUpdate(name="产品与商业"),
        None,
        db,
    )
    assert renamed.name == "产品与商业"
    assert list_material_categories(True, None, db)[0].material_count == 1
    assert list_materials(None, None, None, db, category_id=created.id)[0].id == material.id

    cleared = assign_material_category(
        material.id,
        MaterialCategoryAssign(category_id=None),
        None,
        db,
    )
    assert cleared.category_id is None
    assert cleared.classification_status == "unclassified"

def test_automatic_job_selects_only_configured_material_categories_and_freezes_selection(db):
    target = MaterialCategory(name="目标分类", description="本生产线要使用的素材")
    excluded = MaterialCategory(name="排除分类", description="本生产线不使用")
    model = ModelConfig(provider="fake", name="automatic-selection-model", enabled=True)
    target_source = Source(
        name="target category source",
        source_type="manual",
        url="https://example.com/target-category",
        config_json={"title": "目标分类素材", "content": "目标分类中的中文事实素材。"},
        enabled=False,
    )
    excluded_source = Source(
        name="excluded category source",
        source_type="manual",
        url="https://example.com/excluded-category",
        config_json={"title": "不应入选的素材", "content": "另一个分类中的中文事实素材。"},
        enabled=False,
    )
    db.add_all([target, excluded, model, target_source, excluded_source])
    db.flush()
    target_item = SourceItem(
        source_id=target_source.id,
        title="目标分类素材",
        url=target_source.url,
        canonical_url=target_source.url,
        content="目标分类中的中文事实素材。",
        content_hash="1" * 64,
        status="verified",
        triage_status="inbox",
        category_id=target.id,
        classification_status="classified",
        classification_source="manual",
    )
    excluded_item = SourceItem(
        source_id=excluded_source.id,
        title="不应入选的素材",
        url=excluded_source.url,
        canonical_url=excluded_source.url,
        content="另一个分类中的中文事实素材。",
        content_hash="2" * 64,
        status="verified",
        triage_status="inbox",
        category_id=excluded.id,
        classification_status="classified",
        classification_source="manual",
    )
    strategy = Strategy(
        name="category scoped automation",
        objective="只从目标素材分类自动创作",
        config_json={
            "material_category_ids": [target.id],
            "default_model_id": model.id,
            "review_rules": {"human_review_required": False},
        },
    )
    db.add_all([target_item, excluded_item, strategy])
    db.commit()

    job = create_job(db, strategy, "category-scoped-automation")
    result = run_job(db, job.id, FakeProvider())
    article = db.query(Article).filter(Article.job_id == job.id).one()

    assert result.status == "succeeded"
    assert article.title == "目标分类素材"
    assert article.runtime_snapshot_json["execution_config"]["material_category_ids"] == [target.id]
    assert article.runtime_snapshot_json["material_selection"]["material_ids"] == [target_item.id]
    assert excluded_item.id not in article.runtime_snapshot_json["material_selection"]["material_ids"]

def test_builtin_material_categories_are_seeded_once(db):
    created = ensure_builtin_material_categories(db)
    db.commit()
    repeated = ensure_builtin_material_categories(db)

    assert [item.name for item in created] == ["AI 前沿", "产品与商业", "技术与工具", "行业观察", "其他"]
    assert repeated == []
    assert db.query(MaterialCategory).count() == 5
