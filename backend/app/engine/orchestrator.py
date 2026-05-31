import uuid
import time

from app.engine.state_manager import StateManager
from app.engine.event_bus import EventBus, Event
from app.engine.dag_parser import DAGParser
from app.agents.base import AgentBase, AgentResult
from app.models.dag import DAGBlueprint, DAGNode, FeedbackEdge
from app.models.task import TaskStatus, NodeStatus


def _build_dim_config(schema) -> dict:
    """Build dimension config map from schema definition.

    Returns:
        dim_name -> {"output_type", "evidence_threshold", "description", "keywords", "tracking_sources"}
    """
    dim_config = {}
    for group in schema.groups:
        for dim in group.dimensions:
            dim_config[dim.name] = {
                "output_type": dim.output_type,
                "evidence_threshold": dim.evidence_threshold,
                "description": dim.description,
                "keywords": dim.keywords,
                "tracking_sources": dim.tracking_sources,
            }
    return dim_config


class Orchestrator:
    def __init__(self, state_manager: StateManager, event_bus: EventBus, agents: dict[str, AgentBase]):
        self.sm = state_manager
        self.bus = event_bus
        self.agents = agents

    async def execute_node(self, task_id: str, node: DAGNode) -> AgentResult:
        agent = self.agents.get(node.agent)
        if not agent:
            return AgentResult(success=False, error_message=f"Agent {node.agent} not found")

        self.sm.update_node_status(task_id, node.id, NodeStatus.RUNNING)
        await self.bus.publish(Event(type="node_started", task_id=task_id, node_id=node.id))

        result = await agent.run(node.params, node_id=node.id)

        if result.success:
            self.sm.update_node_status(task_id, node.id, NodeStatus.COMPLETED)
            self.sm.add_trace(task_id, result.trace.model_dump() if result.trace else {})
            if node.agent == "Writer" and result.output.get("report_html"):
                self.sm.set_report(task_id, result.output["report_html"])
            if node.agent == "Reviewer" and result.output:
                self.sm.add_review(task_id, result.output)
                # Set REJECTED if verdict is rejected, otherwise COMPLETED
                verdict = result.output.get("verdict", "")
                if verdict == "rejected":
                    self.sm.update_node_status(task_id, node.id, NodeStatus.REJECTED)
                else:
                    self.sm.update_node_status(task_id, node.id, NodeStatus.COMPLETED)
            await self.bus.publish(Event(type="node_completed", task_id=task_id, node_id=node.id, data=result.output))
        else:
            self.sm.update_node_status(task_id, node.id, NodeStatus.FAILED)
            if result.trace:
                self.sm.add_trace(task_id, result.trace.model_dump())
            await self.bus.publish(Event(type="node_failed", task_id=task_id, node_id=node.id, data={"error": result.error_message}))

        return result

    async def execute_dag(self, task_id: str, blueprint: DAGBlueprint) -> None:
        self.sm.update_task_status(task_id, TaskStatus.RUNNING)
        parser = DAGParser(blueprint)

        max_retries = 3
        retry_count: dict[str, int] = {}

        while True:
            # 检查取消标志
            if self.sm.is_task_cancelled(task_id):
                task = self.sm.get_task(task_id)
                for nid, status in task.node_states.items():
                    if status in (NodeStatus.RUNNING, NodeStatus.PENDING):
                        self.sm.update_node_status(task_id, nid, NodeStatus.SKIPPED)
                self.sm.update_task_status(task_id, TaskStatus.STOPPED)
                await self.bus.publish(Event(type="task_stopped", task_id=task_id))
                break

            completed = {
                nid for nid, status in self.sm.get_task(task_id).node_states.items()
                if status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
            }
            failed = {
                nid for nid, status in self.sm.get_task(task_id).node_states.items()
                if status == NodeStatus.FAILED
            }

            # Only mark nodes ready when ALL dependencies completed (not failed)
            ready = parser.get_ready_nodes(completed)

            if not ready:
                all_nodes = {n.id for n in blueprint.nodes}
                if all_nodes <= completed:
                    self.sm.update_task_status(task_id, TaskStatus.COMPLETED)
                    await self.bus.publish(Event(type="task_completed", task_id=task_id))
                elif not (all_nodes <= (completed | failed)):
                    # Some nodes can't run because deps failed — mark them skipped
                    blocked = all_nodes - completed - failed
                    for nid in blocked:
                        self.sm.update_node_status(task_id, nid, NodeStatus.SKIPPED)
                    self.sm.update_task_status(task_id, TaskStatus.FAILED)
                else:
                    self.sm.update_task_status(task_id, TaskStatus.FAILED)
                break

            # Execute all ready nodes concurrently
            async def _run_ready_node(node_id: str):
                node = parser.nodes[node_id]
                result = await self.execute_node(task_id, node)
                if not result.success:
                    retries = retry_count.get(node_id, 0)
                    if result.error_type == "json_parse" and retries < max_retries:
                        retry_count[node_id] = retries + 1
                        self.sm.update_node_status(task_id, node_id, NodeStatus.PENDING)
                    elif result.error_type == "token_limit":
                        self.sm.update_node_status(task_id, node_id, NodeStatus.SKIPPED)

            import asyncio as _asyncio
            await _asyncio.gather(*[_run_ready_node(nid) for nid in ready])

    async def execute_with_feedback(self, task_id: str, blueprint: DAGBlueprint) -> None:
        parser = DAGParser(blueprint)
        self.sm.update_task_status(task_id, TaskStatus.RUNNING)
        max_feedback_rounds = 3
        feedback_round: dict[str, int] = {}

        await self.execute_dag(task_id, blueprint)

        # 检查是否被停止（execute_dag 可能因取消而 break）
        task = self.sm.get_task(task_id)
        if task and task.status == TaskStatus.STOPPED:
            return

        for fe in blueprint.feedback_edges:
            review = self.sm.get_review(task_id, fe.from_node)
            if review and review.get("verdict") == "rejected":
                rounds = feedback_round.get(fe.from_node, 0)
                if rounds < fe.max_rounds:
                    feedback_round[fe.from_node] = rounds + 1
                    # Mark the rejected node as PENDING to re-run the feedback loop
                    self.sm.update_node_status(task_id, fe.from_node, NodeStatus.PENDING)
                    # Mark the Writer node as PENDING for rewrite
                    self.sm.update_node_status(task_id, fe.to_node, NodeStatus.PENDING)
                    # Add revision_round to trace
                    revision_trace = {
                        "node_id": fe.to_node,
                        "agent": "FeedbackLoop",
                        "revision_round": rounds + 1,
                        "feedback_message": review.get("feedback_message", ""),
                        "feedback_to": review.get("feedback_to", ""),
                    }
                    self.sm.add_trace(task_id, revision_trace)
                    await self.bus.publish(Event(
                        type="review_feedback", task_id=task_id, node_id=fe.from_node,
                        data={"round": rounds + 1, "target": fe.to_node, "feedback": review},
                    ))
                    await self.execute_dag(task_id, blueprint)
                else:
                    if fe.escalation == "auto_approve":
                        self.sm.update_node_status(task_id, fe.from_node, NodeStatus.COMPLETED)

    async def execute_mvp(
        self,
        task_id: str,
        dag: DAGBlueprint,
        competitors: list[dict],
    ) -> None:
        """MVP simplified execution path using built-in DEFAULT_SCHEMA.

        Executes DAG nodes concurrently: nodes whose dependencies are all
        completed run in parallel via asyncio.create_task.
        """
        import asyncio as _asyncio
        from app.schema.mvp_defaults import load_default_schema

        schema = load_default_schema()
        dim_config = _build_dim_config(schema)
        self.sm.update_task_status(task_id, TaskStatus.RUNNING)

        results: dict[tuple[str, str], dict] = {}
        node_tasks: dict[str, _asyncio.Task] = {}

        async def run_node(node: DAGNode):
            # Wait for all dependency tasks to complete first
            for dep_id in node.depends_on:
                dep_task = node_tasks.get(dep_id)
                if dep_task:
                    await dep_task

            # Check cancellation after deps resolve
            if self.sm.is_task_cancelled(task_id):
                return

            import time as time_module
            node_start = time_module.monotonic()
            params = node.params
            comp_name = params.get("competitor", params.get("target", ""))
            dim_name = params.get("dimension", "")
            dim_cfg = dim_config.get(dim_name, {})

            self.sm.update_node_status(task_id, node.id, NodeStatus.RUNNING)
            await self.bus.publish(Event(type="node_started", task_id=task_id, node_id=node.id))

            if node.agent == "Collector":
                collector = self.agents.get("Collector")
                if not collector:
                    self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                    return
                input_data = {
                    "target": comp_name,
                    "domain": params.get("domain", ""),
                    "dimension": dim_name,
                    "keywords": dim_cfg.get("keywords", []),
                    "evidence_threshold": dim_cfg.get("evidence_threshold", 1),
                    "tracking_sources": dim_cfg.get("tracking_sources", ["web"]),
                }
                result = await collector.execute(input_data)
                results[(comp_name, dim_name)] = {"raw_data": result.output, "sources": result.sources}

            elif node.agent == "Analyst":
                analyst = self.agents.get("Analyst")
                if not analyst:
                    self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                    return
                stored = results.get((comp_name, dim_name), {})
                raw = stored.get("raw_data", {})
                sources = stored.get("sources", [])
                input_data = {
                    "competitor": comp_name,
                    "dimension": dim_name,
                    "evidence_threshold": dim_cfg.get("evidence_threshold", 1),
                    "raw_data": raw,
                    "sources": sources,
                }
                result = await analyst.execute(input_data)
                results.setdefault((comp_name, dim_name), {})["analysis"] = result.output

            elif node.agent == "Writer":
                writer = self.agents.get("Writer")
                if not writer:
                    self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                    return
                stored = results.get((comp_name, dim_name), {})
                analysis = stored.get("analysis", {})
                collector_sources = stored.get("sources", [])
                input_data = {
                    "competitor": comp_name,
                    "dimension": dim_name,
                    "output_type": dim_cfg.get("output_type", "paragraph"),
                    "description": dim_cfg.get("description", ""),
                    "findings": analysis.get("findings", []) if isinstance(analysis, dict) else [],
                    "sources": collector_sources,
                }
                result = await writer.execute(input_data)
                results.setdefault((comp_name, dim_name), {})["report"] = result.output

            else:
                self.sm.update_node_status(task_id, node.id, NodeStatus.SKIPPED)
                await self.bus.publish(Event(type="node_failed", task_id=task_id, node_id=node.id, data={"error": f"Unknown agent: {node.agent}"}))
                return

            # Record result state and trace
            if node.agent in ("Collector", "Analyst", "Writer"):
                agent = self.agents.get(node.agent)
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

        # Launch all node tasks concurrently; dependency waiting happens inside each task
        for node in dag.nodes:
            node_tasks[node.id] = _asyncio.create_task(run_node(node))

        # Wait for all tasks to complete (or propagate first exception)
        await _asyncio.gather(*node_tasks.values())

        # Handle cancellation after all tasks finish
        if self.sm.is_task_cancelled(task_id):
            task = self.sm.get_task(task_id)
            for nid, status in task.node_states.items():
                if status in (NodeStatus.RUNNING, NodeStatus.PENDING):
                    self.sm.update_node_status(task_id, nid, NodeStatus.SKIPPED)
            self.sm.update_task_status(task_id, TaskStatus.STOPPED)
            await self.bus.publish(Event(type="task_stopped", task_id=task_id))
            return

        # Merge all report_html pieces into final report
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
        if not final_report.strip():
            self.sm.set_error_message(task_id, "所有 Writer 节点未生成报告内容")
            self.sm.update_task_status(task_id, TaskStatus.FAILED)
        else:
            self.sm.update_task_status(task_id, TaskStatus.COMPLETED)
        await self.bus.publish(Event(type="task_completed", task_id=task_id))
