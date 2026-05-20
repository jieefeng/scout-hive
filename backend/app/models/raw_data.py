from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str
    text: str
    embedding: list[float] = Field(default_factory=list)
    selector: str | None = None
    plain_text_snapshot: str | None = None


class RawDataMetadata(BaseModel):
    fetched_at: str | None = None
    fetched_by: str
    reliability: str = "medium"
    content_type: str = "unknown"
    status: str = "success"
    error_message: str | None = None


class RawData(BaseModel):
    data_id: str
    source_type: str
    source_url: str
    content: str
    content_hash: str = ""
    metadata: RawDataMetadata
    chunks: list[Chunk] = Field(default_factory=list)
