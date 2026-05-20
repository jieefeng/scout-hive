import pytest
from app.cleaner.html_cleaner import clean_html, CleanResult


def test_clean_html_extracts_main_content():
    html = """
    <html>
    <head><title>Test</title></head>
    <body>
        <nav>Navigation bar</nav>
        <div class="main-content">
            <h1>产品介绍</h1>
            <p>这是一段关于竞品的核心内容描述。</p>
            <p>支持多语言、API 开放、SSO 单点登录。</p>
        </div>
        <footer>Copyright 2026</footer>
    </body>
    </html>
    """
    result = clean_html(html, source_url="https://example.com")
    assert result.status == "success"
    assert "产品介绍" in result.text
    assert "Navigation bar" not in result.text
    assert "Copyright" not in result.text


def test_clean_html_handles_empty_content():
    result = clean_html("", source_url="https://empty.com")
    assert result.status == "failed"
    assert result.text == ""


def test_clean_html_too_short():
    html = "<html><body><p>短</p></body></html>"
    result = clean_html(html, min_length=100)
    assert result.status == "partial"


def test_clean_html_plain_text():
    text = "这是一段纯文本内容，不需要 HTML 解析。包含足够的文字长度来通过最小长度检查。"
    result = clean_html(text, min_length=10)
    assert result.status == "success"
    assert "纯文本内容" in result.text
