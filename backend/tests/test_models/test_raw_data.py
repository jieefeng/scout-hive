import pytest
from app.models.raw_data import RawData, Chunk, RawDataMetadata


def test_chunk_creation():
    chunk = Chunk(chunk_id="c001", text="基础版 ¥99/月", selector="body > div.pricing", plain_text_snapshot="基础版 ¥99/月")
    assert chunk.chunk_id == "c001"
    assert chunk.selector == "body > div.pricing"


def test_raw_data_with_content_hash():
    data = RawData(
        data_id="d001", source_type="web", source_url="https://example.com",
        content="测试内容", content_hash="abc123",
        metadata=RawDataMetadata(fetched_by="collector_001", reliability="high", content_type="pricing_page", status="success"),
        chunks=[Chunk(chunk_id="c001", text="测试内容", plain_text_snapshot="测试内容")],
    )
    assert data.content_hash == "abc123"
    assert data.metadata.status == "success"
    assert len(data.chunks) == 1


def test_raw_data_failed_status():
    data = RawData(
        data_id="d002", source_type="web", source_url="https://broken.com",
        content="", content_hash="",
        metadata=RawDataMetadata(fetched_by="collector_001", reliability="low", content_type="unknown", status="failed", error_message="HTTP 404"),
        chunks=[],
    )
    assert data.metadata.status == "failed"
    assert data.metadata.error_message == "HTTP 404"
