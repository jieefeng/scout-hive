import sqlite3
import json
import time
from pathlib import Path

from app.models.task import Task, TaskStatus, NodeStatus, Competitor


class StateManager:
    _db_path = Path(__file__).parent.parent.parent / "data" / "tasks.db"
    _instance: "StateManager | None" = None

    def __new__(cls, db_path: str | None = None, reset: bool = False):
        if reset or cls._instance is None:
            path = db_path or str(cls._db_path)
            instance = super().__new__(cls)
            instance._conn = None
            cls._instance = instance
        return cls._instance

    def __init__(self, db_path: str | None = None, reset: bool = False):
        if self._conn is not None:
            return
        path = db_path or str(self._db_path)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id       TEXT PRIMARY KEY,
                status        TEXT NOT NULL DEFAULT 'pending',
                competitors   TEXT NOT NULL DEFAULT '[]',
                dimensions    TEXT NOT NULL DEFAULT '[]',
                dag_json      TEXT NOT NULL DEFAULT '{}',
                node_states   TEXT NOT NULL DEFAULT '{}',
                created_at    TEXT NOT NULL,
                report_html   TEXT NOT NULL DEFAULT '',
                cancelled     INTEGER NOT NULL DEFAULT 0  -- 0=正常, 1=用户请求停止
            )
        """)
        # Add cancelled column if upgrading from older schema (graceful migration)
        try:
            self._conn.execute("ALTER TABLE tasks ADD COLUMN cancelled INTEGER NOT NULL DEFAULT 0")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        self._conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            task_id=row["task_id"],
            status=TaskStatus(row["status"]),
            competitors=[Competitor(**c) for c in json.loads(row["competitors"])],
            dimensions=json.loads(row["dimensions"]),
            dag_json=json.loads(row["dag_json"]),
            node_states={k: NodeStatus(v) for k, v in json.loads(row["node_states"]).items()},
            created_at=row["created_at"],
            updated_at=row["created_at"],
            report_html=row["report_html"],
            traces=[],
            reviews=[],
            cancelled=bool(row["cancelled"]),
        )

    def create_task(
        self,
        task_id: str,
        competitors: list[Competitor],
        dimensions: list[str],
        dag_json: dict,
    ) -> Task:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            competitors=competitors,
            dimensions=dimensions,
            dag_json=dag_json,
            node_states={},
            created_at=now,
            updated_at=now,
            report_html="",
            traces=[],
            reviews=[],
        )
        self._conn.execute(
            """INSERT INTO tasks (task_id, status, competitors, dimensions, dag_json, node_states, created_at, report_html)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, task.status.value, json.dumps([c.model_dump() for c in competitors]),
             json.dumps(dimensions), json.dumps(dag_json), json.dumps({}), now, ""),
        )
        self._conn.commit()
        return task

    def get_task(self, task_id: str) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(self) -> list[Task]:
        rows = self._conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [self._row_to_task(row) for row in rows]

    def update_task_status(self, task_id: str, status: TaskStatus):
        self._conn.execute(
            "UPDATE tasks SET status = ? WHERE task_id = ?",
            (status.value, task_id),
        )
        self._conn.commit()

    def update_node_status(self, task_id: str, node_id: str, status: NodeStatus):
        row = self._conn.execute("SELECT node_states FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row:
            node_states = json.loads(row["node_states"])
            node_states[node_id] = status.value
            self._conn.execute("UPDATE tasks SET node_states = ? WHERE task_id = ?",
                               (json.dumps(node_states), task_id))
            self._conn.commit()

    def add_trace(self, task_id: str, trace: dict):
        # Not persisted in this simplified schema
        pass

    def add_review(self, task_id: str, review: dict):
        # Not persisted in this simplified schema
        pass

    def set_report(self, task_id: str, html: str):
        self._conn.execute("UPDATE tasks SET report_html = ? WHERE task_id = ?", (html, task_id))
        self._conn.commit()

    def clear_all(self):
        """清除所有任务（仅用于测试）"""
        self._conn.execute("DELETE FROM tasks")
        self._conn.commit()

    def close(self):
        """关闭数据库连接（仅用于测试）"""
        if self._conn:
            self._conn.close()
            self._conn = None
        StateManager._instance = None

    @classmethod
    def reset(cls):
        """重置单例（测试用）"""
        if cls._instance is not None and cls._instance._conn:
            cls._instance._conn.close()
        cls._instance = None
        db_path = Path(cls._db_path)
        if db_path.exists():
            try:
                db_path.unlink()
            except PermissionError:
                pass

    def calculate_progress(self, task: Task) -> float:
        total_nodes = len(task.dag_json.get("nodes", []))
        if total_nodes == 0:
            return 0.0
        completed_nodes = sum(
            1 for s in task.node_states.values()
            if s in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
        )
        return round(completed_nodes / total_nodes, 2)

    def is_task_cancelled(self, task_id: str) -> bool:
        """检查任务是否被用户请求取消。"""
        row = self._conn.execute(
            "SELECT cancelled FROM tasks WHERE task_id = ?",
            (task_id,)
        ).fetchone()
        return bool(row["cancelled"]) if row else False

    def cancel_task(self, task_id: str) -> bool:
        """标记任务为取消状态。返回是否成功（任务存在且未被取消过）。"""
        rows = self._conn.execute(
            "UPDATE tasks SET cancelled = 1 WHERE task_id = ? AND cancelled = 0",
            (task_id,)
        )
        self._conn.commit()
        return rows.rowcount > 0