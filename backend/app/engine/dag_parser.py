from collections import defaultdict, deque

from app.models.dag import DAGBlueprint, DAGNode, FeedbackEdge


class TopologicalError(Exception):
    pass


class DAGParser:
    def __init__(self, blueprint: DAGBlueprint):
        self.blueprint = blueprint
        self.nodes: dict[str, DAGNode] = {n.id: n for n in blueprint.nodes}
        self.edges = blueprint.edges
        self.feedback_edges = blueprint.feedback_edges
        self._adj: dict[str, list[str]] = defaultdict(list)
        self._in_degree: dict[str, int] = defaultdict(int)

        for node in blueprint.nodes:
            self._in_degree[node.id] = 0
        for edge in blueprint.edges:
            self._adj[edge.from_node].append(edge.to_node)
            self._in_degree[edge.to_node] += 1

    def topological_sort(self) -> list[str]:
        in_degree = dict(self._in_degree)
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for neighbor in self._adj[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        if len(order) != len(self.nodes):
            raise TopologicalError("DAG contains a cycle in main edges")
        return order

    def get_ready_nodes(self, completed: set[str]) -> list[str]:
        ready = []
        for node_id, node in self.nodes.items():
            if node_id in completed:
                continue
            if all(dep in completed for dep in node.depends_on):
                ready.append(node_id)
        return ready

    def get_feedback_target(self, node_id: str) -> str | None:
        for fe in self.feedback_edges:
            if fe.from_node == node_id:
                return fe.to_node
        return None
