"""自然语言需求 → DAG 蓝图：纯解析层，不入库、不执行。

调用关系：
    POST /api/tasks/parse          → parse_task_blueprint(...)
    POST /api/tasks/parse/confirm  → DAGBlueprint(**req.blueprint) + _create_and_run
"""
import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.agents.task_parser import TaskParser
from app.models.dag import DAGBlueprint
from app.models.task import Competitor, TaskStatus
from app.schema.mvp_defaults import load_default_schema

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
        "summary": parsed.get("summary", ""),
        "raw_response": raw_truncated,
    }


# ---- HTTP 入口 ----

router = APIRouter(prefix="/api/tasks", tags=["parse"])

# 模块级单例，由 init_router 注入
_orch = None  # type: ignore[var-annotated]
_sm = None    # type: ignore[var-annotated]
_bus = None   # type: ignore[var-annotated]


def init_router(sm, orch, bus):
    """main.create_app 启动时调用。"""
    global _sm, _orch, _bus
    _sm = sm
    _orch = orch
    _bus = bus


class ParseRequest(BaseModel):
    message: str = Field(min_length=0, max_length=10000)


class ParseResponse(BaseModel):
    blueprint: dict
    competitors: list[str]
    dimensions: list[str]
    summary: str = ""


HINT_FALLBACK = "请重写需求使其更具体，或使用 POST /api/tasks 直接提交结构化数据"


@router.post("/parse", response_model=ParseResponse)
async def parse_task(req: ParseRequest):
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(
            status_code=422,
            detail={"error_type": "empty_message", "hint": "需求不能为空"},
        )
    # 截断超长 message（避免烧 token）
    message = message[:MESSAGE_MAX_LEN]

    task_parser = _orch.agents["TaskParser"]
    schema = load_default_schema().model_dump()
    result = await parse_task_blueprint(message, task_parser, schema)

    if not result["success"]:
        raise HTTPException(
            status_code=422,
            detail={
                "error_type": result["error_type"],
                "raw_response": result.get("raw_response", ""),
                "error_message": result.get("error_message", ""),
                "hint": HINT_FALLBACK,
            },
        )

    return ParseResponse(
        blueprint=result["blueprint"],
        competitors=result["competitors"],
        dimensions=result["dimensions"],
        summary=result["summary"],
    )


class ParseConfirmRequest(BaseModel):
    blueprint: dict


@router.post("/parse/confirm")
async def confirm_parse(req: ParseConfirmRequest):
    """二次校验 blueprint + 创建 task + 启动 execute_mvp。"""
    if not req.blueprint or "nodes" not in req.blueprint:
        raise HTTPException(
            status_code=422,
            detail={"error_type": "blueprint_tampered", "error_message": "blueprint 缺少 nodes"},
        )
    try:
        DAGBlueprint(**req.blueprint)
    except (ValueError, ValidationError) as e:
        raise HTTPException(
            status_code=422,
            detail={"error_type": "blueprint_tampered", "error_message": str(e)},
        )

    task_id = str(uuid.uuid4())
    competitors = sorted({
        n["params"].get("target", "")
        for n in req.blueprint["nodes"]
        if n.get("params", {}).get("target")
    })
    dimensions = sorted({
        n["params"].get("dimension", "")
        for n in req.blueprint["nodes"]
        if n.get("params", {}).get("dimension")
    })

    task = _sm.create_task(
        task_id,
        [Competitor(name=c, website="") for c in competitors],
        dimensions,
        req.blueprint,
    )
    task.progress = _sm.calculate_progress(task)

    async def run_dag():
        try:
            await _orch.execute_mvp(
                task_id,
                DAGBlueprint(**req.blueprint),
                [{"name": c, "domain": ""} for c in competitors],
            )
        except Exception as e:
            logger.exception("Confirm task %s failed: %s", task_id, e)
            _sm.set_error_message(task_id, str(e))
            _sm.update_task_status(task_id, TaskStatus.FAILED)

    asyncio.create_task(run_dag())
    return task
