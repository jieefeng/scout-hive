import sys
sys.path.insert(0, "D:/AAComputerCourse/AACode/zijie/backend")

import asyncio
import os
import logging

logging.basicConfig(level=logging.DEBUG)

# Simulate exactly what the backend does
from app.config import load_config
from app.llm.registry import LLMRegistry
from app.agents.task_parser import TaskParser

async def test():
    config = load_config()
    print(f"LLM config: default={config.llm.default}, adapters={list(config.llm.adapters.keys())}")
    for name, adapter_cfg in config.llm.adapters.items():
        print(f"  {name}: type={adapter_cfg.type}, model={adapter_cfg.model}, api_key={'SET' if adapter_cfg.api_key else 'NONE'}")

    registry = LLMRegistry(config.llm)
    parser = TaskParser("TaskParser", registry.get_for_agent("TaskParser"))

    print(f"\nCalling parser.run() with '分析抖音和快手'...")
    result = await parser.run({"message": "分析抖音和快手"})
    print(f"Result: success={result.success}, error_type={result.error_type}, error_message={result.error_message}")
    print(f"Raw response: {repr(result.raw_response[:200]) if result.raw_response else 'EMPTY'}")

asyncio.run(test())