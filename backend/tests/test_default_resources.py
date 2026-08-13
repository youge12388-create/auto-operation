from sqlalchemy import select

from content_ops.default_resource_seeding import ensure_default_resources
from content_ops.models import Skill, Source


def test_default_sources_and_skills_are_seeded_idempotently(db):
    added_sources, added_skills = ensure_default_resources(db)
    db.commit()

    assert added_sources == 9
    assert added_skills == 4
    assert len(db.scalars(select(Source)).all()) == 9
    assert len(db.scalars(select(Skill)).all()) == 4

    assert ensure_default_resources(db) == (0, 0)