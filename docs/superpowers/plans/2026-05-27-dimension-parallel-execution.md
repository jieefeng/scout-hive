# 维度级并发执行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 execute_mvp 从顺序执行改为维度级并发（Semaphore + asyncio.gather），提速约 4.5 倍

**Architecture:** 按 (竞品, 维度) 分组，每组内 C→A→W 顺序执行为一个协程，所有协程用 asyncio.gather 并发，Semaphore(5) 控制并发上限。失败隔离：单维度失败不影响其他维度。

**Tech Stack:** Python asyncio, asyncio.Semaphore, asyncio.gather

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/engine/orchestrator.py` | Modify | 新增 `_group_nodes_by_dimension`、`_run_dimension`，重构 `execute_mvp` |
| `backend/app/api/tasks.py` | Modify | 删除 `prev_end` 逻辑，解除跨维度边 |
| `backend/tests/test_engine/test_orchestrator_mvp.py` | Modify | 新增并发相关测试 |

---

### Task 1: 新增 `_group_nodes_by_dimension` 纯函数

**Files:**
- Modify: `backend/app/engine/orchestrator.py:12` (在 `_build_dim_config` 之后)
- Test: `backend/tests/test_engine/test_orchestrator_mvp.py`

- [ ] **Step 1: 写失败测试**

在 `test_orchestrator_mvp.py` 末尾追加：

```python
from app.engine.orchestrator import _group_nodes_by_dimension


