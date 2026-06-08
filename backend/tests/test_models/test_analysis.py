from app.models.analysis import AnalysisResult, Finding, ComparisonMatrix, CompetitorStatus


def test_finding_with_quote():
    finding = Finding(
        finding_id="f001", claim="竞品A 支持 12 种语言",
        quote="Supporting 12 languages including...", quote_type="exact",
        source_ref="src_003", chunk_ref="chunk_01",
        reasoning_chain=[{"step": 1, "thought": "官网显示语言切换器", "source_ref": "src_003"}],
    )
    assert finding.quote_type == "exact"
    assert finding.quote == "Supporting 12 languages including..."


def test_analysis_result_creation():
    result = AnalysisResult(
        analysis_id="a001", competitor="竞品A", dimension="核心玩法",
        findings=[Finding(
            finding_id="f001", claim="支持多语言", quote="12 languages supported",
            quote_type="exact", source_ref="src_001", chunk_ref="c001",
            reasoning_chain=[],
        )],
        comparison_matrix=ComparisonMatrix(
            dimensions=["多语言"],
            competitors={"竞品A": {"多语言": CompetitorStatus(status="✓", detail="12种语言")}},
        ),
    )
    assert len(result.findings) == 1


def test_finding_ignores_extra_confidence_field():
    """Finding 模型忽略 LLM 偶发输出的 confidence 字段。"""
    finding = Finding(
        finding_id="f002", claim="test claim", quote="quote", quote_type="exact",
        source_ref="src_001", chunk_ref="c001",
        confidence={"score": 0.9, "level": "high"},
    )
    dumped = finding.model_dump()
    assert "confidence" not in dumped
    assert finding.claim == "test claim"
