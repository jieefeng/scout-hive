import json
from pathlib import Path

import pytest

from app.schema.loader import load_active_schema, SCHEMA_DIR
from app.schema.mvp_defaults import SchemaDefinition


def test_schema_dir_exists():
    """schemas/ 目录必须存在并包含至少 1 个 JSON。"""
    assert SCHEMA_DIR.is_dir()
    json_files = list(SCHEMA_DIR.glob("*.json"))
    assert len(json_files) >= 1, "schemas/ 目录至少应有 1 个 JSON schema"


def test_load_general_schema_explicit():
    """显式传 schema_id='general' 加载通用 schema。"""
    schema = load_active_schema("general")
    assert schema.schema_id == "general"
    assert len(schema.groups) >= 1
    # 通用 schema 应有 3 个维度: 功能对比、用户体验、定价策略
    all_dims = [d.name for g in schema.groups for d in g.dimensions]
    assert "功能对比" in all_dims
    assert "用户体验" in all_dims
    assert "定价策略" in all_dims


def test_load_general_schema_from_config():
    """不传 schema_id → 从 config 读 active_schema_id（默认 'general'）。"""
    schema = load_active_schema()
    assert schema.schema_id == "general"


def test_load_nonexistent_schema_raises():
    """不存在的 schema_id 抛 FileNotFoundError，错误信息含可用列表。"""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_active_schema("nonexistent")
    assert "nonexistent" in str(exc_info.value)
    assert ".json" in str(exc_info.value)


def test_general_json_is_valid():
    """general.json 本身必须是合法 JSON。"""
    general_path = SCHEMA_DIR / "general.json"
    assert general_path.exists()
    raw = json.loads(general_path.read_text(encoding="utf-8"))
    assert "groups" in raw
    assert "schema_id" in raw


def test_collab_office_schema_placeholder():
    """collab_office.json 加载成功（占位状态，1 dim 1 group）。"""
    schema = load_active_schema("collab-office")
    assert schema.schema_id == "collab-office"
    assert len(schema.groups) == 1
    assert "占位" in schema.name or "placeholder" in schema.name.lower() or "占位" in schema.groups[0].name
