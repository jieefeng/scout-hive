import pytest
from app.models.task import Competitor, Task

def test_competitor_required_fields():
    c = Competitor(name="飞书", domain="feishu.cn")
    assert c.name == "飞书"
    assert c.domain == "feishu.cn"

def test_competitor_domain_required():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Competitor(name="飞书")  # domain is required

def test_task_with_competitor_list():
    task = Task(
        task_id="test-001",
        competitors=[
            Competitor(name="飞书", domain="feishu.cn"),
            Competitor(name="钉钉", domain="dingtalk.com"),
        ]
    )
    assert len(task.competitors) == 2
    assert task.competitors[0].domain == "feishu.cn"