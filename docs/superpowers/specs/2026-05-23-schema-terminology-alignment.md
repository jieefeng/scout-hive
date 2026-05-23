# Schema 术语对齐与 MVP 优化设计

> 日期：2026-05-23
> 状态：已批准，等待实现

## 1. 背景

基于市面竞品（Kompyte、Klue）调研，发现现有 v3 MVP Schema 存在以下问题：
1. 术语命名不行业通用（`domain` vs `website`）
2. `min_sources` 语义不够清晰（应为 `evidence_threshold`）
3. 缺少 battlecard 输出格式
4. TaskDAG.competitors 类型不准确（应为 list[Competitor]）

## 2. 术语对齐

| 现状字段 | 改为 | 原因 |
|---------|------|------|
| `domain` | `website` | 行业通用命名（Kompyte/Attio 都用 website） |
| `min_sources` | `evidence_threshold` | 更准确描述"最少独立来源数"的含义 |

## 3. 功能增强

### 3.1 输出格式增加 `battlecard` 选项

```python
OutputType = Literal["table", "paragraph", "battlecard"]
```

Writer 行为：
- `battlecard`: 输出分栏卡片式，每张卡片一个竞品
- 卡片内包含：竞品名、核心数据摘要、关键洞察

### 3.2 增加 tracking_sources 可选字段

```python
class DimensionSchema(BaseModel):
    # ... 现有 5 字段 ...
    tracking_sources: list[str] = Field(
        default=["web"],
        description="数据来源：web / social / jobs / reviews / ads"
    )
```

MVP 阶段不强制填写，Collector 使用默认 `web` 策略。

## 4. TaskDAG 修正

```python
class TaskDAG(BaseModel):
    task_id: str
    competitors: list[Competitor]  # ✅ 已修正（原 list[str]）
    dimensions: list[str]
    dag: DAGBlueprint
    traceability: TraceabilityConfig = Field(default_factory=TraceabilityConfig)
```

## 5. 向后兼容

```python
class Competitor(BaseModel):
    name: str
    website: str  # 新名称
    domain: str = Field(default=None, validation_alias="website")  # 兼容旧名
```

## 6. 字段变更汇总

| 操作 | 字段 | 说明 |
|------|------|------|
| 重命名 | `domain` → `website` | 术语对齐 |
| 重命名 | `min_sources` → `evidence_threshold` | 语义更清晰 |
| 新增 | `output_type` 增加 `battlecard` | 输出格式增强 |
| 新增 | `tracking_sources` | 可选字段，采集来源配置 |
| 修正 | `TaskDAG.competitors` 类型 | `list[str]` → `list[Competitor]` |

## 7. 与竞品对比

| 设计 | 市面产品 | 评价 |
|------|---------|------|
| `keywords` 字段 | ❌ 没有 | ⚡ 采集驱动型独创 |
| `output_type: battlecard` | ⚠️ Kompyte 有 | 借鉴并增强 |
| `evidence_threshold` | ❌ 没有 | ⚡ 质量控制独创 |
| `tracking_sources` | ⚠️ Kompyte 有 | 作为可选字段 |

## 8. 下一步

实现上述修改，运行测试验证。