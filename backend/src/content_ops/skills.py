from __future__ import annotations

import io
import stat
import zipfile
from typing import Any

import yaml

ALLOWED_ROOT_FILES = {"skill.yaml", "prompt.md", "README.md"}
ALLOWED_DIRS = ("examples/", "tests/")
SKILL_TYPES = {"research", "outline", "writing", "style", "rewrite", "review", "platform"}


class SkillPackageError(ValueError):
    pass


def _safe_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    return bool(normalized) and not normalized.startswith("/") and ".." not in normalized.split("/")


def validate_skill_package(data: bytes) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SkillPackageError("不是有效的 ZIP Skill 包") from exc

    names = archive.namelist()
    if "skill.yaml" not in names or "prompt.md" not in names:
        raise SkillPackageError("Skill 包必须包含 skill.yaml 和 prompt.md")

    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if not _safe_name(name):
            raise SkillPackageError("Skill 包包含非法路径")
        if info.is_dir():
            continue
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise SkillPackageError("Skill 包不允许符号链接")
        if name not in ALLOWED_ROOT_FILES and not name.startswith(ALLOWED_DIRS):
            raise SkillPackageError(f"Skill 包包含未允许的文件：{name}")

    try:
        manifest = yaml.safe_load(archive.read("skill.yaml")) or {}
    except yaml.YAMLError as exc:
        raise SkillPackageError("skill.yaml 不是有效 YAML") from exc
    if not isinstance(manifest, dict):
        raise SkillPackageError("skill.yaml 必须是对象")
    for key in ("name", "type", "version"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise SkillPackageError(f"skill.yaml 缺少有效字段：{key}")
    if manifest["type"] not in SKILL_TYPES:
        raise SkillPackageError(f"不支持的 Skill 类型：{manifest['type']}")

    prompt = archive.read("prompt.md").decode("utf-8")
    if not prompt.strip():
        raise SkillPackageError("prompt.md 不能为空")
    return {"manifest": manifest, "prompt": prompt}
