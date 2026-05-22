# Schema Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现竞品分析 Schema 数据模型，替换 TaskDAG 中的 `dimensions: list[str]` 为完整的 `SchemaDefinition` 结构。

**Architecture:** 新建 `backend/app/models/schema.py`，定义 Schema 相关模型。修改 `dag.py` 中的 `TaskDAG`，将 `dimensions` 字段替换为 `schema: SchemaDefinition`。新增类型容错输入模型用于 LLM 输出解析。

**Tech Stack:** Python + Pydantic v2

---

## File Structure

```
backend/app/models/
├── __init__.py          # 修改：导出 Schema 相关模型
├── dag.py               # 修改：TaskDAG 中 dimensions → schema
├── schema.py            # 新建：Schema 数据模型
```

---

## Task 1: 创建 Schema 数据模型

**Files:**
- Create: `backend/app/models/schema.py`
- Test: `backend/tests/test_models/test_schema.py`

- [ ] **Step 1: 编写 Schema 模型的基础测试**

```python
# backend/tests/test_models/test_schema.py
import pytest
from app.models.schema import (
    CustomFieldHint,
    EvidenceRequirements,
    DimensionSchema,
    GroupSchema,
    SchemaDefinition,
    DimensionSchemaInput,
    SchemaPatch,
    SchemaChange,
)


def test_custom_field_hint():
    hint = CustomFieldHint(key="region", value="中国", render_hint="badge")
    assert hint.key == "region"
    assert hint.value == "中国"
    assert hint.render_hint == "badge"


def test_evidence_requirements_defaults():
    er = EvidenceRequirements()
    assert er.preferred == []
    assert er.min_sources == 1


def test_dimension_schema_full():
    dim = DimensionSchema(
        name="功能对比",
        description="核心功能差异与优势",
        keywords=["功能", "多语言", "API开放"],
        evidence_requirements=EvidenceRequirements(preferred=["官网产品页"], min_sources=2),
        data_sources=["web", "document"],
        output_format="matrix",
        confidence_baseline=0.8,
        custom_fields=[
            CustomFieldHint(key="region", value="中国", render_hint="badge")
        ],
    )
    assert dim.name == "功能对比"
    assert dim.output_format == "matrix"
    assert len(dim.custom_fields) == 1


def test_group_schema():
    group = GroupSchema(
        name="用户侧",
        description="从用户视角分析的维度",
        dimensions=[
            DimensionSchema(name="功能对比", keywords=["功能"]),
            DimensionSchema(name="用户体验", keywords=["体验", "UI"]),
        ],
    )
    assert len(group.dimensions) == 2
    assert group.name == "用户侧"


def test_schema_definition():
    schema = SchemaDefinition(
        schema_id="uuid-001",
        version="1.0",
        name="通用竞品分析 Schema",
        groups=[
            GroupSchema(
                name="用户侧",
                dimensions=[DimensionSchema(name="功能对比", keywords=["功能"])],
            ),
        ],
    )
    assert schema.schema_id == "uuid-001"
    assert len(schema.groups) == 1


def test_dimension_schema_input_from_llm():
    # 模拟 LLM 输出的原始数据（类型不严格）
    raw = {
        "name": "功能对比",
        "keywords": ["功能", 2024, None, "API"],  # 混入数字和 None
        "confidence_baseline": "0.8",  # 字符串形式的数字
        "custom_fields": [
            {"key": "region", "value": "中国"},
            "not_a_dict",  # 非 dict 项
        ],
    }
    input_model = DimensionSchemaInput.from_llm(raw)
    # keywords 应过滤数字和 None，只保留字符串
    assert all(isinstance(k, str) for k in input_model.keywords)
    assert 2024 not in input_model.keywords
    assert None not in input_model.keywords
    # custom_fields 应过滤非 dict 项
    assert all(isinstance(f, dict) for f in input_model.custom_fields)
    assert "not_a_dict" not in str(input_model.custom_fields)


def test_schema_patch():
    patch = SchemaPatch(
        patch_id="patch-001",
        applied_at="2026-05-23T10:00:00Z",
        triggered_by="review_001",
        changes=[
            SchemaChange(
                type="add_dimension",
                dimension_name="渠道策略",
                field_path="groups/商业侧/dimensions",
                before=None,
                after={"name": "渠道策略", "keywords": ["渠道"]},
            )
        ],
    )
    assert patch.patch_id == "patch-001"
    assert len(patch.changes) == 1
```

- [ ] **Step 2: 运行测试确认失败（模型不存在）**

Run: `cd backend && python -m pytest tests/test_models/test_schema.py -v`
Expected: FAIL — ModuleNotFoundError: No module named 'app.models.schema'

- [ ] **Step 3: 创建 schema.py 模型文件**

