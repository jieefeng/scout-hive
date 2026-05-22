# 竞品分析 Schema 设计文档

## 1. 概述

### 1.1 Schema 的 5 重角色

| # | 角色 | 技术实现 |
|---|------|----------|
| 1 | 精准购物清单 | `keywords` 字段直接驱动采集函数精准采集 |
| 2 | 通用协作语言 | 分组层级 + 统一 `DimensionSchema` 结构 |
| 3 | 标准化尺子 | 所有维度拉齐到统一字段定义 |
| 4 | 证据枷锁 | `evidence_requirements` + 硬规则校验强制 Analyst 引用 |
| 5 | 数字化容器 | 预设模板 + Schema Registry 热更新 + 用户自定义 |

### 1.2 设计原则

- **MVP 优先**：单体进程 + 状态机模拟 Agent 流转，不拆分独立 Agent 服务
- Schema 结构固定，字段值提供默认值，用户可修改
- 每个字段有明确类型定义，后端据此验证
- 用户可添加自定义字段（通过 `custom_fields`）
- **Schema Registry**：Schema 配置化，支持热更新
- 可演进，但历史数据版本化，不追溯修改
- **硬规则校验**：非 LLM 的数值范围校验和来源 ID 校验，防止幻觉

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
    preferred: list[str] = []        # 优先信息来源类型（Tier 1/2/3 加权）
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

### 2.3 来源分级（EvidenceRequirements）

基于 `preferred` 字段实现可信源加权：

| Tier | 来源类型 | 权重 | 示例 |
|------|----------|------|------|
| Tier 1 | 官方来源 | 1.0 | 官网、财报、官方博客 |
| Tier 2 | 第三方数据 | 0.8 | SimilarWeb、七麦数据、SensorTower |
| Tier 3 | UGC 内容 | 0.5 | 社交媒体、评论（仅用于情感分析） |

### 2.4 数值范围校验（硬规则）

在 `DimensionSchemaInput.from_llm()` 中增加数值范围校验，防止幻觉：

| 字段 | 校验规则 | 错误示例 |
|------|----------|----------|
| `confidence_baseline` | 0.0 ≤ x ≤ 1.0 | 1.5, -0.1 |
| `evidence_requirements.min_sources` | ≥ 1 | 0, -1 |
| 自定义百分比字段 | 0.0 ≤ x ≤ 100.0 | 150% |

### 2.5 custom_fields 渲染提示

| render_hint | 渲染方式 |
|-------------|----------|
| `auto` | 自动选择（根据值类型判断） |
| `badge` | 标签样式 |
| `list` | 列表 |
| `paragraph` | 段落文本 |
| `table` | 表格形式 |

---

## 3. 单体流程与 Schema 驱动

### 3.1 固定流程（状态机模拟）

MVP 阶段使用单体进程，通过状态机模拟 Agent 流转，不拆分独立 Agent 服务：

```
用户输入任务
     │
     ▼
┌─────────────────────────┐
│  TaskParser              │
│  理解需求，解析 Schema   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  采集函数 collect()    │
│  按 keywords 精准采集   │
│  fallback_query 兜底    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  分析函数 analyze()     │
│  强制引用 + 硬规则校验   │
│  数值范围 + 来源 ID     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  撰写函数 write()       │
│  按 output_format 渲染   │
│  custom_fields 带提示   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  质检函数 review()      │
│  溯源校验（可触发      │
│  Schema Patch）         │
└────────┬────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 通过 ✅   不通过 ❌
              │
              ▼
      SchemaPatch 热更新
      （记录改动 → 补丁合并 → 继续执行）
```

### 3.2 函数封装（Tools 而非服务）

采集逻辑、分析逻辑封装为独立的 Python 函数（Tools），而非独立服务：

```python
# 采集函数示例
async def collect(dimension: DimensionSchema, competitor: str) -> RawData:
    """按 keywords 采集，fallback_query 兜底"""
    ...

# 分析函数示例
async def analyze(raw_data: RawData, dimension: DimensionSchema) -> AnalysisResult:
    """强制引用 + 硬规则校验"""
    ...
```

### 3.3 采集兜底策略（三层）

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

### 3.4 Analyst 降级机制

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

## 4. Schema 配置化与热更新

### 4.1 Schema Registry

Schema 配置化，利用 SchemaDefinition 构建 Schema Registry（注册中心），产品经理可通过后台界面动态调整：

```python
class SchemaRegistry:
    """Schema 注册中心（内存中或数据库持久化）"""
    _schemas: dict[str, SchemaDefinition] = {}

    @classmethod
    def register(cls, schema: SchemaDefinition):
        cls._schemas[schema.schema_id] = schema

    @classmethod
    def get(cls, schema_id: str) -> SchemaDefinition | None:
        return cls._schemas.get(schema_id)

    @classmethod
    def list_templates(cls) -> list[str]:
        """列出所有注册模板"""
        return [s.name for s in cls._schemas.values()]
```

