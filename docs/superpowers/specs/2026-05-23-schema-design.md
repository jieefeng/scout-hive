# 竞品分析 Schema 设计文档

## 1. 概述

### 1.1 Schema 的 5 重角色

| # | 角色 | 技术实现 |
|---|------|----------|
| 1 | 精准购物清单 | `keywords` 字段直接驱动 Collector 精准采集 |
| 2 | 通用协作语言 | 分组层级 + 统一 `DimensionSchema` 结构 |
| 3 | 标准化尺子 | 所有维度拉齐到统一字段定义 |
| 4 | 证据枷锁 | `evidence_requirements.min_sources` 强制 Analyst 引用 |
| 5 | 数字化容器 | 预设模板（系统提供默认值）+ 用户自定义 |

### 1.2 设计原则

- Schema 结构固定，字段值提供默认值，用户可修改
- 每个字段有明确类型定义，后端据此验证
- 用户可添加自定义字段（通过 `custom_fields`）
- Schema 内嵌于 DAG 蓝图，不独立存储
- 可演进，但历史数据版本化，不追溯修改

---

## 2. 数据模型

### 2.1 核心类型

```python
class CustomFieldHint(BaseModel):
    """用户自定义字段，必须附带渲染提示"""
    key: str                          # 字段名
    value: Any                        # 字段值
    render_hint: str = "auto"        # 渲染方式
    # "auto" | "badge" | "list" | "paragraph" | "table"


class EvidenceRequirements(BaseModel):
    """证据要求"""
    preferred: list[str] = []        # 优先信息来源类型
    min_sources: int = 1             # 最少独立来源数（软限制，低于时降级不阻断）


class DimensionSchema(BaseModel):
    """维度定义"""
    name: str                         # 维度名称
    description: str = ""             # 维度描述
    keywords: list[str] = []          # 搜索关键词（驱动采集）
    fallback_query: str = ""          # 兜底查询（description 作为语义扩展）
    evidence_requirements: EvidenceRequirements = EvidenceRequirements()
    data_sources: list[str] = []      # 信息来源类型
    output_format: str = "list"       # 输出格式："list" | "matrix" | "summary" | "narrative"
    confidence_baseline: float = 0.8  # 置信度基准
    custom_fields: list[CustomFieldHint] = []  # 用户自定义字段（带渲染提示）


class GroupSchema(BaseModel):
    """分组定义"""
    name: str                         # 分组名称
    description: str = ""
    dimensions: list[DimensionSchema] = []


class SchemaDefinition(BaseModel):
    """完整 Schema 定义"""
    schema_id: str
    version: str = "1.0"
    name: str
    groups: list[GroupSchema] = []
```

### 2.2 字段说明

| 字段 | 类型 | 必要性 | 说明 |
|------|------|--------|------|
| `name` | str | 必须 | 维度/分组名称 |
| `description` | str | 必须 | 维度描述（同时作为 fallback_query） |
| `keywords` | list[str] | 必须 | 采集搜索关键词 |
| `fallback_query` | str | 可选 | description 作为兜底搜索 query |
| `evidence_requirements.preferred` | list[str] | 可选 | 优先信息来源类型 |
| `evidence_requirements.min_sources` | int | 可选 | 最少来源数（软限制） |
| `data_sources` | list[str] | 可选 | 信息来源类型：`web`/`document`/`api`/`third_party_reviews` |
| `output_format` | str | 可选 | 输出格式，默认 `list` |
| `confidence_baseline` | float | 可选 | 置信度基准，默认 0.8 |
| `custom_fields` | list[CustomFieldHint] | 可选 | 用户自定义字段 |

### 2.3 custom_fields 渲染提示

| render_hint | 渲染方式 |
|-------------|----------|
| `auto` | 自动选择（根据值类型判断） |
| `badge` | 标签样式 |
| `list` | 列表 |
| `paragraph` | 段落文本 |
| `table` | 表格形式 |

---

## 3. Schema 在 Agent 协作中的流转

### 3.1 流转图

```
用户输入任务
     │
     ▼
┌─────────────────────────┐
│  TaskParser             │
│  输出：DAG Blueprint + │
│  内嵌 Schema            │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Collector             │
│  按 keywords 精准采集   │
│  fallback_query 兜底    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Analyst               │
│  按 evidence_requirements│
│  强制引用 + 降级处理    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Writer                │
│  按 output_format 渲染   │
│  custom_fields 带提示   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Reviewer              │
│  溯源校验（可触发      │
│  Schema Patch）         │
└────────┬────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 通过 ✅   不通过 ❌
              │
              ▼
      Schema Evolution Patch
      （记录改动 → 补丁合并 → 继续执行）
```

