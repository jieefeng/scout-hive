from typing import Literal

from pydantic import BaseModel, Field


class Confidence(BaseModel):
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    level: Literal["high", "medium", "low"] = "medium"
    uncertainty_factors: list[str] = Field(default_factory=list)


class ReasoningStep(BaseModel):
    step: int
    thought: str
    source_ref: str | None = None


class Finding(BaseModel):
    finding_id: str
    claim: str
    quote: str = ""
    quote_type: str = "exact"
    source_ref: str = ""
    chunk_ref: str = ""
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)


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