### 4.2 热加载流程

当业务需要分析新维度（如"AI功能"）时，系统管理员在前端添加配置，后端通过 SchemaPatch 接口热更新：

```
前端修改 Schema
     │
     ▼
SchemaPatch API 接收补丁
     │
     ▼
SchemaRegistry 热合并
     │
     ▼
TaskDAG schema 版本更新（无需重启服务）
```

### 4.3 继承机制（ChildSchema）

允许针对特定任务创建 ChildSchema 进行覆盖：

```python
class ChildSchema(BaseSchema):
    """继承并覆盖特定维度"""
    parent_schema_id: str = ""  # 引用父 Schema

    @model_validator(mode="after")
    def apply_overrides(self):
        if self.parent_schema_id:
            parent = SchemaRegistry.get(self.parent_schema_id)
            if parent:
                # 合并：子 Schema 覆盖父 Schema 的同名维度
                self.groups = self._merge_with_parent(parent)
        return self
```

---

## 5. 硬规则校验（非 LLM）

### 5.1 强制引用检查

在 TaskDAG 输出验证层，增加非 LLM 的校验器，强制要求分析结论中的每个数据点必须包含 `source_id`：

```python
def validate_traceability(analysis_result: AnalysisResult) -> list[str]:
    """返回错误列表，无错误返回空列表"""
    errors = []
    for finding in analysis_result.findings:
        if not finding.source_ref:
            errors.append(f"Finding '{finding.claim}' 缺少 source_ref")
        if not finding.quote:
            errors.append(f"Finding '{finding.claim}' 缺少 quote")
    return errors
```

### 5.2 矛盾检测（软）

利用 SchemaPatch 机制。如果 Reviewer 发现结论置信度低于 `confidence_baseline`，触发修正流程：

```python
def check_confidence_contradiction(
    finding: Finding,
    dimension: DimensionSchema
) -> bool:
    """检测是否需要触发 SchemaPatch 修正"""
    baseline = dimension.confidence_baseline
    actual = finding.confidence.score
    if actual < baseline:
        return True  # 触发 SchemaPatch
    return False
```

### 5.3 数值范围校验

```python
class DimensionSchemaInput(BaseModel):
    """应用层输入模型，用于解析 LLM 输出的原始数据"""
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
        """数值范围校验，防止幻觉"""
        if not 0.0 <= self.confidence_baseline <= 1.0:
            raise ValueError(f"confidence_baseline must be in [0.0, 1.0], got {self.confidence_baseline}")
        er = self.evidence_requirements
        if er.get("min_sources", 1) < 1:
            raise ValueError("min_sources must be >= 1")
        return self
```

---

## 6. Schema 演进机制

### 6.1 Patch 模型

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
    applied_at: str = ""
    triggered_by: str = ""            # 触发来源（如 review_001）
    changes: list[SchemaChange] = []
```

### 6.2 版本化原则

- **只追加不修改**：历史数据标记对应 schema_version，不追溯修改
- **Patch 触发时**：旧节点数据不变（标记旧 schema_version），新节点用新 schema_version
- **Writer 渲染时**：按 schema_version 决定如何解读数据

---

## 7. 类型容错策略

### 7.1 分层验证

| 层级 | 策略 | 目的 |
|------|------|------|
| 入口验证 | 严格模式，拒收非法输入 | 防止脏数据入库 |
| 函数输出解析 | 应用层静默适配，格式错误才抛异常 | 允许类型偏差 |

### 7.2 容错原则

- 类型偏差（数字混进 keywords）→ 静默过滤，不抛异常
- 格式错误（JSON 结构不对）→ 抛异常让调用方处理重试
- 两者分开处理，不混为一谈

---

## 8. 用户操作能力

| 操作 | 说明 |
|------|------|
| 选择预设模板 | 系统提供默认 Schema |
| 修改字段值 | 修改 keywords、output_format 等（基于固定字段名） |
| 自定义字段 | 通过 `custom_fields` 添加，附带 `render_hint` |
| 添加维度 | 在分组下新增 DimensionSchema |
| 删除维度 | 标记移除（不物理删除，记录 Patch） |
| 演进触发 | Reviewer 反馈 → SchemaPatch → 合并后继续 |

---

## 9. 痛点与解决方案对照表

| 痛点 | 解决方案关键词 | 对应代码/模块 |
|------|---------------|---------------|
| 过度工程化 | 单体优先，状态机模拟 | 固定流程 + Python 函数封装 |
| 幻觉/质检 | 硬规则校验 + 引用锚点 | `validate_traceability()` + 数值范围校验 |
| Schema僵化 | 配置中心 + SchemaPatch | SchemaRegistry + 热更新 API |
| 采集漏斗 | 来源分级 + 专业工具集成 | EvidenceRequirements + 数据源加权 |
| 可观测性噪音 | 摘要展示 + 详情钻取 | TraceabilityConfig 控制输出粒度 |