from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import httpx
from sqlalchemy import select
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
        file_path: str | None = None,
        file_size: int | None = None,
    ) -> VoiceFile:
        if file_path is None:
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
            file_size=file_size,
            status=0,
            a3_process_status=0,
            duration_ms=max(int((end_time_utc - start_time_utc).total_seconds() * 1000), 0),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def has_source_url(self, source_url: str) -> bool:
        stmt = select(VoiceFile.id).where(VoiceFile.source_url == source_url).limit(1)
        row = await self.db.execute(stmt)
        return row.scalar_one_or_none() is not None

    async def register_historical_download(
        self,
        *,
        file_name: str,
        source_url: str,
        content: bytes,
        now: datetime | None = None,
    ) -> VoiceFile:
        now_utc = now or self.utc_now()
        storage_dir = Path(settings.a2_audio_storage) / "historical" / now_utc.strftime("%Y%m%d")
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = storage_dir / file_name
        file_path.write_bytes(content)
        end_time = now_utc
        start_time = now_utc
        return await self.register_historical_capture(
            file_name=file_name,
            source_url=source_url,
            start_time_utc=start_time,
            end_time_utc=end_time,
            file_path=str(file_path),
            file_size=len(content),
        )

    async def capture_realtime_stream(
        self,
        *,
        stream_url: str,
        timeout_seconds: int | None = None,
        max_bytes: int | None = None,
        request_headers: dict[str, str] | None = None,
    ) -> VoiceFile | None:
        capture_seconds = timeout_seconds or settings.a2_realtime_capture_seconds
        bytes_limit = max_bytes or settings.a2_realtime_capture_max_bytes
        now_utc = self.utc_now()
        storage_dir = Path(settings.a2_audio_storage) / "realtime" / now_utc.strftime("%Y%m%d")
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{settings.a2_icao_code.lower()}_{now_utc.strftime('%Y%m%dT%H%M%SZ')}.mp3"
        output_path = storage_dir / file_name

        timeout = httpx.Timeout(connect=10.0, read=10.0, write=10.0, pool=10.0)
        start_ts = monotonic()
        written = 0
        with output_path.open("wb") as f:
            async with httpx.AsyncClient(timeout=timeout, headers=request_headers) as client:
                async with client.stream("GET", stream_url, follow_redirects=True) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        if not chunk:
                            await asyncio.sleep(0)
                            continue
                        f.write(chunk)
                        written += len(chunk)
                        elapsed = monotonic() - start_ts
                        if written >= bytes_limit or elapsed >= capture_seconds:
                            break

        if written == 0:
            output_path.unlink(missing_ok=True)
            return None

        end_utc = self.utc_now()
        duration_ms = max(int((end_utc - now_utc).total_seconds() * 1000), 0)
        return await self.register_realtime_capture(
            file_name=file_name,
            file_path=str(output_path),
            start_time_utc=now_utc,
            end_time_utc=end_utc,
            source_url=stream_url,
            file_size=written,
            duration_ms=duration_ms,
        )

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)
