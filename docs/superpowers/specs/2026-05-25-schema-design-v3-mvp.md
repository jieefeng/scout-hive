# 竞品分析 Schema 设计文档 v3 — MVP 最简化版

> 替代 `docs/superpowers/specs/2026-05-23-schema-design-v2.md`。本版面向最快跑通全流程，砍到只剩必要约束。

## 1. 设计原则

- **MVP 只跑一个闭环**：定向采集 → 可溯源分析 → 可读输出
- **Schema 内置，不外露。** 用户只填竞品名称和域名，不碰 Schema
- **复用现有 Agent，不重写采集逻辑。** 微调 prompt 而非重构架构
- **4 字段维度模型 + 硬约束枚举**，不用自然语言"请求" Agent 做事

---

## 2. 数据模型

### 2.1 DimensionSchema（4 字段）

```python
from pydantic import BaseModel, Field
from typing import Literal

OutputType = Literal["table", "paragraph"]

class DimensionSchema(BaseModel):
    name: str                           # 维度名称
    description: str = ""               # AI 理解指令（给 Writer 看，一句话说明要总结什么）
    keywords: list[str] = Field(min_length=1)  # 搜索关键词（给搜索引擎看，驱动采集）
    output_type: OutputType = "paragraph"      # 输出结构：表格 or 段落
    min_sources: int = Field(default=1, ge=1)   # 最少独立来源数
```

### 2.2 SchemaDefinition（内置，不外露）

```python
class GroupSchema(BaseModel):
    name: str
    dimensions: list[DimensionSchema] = Field(min_length=1)

class SchemaDefinition(BaseModel):
    schema_id: str = "default-mvp"
    name: str = "通用竞品分析模板"
    version: str = "1.0"
    groups: list[GroupSchema] = Field(min_length=1)
```

### 2.3 Competitor（必填结构）

```python
class Competitor(BaseModel):
    name: str           # 竞品名称："飞书"
    domain: str         # 官网域名："feishu.cn"（必填）
```

### 2.4 字段决策表

| 字段 | 去掉 | 原因 |
|------|------|------|
| `description` | 加回 | AI 需要知道要提取什么，keywords 只驱动搜索 |
| `target_platform` | — | MVP 只用 `official_website`，硬编码 |
| `preferred_sources` | — | `min_sources` 已够用 |
| `custom_fields` | — | MVP 无人用 |
| `SchemaPatch` | — | 不需要热更新 |
| `SchemaRegistry` | — | 不外露 Schema |

---

## 3. 内置默认模板

Schema 写死在代码里，不读文件，不走 API：

```python
# backend/app/schema/mvp_defaults.py

DEFAULT_SCHEMA: dict = {
    "schema_id": "default-mvp",
    "name": "通用竞品分析模板",
    "version": "1.0",
    "groups": [
        {
            "name": "产品功能",
            "dimensions": [
                {
                    "name": "功能对比",
                    "description": "对比各竞品提供的核心功能差异，列出各竞品支持的功能项和不支持的功能项。",
                    "keywords": ["功能", "特性", "支持"],
                    "output_type": "table",
                    "min_sources": 2
                },
                {
                    "name": "用户体验",
                    "description": "分析各竞品在界面设计、操作体验、用户评价方面的特点。",
                    "keywords": ["用户体验", "UI", "界面"],
                    "output_type": "paragraph",
                    "min_sources": 1
                }
            ]
        },
        {
            "name": "商业策略",
            "dimensions": [
                {
                    "name": "定价策略",
                    "description": "对比各竞品的定价模式（免费/订阅/按需）、价格区间、有无隐藏费用。提取每个竞品的具体价格数据。",
                    "keywords": ["定价", "价格", "套餐", "收费"],
                    "output_type": "table",
                    "min_sources": 1
                }
            ]
        }
    ]
}
```

---

## 4. TaskDAG 模型

```python
# backend/app/models/dag.py

class Competitor(BaseModel):
    name: str           # "飞书"
    domain: str         # "feishu.cn"（必填）

class TaskDAG(BaseModel):
    task_id: str
    competitors: list[Competitor]      # 竞品列表（name + domain）
    # Schema 固定为 DEFAULT_SCHEMA，不外露
    status: str = "pending"
    report_html: str = ""
    traces: list = Field(default_factory=list)
```

---

## 5. 采集策略（硬编码）

MVP 不需要 `target_platform` 枚举，采集策略硬编码：

