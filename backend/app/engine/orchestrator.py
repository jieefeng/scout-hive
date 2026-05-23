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
            await self.bus.publish(Event(type="node_completed", task_id=task_id, node_id=node.id, data=result.output))
        else:
            self.sm.update_node_status(task_id, node.id, NodeStatus.FAILED)
            await self.bus.publish(Event(type="node_failed", task_id=task_id, node_id=node.id, data={"error": result.error_message}))

        return result

    async def execute_dag(self, task_id: str, blueprint: DAGBlueprint) -> None:
        self.sm.update_task_status(task_id, TaskStatus.RUNNING)
        parser = DAGParser(blueprint)

        max_retries = 3
        retry_count: dict[str, int] = {}

        while True:
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

            for node_id in ready:
                node = parser.nodes[node_id]
                result = await self.execute_node(task_id, node)

                if not result.success:
                    retries = retry_count.get(node_id, 0)
                    if result.error_type == "json_parse" and retries < max_retries:
                        retry_count[node_id] = retries + 1
                        self.sm.update_node_status(task_id, node_id, NodeStatus.PENDING)
                        continue
                    elif result.error_type == "token_limit":
                        self.sm.update_node_status(task_id, node_id, NodeStatus.SKIPPED)

    async def execute_with_feedback(self, task_id: str, blueprint: DAGBlueprint) -> None:
        parser = DAGParser(blueprint)
        self.sm.update_task_status(task_id, TaskStatus.RUNNING)
        max_feedback_rounds = 3
        feedback_round: dict[str, int] = {}

        await self.execute_dag(task_id, blueprint)

        for fe in blueprint.feedback_edges:
            from_status = self.sm.get_task(task_id).node_states.get(fe.from_node)
            if from_status == NodeStatus.FAILED:
                rounds = feedback_round.get(fe.from_node, 0)
                if rounds < fe.max_rounds:
                    feedback_round[fe.from_node] = rounds + 1
                    self.sm.update_node_status(task_id, fe.to_node, NodeStatus.PENDING)
                    self.sm.update_node_status(task_id, fe.from_node, NodeStatus.PENDING)
                    await self.bus.publish(Event(
                        type="review_feedback", task_id=task_id, node_id=fe.from_node,
                        data={"round": rounds + 1, "target": fe.to_node},
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

        Executes DAG nodes with dimension config injected per agent:
        - Collector: injects domain, keywords
        - Analyst: injects min_sources
        - Writer: injects output_type, description

        Results are merged into report_html upon completion.
        """
        from app.schema.mvp_defaults import load_default_schema

        schema = load_default_schema()
        dim_config = _build_dim_config(schema)

        results: dict[tuple[str, str], dict] = {}  # (competitor, dimension) -> data

        for node in dag.nodes:
            params = node.params
            comp_name = params.get("competitor", params.get("target", ""))
            dim_name = params.get("dimension", "")
            dim_cfg = dim_config.get(dim_name, {})

            if node.agent == "Collector":
                collector = self.agents.get("Collector")
                if not collector:
                    continue
                result = await collector.execute({
                    "target": comp_name,
                    "domain": params.get("domain", ""),
                    "dimension": dim_name,
                    "keywords": dim_cfg.get("keywords", []),
                    "evidence_threshold": dim_cfg.get("evidence_threshold", 1),
                    "tracking_sources": dim_cfg.get("tracking_sources", ["web"]),
                })
                results[(comp_name, dim_name)] = {"raw_data": result.output}

            elif node.agent == "Analyst":
                analyst = self.agents.get("Analyst")
                if not analyst:
                    continue
                raw = results.get((comp_name, dim_name), {}).get("raw_data", {})
                result = await analyst.execute({
                    "competitor": comp_name,
                    "dimension": dim_name,
                    "evidence_threshold": dim_cfg.get("evidence_threshold", 1),
                    "raw_data": raw,
                })
                results[(comp_name, dim_name)] = results.get((comp_name, dim_name), {})
                results[(comp_name, dim_name)]["analysis"] = result.output

            elif node.agent == "Writer":
                writer = self.agents.get("Writer")
                if not writer:
                    continue
                analysis = results.get((comp_name, dim_name), {}).get("analysis", {})
                result = await writer.execute({
                    "competitor": comp_name,
                    "dimension": dim_name,
                    "output_type": dim_cfg.get("output_type", "paragraph"),
                    "description": dim_cfg.get("description", ""),
                    "findings": analysis.get("findings", []) if isinstance(analysis, dict) else [],
                })
                results[(comp_name, dim_name)] = results.get((comp_name, dim_name), {})
                results[(comp_name, dim_name)]["report"] = result.output

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
        self.sm.update_task_status(task_id, TaskStatus.COMPLETED)
