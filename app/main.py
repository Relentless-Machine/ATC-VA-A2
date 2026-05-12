from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.db.init_db import init_database
from app.db.session import engine
from app.services.ingestion_scheduler import liveatc_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_database(engine)
    if settings.a2_auto_start_scheduler:
        await liveatc_scheduler.start()
    yield
    await liveatc_scheduler.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)
