"""硬收窄后的 schema 目录契约测试。

锁定:loader.py 已删,general.json + collab_office.json 已删,schemas/ 只剩
ai_assistant.json。
"""
import importlib.util
from pathlib import Path


SCHEMAS_DIR = Path(__file__).parent.parent.parent / "app" / "schemas"


def test_loader_module_removed():
    """loader.py 必须已下线。"""
    assert importlib.util.find_spec("app.schema.loader") is None, (
        "app.schema.loader 应已删除;唯一入口是 get_active_schema()"
    )


def test_general_json_removed():
    """通用 schema 文件必须不存在。"""
    assert not (SCHEMAS_DIR / "general.json").exists(), (
        "schemas/general.json 应已删除(硬收窄到 ai-assistant)"
    )


def test_collab_office_json_removed():
    """协同办公占位文件必须不存在。"""
    assert not (SCHEMAS_DIR / "collab_office.json").exists(), (
        "schemas/collab_office.json 应已删除(占位文件无业务价值)"
    )


def test_only_ai_assistant_json_remains():
    """schemas/ 目录只剩 ai_assistant.json。"""
    json_files = sorted(p.name for p in SCHEMAS_DIR.glob("*.json"))
    assert json_files == ["ai_assistant.json"], (
        f"schemas/ 应只剩 ai_assistant.json,实际: {json_files}"
    )
