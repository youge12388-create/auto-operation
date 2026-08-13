from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MaterialCategory


@dataclass(frozen=True)
class MaterialCategorySpec:
    id: str
    name: str
    description: str


BUILTIN_MATERIAL_CATEGORY_SPECS = (
    MaterialCategorySpec(
        id="c1000000-0000-4000-8000-000000000001",
        name="AI 前沿",
        description="模型、研究、智能体与 AI 行业的重要进展",
    ),
    MaterialCategorySpec(
        id="c1000000-0000-4000-8000-000000000002",
        name="产品与商业",
        description="产品发布、商业模式、公司动态与市场机会",
    ),
    MaterialCategorySpec(
        id="c1000000-0000-4000-8000-000000000003",
        name="技术与工具",
        description="开发工具、开源项目、工程实践与使用教程",
    ),
    MaterialCategorySpec(
        id="c1000000-0000-4000-8000-000000000004",
        name="行业观察",
        description="产业趋势、人物观点、政策与社会影响",
    ),
    MaterialCategorySpec(
        id="c1000000-0000-4000-8000-000000000005",
        name="其他",
        description="暂时不适合前述分类，但仍有保留价值的内容",
    ),
)


def ensure_builtin_material_categories(db: Session) -> list[MaterialCategory]:
    existing = {item.id: item for item in db.scalars(select(MaterialCategory)).all()}
    created: list[MaterialCategory] = []
    for spec in BUILTIN_MATERIAL_CATEGORY_SPECS:
        if spec.id in existing:
            continue
        category = MaterialCategory(
            id=spec.id,
            name=spec.name,
            description=spec.description,
            enabled=True,
            is_builtin=True,
        )
        db.add(category)
        created.append(category)
    return created