### 3.2 采集兜底策略

```
Collector 采集策略（三层）：

第1层：keywords 精确匹配
        ↓ 有结果？
第2层：description 语义扩展搜索（fallback_query）
        ↓ 有结果？
第3层：dimension name 泛搜索（最后兜底）
        ↓ 仍无结果？
→ 标记该维度为 "data_insufficient" → 降级输出
```

### 3.3 Analyst 降级机制

```python
# Analyst 内部逻辑
if len(sources) >= dimension.evidence_requirements.min_sources:
    confidence = "high"  # 正常输出
elif len(sources) >= 1:
    confidence = "low"  # 降级输出，标记 "来源不足"
    add_uncertainty("仅找到 N 个来源，建议补充")
else:
    mark_dimension_as("insufficient_data")  # 不阻断，降级标记
```

---

## 4. Schema 演进机制

### 4.1 Patch 模型

```python
class SchemaChange(BaseModel):
    """单次改动"""
    type: str                         # "add_dimension" | "remove_dimension" | "update_field"
    dimension_name: str               # 维度名称
    field_path: str                   # 字段路径，如 "keywords"
    before: Any                       # 改动前的值
    after: Any                       # 改动后的值


class SchemaPatch(BaseModel):
    """Schema 补丁"""
    patch_id: str
    applied_at: datetime
    triggered_by: str                 # 触发来源（如 review_001）
    changes: list[SchemaChange] = []
```

### 4.2 版本化原则

- **只追加不修改**：历史数据标记对应 schema_version，不追溯修改
- **Patch 触发时**：旧节点数据不变（标记旧 schema_version），新节点用新 schema_version
- **Writer 渲染时**：按 schema_version 决定如何解读数据

---

## 5. 类型容错策略

### 5.1 分层验证

| 层级 | 策略 | 目的 |
|------|------|------|
| 入口验证 | 严格模式，拒收非法输入 | 防止脏数据入库 |
| Agent 输出解析 | 应用层静默适配，格式错误才抛异常 | 允许 LLM 类型偏差 |

### 5.2 应用层适配

```python
class DimensionSchemaInput(BaseModel):
    """应用层输入模型，宽松处理类型"""
    name: str
    description: str = ""
    keywords: list[str] = []
    evidence_requirements: dict = {}
    data_sources: list[str] = []
    output_format: str = "list"
    confidence_baseline: float = 0.8
    custom_fields: list[dict] = []

    @classmethod
    def from_llm(cls, raw: dict) -> "DimensionSchemaInput":
        data = raw.copy()
        # keywords 只保留字符串类型（过滤数字等）
        if "keywords" in data:
            data["keywords"] = [str(v) for v in data["keywords"] if v is not None]
        # custom_fields 只保留 dict 类型
        if "custom_fields" in data:
            data["custom_fields"] = [v for v in data["custom_fields"] if isinstance(v, dict)]
        return cls(**data)
```

**容错原则：**
- 类型偏差（数字混进 keywords）→ 静默过滤，不抛异常
- 格式错误（JSON 结构不对）→ 抛异常让 LLM 重试
- 两者分开处理，不混为一谈

---

## 6. 用户操作能力

| 操作 | 说明 |
|------|------|
| 选择预设模板 | 系统提供默认 Schema |
| 修改字段值 | 修改 keywords、output_format 等（基于固定字段名） |
| 自定义字段 | 通过 `custom_fields` 添加，附带 `render_hint` |
| 添加维度 | 在分组下新增 DimensionSchema |
| 删除维度 | 标记移除（不物理删除，记录 Patch） |
| 演进触发 | Reviewer 反馈 → Schema Patch → 合并后继续 |

---

## 7. 与 DAG 蓝图内嵌关系

```python
class DAGBlueprint(BaseModel):
    """DAG 蓝图中嵌 Schema"""
    task_id: str
    competitors: list[str]
    schema: SchemaDefinition        # 内嵌 Schema
    dag: DAGConfig
```

Schema 完整内嵌于 DAG 蓝图中，随任务创建/执行，不独立存储。