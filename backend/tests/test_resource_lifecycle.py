from content_ops.api import (
    add_channel_account,
    add_model,
    disable_channel_account,
    disable_model,
    rollback_skill,
    update_channel_account,
    update_model,
)
from content_ops.models import Skill, SkillVersion
from content_ops.schemas import (
    ChannelAccountCreate,
    ChannelAccountUpdate,
    ModelCreate,
    ModelUpdate,
)


def test_model_and_channel_lifecycle_redacts_secrets(db):
    model = add_model(
        ModelCreate(provider="fake", name="initial", api_key="model-secret"),
        None,
        db,
    )
    updated_model = update_model(model.id, ModelUpdate(name="updated", enabled=False), None, db)
    assert updated_model.enabled is False
    disabled_model = disable_model(model.id, None, db)
    assert disabled_model.enabled is False

    account = add_channel_account(
        ChannelAccountCreate(name="lifecycle-channel", app_id="wx-1", app_secret="channel-secret"),
        None,
        db,
    )
    updated_account = update_channel_account(
        account.id,
        ChannelAccountUpdate(app_secret="channel-secret-2", enabled=False),
        None,
        db,
    )
    assert updated_account.enabled is False
    assert updated_account.has_credentials is True
    assert "channel-secret-2" not in str(updated_account.model_dump())
    disabled_account = disable_channel_account(account.id, None, db)
    assert disabled_account.enabled is False


def test_skill_rollback_restores_version_snapshot(db):
    skill = Skill(
        name="rollback-skill",
        skill_type="rewrite",
        version="2.0.0",
        status="published",
        manifest_json={"name": "rollback-skill", "type": "rewrite", "version": "2.0.0"},
        prompt="new prompt",
    )
    db.add(skill)
    db.flush()
    db.add_all(
        [
            SkillVersion(
                skill_id=skill.id,
                version="1.0.0",
                skill_type="rewrite",
                status="published",
                manifest_json={"name": "rollback-skill", "type": "rewrite", "version": "1.0.0"},
                prompt="old prompt",
            ),
            SkillVersion(
                skill_id=skill.id,
                version="2.0.0",
                skill_type="rewrite",
                status="published",
                manifest_json={"name": "rollback-skill", "type": "rewrite", "version": "2.0.0"},
                prompt="new prompt",
            ),
        ]
    )
    db.commit()

    restored = rollback_skill(skill.id, "1.0.0", None, db)
    assert restored.version == "1.0.0"
    assert restored.status == "published"
    assert restored.manifest["version"] == "1.0.0"
