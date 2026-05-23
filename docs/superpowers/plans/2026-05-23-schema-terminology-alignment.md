# Schema 术语对齐实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 术语对齐 + 功能增强（battlecard 输出 + tracking_sources 可选字段）

**Architecture:**
- 修改 `Competitor` 模型：`domain` → `website`，保留 `domain` alias 兼容旧代码
- 修改 `DimensionSchema`：`min_sources` → `evidence_threshold`，增加 `battlecard` 输出类型，增加 `tracking_sources` 可选字段
- 更新默认 schema 常量
- 更新相关测试

**Tech Stack:** Python, Pydantic, pytest

---

## 文件结构

```
backend/app/models/task.py       # Competitor 修改
backend/app/schema/mvp_defaults.py  # DimensionSchema 修改
backend/tests/test_schema/test_mvp_defaults.py  # 测试更新
backend/tests/test_models/test_task.py  # 测试更新
```

---

## Task 1: 修改 Competitor 模型（task.py）

**Files:**
- Modify: `backend/app/models/task.py:20-23`
- Test: `backend/tests/test_models/test_task.py`

- [ ] **Step 1: 添加 website 字段并保留 domain alias**

```python
class Competitor(BaseModel):
    """竞品结构：name + website（必填）"""
    name: str           # "飞书"
    website: str        # "feishu.cn"  # 新名称
    domain: str = Field(default=None, validation_alias="website")  # 兼容旧名
```

- [ ] **Step 2: 运行测试验证向后兼容**

Run: `pytest backend/tests/test_models/test_task.py -v`
Expected: PASS（domain 作为 alias 仍可工作）

- [ ] **Step 3: 添加 website 属性测试**

```python
def test_competitor_website_alias():
    c = Competitor(name="飞书", website="feishu.cn")
    assert c.website == "feishu.cn"
    # domain 仍可通过 alias 访问
    assert c.model_dump()["domain"] == "feishu.cn"
```

- [ ] **Step 4: 运行新测试**

Run: `pytest backend/tests/test_models/test_task.py::test_competitor_website_alias -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/task.py backend/tests/test_models/test_task.py
git commit -m "feat: rename Competitor.domain to website, add alias for backward compat"
```

---

## Task 2: 修改 DimensionSchema（mvp_defaults.py）

**Files:**
- Modify: `backend/app/schema/mvp_defaults.py:4-11`
- Test: `backend/tests/test_schema/test_mvp_defaults.py`

- [ ] **Step 1: 更新 OutputType 加入 battlecard**

```python
from typing import Literal

OutputType = Literal["table", "paragraph", "battlecard"]  # 增加 battlecard
```

- [ ] **Step 2: 修改 DimensionSchema 字段**

```python
class DimensionSchema(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = Field(min_length=1)
    output_type: OutputType = "paragraph"
    evidence_threshold: int = Field(default=1, ge=1)  # 原 min_sources，已改名
    tracking_sources: list[str] = Field(
        default=["web"],
        description="数据来源：web / social / jobs / reviews / ads"
    )  # 新增可选字段
```

- [ ] **Step 3: 更新 DEFAULT_SCHEMA 常量**

在 `DEFAULT_SCHEMA["groups"][0]["dimensions"][0]` 中：
```python
{
    "name": "功能对比",
    "description": "对比各竞品提供的核心功能差异，列出各竞品支持的功能项和不支持的功能项。",
    "keywords": ["功能", "特性", "支持"],
    "output_type": "table",
    "evidence_threshold": 2,  # 原 min_sources，已改名
    "tracking_sources": ["web"]  # 新增
},
```

在 `DEFAULT_SCHEMA["groups"][0]["dimensions"][1]` 中：
```python
{
    "name": "用户体验",
    "description": "分析各竞品在界面设计、操作体验、用户评价方面的特点。",
    "keywords": ["用户体验", "UI", "界面"],
    "output_type": "paragraph",
    "evidence_threshold": 1,  # 原 min_sources，已改名
    "tracking_sources": ["web"]  # 新增
},
```

在 `DEFAULT_SCHEMA["groups"][1]["dimensions"][0]` 中：
```python
{
    "name": "定价策略",
    "description": "对比各竞品的定价模式（免费/订阅/按需）、价格区间、有无隐藏费用。提取每个竞品的具体价格数据。",
    "keywords": ["定价", "价格", "套餐", "收费"],
    "output_type": "table",
    "evidence_threshold": 1,  # 原 min_sources，已改名
    "tracking_sources": ["web"]  # 新增
},
```

- [ ] **Step 4: 运行测试验证**

Run: `pytest backend/tests/test_schema/test_mvp_defaults.py -v`
Expected: FAIL（因为测试中仍使用 `min_sources`）

- [ ] **Step 5: 更新测试文件**

```python
def test_dimension_schema_fields():
    schema = load_default_schema()
    dim = schema.groups[0].dimensions[0]
    assert dim.name == "功能对比"
    assert dim.output_type in ["table", "paragraph", "battlecard"]  # 更新
    assert len(dim.keywords) >= 1
    assert dim.evidence_threshold >= 1  # 原 min_sources，已改名
    assert dim.tracking_sources == ["web"]  # 新增

def test_battlecard_output_type():
    t = DimensionSchema(
        name="测试", description="测试",
        keywords=["测试"], output_type="battlecard"
    )
    assert t.output_type == "battlecard"

def test_tracking_sources_default():
    t = DimensionSchema(
        name="测试", description="测试",
        keywords=["测试"]
    )
    assert t.tracking_sources == ["web"]
```

- [ ] **Step 6: 运行测试**

Run: `pytest backend/tests/test_schema/test_mvp_defaults.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/schema/mvp_defaults.py backend/tests/test_schema/test_mvp_defaults.py
git commit -m "feat: add battlecard output_type and tracking_sources to DimensionSchema"
```

---

## Task 3: 全局测试验证

**Files:**
- Test: `backend/tests/` 下所有测试

- [ ] **Step 1: 运行所有相关测试**

Run: `pytest backend/tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 2: 提交**

```bash
git add -A
git commit -m "test: verify all tests pass after schema terminology alignment"
```

---

## 变更汇总

| 文件 | 变更 |
|------|------|
| `task.py` | `domain` → `website` + alias |
| `mvp_defaults.py` | `min_sources` → `evidence_threshold`, 增加 `battlecard`, 增加 `tracking_sources` |
| `test_mvp_defaults.py` | 更新测试用例 |
| `test_task.py` | 增加 website alias 测试 |

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-05-23-schema-terminology-alignment.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**