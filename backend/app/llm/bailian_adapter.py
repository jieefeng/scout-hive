import openai
from app.llm.base import LLMError
from app.llm.openai_adapter import OpenAIAdapter


class BailianAdapter(OpenAIAdapter):
    def __init__(self, api_key: str, model: str = "qwen-plus"):
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model

    async def chat(self, messages, **kwargs):
        try:
            return await super().chat(messages, **kwargs)
        except openai.AuthenticationError:
            raise LLMError("bailian_auth", "DASHSCOPE_API_KEY 无效或未设置")
        except openai.RateLimitError:
            raise LLMError("bailian_rate_limit", "百练平台限流，请稍后重试")
        except openai.APIStatusError as e:
            raise LLMError("bailian_api", f"百练 API 错误: {e.status_code}")

    async def stream_chat(self, messages, **kwargs):
        try:
            async for chunk in super().stream_chat(messages, **kwargs):
                yield chunk
        except openai.AuthenticationError:
            raise LLMError("bailian_auth", "DASHSCOPE_API_KEY 无效或未设置")
        except openai.RateLimitError:
            raise LLMError("bailian_rate_limit", "百练平台限流，请稍后重试")
        except openai.APIStatusError as e:
            raise LLMError("bailian_api", f"百练 API 错误: {e.status_code}")
