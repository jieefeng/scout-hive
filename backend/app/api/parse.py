"""自然语言需求 → DAG 蓝图：纯解析层，不入库、不执行。

调用关系：
    POST /api/tasks/parse          → parse_task_blueprint(...)
    POST /api/tasks/parse/confirm  → DAGBlueprint(**req.blueprint) + _create_and_run
"""
import json
import logging
from typing import Any

from app.agents.task_parser import TaskParser

logger = logging.getLogger(__name__)

# 仅这两类错误值得重试；其他重试无意义或方向错误。
RETRYABLE_ERRORS = {"json_parse", "llm_empty"}

MAX_COMPETITORS = 10
MESSAGE_MAX_LEN = 2000
RAW_RESPONSE_MAX_LEN = 200


def _all_dim_names(schema: dict) -> set[str]:
    return {d["name"] for g in schema.get("groups", []) for d in g.get("dimensions", [])}


def _raw_content(result) -> str:
    """优先取 llm_response.content（execute 异常路径不会设 raw_response）。"""
    if result.llm_response and result.llm_response.content:
        return result.llm_response.content
    return result.raw_response or ""


def _extract_summary(raw: str) -> str:
    """TaskDAG.model_dump() 丢掉 summary 字段，从 LLM 原文里补回。"""
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        s = "\n".join(lines[1:-1]) if len(lines) >= 2 else s.lstrip("`")
    try:
        parsed = json.loads(s)
    except json.JSONDecodeError:
        return ""
    if isinstance(parsed, dict):
        return parsed.get("summary", "") or ""
    return ""


def _classify_error(result) -> str:
    """execute 内 DAGBlueprint 验证失败时被 AgentBase.run 捕获,
    error_type 会被分类为 'unknown'。识别 Pydantic 对 DAGBlueprint 的验证错误。"""
    et = result.error_type or "unknown"
    if et == "unknown" and "DAGBlueprint" in (result.error_message or ""):
        return "topology_error"
    return et


async def parse_task_blueprint(
    message: str,
    task_parser: TaskParser,
    schema: dict,
) -> dict[str, Any]:
    """调 TaskParser 1 次，失败重试 1 次（仅 RETRYABLE_ERRORS）；做严格短路校验。

    Returns:
        success=True  → {success, blueprint, competitors, dimensions, summary, raw_response}
        success=False → {success, error_type, raw_response, error_message}
    """
    result = await task_parser.run({"message": message})

    if (not result.success) and result.error_type in RETRYABLE_ERRORS:
        result = await task_parser.retry_with_prompt_hint(
            {"message": message},
            error_hint=result.error_message or "输出格式有误",
        )

    raw_truncated = _raw_content(result)[:RAW_RESPONSE_MAX_LEN]

    if not result.success:
        return {
            "success": False,
            "error_type": _classify_error(result),
            "raw_response": raw_truncated,
            "error_message": result.error_message or "",
        }

    parsed = result.output
    competitors = parsed.get("competitors", [])
    dimensions = parsed.get("dimensions", [])

    # 严格短路：dim 必须在 schema 内
    allowed = _all_dim_names(schema)
    for dim in dimensions:
        if dim not in allowed:
            return {
                "success": False,
                "error_type": "dim_not_in_schema",
                "raw_response": raw_truncated,
                "error_message": f"维度 '{dim}' 不在 DEFAULT_SCHEMA 内",
            }

    # 竞品数校验
    if not competitors:
        return {
            "success": False,
            "error_type": "empty_competitors",
            "raw_response": raw_truncated,
        }
    if len(competitors) > MAX_COMPETITORS:
        return {
            "success": False,
            "error_type": "too_many_competitors",
            "raw_response": raw_truncated,
        }

    return {
        "success": True,
        "blueprint": parsed["dag"],
        "competitors": competitors,
        "dimensions": dimensions,
        "summary": _extract_summary(_raw_content(result)),
        "raw_response": raw_truncated,
    }
