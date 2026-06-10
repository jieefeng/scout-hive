import pytest
from app.models.raw_data import RawData


def test_raw_data_creation():
    data = RawData(
        source_url="https://www.feishu.cn/",
        title="飞书官网",
        description="飞书官方网站",
        content="飞书完整内容...",
    )
    assert data.source_url == "https://www.feishu.cn/"
    assert data.title == "飞书官网"
    assert data.description == "飞书官方网站"
    assert data.content == "飞书完整内容..."


def test_raw_data_defaults():
    data = RawData(source_url="https://example.com", content="some content")
    assert data.title == ""
    assert data.description == ""


def test_raw_data_from_api_dict():
    """模拟 AnySearch API 返回结构直接构造 RawData"""
    api_result = {
        "url": "https://www.feishu.cn/",
        "title": "飞书官网",
        "description": "飞书官方网站",
        "content": "飞书完整内容...",
    }
    data = RawData(
        source_url=api_result["url"],
        title=api_result["title"],
        description=api_result["description"],
        content=api_result["content"],
    )
    assert data.source_url == api_result["url"]
