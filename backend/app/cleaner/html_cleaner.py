from pydantic import BaseModel
import trafilatura


class CleanResult(BaseModel):
    text: str
    status: str  # success | partial | failed
    title: str = ""
    error: str | None = None


def clean_html(
    content: str,
    source_url: str = "",
    min_length: int = 50,
) -> CleanResult:
    if not content or not content.strip():
        return CleanResult(text="", status="failed", error="Empty content")

    # 如果是纯文本（不含 HTML 标签），直接返回
    if "<" not in content:
        text = content.strip()
        if len(text) < min_length:
            return CleanResult(text=text, status="partial", error="Content too short")
        return CleanResult(text=text, status="success")

    # 使用 trafilatura 提取正文
    extracted = trafilatura.extract(
        content, url=source_url,
        include_comments=False, include_tables=True, favor_precision=True,
    )

    if not extracted:
        return CleanResult(text="", status="failed", error="No content extracted")

    title = trafilatura.extract(content, output_format="xml", include_comments=False)
    title_text = ""
    if title and "<title>" in title:
        start = title.index("<title>") + 7
        end = title.index("</title>")
        title_text = title[start:end]

    if len(extracted) < min_length:
        return CleanResult(text=extracted, title=title_text, status="partial", error="Content too short")

    return CleanResult(text=extracted, title=title_text, status="success")
