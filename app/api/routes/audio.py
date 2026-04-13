from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.query_service import AudioQueryService

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])


@router.get("/stream", summary="Stream audio by UTC range")
async def stream_audio(
    start_time_utc: datetime = Query(...),
    end_time_utc: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if end_time_utc <= start_time_utc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_time_utc must be after start_time_utc")

    svc = AudioQueryService(db)
    segments = await svc.find_segments(start_time_utc, end_time_utc)
    if not segments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audio segment found in range")

    segment = segments[0]
    voice_file = await svc.get_voice_file(segment.voice_file_id)
    if not voice_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found")

    await svc.touch_last_access(voice_file)
    stream = svc.iter_file_stream(voice_file.file_path)

    headers = {
        "X-Voice-File-Id": str(voice_file.id),
        "X-Segment-Id": str(segment.id),
    }
    return StreamingResponse(stream, media_type="audio/mpeg", headers=headers, status_code=status.HTTP_206_PARTIAL_CONTENT)
