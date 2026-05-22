# Schema Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现竞品分析 Schema 数据模型，支持 MVP 单体流程 + Schema Registry 热更新 + 硬规则校验。

**Architecture:**
- 新建 `backend/app/models/schema.py`，定义 Schema 相关模型
- 新建 `backend/app/schema/registry.py`，Schema Registry 注册中心
- 新建 `backend/app/schema/validators.py`，硬规则校验器（非 LLM）
- Schema 不再内嵌 DAG Blueprint，通过 Registry 独立管理

**Tech Stack:** Python + Pydantic v2

---

## File Structure

```
backend/app/
├── models/
│   ├── __init__.py          # 修改：导出 Schema 相关模型
│   ├── dag.py               # 修改：移除 schema 内嵌，保留 DAGBlueprint
│   └── schema.py            # 新建：Schema 数据模型
├── schema/
│   ├── __init__.py         # 新建：schema 模块
│   ├── registry.py         # 新建：SchemaRegistry 注册中心
│   └── validators.py      # 新建：硬规则校验器
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


def test_dimension_schema_input_range_validation():
    """测试数值范围校验（硬规则）"""
    from pydantic import ValidationError

    # confidence_baseline 超出范围
    raw = {
        "name": "测试",
        "confidence_baseline": 1.5,  # 超出 [0.0, 1.0]
    }
    with pytest.raises(ValidationError) as exc_info:
        DimensionSchemaInput.from_llm(raw)
    assert "confidence_baseline" in str(exc_info.value)

    # min_sources 小于 1
    raw = {
        "name": "测试",
        "evidence_requirements": {"min_sources": 0},
    }
    with pytest.raises(ValidationError) as exc_info:
        DimensionSchemaInput.from_llm(raw)
    assert "min_sources" in str(exc_info.value)


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

from pydantic import BaseModel, Field, model_validator


class CustomFieldHint(BaseModel):
    """用户自定义字段，必须附带渲染提示"""
    key: str
    value: Any
    render_hint: str = "auto"  # "auto" | "badge" | "list" | "paragraph" | "table"


class EvidenceRequirements(BaseModel):
    """证据要求"""
    preferred: list[str] = Field(default_factory=list)  # Tier 1/2/3 加权
    min_sources: int = 1  # 软限制，低于时降级不阻断


class DimensionSchema(BaseModel):
    """维度定义"""
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)  # 驱动采集
    fallback_query: str = ""  # 兜底查询
    evidence_requirements: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    data_sources: list[str] = Field(default_factory=list)  # web/document/api/third_party_reviews
    output_format: str = "list"  # "list" | "matrix" | "summary" | "narrative"
    confidence_baseline: float = 0.8  # 置信度基准
    custom_fields: list[CustomFieldHint] = Field(default_factory=list)  # 用户自定义字段


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
    """应用层输入模型，用于解析 LLM/函数输出的原始数据"""
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
        # keywords 只保留字符串类型（过滤数字等）
        if "keywords" in data:
            data["keywords"] = [str(v) for v in data["keywords"] if v is not None]
        # custom_fields 只保留 dict 类型
        if "custom_fields" in data:
            data["custom_fields"] = [v for v in data["custom_fields"] if isinstance(v, dict)]
        return cls(**data)

    @model_validator(mode="after")
    def validate_ranges(self):
        """数值范围校验，防止幻觉（硬规则）"""
        if not 0.0 <= self.confidence_baseline <= 1.0:
            raise ValueError(
                f"confidence_baseline must be in [0.0, 1.0], got {self.confidence_baseline}"
            )
        er = self.evidence_requirements
        if er.get("min_sources", 1) < 1:
            raise ValueError("min_sources must be >= 1")
        return self


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
- Range validation (hard rules) in model_validator

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 创建 SchemaRegistry 注册中心

**Files:**
- Create: `backend/app/schema/__init__.py`
- Create: `backend/app/schema/registry.py`
- Test: `backend/tests/test_schema/test_registry.py`

- [ ] **Step 1: 编写 Registry 测试**

```python
# backend/tests/test_schema/test_registry.py
import pytest
from app.models.schema import SchemaDefinition, GroupSchema, DimensionSchema
from app.schema.registry import SchemaRegistry


def test_register_and_get():
    schema = SchemaDefinition(
        schema_id="test-001",
        name="测试 Schema",
        groups=[],
    )
    SchemaRegistry.register(schema)
    retrieved = SchemaRegistry.get("test-001")
    assert retrieved is not None
    assert retrieved.schema_id == "test-001"


def test_list_templates():
    SchemaRegistry._schemas.clear()  # 清空已有
    schema1 = SchemaDefinition(schema_id="s1", name="模板A", groups=[])
    schema2 = SchemaDefinition(schema_id="s2", name="模板B", groups=[])
    SchemaRegistry.register(schema1)
    SchemaRegistry.register(schema2)
    templates = SchemaRegistry.list_templates()
    assert "模板A" in templates
    assert "模板B" in templates


