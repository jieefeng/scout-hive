# PR 2.1: Schema 多文件加载机制 + general.json 迁移

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单文件 `mvp_defaults.py` 的 `DEFAULT_SCHEMA` 字典迁移到 `schemas/general.json`；新增 `loader.py` 按 `config.yaml` 的 `active_schema_id` 加载对应 JSON；为 `DimensionSchema` 加 `fields` / `quality_rules` 字段（PR 2.2 用）；保持向后兼容。

**Architecture:** 
- `mvp_defaults.py` 仍保留 `SchemaDefinition` / `GroupSchema` / `DimensionSchema` Pydantic 模型（不挪位置，避免大改 import 链）
- 新增 `backend/app/schema/loader.py::load_active_schema()` 读 `config.active_schema_id` → 加载 `schemas/<id>.json` → 返回 `SchemaDefinition`
- `mvp_defaults.py::load_default_schema()` 改为 delegate 到 loader（active_schema_id 默认 "general"），所有现有调用方零改动
- `mvp_defaults.py` 中 `DEFAULT_SCHEMA` 字典常量保留（向后兼容 + 测试用），但标注 deprecated

**Tech Stack:** Python 3.11 + pytest + Pydantic v2 + PyYAML

**Spec 参考:** [../specs/2026-06-07-ai-assistant-vertical-design.md](../specs/2026-06-07-ai-assistant-vertical-design.md) 决策 1 + 数据模型段

---

## File Structure

| 路径 | 操作 | 职责 |
|---|---|---|
| `backend/app/schema/loader.py` | 新建 | `load_active_schema()` / `SCHEMA_DIR` 常量 |
| `backend/app/schemas/__init__.py` | 新建 | schema 包初始化（空文件） |
| `backend/app/schemas/general.json` | 新建 | 从 `mvp_defaults.py::DEFAULT_SCHEMA` 字典迁移过来 |
| `backend/app/schemas/collab_office.json` | 新建 | 占位文件（最小骨架，1 group + 1 dim） |
| `backend/app/schema/mvp_defaults.py` | 修改 | 加 `fields` / `quality_rules` 字段；`load_default_schema` delegate 到 loader；`DEFAULT_SCHEMA` 标 deprecated |
| `backend/app/config.py` | 修改 | `AppConfig` 加 `active_schema_id: str = "general"` 字段 |
| `backend/app/config.yaml` | 修改 | 加 `active_schema_id: "general"`（与 default 对齐，注释说明） |
| `backend/tests/test_schema/test_multi_schema.py` | 新建 | 验证多文件加载机制 |
| `backend/tests/test_schema/test_dimension_fields.py` | 新建 | 验证 DimensionSchema.fields/quality_rules 字段 |
| `backend/tests/test_schema/test_mvp_defaults.py` | 修改 | 现有测试加 `fields` / `quality_rules` 默认值断言 |

不删任何文件。

---

## Task 1: DimensionSchema 加 fields / quality_rules 字段（red）

**Files:**
- Modify: `backend/app/schema/mvp_defaults.py:6-15`

- [ ] **Step 1: 加字段**

打开 `backend/app/schema/mvp_defaults.py`，找到 `DimensionSchema` 类（line 6-15）。在 `tracking_sources` 字段**下方**加：

```python
    fields: list[dict] = Field(
        default_factory=list,
        description="维度字段定义（含 type + 质检规则），如 [{name, type, required, min}]"
    )
    quality_rules: list[str] = Field(
        default_factory=list,
        description="LLM 可读的质检规则文本，如 ['context_window 必须是数字 ≥ 8000']"
    )
```

`DimensionSchema` 类现在形如：
```python
class DimensionSchema(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = Field(min_length=1)
    output_type: OutputType = "paragraph"
    evidence_threshold: int = Field(default=1, ge=1)
    tracking_sources: list[str] = Field(default_factory=lambda: ["web"], description="...")
    fields: list[dict] = Field(default_factory=list, description="...")
    quality_rules: list[str] = Field(default_factory=list, description="...")
```

- [ ] **Step 2: 写新测试**

新建 `backend/tests/test_schema/test_dimension_fields.py`：

