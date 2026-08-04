import asyncio
import io
import zipfile

from fastapi import UploadFile
from sqlalchemy import select

from content_ops.api import (
    add_model,
    disable_skill,
    import_skill,
    list_skill_versions,
    model_connection_test,
    publish_skill,
)
from content_ops.models import SkillVersion
from content_ops.schemas import ModelCreate


def skill_zip(version: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("skill.yaml", f"name: rewrite-demo\ntype: rewrite\nversion: {version}\n")
        archive.writestr("prompt.md", "保留事实并减少模板化表达")
    return buffer.getvalue()


def test_skill_import_keeps_versions_and_status_transitions(db):
    first = asyncio.run(
        import_skill(UploadFile(filename="skill.zip", file=io.BytesIO(skill_zip("1.0.0"))), None, db)
    )
    second = asyncio.run(
        import_skill(UploadFile(filename="skill.zip", file=io.BytesIO(skill_zip("1.1.0"))), None, db)
    )

    versions = (
        db.scalars(select(SkillVersion).where(SkillVersion.skill_id == first.id).order_by(SkillVersion.version))
        .all()
    )
    listed = list_skill_versions(first.id, None, db)
    published = publish_skill(first.id, None, db)
    disabled = disable_skill(first.id, None, db)

    assert second.version == "1.1.0"
    assert [item.version for item in versions] == ["1.0.0", "1.1.0"]
    assert [item.version for item in listed] == ["1.1.0", "1.0.0"]
    assert published.status == "published"
    assert disabled.status == "disabled"


def test_fake_model_connection_test_is_local_and_redacted(db):
    model = add_model(ModelCreate(provider="fake", name="fake-test"), None, db)
    result = model_connection_test(model.id, None, db)

    assert result.ok is True
    assert "api_key" not in result.message.lower()