def test_group_nodes_by_dimension_single():
    """单竞品单维度：3 个节点分为 1 组，顺序为 C→A→W。"""
    nodes = [
        DAGNode(id="w_001", agent="Writer", action="write", params={"competitor": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="c_001", agent="Collector", action="collect", params={"target": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="a_001", agent="Analyst", action="analyze", params={"competitor": "竞品A", "dimension": "功能对比"}),
    ]
    groups = _group_nodes_by_dimension(nodes)
    assert len(groups) == 1
    key = ("竞品A", "功能对比")
    assert key in groups
    assert [n.agent for n in groups[key]] == ["Collector", "Analyst", "Writer"]


def test_group_nodes_by_dimension_multi():
    """多竞品多维度：正确分组。"""
    nodes = [
        DAGNode(id="c_A_f", agent="Collector", action="collect", params={"target": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="a_A_f", agent="Analyst", action="analyze", params={"competitor": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="w_A_f", agent="Writer", action="write", params={"competitor": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="c_B_p", agent="Collector", action="collect", params={"target": "竞品B", "dimension": "定价策略"}),
        DAGNode(id="a_B_p", agent="Analyst", action="analyze", params={"competitor": "竞品B", "dimension": "定价策略"}),
        DAGNode(id="w_B_p", agent="Writer", action="write", params={"competitor": "竞品B", "dimension": "定价策略"}),
    ]
    groups = _group_nodes_by_dimension(nodes)
    assert len(groups) == 2
    assert ("竞品A", "功能对比") in groups
    assert ("竞品B", "定价策略") in groups
    assert len(groups[("竞品A", "功能对比")]) == 3
    assert len(groups[("竞品B", "定价策略")]) == 3


def test_group_nodes_by_dimension_missing_params():
    """缺少 competitor/dimension 的节点被跳过。"""
    nodes = [
        DAGNode(id="bad", agent="Collector", action="collect", params={}),
        DAGNode(id="c_001", agent="Collector", action="collect", params={"target": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="a_001", agent="Analyst", action="analyze", params={"competitor": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="w_001", agent="Writer", action="write", params={"competitor": "竞品A", "dimension": "功能对比"}),
    ]
    groups = _group_nodes_by_dimension(nodes)
    assert len(groups) == 1
    assert ("竞品A", "功能对比") in groups
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py::test_group_nodes_by_dimension_single tests/test_engine/test_orchestrator_mvp.py::test_group_nodes_by_dimension_multi tests/test_engine/test_orchestrator_mvp.py::test_group_nodes_by_dimension_missing_params -v`
Expected: FAIL — `ImportError: cannot import name '_group_nodes_by_dimension'`

- [ ] **Step 3: 实现 `_group_nodes_by_dimension`**

在 `orchestrator.py` 的 `_build_dim_config` 函数之后（第 28 行后）插入：

```python
def _group_nodes_by_dimension(nodes: list[DAGNode]) -> dict[tuple[str, str], list[DAGNode]]:
    """按 (competitor, dimension) 分组，组内按 agent 类型排序为 C→A→W。"""
    import logging
    logger = logging.getLogger(__name__)
    groups: dict[tuple[str, str], list[DAGNode]] = {}
    agent_order = {"Collector": 0, "Analyst": 1, "Writer": 2}
    for node in nodes:
        comp = node.params.get("competitor") or node.params.get("target", "")
        dim = node.params.get("dimension", "")
        if not comp or not dim:
            logger.warning(f"Node {node.id} missing competitor/dimension, skipping")
            continue
        key = (comp, dim)
        groups.setdefault(key, []).append(node)
    for key in groups:
        groups[key].sort(key=lambda n: agent_order.get(n.agent, 99))
        if len(groups[key]) != 3:
            logger.warning(f"Dimension {key} has {len(groups[key])} nodes, expected 3")
    return groups
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py::test_group_nodes_by_dimension_single tests/test_engine/test_orchestrator_mvp.py::test_group_nodes_by_dimension_multi tests/test_engine/test_orchestrator_mvp.py::test_group_nodes_by_dimension_missing_params -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/engine/orchestrator.py backend/tests/test_engine/test_orchestrator_mvp.py
git commit -m "feat: 新增 _group_nodes_by_dimension 分组函数及测试"
```

---

### Task 2: 新增 `_run_dimension` 协程

**Files:**
- Modify: `backend/app/engine/orchestrator.py` (在 `_group_nodes_by_dimension` 之后)
- Test: `backend/tests/test_engine/test_orchestrator_mvp.py`

- [ ] **Step 1: 写失败测试**

在 `test_orchestrator_mvp.py` 末尾追加：

```python
import asyncio


@pytest.mark.asyncio
async def test_run_dimension_sequential_execution():
    """单维度内 C→A→W 顺序执行，Collector 先于 Analyst 完成。"""
    sm = StateManager()
    bus = EventBus()
    execution_order = []

    mock_collector = MagicMock()
    async def collector_execute(input_data):
        execution_order.append("Collector")
        return AgentResult(success=True, output={"raw_data": {}}, sources=[])
    mock_collector.execute = collector_execute
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    async def analyst_execute(input_data):
        execution_order.append("Analyst")
        return AgentResult(success=True, output={"findings": []})
    mock_analyst.execute = analyst_execute
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    async def writer_execute(input_data):
        execution_order.append("Writer")
        return AgentResult(success=True, output={"report_html": "<p>test</p>"})
    mock_writer.execute = writer_execute
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_run_dim_001"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="test")], ["功能对比"], {})

    nodes = [
        DAGNode(id="c_001", agent="Collector", action="collect", params={"target": "竞品A", "dimension": "功能对比", "domain": "test"}),
        DAGNode(id="a_001", agent="Analyst", action="analyze", params={"competitor": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="w_001", agent="Writer", action="write", params={"competitor": "竞品A", "dimension": "功能对比"}),
    ]
    dim_cfg = {"keywords": ["功能"], "evidence_threshold": 1, "output_type": "paragraph", "description": "", "tracking_sources": ["web"]}
    sem = asyncio.Semaphore(5)

    comp, dim, data = await orch._run_dimension(task_id, "竞品A", "功能对比", nodes, dim_cfg, sem)

    assert comp == "竞品A"
    assert dim == "功能对比"
    assert execution_order == ["Collector", "Analyst", "Writer"]
    assert "raw_data" in data
    assert "analysis" in data
    assert "report" in data


@pytest.mark.asyncio
async def test_run_dimension_failure_isolation():
    """Collector 失败时，Analyst 和 Writer 不执行，但协程不抛异常。"""
    sm = StateManager()
    bus = EventBus()

    mock_collector = MagicMock()
    mock_collector.execute = AsyncMock(return_value=AgentResult(success=False, error_message="网络超时"))
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    mock_analyst.execute = AsyncMock(return_value=AgentResult(success=True, output={}))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    mock_writer.execute = AsyncMock(return_value=AgentResult(success=True, output={}))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {"Collector": mock_collector, "Analyst": mock_analyst, "Writer": mock_writer}

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_run_dim_002"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="test")], ["功能对比"], {})

    nodes = [
        DAGNode(id="c_001", agent="Collector", action="collect", params={"target": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="a_001", agent="Analyst", action="analyze", params={"competitor": "竞品A", "dimension": "功能对比"}),
        DAGNode(id="w_001", agent="Writer", action="write", params={"competitor": "竞品A", "dimension": "功能对比"}),
    ]
    dim_cfg = {"keywords": [], "evidence_threshold": 1, "output_type": "paragraph", "description": "", "tracking_sources": ["web"]}
    sem = asyncio.Semaphore(5)

    comp, dim, data = await orch._run_dimension(task_id, "竞品A", "功能对比", nodes, dim_cfg, sem)

    # Analyst 和 Writer 不应被调用
    mock_analyst.execute.assert_not_called()
    mock_writer.execute.assert_not_called()
    # 失败节点状态应为 FAILED
    assert sm.get_task(task_id).node_states["c_001"] == NodeStatus.FAILED


@pytest.mark.asyncio
async def test_run_dimension_cancelled():
    """任务取消后，协程返回 skipped。"""
    sm = StateManager()
    bus = EventBus()

    mock_agents = {name: MagicMock() for name in ["Collector", "Analyst", "Writer"]}
    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_run_dim_003"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="test")], ["功能对比"], {})
    sm.cancel_task(task_id)

    nodes = [DAGNode(id="c_001", agent="Collector", action="collect", params={"target": "竞品A", "dimension": "功能对比"})]
    sem = asyncio.Semaphore(5)

    comp, dim, data = await orch._run_dimension(task_id, "竞品A", "功能对比", nodes, {}, sem)
    assert data.get("skipped") is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py::test_run_dimension_sequential_execution tests/test_engine/test_orchestrator_mvp.py::test_run_dimension_failure_isolation tests/test_engine/test_orchestrator_mvp.py::test_run_dimension_cancelled -v`
Expected: FAIL — `AttributeError: 'Orchestrator' object has no attribute '_run_dimension'`

- [ ] **Step 3: 实现 `_run_dimension`**

在 `orchestrator.py` 的 `Orchestrator` 类中，在 `execute_mvp` 方法之前插入：

```python
    async def _run_dimension(
        self,
        task_id: str,
        comp_name: str,
        dim_name: str,
        dim_nodes: list[DAGNode],
        dim_cfg: dict,
        semaphore: asyncio.Semaphore,
    ) -> tuple[str, str, dict]:
        """单个 (竞品, 维度) 的执行协程。内部顺序执行，外部并发。"""
        import time as time_module

        async with semaphore:
            # 必须在获取信号量后检查，避免已取消任务占用并发槽位
            if self.sm.is_task_cancelled(task_id):
                return (comp_name, dim_name, {"skipped": True})

            result_data: dict = {}
            for node in dim_nodes:
                node_start = time_module.monotonic()
                params = node.params
                dim_cfg_local = dim_cfg

                self.sm.update_node_status(task_id, node.id, NodeStatus.RUNNING)
                await self.bus.publish(Event(type="node_started", task_id=task_id, node_id=node.id))

                try:
                    if node.agent == "Collector":
                        agent = self.agents.get("Collector")
                        if not agent:
                            self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                            continue
                        input_data = {
                            "target": comp_name,
                            "domain": params.get("domain", ""),
                            "dimension": dim_name,
                            "keywords": dim_cfg_local.get("keywords", []),
                            "evidence_threshold": dim_cfg_local.get("evidence_threshold", 1),
                            "tracking_sources": dim_cfg_local.get("tracking_sources", ["web"]),
                        }
                        result = await agent.execute(input_data)
                        result_data["raw_data"] = result.output
                        result_data["sources"] = result.sources

                    elif node.agent == "Analyst":
                        agent = self.agents.get("Analyst")
                        if not agent:
                            self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                            continue
                        input_data = {
                            "competitor": comp_name,
                            "dimension": dim_name,
                            "evidence_threshold": dim_cfg_local.get("evidence_threshold", 1),
                            "raw_data": result_data.get("raw_data", {}),
                            "sources": result_data.get("sources", []),
                        }
                        result = await agent.execute(input_data)
                        result_data["analysis"] = result.output

                    elif node.agent == "Writer":
                        agent = self.agents.get("Writer")
                        if not agent:
                            self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                            continue
                        analysis = result_data.get("analysis", {})
                        input_data = {
                            "competitor": comp_name,
                            "dimension": dim_name,
                            "output_type": dim_cfg_local.get("output_type", "paragraph"),
                            "description": dim_cfg_local.get("description", ""),
                            "findings": analysis.get("findings", []) if isinstance(analysis, dict) else [],
                        }
                        result = await agent.execute(input_data)
                        result_data["report"] = result.output

                    else:
                        self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                        await self.bus.publish(Event(type="node_failed", task_id=task_id, node_id=node.id, data={"error": f"Unknown agent: {node.agent}"}))
                        continue

                    # Record trace and state
                    elapsed_ms = int((time_module.monotonic() - node_start) * 1000)
                    trace_record = agent._build_trace(
                        node.id, input_data, result.output, elapsed_ms,
                        llm_response=result.llm_response,
                        reasoning_chain=result.reasoning_chain,
                        sources=result.sources,
                        confidence=result.confidence,
                        error=str(result.error_message) if not result.success else None,
                    )
                    if result.success:
                        self.sm.update_node_status(task_id, node.id, NodeStatus.COMPLETED)
                        self.sm.add_trace(task_id, trace_record.model_dump())
                        if node.agent == "Writer" and result.output.get("report_html"):
                            self.sm.set_report(task_id, result.output["report_html"])
                        await self.bus.publish(Event(type="node_completed", task_id=task_id, node_id=node.id, data=result.output))
                    else:
                        self.sm.update_node_status(task_id, node.id, NodeStatus.FAILED)
                        self.sm.add_trace(task_id, trace_record.model_dump())
                        await self.bus.publish(Event(type="node_failed", task_id=task_id, node_id=node.id, data={"error": result.error_message}))
                        break  # 失败后跳过该维度后续节点

                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"[{comp_name}/{dim_name}] Node {node.id} exception: {e}", exc_info=e)
                    self.sm.update_node_status(task_id, node.id, NodeStatus.FAILED)
                    await self.bus.publish(Event(type="node_failed", task_id=task_id, node_id=node.id, data={"error": str(e)}))
                    break

            return (comp_name, dim_name, result_data)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py::test_run_dimension_sequential_execution tests/test_engine/test_orchestrator_mvp.py::test_run_dimension_failure_isolation tests/test_engine/test_orchestrator_mvp.py::test_run_dimension_cancelled -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/engine/orchestrator.py backend/tests/test_engine/test_orchestrator_mvp.py
git commit -m "feat: 新增 _run_dimension 单维度执行协程及测试"
```

---

### Task 3: 重构 `execute_mvp` 使用 gather + Semaphore

**Files:**
- Modify: `backend/app/engine/orchestrator.py:168-308`
- Test: `backend/tests/test_engine/test_orchestrator_mvp.py`

- [ ] **Step 1: 写失败测试**

在 `test_orchestrator_mvp.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_execute_mvp_concurrent_dimensions():
    """多个维度并发执行，验证 gather 行为。"""
    sm = StateManager()
    bus = EventBus()

    import time as time_module
    start_times = {}

    mock_collector = MagicMock()
    async def collector_execute(input_data):
        dim = input_data["dimension"]
        start_times[dim] = time_module.monotonic()
        await asyncio.sleep(0.05)  # 模拟 I/O
        return AgentResult(success=True, output={"raw_data": {}}, sources=[])
    mock_collector.execute = collector_execute
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    mock_analyst.execute = AsyncMock(return_value=AgentResult(success=True, output={"findings": []}))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    mock_writer.execute = AsyncMock(return_value=AgentResult(success=True, output={"report_html": "<p>ok</p>"}))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {"Collector": mock_collector, "Analyst": mock_analyst, "Writer": mock_writer}
    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_concurrent_001"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="test")], ["功能对比", "用户体验", "定价策略"], {})

    # 构建 3 个维度的 DAG（无跨维度边）
    nodes = []
    edges = []
    for dim in ["功能对比", "用户体验", "定价策略"]:
        c_id = f"c_{dim}"
        a_id = f"a_{dim}"
        w_id = f"w_{dim}"
        nodes.extend([
            DAGNode(id=c_id, agent="Collector", action="collect", params={"target": "竞品A", "dimension": dim, "domain": "test"}),
            DAGNode(id=a_id, agent="Analyst", action="analyze", params={"competitor": "竞品A", "dimension": dim}),
            DAGNode(id=w_id, agent="Writer", action="write", params={"competitor": "竞品A", "dimension": dim}),
        ])
        edges.extend([
            DAGEdge(from_node=c_id, to_node=a_id),
            DAGEdge(from_node=a_id, to_node=w_id),
        ])

    blueprint = DAGBlueprint(nodes=nodes, edges=edges)
    total_start = time_module.monotonic()
    await orch.execute_mvp(task_id, blueprint, [{"name": "竞品A", "domain": "test"}])
    total_elapsed = time_module.monotonic() - total_start

    assert sm.get_task(task_id).status == TaskStatus.COMPLETED
    # 3 个维度并发执行，总时间应远小于 3 × 0.05 = 0.15 秒（串行）
    # 并发应接近 0.05 秒，留余量给开销
    assert total_elapsed < 0.12, f"Concurrent execution too slow: {total_elapsed:.3f}s"
    assert mock_collector.execute.call_count == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py::test_execute_mvp_concurrent_dimensions -v`
Expected: FAIL（当前 execute_mvp 是顺序执行，耗时超过 0.12s）

- [ ] **Step 3: 重构 execute_mvp**

将 `orchestrator.py` 中 `execute_mvp` 方法（第 168-308 行）替换为：

```python
    async def execute_mvp(
        self,
        task_id: str,
        dag: DAGBlueprint,
        competitors: list[dict],
    ) -> None:
        """MVP simplified execution path using built-in DEFAULT_SCHEMA.

        Executes DAG nodes concurrently per dimension:
        - Each (competitor, dimension) runs C→A→W sequentially
        - All dimensions run in parallel with Semaphore(5) limit
        - Failed dimensions don't block others
        """
        import logging
        from app.schema.mvp_defaults import load_default_schema

        logger = logging.getLogger(__name__)
        schema = load_default_schema()
        dim_config = _build_dim_config(schema)
        self.sm.update_task_status(task_id, TaskStatus.RUNNING)

        # 1. 按 (competitor, dimension) 分组
        dim_groups = _group_nodes_by_dimension(dag.nodes)

        if not dim_groups:
            self.sm.update_task_status(task_id, TaskStatus.COMPLETED)
            await self.bus.publish(Event(type="task_completed", task_id=task_id))
            return

        # 2. 构建协程列表，Semaphore(5) 控制并发上限
        sem = asyncio.Semaphore(5)
        coroutines = [
            self._run_dimension(task_id, comp, dim, nodes, dim_config.get(dim, {}), sem)
            for (comp, dim), nodes in dim_groups.items()
        ]

        # 3. 并发执行
        results_list = await asyncio.gather(*coroutines, return_exceptions=True)

        # 4. 合并结果（结构化异常处理，非静默跳过）
        results: dict[tuple[str, str], dict] = {}
        for item in results_list:
            if isinstance(item, Exception):
                logger.error(f"Dimension execution failed: {item}", exc_info=item)
                continue
            comp, dim, data = item
            if not data.get("skipped"):
                results[(comp, dim)] = data

        # 5. 检查是否被取消
        if self.sm.is_task_cancelled(task_id):
            task = self.sm.get_task(task_id)
            for nid, status in task.node_states.items():
                if status in (NodeStatus.RUNNING, NodeStatus.PENDING):
                    self.sm.update_node_status(task_id, nid, NodeStatus.SKIPPED)
            self.sm.update_task_status(task_id, TaskStatus.STOPPED)
            await self.bus.publish(Event(type="task_stopped", task_id=task_id))
            return

        # 6. 拼接报告
        report_parts = []
        for (comp, dim), data in results.items():
            report = data.get("report", {})
            if isinstance(report, dict):
                html = report.get("report_html", "")
                if html:
                    report_parts.append(html)
            elif isinstance(report, str) and report:
                report_parts.append(report)

        final_report = "\n\n".join(report_parts)
        self.sm.set_report(task_id, final_report)
        self.sm.update_task_status(task_id, TaskStatus.COMPLETED)
        await self.bus.publish(Event(type="task_completed", task_id=task_id))
```

- [ ] **Step 4: 运行新测试确认通过**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py::test_execute_mvp_concurrent_dimensions -v`
Expected: PASS

- [ ] **Step 5: 运行全部已有测试确认无回归**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py -v`
Expected: 所有测试通过（包括 test_execute_mvp_loads_default_schema、test_execute_mvp_multi_competitor、test_execute_mvp_empty_dag）

- [ ] **Step 6: 运行集成测试确认无回归**

Run: `cd backend && python -m pytest tests/test_integration/test_mvp_flow.py -v`
Expected: 所有测试通过

- [ ] **Step 7: 提交**

```bash
git add backend/app/engine/orchestrator.py backend/tests/test_engine/test_orchestrator_mvp.py
git commit -m "feat: 重构 execute_mvp 为维度级并发执行（Semaphore + gather）"
```

---

### Task 4: 删除 DAG 构建中的 prev_end 逻辑

**Files:**
- Modify: `backend/app/api/tasks.py:68-81`

- [ ] **Step 1: 删除 prev_end 逻辑**

在 `tasks.py` 的 `create_task` 函数中，将第 68-81 行：

```python
    prev_end = None
    for comp in competitors:
        for dim in dimensions:
            c_id = f"c_{comp.name}_{dim}"
            a_id = f"a_{comp.name}_{dim}"
            w_id = f"w_{comp.name}_{dim}"
            nodes.append({"id": c_id, "agent": "Collector", "action": "collect", "params": {"target": comp.name, "domain": comp.website, "dimension": dim}})
            nodes.append({"id": a_id, "agent": "Analyst", "action": "analyze", "params": {"competitor": comp.name, "dimension": dim}})
            nodes.append({"id": w_id, "agent": "Writer", "action": "write", "params": {"competitor": comp.name, "dimension": dim}})
            edges.append({"from_node": c_id, "to_node": a_id})
            edges.append({"from_node": a_id, "to_node": w_id})
            if prev_end:
                edges.append({"from_node": prev_end, "to_node": c_id})
            prev_end = w_id
```

替换为：

```python
    for comp in competitors:
        for dim in dimensions:
            c_id = f"c_{comp.name}_{dim}"
            a_id = f"a_{comp.name}_{dim}"
            w_id = f"w_{comp.name}_{dim}"
            nodes.append({"id": c_id, "agent": "Collector", "action": "collect", "params": {"target": comp.name, "domain": comp.website, "dimension": dim}})
            nodes.append({"id": a_id, "agent": "Analyst", "action": "analyze", "params": {"competitor": comp.name, "dimension": dim}})
            nodes.append({"id": w_id, "agent": "Writer", "action": "write", "params": {"competitor": comp.name, "dimension": dim}})
            edges.append({"from_node": c_id, "to_node": a_id})
            edges.append({"from_node": a_id, "to_node": w_id})
```

- [ ] **Step 2: 运行全部后端测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/tasks.py
git commit -m "refactor: 删除 DAG 构建中的 prev_end 跨维度边，各维度独立执行"
```

---

### Task 5: 全量验证

- [ ] **Step 1: 运行全部后端测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 所有测试通过，无 WARNING

- [ ] **Step 2: 手动启动后端验证**

Run: `cd backend && uvicorn app.main:app --reload --port 5010`
Expected: 服务正常启动，无报错

- [ ] **Step 3: 最终提交（如有遗漏）**

```bash
git status
# 确认无遗漏文件
```
