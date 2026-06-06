"""真实 LLM 端到端 demo 脚本。

走真实 HTTP 端点（API_BASE，默认 http://localhost:5010）：
    POST /api/tasks/parse          → blueprint
    POST /api/tasks/parse/confirm  → task_id
    GET  /api/tasks/{id}           → 轮询直到终态

默认竞品：Notion AI / Tana / Reflect（AI 笔记类）。
可改：python scripts/demo_e2e.py --competitors "钉钉,飞书,企微"
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# Windows console encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_COMPETITORS = ["Notion AI", "Tana", "Reflect"]
DEFAULT_MESSAGE_TEMPLATE = "分析 {competitor} 的功能对比与定价策略"
API_BASE = os.getenv("API_BASE", "http://localhost:5010")
OUTPUT_DIR = Path("scripts/demo_runs")


def check_env() -> bool:
    """验证 DASHSCOPE_API_KEY + Backend 可达。

    Returns:
        True 全部通过；False 任意一项缺失。
    """
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY")
    if not key:
        print("✗ DASHSCOPE_API_KEY 未设置")
        return False
    print(f"✓ API key 已设置（前缀 {key[:8]}...）")
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        r.raise_for_status()
        print(f"✓ Backend 健康检查通过（{API_BASE}）")
    except Exception as e:
        print(f"✗ Backend 不可达：{e}")
        return False
    return True


async def parse_one(client: httpx.AsyncClient, competitor: str) -> dict:
    """POST /api/tasks/parse → blueprint dict."""
    message = DEFAULT_MESSAGE_TEMPLATE.format(competitor=competitor)
    r = await client.post("/api/tasks/parse", json={"message": message}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data.get("blueprint"):
        raise RuntimeError(f"parse 失败: {data.get('error_type')} - {data.get('error_message')}")
    return data


async def confirm_one(client: httpx.AsyncClient, blueprint: dict) -> str:
    """POST /api/tasks/parse/confirm → task_id."""
    r = await client.post(
        "/api/tasks/parse/confirm",
        json={"blueprint": blueprint},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["task_id"]


async def poll_until_done(client: httpx.AsyncClient, task_id: str, timeout: int = 600) -> dict:
    """轮询 GET /api/tasks/{id} 直到 status 终态，返回完整 task dict."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = await client.get(f"/api/tasks/{task_id}", timeout=30)
        r.raise_for_status()
        task = r.json()
        status = task.get("status")
        if status in ("completed", "failed"):
            return task
        await asyncio.sleep(5)
    raise TimeoutError(f"task {task_id} 超时（{timeout}s）")


def save_artifacts(task: dict, run_dir: Path) -> tuple[Path, Path]:
    """保存 report_html 与 traces 到 run_dir，返回路径元组."""
    task_id = task["task_id"]
    report_path = run_dir / f"{task_id}_report.html"
    trace_path = run_dir / f"{task_id}_traces.json"
    report_path.write_text(task.get("report_html") or "", encoding="utf-8")
    trace_path.write_text(
        json.dumps(task.get("traces", []), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path, trace_path


async def run_one(competitor: str, run_dir: Path) -> dict:
    """跑 1 个竞品的完整流程。

    Returns:
        {competitor, task_id, status, report, trace, findings_count}
    Raises:
        RuntimeError: 任务失败时
    """
    message = DEFAULT_MESSAGE_TEMPLATE.format(competitor=competitor)
    async with httpx.AsyncClient(base_url=API_BASE) as client:
        print(f"[{competitor}] parse ...", flush=True)
        parsed = await parse_one(client, competitor)
        print(f"[{competitor}] confirm ...", flush=True)
        task_id = await confirm_one(client, parsed["blueprint"])
        print(f"[{competitor}] task_id={task_id}, 轮询中 ...", flush=True)
        task = await poll_until_done(client, task_id)
        if task["status"] != "completed":
            raise RuntimeError(f"[{competitor}] 任务失败: {task.get('error_message')}")
        report_path, trace_path = save_artifacts(task, run_dir)
        return {
            "competitor": competitor,
            "task_id": task_id,
            "status": task["status"],
            "report": str(report_path),
            "trace": str(trace_path),
            "findings_count": sum(
                len(t.get("output", {}).get("findings", []))
                for t in task.get("traces", [])
            ),
        }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="真实 LLM 端到端 demo")
    p.add_argument("--competitors", default=",".join(DEFAULT_COMPETITORS),
                   help="逗号分隔的竞品名")
    p.add_argument("--concurrency", type=int, default=2, help="并发数")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    competitors = [c.strip() for c in args.competitors.split(",") if c.strip()]
    if not check_env():
        return 1
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== 跑 1 个竞品（{competitors[0]}）===")
    try:
        result = asyncio.run(run_one(competitors[0], run_dir))
    except Exception as e:
        print(f"✗ {e}")
        return 1
    print(f"\n✓ 成功：report={result['report']}, trace={result['trace']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
