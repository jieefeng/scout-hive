# 核心可演示性补完 — 路线图设计

> 目标：让"AI 驱动的竞品分析 Agent 协作系统"在答辩场景下能完整、有据、可重放地展示。

## 为什么

课题已要求的能力（多 Agent / Schema / DAG / 反馈 / 溯源 / 可观测）在代码中**都已实现并通过单元/集成/E2E 测试**（168 个测试）。从「代码层面」看，核心闭环已经闭合。

但答辩场景的挑战不在「代码能不能跑」，而在「评委能不能信」：

- **看不到真实数据** — 现有 E2E 都用 mock LLM，评委无法判断真实场景下质量
- **看不到整体设计** — 5 个 Agent 如何协作、DAG 如何流转、反馈如何循环，只看代码心智负担大
- **看不到设计决策** — 评委问"为什么这样设计"时，需要有书面依据

补完这 3 块工件（真实跑通 / 架构图 / 架构文档），将「代码能跑」升级为「评委能信」。

## 做什么

3 块工件，按依赖顺序执行：

1. **真实 LLM 端到端跑通** — 用真实 Bailian + AnySearch，对 3 个真实竞品跑通主流程，输出真实报告
2. **架构图** — 一张 Mermaid 图覆盖系统全貌
3. **架构文档** — 一份文档讲清设计决策与权衡

### 不做什么

- ❌ Docker / CI/CD / 监控 / 限流 / 压测（生产化议题，超出"可演示性"范围）
- ❌ 答辩 Demo 脚本（用户明确不要）
- ❌ 自动重放脚本（YAGNI）
- ❌ 数据库迁移工具（SQLite 单文件 + ALTER TABLE 够用）
- ❌ 性能基准（无明确 SLA）
- ❌ 录屏材料
- ❌ 引入新抽象层（修复点直接打补丁，不为一次性代码建工具）

## 怎么做

### 工件 1：真实 LLM 端到端跑通

**核心决策**（已与用户确认）：写独立 `scripts/demo_e2e.py`，**不**与现有测试耦合。

**为什么**：
- 现有 e2e 测试（`backend/tests/test_e2e/test_parse_to_report.py`）用 mock LLM，覆盖逻辑路径即可
- 真实 LLM 跑通是「演示资产」，应该与「测试资产」分离
- 独立脚本便于答辩前快速重放

**做法**：
1. 验证环境 — `BAILIAN_API_KEY`、AnySearch 端点、quota
2. 选 3 个真实竞品（建议二选一：AI 笔记类 — Notion AI / Tana / Reflect；企业协作 — 钉钉 / 飞书 / 企微）
3. 写 `scripts/demo_e2e.py`：参数化竞品清单、可调并发、跑完输出 trace + report 路径
4. 跑 1 轮，逐条记录失败
5. 修复阻塞性 bug（已知陷阱：AnySearch 端点、`data.data.results` 路径、`content` 字段、SPA 页面、CN zone 偶发空结果）
6. 复跑 3 轮稳定

**关键设计**：
- 不引入新抽象 — 修复点直接打补丁
- 失败要可见 — 脚本输出每步状态、错误、产物路径
- 幂等可重放 — task_id 用 uuid 避免冲突，DB 可重复写

### 工件 2：架构图

**核心决策**：用 **Mermaid**，不用 Draw.io / PNG。

**为什么**：
- 文本格式，可版本控制、PR diff 友好、嵌入 Markdown
- 答辩时可直接在 GitHub / IDE 渲染
- 系统规模（~10 个核心模块）Mermaid 表达力够用
- 不增加二进制文件，repo 干净

**包含**（一张总览图）：
- 5 个 Agent（TaskParser / Collector / Analyst / Writer / Reviewer）
- 调度层（Orchestrator + StateManager + EventBus）
- LLM 适配层（LLMRegistry + 4 个 adapter）
- 外部依赖（AnySearch / LLM API / SQLite / 前端）
- 关键数据流（自然语言 → DAG 蓝图 → 拓扑执行 → 报告 + trace）

**嵌入位置**：`docs/architecture.md`（主）+ `README.md`（简版）

### 工件 3：架构文档

**核心决策**：单文件 `docs/architecture.md`，**不**扩展现有 `2026-05-21` design doc。

**为什么**：
- 现有 design doc 是「实现思路」类，混入架构论述会破坏历史
- 架构文档是「讲给评委」，与「写给开发者」的目标不同
- 单文件 300-500 行可控

**结构**（按 CLAUDE.md 规范：为什么 → 做什么 → 怎么做 → 成功标准）：
1. 系统定位与课题目标
2. 整体架构（含 Mermaid 图）
3. 5 个 Agent 职责与契约
4. DAG 调度与反馈闭环
5. 数据模型（Schema / Claim / Trace）
6. 关键设计决策（含 trade-off）
7. 已知限制与不做事项

## 怎么算成功

| 工件 | 成功标准 |
|------|---------|
| 真实跑通 | `scripts/demo_e2e.py` 对 3 个真实竞品连续 3 轮跑通，3 份报告无字段缺失，trace 可回放 |
| 架构图 | 1 张 Mermaid 图，能在 GitHub 渲染，30 秒让评委看懂系统全貌 |
| 架构文档 | `docs/architecture.md` 存在、结构完整，评委问"为什么 X 这样设计"时有书面依据 |
| 总评 | 4 小时内完成 3 块工件，5 分钟讲解能让评委听懂系统全貌 |

## 依赖与时序

```
Section 1 真实跑通 ──产出──> 3 份真实报告 + trace
                              │
                              ↓
Section 2 架构图 ──┐
Section 3 架构文档 ┴─引用──> 完成
```

- **Section 1 必须先做**（没有真实数据，文档没东西可引用）
- **Section 2 + 3 可并行**（独立工件）
- **Section 3 引用 Section 1 的产物 + Section 2 的图**
