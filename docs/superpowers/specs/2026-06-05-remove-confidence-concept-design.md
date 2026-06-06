# 彻底删除置信度概念

## 概述

移除分析报告系统中的"置信度"概念：删除 `Confidence` 数据模型、`Finding`/`TraceRecord`/`AgentResult` 上的 confidence 字段、Analyst/Writer/Reviewer 中的置信度计算与展示逻辑、前端 `ConfidenceHeatmap` 组件及其类型字段，以及所有相关测试。

保留 Analyst 的降级警告（⚠️ 标记 + data_insufficient 行为）——该机制独立于置信度评分。

## 背景与动机

### 为什么做

置信度评分是"虚假精度"的源头：当前实现混合了三类信号——

- 量化分数（0-1 浮点数，LLM 自由填写）
- 离散级别（high/medium/low/insufficient）
- 降级标记（⚠️）

三类信号彼此独立又被强行映射到同一字段，导致：

- **score 缺乏标定**：不同 LLM、不同 prompt 下 0.85 与 0.7 的实际意义不一致
- **level 阈值随意**：Writer 写死 `confidence={"score": 0.8, "level": "high"}`，Reviewer 用 `pass_count/total` 推导——两条计算路径互不对齐
- **UI 展示的"0.85"无可比性**：用户看到百分比会高估其客观性，但底层只是 LLM 的自由输出

系统地讲，置信度不提供超出"是否找到来源"的额外信息——而这正是 Analyst 已经在做的事（用 ⚠️ 标记）。

### 不做什么

- **不重构**降级警告机制。⚠️ 标记、data_insufficient 状态、`source_count` 统计保留。
- **不修改**历史 spec/plan 文档（保留作为变更轨迹）。
- **不迁移**SQLite 旧 trace 数据（schema 保留 `confidence` 列，新写入不再填充）。
- **不删除**数据库 schema 中的 `confidence` 列（兼容历史任务读取）。

## 范围

### 数据模型层（`backend/app/models/`）

| 文件 | 改动 |
|------|------|
| `analysis.py` | 删除 `Confidence` 类（6-9 行）；`Finding.confidence` 字段移除（26 行） |
| `trace.py` | `TraceRecord.confidence: dict` 字段移除（28 行） |

### Agent 业务逻辑层（`backend/app/agents/`）

| 文件 | 改动 |
|------|------|
| `base.py` | `AgentResult.confidence: dict` 字段移除（22 行）；`_build_trace` 签名移除 `confidence` 形参，调用方同步清理 |
| `analyst.py` | ① 删除 import 的 `Confidence`；② SYSTEM_PROMPT 移除"confidence"字段定义、移除 min_sources→confidence.level 映射，**保留** ⚠️ 标记与 data_insufficient 行为；③ 移除 `confidence_level` 推导，`_downgrade_hint` 重写为不依赖 confidence_level 的证据强度提示；④ 删除 `best_confidence` 取值；⑤ `AgentResult(...)` 不再传 `confidence=...` |
| `writer.py` | ① SYSTEM_PROMPT_TABLE/PARAGRAPH 移除"置信度用进度条展示"；② `AgentResult(...)` 移除 `confidence=...` 字段 |
| `reviewer.py` | ① SYSTEM_PROMPT 移除"置信度校准"维度；② 不再计算 `confidence`；③ reasoning_chain 注释中的"置信度"措辞清理 |

### Orchestrator（`backend/app/engine/orchestrator.py`）

- 仅在传 confidence 给下游节点时清理相关键（grep 后确认）
- `reasoning_chain` 和 `sources` 透传逻辑保留

### 前端展示层（`frontend/src/`）

| 文件 | 改动 |
|------|------|
| `components/ConfidenceHeatmap.tsx` | 整文件删除 |
| `types/index.ts` | `TraceRecord.confidence` 字段移除 |

## 数据流与边界

### Analyst 节点流（删除后）

```
Collector 产出 → Orchestrator 透传 sources/raw_data/evidence_threshold
    ↓
Analyst.execute()
  ├─ _count_sources() → source_count         (保留)
  ├─ source_count < evidence_threshold?       (保留判定)
  │    ├─ 是 → downgrade_hint = "⚠️ ..."     (保留，但不映射到 confidence_level)
  │    └─ 否 → 无 hint
  ├─ 注入 _downgrade_hint 到 user message    (保留)
  ├─ LLM 输出 JSON
  │    └─ finding.quote + source_ref 缺失 → 丢弃   (保留)
  └─ findings[] 不含 confidence 字段
    ↓
AgentResult(output=AnalysisResult, reasoning_chain, sources)
```

### Reviewer 节点流（删除后）

```
检查维度（仅 2 项）：
  1. JSON 格式：report_html 完整
  2. 溯源完整性：每条 finding 有 quote + source_ref
不计算 pass_count/total 映射分数。
AgentResult(output=ReviewResult, reasoning_chain)
```

### Writer 节点流（删除后）

```
SYSTEM_PROMPT 改动：
  - 旧："3. 置信度用进度条展示"
  - 新：删除该行
  - 其余规则保持（溯源浮窗、Markdown 表格、维度名规则等）
AgentResult(output={report_html, summary}, sources)
```

### 错误处理

LLM 偶尔仍会输出 confidence 字段（行为惯性）：`Finding(**f)` 不再接受该字段 → Pydantic 抛 ValidationError。

**决策**：在 `Finding` 模型上加 `model_config = ConfigDict(extra='ignore')`，使 Pydantic 默认忽略多余字段，避免 LLM 偶发输出 confidence 触发崩溃。该配置放在 `backend/app/models/analysis.py:1-3`（import 区域下方）。

