import time

from app.models.task import Task, TaskStatus, NodeStatus


class StateManager:
    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def create_task(
        self,
        task_id: str,
        competitors: list[str],
        dimensions: list[str],
        dag_json: dict,
    ) -> Task:
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            competitors=competitors,
            dimensions=dimensions,
            dag_json=dag_json,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def update_task_status(self, task_id: str, status: TaskStatus):
        task = self._tasks[task_id]
        task.status = status
        task.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def update_node_status(self, task_id: str, node_id: str, status: NodeStatus):
        task = self._tasks[task_id]
        task.node_states[node_id] = status
        task.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def add_trace(self, task_id: str, trace: dict):
        task = self._tasks[task_id]
        task.traces.append(trace)

    def add_review(self, task_id: str, review: dict):
        task = self._tasks[task_id]
        task.reviews.append(review)

    def set_report(self, task_id: str, html: str):
        task = self._tasks[task_id]
        task.report_html = html