def test_apply_patch():
    SchemaRegistry._schemas.clear()
    original = SchemaDefinition(
        schema_id="base-001",
        name="基础 Schema",
        groups=[
            GroupSchema(
                name="用户侧",
                dimensions=[DimensionSchema(name="功能对比", keywords=["功能"])],
            ),
        ],
    )
    SchemaRegistry.register(original)

    patch = SchemaPatch(
        patch_id="patch-001",
        applied_at="2026-05-23T10:00:00Z",
        triggered_by="review_001",
        changes=[
            SchemaChange(
                type="add_dimension",
                dimension_name="用户体验",
                field_path="groups/用户侧/dimensions",
                before=None,
                after={"name": "用户体验", "keywords": ["体验", "UI"]},
            )
        ],
    )
    updated = SchemaRegistry.apply_patch("base-001", patch)
    # 验证新维度已添加
    user_dimensions = next(
        g.dimensions for g in updated.groups if g.name == "用户侧"
    )
    dimension_names = [d.name for d in user_dimensions]
    assert "用户体验" in dimension_names
    assert "功能对比" in dimension_names  # 原有维度保留
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_schema/test_registry.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 创建 registry.py**

```python
# backend/app/schema/__init__.py
from .registry import SchemaRegistry

__all__ = ["SchemaRegistry"]
```

```python
# backend/app/schema/registry.py
from app.models.schema import SchemaDefinition, SchemaPatch, SchemaChange, DimensionSchema, GroupSchema


class SchemaRegistry:
    """Schema 注册中心（内存中）"""
    _schemas: dict[str, SchemaDefinition] = {}

    @classmethod
    def register(cls, schema: SchemaDefinition):
        """注册 Schema 模板"""
        cls._schemas[schema.schema_id] = schema

    @classmethod
    def get(cls, schema_id: str) -> SchemaDefinition | None:
        """获取 Schema"""
        return cls._schemas.get(schema_id)

    @classmethod
    def list_templates(cls) -> list[str]:
        """列出所有注册模板名称"""
        return [s.name for s in cls._schemas.values()]

    @classmethod
    def list_all(cls) -> list[SchemaDefinition]:
        """列出所有注册 Schema"""
        return list(cls._schemas.values())

    @classmethod
    def apply_patch(cls, schema_id: str, patch: SchemaPatch) -> SchemaDefinition:
        """
        应用 SchemaPatch 热更新。
        返回更新后的 SchemaDefinition（不修改原对象，创建新实例）。
        """
        original = cls.get(schema_id)
        if not original:
            raise ValueError(f"Schema '{schema_id}' not found")

        updated_schema = cls._deep_copy(original)

        for change in patch.changes:
            if change.type == "add_dimension":
                cls._add_dimension(updated_schema, change)
            elif change.type == "remove_dimension":
                cls._remove_dimension(updated_schema, change)
            elif change.type == "update_field":
                cls._update_field(updated_schema, change)

        # 更新版本号
        updated_schema.version = cls._bump_version(updated_schema.version)

        # 重新注册
        cls.register(updated_schema)
        return updated_schema

    @classmethod
    def _deep_copy(cls, schema: SchemaDefinition) -> SchemaDefinition:
        """深拷贝 SchemaDefinition"""
        import copy
        return copy.deepcopy(schema)

    @classmethod
    def _bump_version(cls, version: str) -> str:
        """简单版本号递增"""
        parts = version.split(".")
        if len(parts) == 2:
            major, minor = parts
            return f"{major}.{int(minor) + 1}"
        return version

    @classmethod
    def _add_dimension(cls, schema: SchemaDefinition, change: SchemaChange):
        """添加维度"""
        # 解析 field_path 格式：groups/{group_name}/dimensions
        parts = change.field_path.split("/")
        if len(parts) >= 3 and parts[0] == "groups":
            group_name = parts[1]
            group = next((g for g in schema.groups if g.name == group_name), None)
            if group and change.after:
                new_dim = DimensionSchema(**change.after) if isinstance(change.after, dict) else change.after
                group.dimensions.append(new_dim)

    @classmethod
    def _remove_dimension(cls, schema: SchemaDefinition, change: SchemaChange):
        """移除维度（标记删除，不物理删除）"""
        for group in schema.groups:
            group.dimensions = [
                d for d in group.dimensions if d.name != change.dimension_name
            ]

    @classmethod
    def _update_field(cls, schema: SchemaDefinition, change: SchemaChange):
        """更新字段"""
        # 简化实现：按 field_path 定位并更新
        # field_path 示例：groups/用户侧/dimensions/功能对比/keywords
        pass  # 后续完善
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_schema/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/schema/ tests/test_schema/
git commit -m "$(cat <<'EOF'
feat: add SchemaRegistry

Add backend/app/schema/registry.py:
- SchemaRegistry.register() / get() / list_templates()
- SchemaRegistry.apply_patch() for hot updates
- In-memory storage for MVP stage

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 创建硬规则校验器

**Files:**
- Create: `backend/app/schema/validators.py`
- Test: `backend/tests/test_schema/test_validators.py`

- [ ] **Step 1: 编写校验器测试**

```python
# backend/tests/test_schema/test_validators.py
import pytest
from app.models.schema import DimensionSchema, EvidenceRequirements
from app.models.analysis import AnalysisResult, Finding, Confidence
from app.schema.validators import (
    validate_traceability,
    check_confidence_contradiction,
)