```
Collector 行为规则：

1. 对每个竞品 + 每个维度：
   - 使用 keywords 构造搜索 query
   - 搜索范围：site:{competitor.domain}
   - 优先找主域名，找不到可尝试子域名（如 buy.{domain}、help.{domain}）

2. 对每个结果：
   - 抓取页面内容 → 切 chunk
   - chunk 保存：原始文本 + URL + 抓取时间

3. 找不到数据时：
   - 标记维度为 data_insufficient
   - 不阻断其他维度，继续执行
```

---

## 6. 输出控制（Writer Agent prompt 注入）

`output_type` 通过 prompt 注入，控制 Writer 行为：

| output_type | Writer 行为 |
|-------------|------------|
| `table` | 必须输出 Markdown 表格，不得输出纯段落 |
| `paragraph` | 输出段落叙述，不得生成表格 |

**Writer system prompt 追加：**

```
当 output_type = "table" 时：
- 输出 Markdown 表格，第一列是维度名，其余列是竞品
- 所有竞品必须使用完全相同的行维度（如"基础版价格"、"专业版价格"），没有数据的单元格填"无"
- 绝对禁止出现行列错位
- 表格后附数据来源脚注（URL）

当 output_type = "paragraph" 时：
- 用自然段落叙述，结构为：[竞品名]：[分析结论]
- 每条结论后附 (来源: URL)
```

---

## 7. 降级策略（min_sources）

```
Analyst 评估证据数量：

  sources >= min_sources  → 正常输出

  0 < sources < min_sources  → 降级输出
    - claim 前加 ⚠️
    - confidence.level = "low"
    - 记录 uncertainty_factors

  sources == 0  → 维度标记 data_insufficient
    - Writer 输出 "⚠️ 该维度数据不足，无法分析"
    - 不阻断任务
```

---

## 8. API 设计（MVP 精简版）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/tasks` | 创建任务 `{ competitors: [{name, domain}] }` |
| GET | `/api/tasks/{task_id}` | 查询状态 + 获取报告 HTML |
| GET | `/api/tasks/{task_id}/traces` | 获取执行痕迹 |

**砍掉：**
- Schema CRUD API（不需要）
- Schema reload API（不需要）
- Schema list API（不需要）

---

## 9. 执行流程

```
用户输入
  └─ 竞品列表：[{name: "飞书", domain: "feishu.cn"}, {name: "钉钉", domain: "dingtalk.com"}]
          │
          ▼
Orchestrator.load_schema()  → 返回内置 DEFAULT_SCHEMA
          │
          ▼
展开维度 × 竞品 → 生成采集任务
  - 飞书 × 功能对比
  - 飞书 × 定价策略
  - 钉钉 × 功能对比
  - 钉钉 × 定价策略
          │
          ▼
Collector 按 keywords + site:{domain} 采集
          │
          ▼
Analyst 按 min_sources 校验 → 降级或正常输出
          │
          ▼
Writer 按 output_type 生成 table 或 paragraph
          │
          ▼
Reviewer 校验引用完整性（validate_traceability）
          │
          ▼
输出 HTML 报告
```

---

## 10. 实现工作量估算

| 任务 | 工时 |
|------|------|
| 精简 DimensionSchema（砍字段） | 1h |
| 内置 DEFAULT_SCHEMA 常量 | 0.5h |
| 更新 TaskDAG + Competitor 模型 | 1h |
| Writer output_type prompt 注入 | 2h |
| Analyst min_sources prompt 注入 | 1h |
| 前端竞品输入框（name + domain） | 3h |
| 串联测试 + 修 bug | 3h |
| **合计** | **约 11.5h** |

---

## 11. 与 v2 的差异摘要

| v2 | v3 (MVP) |
|-----|---------|
| 6 字段 DimensionSchema | 5 字段（name, description, keywords, output_type, min_sources） |
| JSON 文件存储 + 代码 fallback | 纯代码内置 |
| Schema CRUD API | 无 Schema API |
| target_platform 枚举（6 值） | 硬编码 official_website |
| description 自然语言引导 | 砍掉 description |
| 两段式 description 规范 | 无 |
| Competitor.domain 可选 | 必填 |
| Schema Registry | 无 |

---

## 12. 下一步

MVP 跑通后，可逐步加回（按优先级）：

| 优先级 | 特性 | 说明 |
|--------|------|------|
| P1 | 用户自定义 Schema | 放开 Schema CRUD API |
| P1 | target_platform 扩展 | 加 app_store, github 等 |
| P2 | description 引导 | 加回自然语言描述 |
| P2 | preferred_sources | 加来源加权 |
| P3 | Schema 热更新 | 替代整文件替换 |