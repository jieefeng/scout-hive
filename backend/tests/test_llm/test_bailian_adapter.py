import pytest
from app.llm.bailian_adapter import BailianAdapter
from app.llm.openai_adapter import OpenAIAdapter


def test_inheritance():
    assert issubclass(BailianAdapter, OpenAIAdapter)


def test_default_model():
    adapter = BailianAdapter(api_key="dummy_key")
    assert adapter.model == "qwen-plus"


def test_custom_model():
    adapter = BailianAdapter(api_key="dummy_key", model="qwen-max")
    assert adapter.model == "qwen-max"


def test_base_url():
    adapter = BailianAdapter(api_key="dummy_key")
    assert str(adapter.client.base_url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/"


def test_base_url_not_openai():
    adapter = BailianAdapter(api_key="dummy_key")
    assert "openai.com" not in str(adapter.client.base_url)
