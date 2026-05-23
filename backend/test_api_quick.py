import os, sys
sys.path.insert(0, '.')
import asyncio
from app.llm.bailian_adapter import BailianAdapter
from app.llm.base import Message

async def quick_test():
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        print("DASHSCOPE_API_KEY not set")
        return
    adapter = BailianAdapter(api_key=key, model="qwen3.6-plus-2026-04-02")
    messages = [Message(role="user", content="用一句话介绍自己")]
    print("Calling Bailian API...")
    resp = await adapter.chat(messages)
    print(f"Success! Model: {resp.model}, Tokens: {resp.tokens_used}")
    print(f"Response: {resp.content[:200]}")

asyncio.run(quick_test())