# 竞品分析 Schema 设计文档 v2

> 替代 `docs/superpowers/specs/2026-05-23-schema-design.md`。本版基于原设计的批判性审视，砍掉过度工程化部分，保留核心价值。

## 1. 设计原则

- **Schema 是配置文件，不是子系统。** 不需要 Registry、Patch、热更新机制。JSON 文件存储 + 代码常量 fallback，启动加载，API 读写。
- **MVP 优先刚性约束。** 用枚举控制输出格式和采集目标，少用自然语言"请求" Agent 做事。
- **硬约束用枚举和数值范围，软引导用自然语言。** `output_type` 和 `target_platform` 是硬约束，`description` 是软引导。
- **失败不阻断。** 数据不足时降级输出、明确标注，不重试死循环、不报错崩溃。

---

## 2. 数据模型

### 2.1 DimensionSchema

```python
from pydantic import BaseModel, Field
from typing import Literal

Platform = Literal["any", "official_website"]
OutputType = Literal["auto", "table", "paragraph"]

class DimensionSchema(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    target_platform: Platform = "any"
    output_type: OutputType = "auto"
    min_sources: int = Field(default=1, ge=1)
    preferred_sources: list[str] = Field(default_factory=list)
```

### 2.2 GroupSchema

```python
class GroupSchema(BaseModel):
    name: str
    description: str = ""
    dimensions: list[DimensionSchema] = Field(default_factory=list)
```

### 2.3 SchemaDefinition

```python
class SchemaDefinition(BaseModel):
    schema_id: str
    name: str
    version: str = "1.0"
    groups: list[GroupSchema] = Field(default_factory=list)
```

### 2.4 字段职责表

| 字段 | 使用者 | 作用 | 约束类型 |
|------|--------|------|----------|
| `name` | 全部 Agent | 维度标识 | — |
| `description` | Collector, Writer | 理解分析意图、补充上下文 | 软引导（自然语言） |
| `keywords` | Collector | 搜索关键词 | 软引导 |
| `target_platform` | Collector | 必须去哪采集 | 硬约束（枚举） |
| `output_type` | Writer | 输出结构：表格/段落/自动 | 硬约束（枚举） |
| `min_sources` | Analyst, Reviewer | 证据数量底线 | 硬约束（数值） |
| `preferred_sources` | Collector | 优先来源加权 | 软引导 |

### 2.5 与 v1 的差异

| v1 存在 | v2 状态 | 原因 |
|----------|---------|------|
| `CustomFieldHint` | 砍掉 | MVP 无人使用，等需求验证 |
| `EvidenceRequirements` 独立类 | 砍掉（字段扁平化） | 仅 2 字段，不需要独立模型 |
| `output_format` / `analysis_structure` | 改为 `output_type: Literal["auto", "table", "paragraph"]` | 自然语言不可靠，MVP 需要枚举硬约束 |
| `confidence_baseline` | 砍掉 | LLM 置信度打分不可靠，`min_sources` 已足够 |
| `fallback_query` | 砍掉 | `description` 本身即是兜底查询 |
| `DimensionSchemaInput` + `from_llm()` | 砍掉 | Schema 是用户配置，非 LLM 输出 |
| `SchemaChange` / `SchemaPatch` | 砍掉 | 整文件替换，不搞增量补丁 |
| `SchemaRegistry` 类 | 砍掉 | JSON 文件 CRUD 替代 |
| `source_hints: list[str]` | 改为 `target_platform: Platform` | 硬约束替代软提示 |
| `data_sources` | 砍掉 | 与 `target_platform` 高度重叠，映射表已决定工具选择 |
| `target_platform` (6 值) | 砍为 2 值 (`any`, `official_website`) | 专用平台 API 未实现，MVP 先跑通通用搜索 |

---

## 3. target_platform 映射表

MVP 阶段只开放两个枚举值，其余专用平台（app_store、github 等）待 API 工具实现后再加。

### 3.1 映射表

