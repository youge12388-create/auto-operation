from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .default_resources import DEFAULT_SKILLS, DEFAULT_SOURCES
from .models import Skill, SkillVersion, Source, SourceGroup


def ensure_default_resources(db: Session) -> tuple[int, int]:
    """Insert curated sources and Skills that are missing from a deployment.

    Existing operator records are left untouched. This makes bootstrap safe for
    upgrades while ensuring a fresh server receives the same sources and Skills
    that were verified in the local workspace.
    """

    added_sources = 0
    added_skills = 0
    groups: dict[str, SourceGroup | None] = {}

    for definition in DEFAULT_SOURCES:
        source = db.scalar(select(Source).where(Source.name == definition["name"]))
        if source is not None:
            continue
        group_name = str(definition.get("group_name") or "default")
        group = groups.get(group_name)
        if group_name != "default" and group is None:
            group = db.scalar(select(SourceGroup).where(SourceGroup.name == group_name))
            if group is None:
                group = SourceGroup(name=group_name, description="Curated information sources")
                db.add(group)
                db.flush()
            groups[group_name] = group
        db.add(
            Source(
                name=definition["name"],
                source_type=definition["source_type"],
                url=definition["url"],
                group_name=group_name,
                group_id=group.id if group is not None else None,
                enabled=bool(definition.get("enabled", True)),
                requires_review=bool(definition.get("requires_review", False)),
                config_json=dict(definition.get("config") or {}),
            )
        )
        added_sources += 1

    for definition in DEFAULT_SKILLS:
        skill = db.scalar(select(Skill).where(Skill.name == definition["name"]))
        if skill is None:
            skill = Skill(
                name=definition["name"],
                skill_type=definition["skill_type"],
                version=definition["version"],
                status=definition.get("status", "published"),
                manifest_json=dict(definition.get("manifest") or {}),
                prompt=definition["prompt"],
            )
            db.add(skill)
            db.flush()
            added_skills += 1
        version = db.scalar(
            select(SkillVersion).where(SkillVersion.skill_id == skill.id, SkillVersion.version == definition["version"])
        )
        if version is None:
            db.add(
                SkillVersion(
                    skill_id=skill.id,
                    version=definition["version"],
                    skill_type=definition["skill_type"],
                    status=definition.get("status", "published"),
                    manifest_json=dict(definition.get("manifest") or {}),
                    prompt=definition["prompt"],
                )
            )

    return added_sources, added_skills
