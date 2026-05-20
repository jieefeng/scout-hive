import pytest
from app.models.analysis import AnalysisResult, Finding, Confidence, ComparisonMatrix, CompetitorStatus


def test_finding_with_quote():
    finding = Finding(
        finding_id="f001", claim="竞品A 支持 12 种语言",
        quote="Supporting 12 languages including...", quote_type="exact",
        source_ref="src_003", chunk_ref="chunk_01",
        reasoning_chain=[{"step": 1, "thought": "官网显示语言切换器", "source_ref": "src_003"}],
        confidence=Confidence(score=0.92, level="high", uncertainty_factors=[]),
    )
    assert finding.quote_type == "exact"
    assert finding.confidence.score == 0.92


def test_analysis_result_creation():
    result = AnalysisResult(
        analysis_id="a001", competitor="竞品A", dimension="功能对比",
        findings=[Finding(
            finding_id="f001", claim="支持多语言", quote="12 languages supported",
            quote_type="exact", source_ref="src_001", chunk_ref="c001",
            reasoning_chain=[], confidence=Confidence(score=0.9, level="high"),
        )],
        comparison_matrix=ComparisonMatrix(
            dimensions=["多语言"],
            competitors={"竞品A": {"多语言": CompetitorStatus(status="✓", detail="12种语言")}},
        ),
    )
    assert len(result.findings) == 1
