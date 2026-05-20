import pytest
from app.llm.base import Message, LLMResponse


def test_message_creation():
    msg = Message(role="user", content="分析竞品A")
    assert msg.role == "user"
    assert msg.content == "分析竞品A"


def test_llm_response():
    resp = LLMResponse(content='{"result": "ok"}', model="test-model", tokens_used=100, latency_ms=500)
    assert resp.content == '{"result": "ok"}'
    assert resp.tokens_used == 100


def test_llm_error_creation():
    from app.llm.base import LLMError
    err = LLMError("bailian_auth", "API Key 无效")
    assert err.code == "bailian_auth"
    assert err.message == "API Key 无效"
    assert str(err) == "[bailian_auth] API Key 无效"


def test_llm_error_inheritance():
    from app.llm.base import LLMError
    assert issubclass(LLMError, Exception)