| target_platform | Collector 行为 | 搜索模板 |
|-----------------|---------------|----------|
| `any` | 通用搜索，不限制来源 | `{keywords} {competitor_name}` |
| `official_website` | 限定竞品官网域名搜索 | `site:{competitor_domain} {keywords}` |

### 3.2 实现要求

Collector Agent 的 prompt 中必须包含此映射逻辑。当 `target_platform = "official_website"` 时，Collector 必须使用 `site:` 限定域名，不得自由发挥。若指定平台无结果，标记维度为 `data_insufficient`，不得退化为通用搜索。

### 3.3 未来扩展

以下平台待对应 API/爬虫实现后再加入枚举：

| 平台 | 需要的工具 | 优先级 |
|------|-----------|--------|
| `app_store` | 七麦数据 API / App Store Search API | P1 |
| `github` | GitHub Search API | P2 |
| `pricing_page` | 官网 pricing 页面爬虫 | P2 |
| `g2_reviews` | G2 页面爬虫 | P3 |

新平台加入时，必须同步补充此映射表中的"Collector 行为"和"搜索模板"列。

---

## 4. description 和 output_type 使用指南

`output_type` 控制输出结构（刚性），`description` 补充分析意图（柔性）。Writer 必须遵守 `output_type`，同时参考 `description` 中的上下文。

### 4.1 output_type 行为契约

| output_type | Writer 行为 | 适用场景 |
|-------------|------------|----------|
| `auto` | 自主决定输出结构（根据数据特征选表格或段落） | 用户不确定输出格式 |
| `table` | 必须输出表格（对比表/参数矩阵），找不到可比维度则标注"无可比数据" | 定价对比、功能对比 |
| `paragraph` | 必须输出段落叙述，不得生成表格 | 深度分析、趋势解读 |

### 4.2 description 编写范例

**好的 description：**

> "对比各竞品的定价档位（免费版/专业版/企业版）、核心权益差异及隐藏费用（如超出限额的额外收费）。若某竞品无公开定价，注明'未公开'并记录获取报价途径。"

> "分析各竞品在移动端的用户评分、近期差评趋势（近 3 个月）及官方响应情况。区分 iOS 和 Android 平台数据。优先引用量化评分和排名。"

**不好的 description：**

> "分析定价。" — 太简略，Writer 不知道要关注什么

> "必须以表格列出定价档位然后写一段分析。" — 越权指挥，output_type 已管结构

### 4.3 编写原则

1. **说清楚关注点**（价格档位、功能差异、用户评分）
2. **允许异常情况**（无公开定价、数据缺失），给出处理方式
3. **不指定格式**（格式由 `output_type` 控制，description 只管内容）

---

## 5. min_sources 降级策略

### 5.1 分级处理

```
Analyst 评估证据数量:

  sources >= min_sources  → 正常输出，confidence = "high"
  
  sources >= 1 但 < min_sources  → 降级输出，confidence = "low"
                                   在 claim 前加 ⚠️ 标记
                                   在 finding 中记录: "仅找到 N 条来源，未达最低要求 (min_sources)"
  
  sources == 0  → 标记维度为 data_insufficient
                  不阻断任务，Writer 在报告中输出 "该维度数据不足，无法分析"
```

### 5.2 关键约束

- **不重试采集。** Collector 的每次采集已经是最优尝试。证据不足是信息客观缺失，不是采集失败。
- **不阻断流程。** 一个维度数据不足，其他维度正常推进。Writer 在最终报告中明确标注哪些维度数据不足。
- **不明说"禁止编造"。** 这个约束写在 Analyst 的 system prompt 里，不在数据模型层。

### 5.3 失败态输出格式

数据不足的 finding 示例：

```json
{
  "finding_id": "f_dim3_insufficient",
  "claim": "⚠️ 数据不足：未找到满足 min_sources=2 的独立来源",
  "quote": "",
  "source_ref": "",
  "confidence": { "score": 0.0, "level": "low", "uncertainty_factors": ["仅找到 1 条来源"] }
}
```

