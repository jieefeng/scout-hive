"""Schema 多文件加载机制。

按 config.yaml 的 active_schema_id 加载对应的 JSON schema 文件，验证后返回 SchemaDefinition。
"""
import json
from pathlib import Path

from app.config import load_config
from app.schema.mvp_defaults import SchemaDefinition

# schemas 目录的绝对路径（相对 backend/app/schema/loader.py）
SCHEMA_DIR = Path(__file__).parent.parent / "schemas"


def load_active_schema(schema_id: str | None = None) -> SchemaDefinition:
    """根据 schema_id 加载对应 JSON schema 文件。

    Args:
        schema_id: schema 文件名（不含 .json），如 "general" / "ai-assistant"。
                   传 None 时从 config.yaml 读 active_schema_id 字段。

    Returns:
        验证后的 SchemaDefinition 实例。

    Raises:
        FileNotFoundError: schema_id 对应的 JSON 文件不存在。
        ValidationError: JSON 内容不合法。
    """
    if schema_id is None:
        schema_id = load_config().active_schema_id

    # 文件名约定: ai-assistant → ai_assistant.json（连字符转下划线）
    file_name = schema_id.replace("-", "_") + ".json"
    schema_path = SCHEMA_DIR / file_name

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema file not found: {schema_path}. "
            f"Available: {sorted(p.name for p in SCHEMA_DIR.glob('*.json'))}"
        )

    raw = json.loads(schema_path.read_text(encoding="utf-8"))
    return SchemaDefinition.model_validate(raw)