### 数据持久化边界

- StateManager / SQLite schema 不变（trace 表 schema 包含 confidence 列，新写入不再填充）
- 旧任务的 trace 记录保持原样，UI 已不读取 `confidence` 字段，**无破坏性影响**
- 不做数据迁移脚本

### API 边界

- 响应模型 `TraceRecord` 移除 confidence 字段 → 前端类型同步 → 无 TypeScript 编译错误
- `TaskSummary.confidence`（前端已有）来源是 `TraceRecord.confidence`，自动失效，无需额外清理

## 测试策略

### 需要删除的测试（专用）

| 测试 | 文件 |
|------|------|
| `test_reviewer_checks_confidence_calibration` | `tests/test_agents/test_reviewer.py:55` |
| `test_writer_includes_confidence_bar` | `tests/test_agents/test_writer.py:41` |

### 需要更新的测试（断言清理）

| 测试 | 文件 | 改动 |
|------|------|------|
| `test_finding_with_quote` | `tests/test_models/test_analysis.py:5` | 移除 `confidence=Confidence(...)` 实参；移除 `finding.confidence.score` 断言 |
| `test_analysis_result_creation` | `tests/test_models/test_analysis.py:17` | 移除 `Confidence` 导入与实例化 |
| `test_reviewer_returns_*_verdict` | `tests/test_agents/test_reviewer.py` | 不再断言 `result.confidence` 字段 |
| `test_analyst_*` 系列 | `tests/test_agents/test_analyst.py` | 移除 mock LLM 返回中 `confidence` 字段；移除 `result.confidence` 断言 |
| `test_trace_*` / `test_dag_*` | `tests/test_models/` | 移除 `TraceRecord(confidence=...)` 实参 |
| `test_integration_*` | `tests/test_engine/`, `tests/test_integration/` | 移除端到端流中对 `confidence` 字段的检查 |

### 需要新增的测试

| 新测试 | 目的 |
|------|------|
| `test_finding_ignores_extra_confidence_field` | 验证 Pydantic `extra='ignore'` 生效 |
| `test_analyst_downgrade_hint_without_confidence` | 验证 `downgrade_hint` 仍提示 ⚠️ 但不再含 `confidence.level=low` 措辞 |
| `test_reviewer_no_confidence_dimension` | 验证 Reviewer 输出 checks 不含"置信度校准"维度 |
| `test_trace_record_no_confidence_field` | 验证 `TraceRecord` 实例化无 `confidence` 字段 |

### 覆盖目标

- 后端整体覆盖率保持 ≥ 80%（与项目既有标准一致；置信度相关代码删除后，被覆盖的代码行也消失，因此覆盖率分子分母同向减少，绝对值不应下降）
- 新增 4 个测试覆盖边界行为
- 端到端：`test_mvp_flow.py` 跑通完整 MVP 流程，断言报告 HTML 不含进度条/百分比/level 标签

### 验证命令

```bash
cd backend && python -m pytest -v
cd backend && python -m pytest tests/test_agents/ tests/test_models/ tests/test_engine/ tests/test_integration/
grep -rn "Confidence\|confidence" backend/app/ frontend/src/types/   # 应无业务相关命中
```

## 原子提交顺序（1 PR 内）

1. `chore(models): remove Confidence class and confidence fields`
2. `refactor(agents): remove confidence computation from Analyst/Writer/Reviewer`
3. `refactor(agents): clean AgentResult and _build_trace confidence plumbing`
4. `feat(frontend): remove ConfidenceHeatmap component and TraceRecord.confidence type`
5. `test: update or remove confidence-dependent tests`
6. `docs(spec): add this design doc`

## 风险与回滚

- 数据库 schema 不变（`confidence` 列保留以兼容历史 trace），无需迁移
- 唯一不可逆操作是删除 `Confidence` 类和 `ConfidenceHeatmap.tsx` 文件 —— 但 git 历史可恢复
- 单 PR 内 5-7 次原子提交，任意提交点可独立 `git revert`

## 历史文档处理

**不动文件**：
- `docs/superpowers/specs/2026-06-05-remove-confidence-ui-design.md`（UI 移除专项，保留作为历史记录）
- 所有 `docs/superpowers/plans/*.md`
- `backend/tests/` 下的过时测试（仅按本设计更新依赖项，不重写历史）

**新建文件**：
- `docs/superpowers/specs/2026-06-05-remove-confidence-concept-design.md`（本文档）
- `docs/superpowers/plans/2026-06-05-remove-confidence-concept.md`（由 writing-plans 产出）

## 成功标准

1. 全代码库 grep 不到 `Confidence`（类）、`confidence` 字段写入
2. pytest 全部通过，不存在 confidence 相关断言
3. 前端 `npm run build` 通过，无 ConfidenceHeatmap 引用
4. 一次跑通 MVP 流程：报告 HTML 中不出现进度条/百分比/level 标签，claim 仍按 Analyst 降级规则带 ⚠️ 标记
5. 历史规范/计划文件未修改
6. 后端覆盖率 ≥ 80%

## 完成定义（DoD）

- [ ] 5-7 个原子提交已落库
- [ ] `pytest` 全部通过，覆盖率 ≥ 80%
- [ ] `npm run build` 通过
- [ ] `grep -rn "Confidence" backend/app/` 仅命中 `test_models/test_analysis.py`（已更新）中的注释或 import 残留
- [ ] 跑通一次端到端 MVP 流程，生成报告 HTML 不含置信度元素
- [ ] 本 spec 文件已 commit
- [ ] writing-plans 产出的实现计划已 commit
