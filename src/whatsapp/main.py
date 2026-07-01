from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from whatsapp.database import engine
from whatsapp.models.base import Base
from whatsapp.redis import close_redis
from whatsapp.routers import routers


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Create tables on startup (idempotent — safe for production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(title="WhatsApp MVP", version="0.1.0", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    for router in routers:
        app.include_router(router)

    return app


app = create_app()
