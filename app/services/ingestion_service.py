from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import VoiceFile


class LiveATCIngestionService:
    """A-2 ingestion service skeleton for realtime and historical data pipelines."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_realtime_capture(
        self,
        *,
        file_name: str,
        file_path: str,
        start_time_utc: datetime,
        end_time_utc: datetime,
        source_url: str,
        file_size: int | None = None,
        duration_ms: int = 0,
    ) -> VoiceFile:
        record = VoiceFile(
            file_name=file_name,
            file_path=file_path,
            icao_code=settings.a2_icao_code,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            file_size=file_size,
            source_url=source_url,
            status=1,
            duration_ms=duration_ms,
            a3_process_status=0,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def register_historical_capture(
        self,
        *,
        file_name: str,
        source_url: str,
        start_time_utc: datetime,
        end_time_utc: datetime,
    ) -> VoiceFile:
        storage_dir = Path(settings.a2_audio_storage)
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(storage_dir / file_name)

        record = VoiceFile(
            file_name=file_name,
            file_path=file_path,
            icao_code=settings.a2_icao_code,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            source_url=source_url,
            status=0,
            a3_process_status=0,
            duration_ms=max(int((end_time_utc - start_time_utc).total_seconds() * 1000), 0),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)
