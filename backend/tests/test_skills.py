import io
import zipfile

import pytest

from content_ops.skills import SkillPackageError, validate_skill_package


def package(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_valid_skill_package_is_parsed():
    result = validate_skill_package(
        package(
            {
                "skill.yaml": "name: 自然表达\ntype: rewrite\nversion: 1.0.0\n",
                "prompt.md": "请保留事实并减少套话。",
                "examples/input.md": "原文",
            }
        )
    )
    assert result["manifest"]["type"] == "rewrite"


@pytest.mark.parametrize(
    "name",
    ["../escape.txt", "/absolute.txt", "scripts/run.py", "unknown.json"],
)
def test_skill_rejects_unsafe_or_unknown_files(name: str):
    with pytest.raises(SkillPackageError):
        validate_skill_package(
            package(
                {
                    "skill.yaml": "name: x\ntype: rewrite\nversion: 1.0.0\n",
                    "prompt.md": "规则",
                    name: "危险内容",
                }
            )
        )