---

## 6. 文件持久化

### 6.1 存储方案

Schema 以 JSON 文件形式存储在 `backend/schemas/` 目录下。每个文件一个 Schema：

```
backend/schemas/
├── default-general.json      # 通用竞品分析模板
├── default-saas.json         # SaaS 产品分析模板
└── {schema_id}.json          # 用户自定义模板（文件名 = schema_id）
```

### 6.2 加载机制

- **启动时**：先加载代码内置默认模板（见 6.3），再扫描 `backend/schemas/` 目录。目录中同 `schema_id` 的文件覆盖内置模板
- **目录不存在或为空**：仅使用内置模板，系统正常运行
- **运行时**：通过 API 读取/写入文件
- **"热更新"**：调用 reload API 端点重新扫描目录

```python
# backend/app/schema/defaults.py — 内置默认模板（代码常量 fallback）

DEFAULT_SCHEMAS: list[dict] = [
    {
        "schema_id": "default-general",
        "name": "通用竞品分析模板",
        "version": "1.0",
        "groups": [
            {
                "name": "产品功能",
                "description": "核心功能维度对比",
                "dimensions": [
                    {
                        "name": "功能对比",
                        "description": "对比各竞品的核心功能差异与优势。若某竞品缺少某项功能请明确标注。",
                        "keywords": ["功能", "特性", "支持"],
                        "target_platform": "official_website",
                        "output_type": "table",
                        "min_sources": 2,
                        "preferred_sources": ["官网产品页", "官方文档"]
                    }
                ]
            }
        ]
    }
]
```

### 6.3 示例文件

```json
{
  "schema_id": "default-general",
  "name": "通用竞品分析模板",
  "version": "1.0",
  "groups": [
    {
      "name": "产品功能",
      "description": "核心功能维度对比",
      "dimensions": [
        {
          "name": "功能对比",
          "description": "对比各竞品的核心功能差异与优势。若某竞品缺少某项功能请明确标注。每个功能点需附带来源引用。",
          "keywords": ["功能", "特性", "支持"],
          "target_platform": "official_website",
          "output_type": "table",
          "min_sources": 2,
          "preferred_sources": ["官网产品页", "官方文档"]
        }
      ]
    }
  ]
}
```

---

## 7. Schema → TaskDAG 绑定流程

### 7.1 模型关系

Schema（静态模板）和 TaskDAG（任务实例）是分离的两层：

- **SchemaDefinition**: 定义"分析什么维度、怎么采集"（可复用模板）
- **TaskDAG**: 绑定 Schema + 竞品名单 + 执行 DAG，是单次任务的完整定义

### 7.2 现有 TaskDAG 的调整

```python
# backend/app/models/dag.py — TaskDAG 修改

class Competitor(BaseModel):
    name: str           # "飞书"
    domain: str         # "feishu.cn"（必填，target_platform=official_website 时使用）

class TaskDAG(BaseModel):
    task_id: str
    schema_id: str = ""           # 新增：引用 Schema
    schema_version: str = ""      # 新增：记录使用的 Schema 版本
    competitors: list[Competitor] # 升级：从 list[str] 改为结构化
    dag: DAGBlueprint
    traceability: TraceabilityConfig = Field(default_factory=TraceabilityConfig)
```

`dimensions: list[str]` 移除——维度信息现在从 Schema 文件中读取。

### 7.3 运行时流程

```
用户操作                           系统行为
───────                           ──────
1. 前端展示 Schema 模板列表        GET /api/schemas
2. 用户选择模板 + 填写竞品名单     域名必填（见 7.4）
3. 提交任务                        POST /api/tasks { schema_id, competitors }
4. Orchestrator 加载 Schema        读内置默认模板 → 目录 JSON 覆盖
5. 展开维度 → 生成 DAG 节点        每个 DimensionSchema → Collector/Analyst/Writer 任务
6. Collector 按 target_platform    注入 competitor.domain，执行定向采集
7. Analyst 按 min_sources 校验     降级或正常输出
8. Writer 按 output_type 约束      table/paragraph/auto 决定输出结构
```