```python
from app.schema.mvp_defaults import DimensionSchema


def test_dimension_fields_default_empty_list():
    """默认 fields 为空 list（向后兼容旧 schema）。"""
    dim = DimensionSchema(
        name="测试", description="测试", keywords=["测试"]
    )
    assert dim.fields == []
    assert dim.quality_rules == []


def test_dimension_fields_populated():
    """fields 和 quality_rules 可填充。"""
    dim = DimensionSchema(
        name="AI 模型能力",
        description="底层模型、上下文、响应速度",
        keywords=["模型", "上下文", "token"],
        output_type="table",
        fields=[
            {"name": "underlying_model", "type": "string", "required": True},
            {"name": "context_window", "type": "number", "min": 8000},
        ],
        quality_rules=[
            "context_window 必须是数字 ≥ 8000",
            "underlying_model 必须给出具体模型名",
        ],
    )
    assert len(dim.fields) == 2
    assert dim.fields[0]["name"] == "underlying_model"
    assert "≥ 8000" in dim.quality_rules[0]
```

- [ ] **Step 3: 运行测试，验证它 PASS（绿）**

```bash
cd backend && python -m pytest tests/test_schema/test_dimension_fields.py -v
```

预期: **PASS**（本任务的红绿同时进行——Step 1 实现的字段直接通过 Step 2 的测试）。

- [ ] **Step 4: 跑现有 DimensionSchema 测试**

```bash
cd backend && python -m pytest tests/test_schema/test_mvp_defaults.py -v
```

