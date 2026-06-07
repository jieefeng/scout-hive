"""国内 AI 助手 5 竞品 × 3 维度横评 demo。

走真实 HTTP 端点(API_BASE,默认 http://localhost:5010):
    POST /api/tasks/parse          → blueprint
    POST /api/tasks/parse/confirm  → task_id
    GET  /api/tasks/{id}           → 轮询直到终态

用法:
    python scripts/demo_ai_assistant.py                              # 默认 5×3 主 demo
    python scripts/demo_ai_assistant.py --dimensions "核心玩法"      # 现场追问 demo
    python scripts/demo_ai_assistant.py --dimensions "Agent 能力,商业模式"  # 多维度
    python scripts/demo_ai_assistant.py --no-poll                    # 启动后立即退出,不轮询

输出:
    启动时: Task created: <task_id>
    每节点: [Analyst] 豆包/核心玩法 - 完成 (12.3s)
    跑完后: View report: http://localhost:5000/task/<task_id>
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx
import yaml

# Windows console encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CONFIG_PATH = Path(__file__).parent / "demo_ai_assistant.yaml"
DEFAULT_DIMENSIONS_MODE = "primary"  # "primary" | "backup" | "all"


def load_config():
    """加载 demo YAML 配置。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_env(api_base: str) -> bool:
    """验证 Backend 可达 + DASHSCOPE_API_KEY 设置。"""
    import os
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY")
    if not key:
        print("✗ DASHSCOPE_API_KEY 未设置(export DASHSCOPE_API_KEY=...)")
        return False
    print(f"✓ API key 已设置(前缀 {key[:8]}...)")
    try:
        r = httpx.get(f"{api_base}/health", timeout=5)
        r.raise_for_status()
        print(f"✓ Backend 健康检查通过({api_base})")
    except Exception as e:
        print(f"✗ Backend 不可达:{e}")
        return False
    return True


def build_message(competitors: list, dimensions: list) -> str:
    """从竞品列表 + 维度列表生成自然语言 message(喂给 parse 端)。"""
    comp_names = "、".join(c["name"] for c in competitors)
    dim_text = "、".join(dimensions)
    return (
        f"对比分析 {comp_names}。重点分析:{dim_text}。"
        "请输出结构化竞品分析报告。"
    )


async def create_task(api_base: str, message: str) -> str:
    """调 parse + confirm 端点,返回 task_id。"""
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. parse
        print(f"\n[1/3] Calling POST /api/tasks/parse ...")
        r = await client.post(f"{api_base}/api/tasks/parse", json={"message": message})
        if r.status_code == 422:
            err = r.json().get("detail", {})
            print(f"✗ Parse 失败: {err.get('error_type')} - {err.get('error_message')}")
            print(f"  Hint: {err.get('hint')}")
            print(f"  Raw response (前 500 字符): {err.get('raw_response', '')[:500]}")
            sys.exit(1)
        r.raise_for_status()
        blueprint_resp = r.json()
        print(f"  ✓ Blueprint: {len(blueprint_resp['competitors'])} 竞品, {len(blueprint_resp['dimensions'])} 维度")

        # 2. confirm
        print(f"[2/3] Calling POST /api/tasks/parse/confirm ...")
        r = await client.post(f"{api_base}/api/tasks/parse/confirm", json={"blueprint": blueprint_resp["blueprint"]})
        r.raise_for_status()
        task = r.json()
        task_id = task["task_id"]
        print(f"  ✓ Task created: {task_id}")
        return task_id


async def poll_progress(api_base: str, task_id: str, frontend_url: str, poll_interval: int, timeout: int, no_poll: bool) -> dict:
    """轮询 task 状态直到终态。"""
    if no_poll:
        print(f"\n[3/3] --no-poll: 跳过轮询")
        print(f"  View report (跑完后): {frontend_url}/task/{task_id}")
        return {"task_id": task_id, "status": "submitted"}

    print(f"\n[3/3] Polling task status (interval={poll_interval}s, timeout={timeout}s) ...")
    start = time.monotonic()
    last_node_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                print(f"✗ 超时(>{timeout}s),停止轮询")
                return {"task_id": task_id, "status": "timeout"}

            r = await client.get(f"{api_base}/api/tasks/{task_id}")
            r.raise_for_status()
            task = r.json()

            # 打印新增完成的节点
            completed_nodes = [
                (nid, st) for nid, st in task["node_states"].items()
                if st == "completed"
            ]
            if len(completed_nodes) > last_node_count:
                for nid, _ in completed_nodes[last_node_count:]:
                    print(f"  ✓ {nid}")
                last_node_count = len(completed_nodes)

            status = task["status"]
            if status in ("completed", "failed", "stopped"):
                print(f"\n=== Task {status.upper()} ===")
                print(f"耗时: {elapsed:.1f}s")
                print(f"完成节点: {last_node_count}")
                print(f"View report: {frontend_url}/task/{task_id}")
                return task

            await asyncio.sleep(poll_interval)


async def run_demo(args):
    config = load_config()
    api_base = config["api"]["base_url"]
    frontend_url = config["api"]["frontend_url"]
    poll_interval = config["api"]["poll_interval_seconds"]
    timeout = config["api"]["timeout_seconds"]

    print("=== 国内 AI 助手横评 Demo ===")
    print(f"Config: {CONFIG_PATH}")
    print(f"Backend: {api_base}")
    print(f"Frontend: {frontend_url}")

    if not check_env(api_base):
        sys.exit(1)

    # 决定要跑哪些维度
    if args.dimensions:
        dimensions = [d.strip() for d in args.dimensions.split(",")]
        print(f"\n自定义维度: {dimensions}")
    else:
        if args.mode == "primary":
            dimensions = config["primary_dimensions"]
        elif args.mode == "backup":
            dimensions = config["backup_dimensions"]
        else:  # all
            dimensions = config["primary_dimensions"] + config["backup_dimensions"]
        print(f"\n模式: {args.mode} → {len(dimensions)} 维度: {dimensions}")

    competitors = config["competitors"]
    print(f"竞品: {[c['name'] for c in competitors]} ({len(competitors)} 个)")

    message = build_message(competitors, dimensions)
    print(f"\nMessage: {message[:200]}{'...' if len(message) > 200 else ''}")

    task_id = await create_task(api_base, message)
    final = await poll_progress(
        api_base, task_id, frontend_url, poll_interval, timeout, args.no_poll
    )

    if final.get("status") == "failed":
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="国内 AI 助手横评 demo")
    parser.add_argument(
        "--dimensions",
        type=str,
        default="",
        help="逗号分隔的维度列表(覆盖 YAML 配置)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["primary", "backup", "all"],
        default=DEFAULT_DIMENSIONS_MODE,
        help="维度模式(默认 primary 跑 3 维度)",
    )
    parser.add_argument(
        "--no-poll",
        action="store_true",
        help="启动后立即退出,不轮询(用于批量启动多个任务)",
    )
    args = parser.parse_args()
    asyncio.run(run_demo(args))


if __name__ == "__main__":
    main()