### 7.4 竞品域名（必填约束）

`target_platform = "official_website"` 时，Collector 需要 `competitor.domain` 构造 `site:` 搜索模板。**MVP 阶段不允许 AI 猜测域名**——域名必须由用户提供。

- 前端：竞品名称 + 域名两个输入框，域名校验格式（含 `.` 的合法域名）
- 后端：`Competitor.domain` 为必填字段（Pydantic `Field(min_length=1)`）
- 若用户确实不知道竞品官网，选择 `target_platform: "any"` 走通用搜索

---

## 8. API 设计

### 8.1 Schema CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/schemas` | 列出所有 Schema（名称、ID、版本） |
| GET | `/api/schemas/{schema_id}` | 获取完整 Schema 定义 |
| PUT | `/api/schemas/{schema_id}` | 创建或替换 Schema |
| DELETE | `/api/schemas/{schema_id}` | 删除 Schema |
| POST | `/api/schemas/reload` | 重新扫描目录，刷新缓存 |

### 8.2 校验规则

PUT 创建/替换时：
1. JSON 解析 → 通过 Pydantic `SchemaDefinition.model_validate()` 校验
2. 校验通过 → 写入 `backend/schemas/{schema_id}.json`
3. 校验失败 → 返回 422 + ValidationError 详情

没有运行时"热合并"。修改 Schema 不影响已在执行的任务（任务持有 `schema_version` 快照）。

---

## 9. 硬规则校验器

### 9.1 保留的校验

只保留一个校验器：`validate_traceability`

```python
def validate_traceability(analysis_result: AnalysisResult) -> list[str]:
    """检查每个 finding 的 source_ref 和 quote 是否非空。
    跳过数据不足的 finding（confidence.score == 0.0 为 insufficient_data 信号）。
    """
    errors = []
    for finding in analysis_result.findings:
        if finding.confidence.score == 0.0:
            continue  # 数据不足标记，跳过校验
        if not finding.source_ref:
            errors.append(f"Finding '{finding.claim}' 缺少 source_ref")
        if not finding.quote:
            errors.append(f"Finding '{finding.claim}' 缺少 quote")
    return errors
```

**跳过逻辑：** `confidence.score == 0.0` 是降级策略的输出信号（见 5.3）。数据不足的 finding 天然没有 source_ref 和 quote，不应对其报错。正常 finding 的 score 始终 > 0（由 Analyst 设定），不会误命中。

### 9.2 砍掉的校验

| 砍掉的校验 | 原因 |
|-----------|------|
| `check_confidence_contradiction` | LLM 置信度打分不可靠，数值比较无意义 |
| `validate_percentage_field` | 模型中没有百分比字段 |
| `DimensionSchemaInput.validate_ranges` | Pydantic `Field(ge=, le=)` 已替代 |

### 9.3 校验器定位

硬规则校验器的能力边界：**只能检查字段是否缺失，不能检查内容是否准确。** 引用准确性验证需要 LLM 自行判断（通过 Reviewer Agent），非硬规则能解决。

---

## 10. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 存储方案 | JSON 文件 + 代码常量 fallback | 可 API 操作，目录缺失仍可运行 |
| Schema 更新方式 | 整文件替换 | 避免手写 JSON Patch 的脆弱性 |
| 输出结构控制 | `output_type` 枚举（硬约束）+ `description` 补充（软引导） | MVP 需要刚性约束保证稳定性 |
| 质量门禁 | min_sources（硬约束） | 比置信度打分更可靠、更可操作 |
| 采集目标约束 | `target_platform` 仅 2 值（any/official_website） | 专用平台 API 未就绪，MVP 先跑通通用搜索 |
| 竞品域名 | 用户必填，无 AI 兜底 | MVP 不允许 AI 猜测域名 |
| 失败处理 | 降级标注，不阻断 | 部分数据 > 零数据 > 卡死 |
