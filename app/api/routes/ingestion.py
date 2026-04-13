from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.ingestion_service import LiveATCIngestionService

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


class RealtimeRegisterRequest(BaseModel):
    file_name: str
    file_path: str
    start_time_utc: datetime
    end_time_utc: datetime
    source_url: str
    file_size: int | None = None
    duration_ms: int = 0


class HistoricalRegisterRequest(BaseModel):
    file_name: str
    source_url: str
    start_time_utc: datetime
    end_time_utc: datetime


@router.post("/realtime/register", status_code=status.HTTP_201_CREATED)
async def register_realtime_file(payload: RealtimeRegisterRequest, db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    svc = LiveATCIngestionService(db)
    row = await svc.register_realtime_capture(
        file_name=payload.file_name,
        file_path=payload.file_path,
        start_time_utc=payload.start_time_utc,
        end_time_utc=payload.end_time_utc,
        source_url=payload.source_url,
        file_size=payload.file_size,
        duration_ms=payload.duration_ms,
    )
    return {"voice_file_id": row.id}


@router.post("/historical/register", status_code=status.HTTP_201_CREATED)
async def register_historical_file(payload: HistoricalRegisterRequest, db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    svc = LiveATCIngestionService(db)
    row = await svc.register_historical_capture(
        file_name=payload.file_name,
        source_url=payload.source_url,
        start_time_utc=payload.start_time_utc,
        end_time_utc=payload.end_time_utc,
    )
    return {"voice_file_id": row.id}
