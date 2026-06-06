from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    finding_id: str
    claim: str
    quote: str = ""
    quote_type: str = "exact"
    source_ref: str = ""
    chunk_ref: str = ""
    reasoning_chain: list[dict] = Field(default_factory=list)


class CompetitorStatus(BaseModel):
    status: str
    detail: str = ""


class ComparisonMatrix(BaseModel):
    dimensions: list[str] = Field(default_factory=list)
    competitors: dict[str, dict[str, CompetitorStatus]] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    analysis_id: str
    competitor: str
    dimension: str
    findings: list[Finding] = Field(default_factory=list)
    comparison_matrix: ComparisonMatrix = Field(default_factory=ComparisonMatrix)
