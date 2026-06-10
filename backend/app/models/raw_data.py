from pydantic import BaseModel


class RawData(BaseModel):
    source_url: str
    title: str = ""
    description: str = ""
    content: str