预期: 全部 PASS（新字段带 default，向后兼容）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schema/mvp_defaults.py backend/tests/test_schema/test_dimension_fields.py
git commit -m "feat(schema): add fields/quality_rules to DimensionSchema for vertical schema"
```

---

## Task 2: 把 DEFAULT_SCHEMA 字典迁到 schemas/general.json

**Files:**
- Create: `backend/app/schemas/general.json`
- Create: `backend/app/schemas/__init__.py`
- Modify: `backend/app/schema/mvp_defaults.py:28-70` (留 dict 但加 deprecation 注释)

- [ ] **Step 1: 建 schemas 目录和 __init__.py**

```bash
mkdir -p backend/app/schemas
touch backend/app/schemas/__init__.py
```

`__init__.py` 内容留空（仅作为 package 标记）。

- [ ] **Step 2: 建 general.json，内容等于当前 DEFAULT_SCHEMA**

新建 `backend/app/schemas/general.json`：

```json
{
  "schema_id": "general",
  "name": "通用竞品分析模板",
  "version": "1.0",
  "groups": [
    {
      "name": "产品功能",
      "description": "核心产品功能维度",
      "dimensions": [
        {
          "name": "功能对比",
          "description": "对比各竞品提供的核心功能差异，列出各竞品支持的功能项和不支持的功能项。",
          "keywords": ["功能", "特性", "支持"],
          "output_type": "table",
          "evidence_threshold": 2,
          "tracking_sources": ["web"],
          "fields": [],
          "quality_rules": []
        },
        {
          "name": "用户体验",
          "description": "分析各竞品在界面设计、操作体验、用户评价方面的特点。",
          "keywords": ["用户体验", "UI", "界面"],
          "output_type": "paragraph",
          "evidence_threshold": 1,
          "tracking_sources": ["web"],
          "fields": [],
          "quality_rules": []
        }
      ]
    },
    {
      "name": "商业策略",
      "description": "定价与商业策略维度",
      "dimensions": [
        {
          "name": "定价策略",
          "description": "对比各竞品的定价模式（免费/订阅/按需）、价格区间、有无隐藏费用。提取每个竞品的具体价格数据。",
          "keywords": ["定价", "价格", "套餐", "收费"],
          "output_type": "table",
          "evidence_threshold": 1,
          "tracking_sources": ["web"],
          "fields": [],
          "quality_rules": []
        }
      ]
    }
  ]
}
```

**注意**：`schema_id` 改为 `"general"`（原来是 `"default-mvp"`）。这是 spec 决策 1 明确——id 命名对齐文件名。

- [ ] **Step 3: 在 mvp_defaults.py 的 DEFAULT_SCHEMA 顶部加 deprecation 注释**

打开 `backend/app/schema/mvp_defaults.py`，找到第 28 行 `DEFAULT_SCHEMA: dict = {`。在它**上方**加 3 行注释：

```python
# DEPRECATED: 此常量已迁移到 backend/app/schemas/general.json。
# 保留仅为向后兼容与测试用途。新代码请用 loader.load_active_schema()。
DEFAULT_SCHEMA: dict = {
```

- [ ] **Step 4: 跑现有测试，确认无破坏**

```bash
cd backend && python -m pytest tests/test_schema/ -v
```

预期: 全部 PASS（包括 `test_load_default_schema` 等，`DEFAULT_SCHEMA` 仍被引用为 raw dict）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/__init__.py backend/app/schemas/general.json backend/app/schema/mvp_defaults.py
git commit -m "refactor(schema): migrate DEFAULT_SCHEMA to schemas/general.json (backward compat)"
```

---

## Task 3: 实现 loader.py + AppConfig 加 active_schema_id 字段

**Files:**
- Create: `backend/app/schema/loader.py`
- Modify: `backend/app/config.py:71-77` (AppConfig 加字段)
- Modify: `backend/app/config.yaml` (加 active_schema_id)

- [ ] **Step 1: 加 AppConfig 字段**

打开 `backend/app/config.py`，找到 `AppConfig` 类（line 71-77）。在 `llm_pricing` 字段**下方**加：

```python
    active_schema_id: str = Field(
        default="general",
        description="当前激活的 schema ID（对应 schemas/<id>.json 文件名）",
    )
```

`Field` 需要从 `pydantic` 导入：`from pydantic import BaseModel, Field`（line 3，已在）。**注意**：Field 已经在 line 2 导入（`from pydantic import BaseModel, Field`）—— 实际看代码 line 2 是 `from pydantic import BaseModel, Field` 没问题。

- [ ] **Step 2: 在 config.yaml 加 active_schema_id**

打开 `backend/app/config.yaml`，在文件**最顶部**加（作为 schema 切换的总开关）：

```yaml
# 当前激活的 schema，对应 backend/app/schemas/<active_schema_id>.json
# 可选: general | ai-assistant | collab-office
# 切换后需重启服务
active_schema_id: "general"
```

- [ ] **Step 3: 写 loader.py**

新建 `backend/app/schema/loader.py`：

```python
"""Schema 多文件加载机制。

按 config.yaml 的 active_schema_id 加载对应的 JSON schema 文件，验证后返回 SchemaDefinition。
向后兼容：load_default_schema() 现在 delegate 到本模块的 load_active_schema()。
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
```

- [ ] **Step 4: 写多文件加载测试**

新建 `backend/tests/test_schema/test_multi_schema.py`：

```python
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
```

- [ ] **Step 5: 运行测试，验证 PASS（绿）**

```bash
cd backend && python -m pytest tests/test_schema/test_multi_schema.py -v
```

预期: 全部 PASS（loader + JSON 一次写好）。

- [ ] **Step 6: 跑所有 schema 测试**

```bash
cd backend && python -m pytest tests/test_schema/ -v
```

预期: 全部 PASS（包括现有 `test_mvp_defaults.py` 和新加的 `test_dimension_fields.py` / `test_multi_schema.py`）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/schema/loader.py backend/app/config.py backend/app/config.yaml backend/tests/test_schema/test_multi_schema.py
git commit -m "feat(schema): multi-file loader with config-driven active_schema_id"
```

---

## Task 4: 改 mvp_defaults.load_default_schema delegate 到 loader

**Files:**
- Modify: `backend/app/schema/mvp_defaults.py:72-78`

- [ ] **Step 1: 改 load_default_schema 实现**

打开 `backend/app/schema/mvp_defaults.py`，找到 line 72-78 的 `load_default_schema` 函数。**完整替换**为：

```python
def load_default_schema() -> SchemaDefinition:
    """向后兼容入口：delegate 到 loader.load_active_schema()。

    默认从 config.yaml 读 active_schema_id（默认 'general'）。
    现有调用方（如 _load_dimensions / parse_task / execute_mvp）零改动。
    """
    from app.schema.loader import load_active_schema
    return load_active_schema()
```

- [ ] **Step 2: 跑所有 schema 测试 + 现有调用方测试**

```bash
cd backend && python -m pytest tests/test_schema/ tests/test_api/test_parse_endpoint.py tests/test_engine/ -v
```

预期: 全部 PASS。特别注意：
- `test_load_default_schema` 仍通过（默认 general）
- `test_dimension_schema_fields` 仍通过
- `_load_dimensions` 调用 `load_default_schema` 仍能用

- [ ] **Step 3: 跑全量后端测试**

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS（向后兼容的承诺）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/schema/mvp_defaults.py
git commit -m "refactor(schema): load_default_schema delegates to loader.load_active_schema"
```

---

## Task 5: 加 collab_office.json 占位

**Files:**
- Create: `backend/app/schemas/collab_office.json`

- [ ] **Step 1: 建占位 JSON**

新建 `backend/app/schemas/collab_office.json`：

```json
{
  "schema_id": "collab-office",
  "name": "协同办公赛道模板（占位，PR 2.4+ 完善）",
  "version": "0.1",
  "groups": [
    {
      "name": "占位",
      "description": "未来 spec 完善此 schema（飞书/钉钉/企微 协同办公维度）",
      "dimensions": [
        {
          "name": "占位维度",
          "description": "待 PR 2.4+ 替换为真实维度",
          "keywords": ["占位"],
          "output_type": "paragraph",
          "evidence_threshold": 1,
          "tracking_sources": ["web"],
          "fields": [],
          "quality_rules": []
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: 加测试**

在 `backend/tests/test_schema/test_multi_schema.py` 末尾追加：

```python
def test_collab_office_schema_placeholder():
    """collab_office.json 加载成功（占位状态，1 dim 1 group）。"""
    schema = load_active_schema("collab-office")
    assert schema.schema_id == "collab-office"
    assert len(schema.groups) == 1
    assert "占位" in schema.name or "placeholder" in schema.name.lower() or "占位" in schema.groups[0].name
```

- [ ] **Step 3: 运行新测试**

```bash
cd backend && python -m pytest tests/test_schema/test_multi_schema.py::test_collab_office_schema_placeholder -v
```

预期: PASS。

- [ ] **Step 4: 跑全量 schema 测试**

```bash
cd backend && python -m pytest tests/test_schema/ -v
```

预期: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/collab_office.json backend/tests/test_schema/test_multi_schema.py
git commit -m "feat(schema): add collab_office.json placeholder for future vertical"
```

---

## Task 6: 跑全量后端测试 + 验证向后兼容

**Files:** 无（验证步）

- [ ] **Step 1: 跑全量后端测试**

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS。无回归。

- [ ] **Step 2: 手动验证 config 切换（可选，跳过如不需要）**

```python
# 临时改 config.yaml 试试切换（记得改回去）
# active_schema_id: "collab-office"
# python -c "from app.schema.loader import load_active_schema; s = load_active_schema(); print(s.name)"
# 应输出 "协同办公赛道模板（占位，PR 2.4+ 完善）"
# 改回 "general"
```

- [ ] **Step 3: 提交（如有 config 切换验证临时文件）**

无修改 → 跳过。

---

## Self-Review

### Spec coverage

| Spec 段 | 覆盖任务 |
|---|---|
| 决策 1（多文件 + config 切换） | Task 2 (general.json) + Task 3 (loader) + Task 5 (collab_office.json) |
| 数据模型段（DimensionSchema 加 fields/quality_rules） | Task 1 |
| 改动文件清单（PR 2.1 阶段） | Task 1-5 覆盖 |

### Placeholder scan

- [x] 无 TBD / TODO
- [x] 无 "implement later" — Task 5 注释"PR 2.4+ 完善"是引用未来 spec 计划，不是 placeholder
- [x] 每个 code block 完整可用
- [x] 步骤命令带预期输出

### Type consistency

- `load_active_schema(schema_id: str | None = None) -> SchemaDefinition` 签名只在一处定义（loader.py）
- `DimensionSchema.fields: list[dict]` 字段类型一致
- `active_schema_id: str` 在 config.py 和 config.yaml 字符串值一致（"general"）

### 命名一致性

- 文件名 `general.json` / `collab_office.json` 与 `schema_id` 值 `general` / `collab-office` 一致（loader 用 `.replace("-", "_")` 转换）
- `load_active_schema` 函数名在测试和实现中一致
