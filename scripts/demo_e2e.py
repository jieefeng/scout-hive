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
    print(f"将跑 {len(competitors)} 个竞品：{competitors}")
    return 0  # 后续 task 补全


if __name__ == "__main__":
    sys.exit(main())