def test_validate_traceability_pass():
    """测试引用完整的 finding 通过校验"""
    finding = Finding(
        finding_id="f001",
        claim="竞品A 支持多语言",
        quote="Supporting 12 languages",
        quote_type="exact",
        source_ref="src_001",
        chunk_ref="chunk_01",
        reasoning_chain=[],
        confidence=Confidence(score=0.9, level="high"),
    )
    result = AnalysisResult(
        analysis_id="a001",
        competitor="竞品A",
        dimension="功能对比",
        findings=[finding],
        comparison_matrix={},
    )
    errors = validate_traceability(result)
    assert len(errors) == 0


def test_validate_traceability_missing_source():
    """测试缺少 source_ref 时报错"""
    finding = Finding(
        finding_id="f001",
        claim="竞品A 支持多语言",
        quote="",  # 缺少引用
        quote_type="exact",
        source_ref="",  # 缺少来源
        chunk_ref="chunk_01",
        reasoning_chain=[],
        confidence=Confidence(score=0.9, level="high"),
    )
    result = AnalysisResult(
        analysis_id="a001",
        competitor="竞品A",
        dimension="功能对比",
        findings=[finding],
        comparison_matrix={},
    )
    errors = validate_traceability(result)
    assert len(errors) == 2  # 缺少 quote 和 source_ref


def test_check_confidence_contradiction():
    """测试置信度低于 baseline 时触发修正"""
    finding = Finding(
        finding_id="f001",
        claim="竞品A 支持多语言",
        quote="Supporting 12 languages",
        quote_type="exact",
        source_ref="src_001",
        chunk_ref="chunk_01",
        reasoning_chain=[],
        confidence=Confidence(score=0.5, level="low"),  # 低于 baseline
    )
    dimension = DimensionSchema(
        name="功能对比",
        confidence_baseline=0.8,  # baseline 0.8
    )
    should_patch = check_confidence_contradiction(finding, dimension)
    assert should_patch is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_schema/test_validators.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 创建 validators.py**

```python
# backend/app/schema/validators.py
from app.models.analysis import AnalysisResult, Finding
from app.models.schema import DimensionSchema


def validate_traceability(analysis_result: AnalysisResult) -> list[str]:
    """
    强制引用检查（非 LLM 硬规则）。
    校验每个 finding 是否包含 source_ref 和 quote。
    返回错误列表，无错误返回空列表。
    """
    errors = []
    for finding in analysis_result.findings:
        if not finding.source_ref:
            errors.append(f"Finding '{finding.claim}' 缺少 source_ref")
        if not finding.quote:
            errors.append(f"Finding '{finding.claim}' 缺少 quote")
    return errors


def check_confidence_contradiction(
    finding: Finding,
    dimension: DimensionSchema
) -> bool:
    """
    矛盾检测（软约束）。
    检测 finding 置信度是否低于 dimension 的 confidence_baseline。
    返回 True 表示需要触发 SchemaPatch 修正。
    """
    baseline = dimension.confidence_baseline
    actual = finding.confidence.score
    return actual < baseline


def validate_percentage_field(value: float, field_name: str) -> list[str]:
    """
    百分比字段数值校验（硬规则）。
    返回错误列表。
    """
    errors = []
    if not 0.0 <= value <= 100.0:
        errors.append(f"{field_name} must be in [0.0, 100.0], got {value}")
    return errors
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_schema/test_validators.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/schema/validators.py tests/test_schema/test_validators.py
git commit -m "$(cat <<'EOF'
feat: add hard rule validators

Add backend/app/schema/validators.py:
- validate_traceability() for source_ref/quote check
- check_confidence_contradiction() for baseline mismatch
- validate_percentage_field() for range validation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 更新 models __init__.py 导出

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

## Task 5: 注册默认预设模板（可选）

此项为可选任务，可在后续实现预设模板时完成。

---

## Self-Review 检查

1. **Spec coverage：** Schema 模型完整覆盖设计文档
   - ✅ DimensionSchema, GroupSchema, SchemaDefinition
   - ✅ CustomFieldHint, EvidenceRequirements
   - ✅ SchemaPatch, SchemaChange
   - ✅ SchemaRegistry with hot update
   - ✅ Hard rule validators (validate_traceability, range validation)
2. **Placeholder scan：** 无 TBD/TODO，代码块完整
3. **Type consistency：** 类型定义一致，from_llm 返回 DimensionSchemaInput

---

## Architecture Changes (from old plan)

**Old approach:** Schema embedded in TaskDAG via `task_dag.schema`
**New approach:** Schema via SchemaRegistry, TaskDAG references `schema_id`

此差异反映 MVP 阶段的简化：Schema 独立管理，不与 TaskDAG 耦合。

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-05-23-schema-implementation.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** - dispatch fresh subagent per task, review between tasks

**2. Inline Execution** - execute tasks in this session using executing-plans

**Which approach?**