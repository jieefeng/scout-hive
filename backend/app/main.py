from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_config


def create_app() -> FastAPI:
    config = load_config()

    app = FastAPI(
        title="竞品分析 Agent 协作系统",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.config = config

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
