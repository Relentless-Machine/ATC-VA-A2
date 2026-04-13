from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import VoiceFile, VoiceSegment


class AudioQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_segments(self, start_time: datetime, end_time: datetime) -> list[VoiceSegment]:
        stmt = select(VoiceSegment).where(
            and_(
                VoiceSegment.abs_start_time < end_time,
                VoiceSegment.abs_end_time > start_time,
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_voice_file(self, voice_file_id: int) -> VoiceFile | None:
        return await self.db.get(VoiceFile, voice_file_id)

    async def touch_last_access(self, file_record: VoiceFile) -> None:
        file_record.last_access_at = datetime.now(timezone.utc)
        self.db.add(file_record)
        await self.db.commit()

    async def iter_file_stream(self, file_path: str) -> AsyncGenerator[bytes, None]:
        chunk_size = settings.a2_chunk_size

        def _open_file() -> object:
            return open(file_path, "rb")

        fp = await asyncio.to_thread(_open_file)
        try:
            while True:
                data = await asyncio.to_thread(fp.read, chunk_size)
                if not data:
                    break
                yield data
        finally:
            await asyncio.to_thread(fp.close)
