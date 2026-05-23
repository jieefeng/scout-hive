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

def test_competitor_website_alias():
    c = Competitor(name="飞书", website="feishu.cn")
    assert c.website == "feishu.cn"
    # domain 仍可通过 property 访问
    assert c.domain == "feishu.cn"