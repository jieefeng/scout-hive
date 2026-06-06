import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from app.config import load_config
from app.engine.state_manager import StateManager
from app.engine.event_bus import EventBus
from app.engine.orchestrator import Orchestrator
from app.llm.registry import LLMRegistry
from app.agents.task_parser import TaskParser
from app.agents.collector import Collector
from app.agents.analyst import Analyst
from app.agents.writer import Writer
from app.agents.reviewer import Reviewer
from app.api import tasks, websocket, parse as parse_api


def create_app() -> FastAPI:
    config = load_config()

    app = FastAPI(
        title="竞品分析 Agent 协作系统",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5000", "http://127.0.0.1:5000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.config = config

    state_manager = StateManager()
    event_bus = EventBus()

    # 启动时恢复中断的任务
    recovered = state_manager.recover_running_tasks()
    if recovered > 0:
        logger.info("Recovered %d running tasks from previous session", recovered)

    llm_registry = LLMRegistry(config.llm)
    agents = {
        "TaskParser": TaskParser("TaskParser", llm_registry.get_for_agent("TaskParser")),
        "Collector": Collector("Collector", llm_registry.get_for_agent("Collector")),
        "Analyst": Analyst("Analyst", llm_registry.get_for_agent("Analyst")),
        "Writer": Writer("Writer", llm_registry.get_for_agent("Writer")),
        "Reviewer": Reviewer("Reviewer", llm_registry.get_for_agent("Reviewer")),
    }
    orchestrator = Orchestrator(state_manager, event_bus, agents)

    tasks.init_router(state_manager, orchestrator, event_bus)
    websocket.init_router(event_bus)
    parse_api.init_router(orchestrator, state_manager, event_bus)
    app.include_router(tasks.router)
    app.include_router(websocket.router)
    app.include_router(parse_api.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
