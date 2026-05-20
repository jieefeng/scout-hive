import uuid
import time

from app.engine.state_manager import StateManager
from app.engine.event_bus import EventBus, Event
from app.engine.dag_parser import DAGParser
from app.agents.base import AgentBase, AgentResult
from app.models.dag import DAGBlueprint, DAGNode, FeedbackEdge
from app.models.task import TaskStatus, NodeStatus


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

            ready = parser.get_ready_nodes(completed | failed)

            if not ready:
                all_nodes = {n.id for n in blueprint.nodes}
                if all_nodes <= completed:
                    self.sm.update_task_status(task_id, TaskStatus.COMPLETED)
                    await self.bus.publish(Event(type="task_completed", task_id=task_id))
                elif all_nodes <= (completed | failed):
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