```python
# backend/app/models/schema.py
from typing import Any

from pydantic import BaseModel, Field


class CustomFieldHint(BaseModel):
    """用户自定义字段，必须附带渲染提示"""
    key: str
    value: Any
    render_hint: str = "auto"  # "auto" | "badge" | "list" | "paragraph" | "table"


class EvidenceRequirements(BaseModel):
    """证据要求"""
    preferred: list[str] = Field(default_factory=list)
    min_sources: int = 1


class DimensionSchema(BaseModel):
    """维度定义"""
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    fallback_query: str = ""
    evidence_requirements: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    data_sources: list[str] = Field(default_factory=list)
    output_format: str = "list"
    confidence_baseline: float = 0.8
    custom_fields: list[CustomFieldHint] = Field(default_factory=list)


class GroupSchema(BaseModel):
    """分组定义"""
    name: str
    description: str = ""
    dimensions: list[DimensionSchema] = Field(default_factory=list)


class SchemaDefinition(BaseModel):
    """完整 Schema 定义"""
    schema_id: str
    version: str = "1.0"
    name: str
    groups: list[GroupSchema] = Field(default_factory=list)


class DimensionSchemaInput(BaseModel):
    """应用层输入模型，用于解析 LLM 输出的原始数据"""
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    evidence_requirements: dict = Field(default_factory=dict)
    data_sources: list[str] = Field(default_factory=list)
    output_format: str = "list"
    confidence_baseline: float = 0.8
    custom_fields: list[dict] = Field(default_factory=list)

    @classmethod
    def from_llm(cls, raw: dict) -> "DimensionSchemaInput":
        """从 LLM 原始输出构建输入模型，自动过滤类型错误项"""
        data = raw.copy()
        if "keywords" in data:
            data["keywords"] = [str(v) for v in data["keywords"] if v is not None]
        if "custom_fields" in data:
            data["custom_fields"] = [v for v in data["custom_fields"] if isinstance(v, dict)]
        return cls(**data)


class SchemaChange(BaseModel):
    """Schema 单次改动"""
    type: str  # "add_dimension" | "remove_dimension" | "update_field"
    dimension_name: str
    field_path: str = ""
    before: Any = None
    after: Any = None


class SchemaPatch(BaseModel):
    """Schema 补丁"""
    patch_id: str
    applied_at: str = ""
    triggered_by: str = ""
    changes: list[SchemaChange] = Field(default_factory=list)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_models/test_schema.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/models/schema.py tests/test_models/test_schema.py
git commit -m "$(cat <<'EOF'
feat: add Schema data models

Add backend/app/models/schema.py with:
- CustomFieldHint, EvidenceRequirements, DimensionSchema
- GroupSchema, SchemaDefinition, DimensionSchemaInput
- SchemaChange, SchemaPatch
- from_llm() for LLM output type tolerance

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 修改 TaskDAG，dimensions 替换为 schema

**Files:**
- Modify: `backend/app/models/dag.py` — TaskDAG 中 `dimensions: list[str]` → `schema: SchemaDefinition`
- Test: `backend/tests/test_models/test_dag.py`

- [ ] **Step 1: 添加 Schema 嵌入后的 TaskDAG 测试**

```python
# backend/tests/test_models/test_dag.py 新增测试
from app.models.schema import SchemaDefinition, GroupSchema, DimensionSchema

def test_task_dag_with_schema():
    schema = SchemaDefinition(
        schema_id="uuid-001",
        name="通用 Schema",
        groups=[
            GroupSchema(
                name="用户侧",
                dimensions=[DimensionSchema(name="功能对比", keywords=["功能"])],
            ),
        ],
    )
    dag = DAGBlueprint(
        nodes=[
            DAGNode(id="collect_001", agent="Collector", action="web_search", params={}),
        ],
        edges=[],
    )
    task_dag = TaskDAG(
        task_id="task-001",
        competitors=["竞品A", "竞品B"],
        schema=schema,
        dag=dag,
    )
    assert task_dag.schema.schema_id == "uuid-001"
    assert len(task_dag.schema.groups) == 1
    assert task_dag.schema.groups[0].dimensions[0].name == "功能对比"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_models/test_dag.py::test_task_dag_with_schema -v`
Expected: FAIL — TaskDAG 不接受 schema 参数

- [ ] **Step 3: 修改 dag.py，dimensions 替换为 schema**

```python
# backend/app/models/dag.py

# ... 现有代码保持不变 ...

from .schema import SchemaDefinition  # 新增导入

# ... TaskDAG 类修改 ...
class TaskDAG(BaseModel):
    task_id: str
    competitors: list[str]
    schema: SchemaDefinition                           # 替换原来的 dimensions: list[str]
    dag: DAGBlueprint
    traceability: TraceabilityConfig = Field(default_factory=TraceabilityConfig)
```

**注意：** 需要保留向后兼容性吗？当前设计为"仅本次有效"，不需要兼容旧数据。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_models/test_dag.py::test_task_dag_with_schema -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/models/dag.py tests/test_models/test_dag.py
git commit -m "$(cat <<'EOF'
refactor: replace TaskDAG.dimensions with TaskDAG.schema

TaskDAG now embeds full SchemaDefinition instead of list[str].
TaskDAG.schema provides complete dimension definitions with keywords,
evidence_requirements, output_format, and custom_fields.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 更新 models __init__.py 导出

**Files:**
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 添加 Schema 模型导出**

```python
# backend/app/models/__init__.py
from .dag import DAGBlueprint, DAGEdge, FeedbackEdge, DAGNode, TaskDAG, TraceabilityConfig
from .schema import (
    CustomFieldHint,
    EvidenceRequirements,
    DimensionSchema,
    GroupSchema,
    SchemaDefinition,
    DimensionSchemaInput,
    SchemaChange,
    SchemaPatch,
)
```

- [ ] **Step 2: 提交**

```bash
cd backend && git add app/models/__init__.py
git commit -m "$(cat <<'EOF'
refactor: export Schema models from app.models

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Schema 预设模板（可选，后续扩展）

此项为可选任务，当前 Scope 为 Schema 模型定义本身。预设模板可在后续实现。

---

## Self-Review 检查

1. **Spec coverage：** Schema 模型完整覆盖设计文档中的 `DimensionSchema`、`GroupSchema`、`SchemaDefinition`、`CustomFieldHint`、`EvidenceRequirements`、`SchemaPatch`
2. **Placeholder scan：** 无 TBD/TODO，代码块完整
3. **Type consistency：** `DimensionSchema.keywords: list[str]`，`DimensionSchemaInput.from_llm()` 返回类型正确

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-05-23-schema-implementation.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** - dispatch fresh subagent per task, review between tasks

**2. Inline Execution** - execute tasks in this session using executing-plans

**Which approach?**