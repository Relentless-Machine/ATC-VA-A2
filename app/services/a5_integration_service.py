"""
A-5 Integration Service

Manages interaction with A-5 database module:
- Track metadata lookup and linking
- User/Annotator resolution
- Cross-module data queries
- Annotation metadata synchronization
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import VoiceFile, VoiceSegment
from app.services.query_service import AudioQueryService

logger = logging.getLogger(__name__)


class A5IntegrationService:
    """Service for coordinating with A-5 database module."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.query_service = AudioQueryService(db)

    async def get_track_metadata(self, track_id: int) -> dict:
        """
        Retrieve track metadata from A-5 module.

        In production, this would call A-5 API. Currently returns template.
        
        RQ-A-5-50: Link with A-5 track API for flight metadata.
        """
        # In real implementation, call A-5 REST API:
        # response = await httpx_client.get(f"{A5_API_URL}/tracks/{track_id}")
        # return response.json()

        logger.info(f"Fetching track metadata for track_id={track_id}")

        # Template response (A-5 module responsibility)
        return {
            "track_id": track_id,
            "flight_number": f"FLT{track_id:04d}",  # Placeholder
            "aircraft_type": "B738",  # Placeholder
            "callsign": "CATHAY",  # Placeholder
            "departure": "VHHH",
            "arrival": "RJTT",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_user_metadata(self, author_id: int) -> dict:
        """
        Retrieve user/annotator metadata from A-5 module.

        In production, this would call A-5 API. Currently returns template.
        
        RQ-A-5-40: Link with A-5 user API for annotator info.
        """
        # In real implementation, call A-5 REST API:
        # response = await httpx_client.get(f"{A5_API_URL}/users/{author_id}")
        # return response.json()

        logger.info(f"Fetching user metadata for author_id={author_id}")

        # Template response (A-5 module responsibility)
        return {
            "author_id": author_id,
            "username": f"annotator_{author_id}",  # Placeholder
            "email": f"user{author_id}@example.com",  # Placeholder
            "role": "data_annotator",
            "active": True,
            "created_at": datetime.utcnow().isoformat(),
        }

    async def list_audio_by_track(self, track_id: int, limit: int = 50) -> dict:
        """
        List all audio segments associated with a specific flight track.

        RQ-A-2-40 + A-5 integration: Query segments by track_id.
        """
        query = select(VoiceFile).where(VoiceFile.track_id == track_id).order_by(VoiceFile.start_time_utc.asc()).limit(limit)

        result = await self.db.execute(query)
        files = result.scalars().all()

        if not files:
            logger.warning(f"No audio files found for track_id={track_id}")

        items = []
        for file in files:
            # Get segments for this file
            seg_query = select(VoiceSegment).where(VoiceSegment.voice_file_id == file.id)
            seg_result = await self.db.execute(seg_query)
            segments = seg_result.scalars().all()

            items.append(
                {
                    "voice_file_id": file.id,
                    "file_name": file.file_name,
                    "track_id": file.track_id,
                    "start_time_utc": file.start_time_utc.isoformat(),
                    "end_time_utc": file.end_time_utc.isoformat(),
                    "file_size": file.file_size,
                    "segment_count": len(segments),
                    "annotated_count": sum(1 for seg in segments if seg.is_annotated),
                    "a3_process_status": file.a3_process_status,
                    "source_url": file.source_url,
                }
            )

        return {
            "track_id": track_id,
            "file_count": len(files),
            "files": items,
        }

    async def list_audio_by_annotator(self, author_id: int, limit: int = 50) -> dict:
        """
        List all audio segments annotated by a specific user.

        RQ-A-2-40 + A-5 integration: Query segments by author_id.
        """
        query = (
            select(VoiceSegment)
            .where(VoiceSegment.author_id == author_id)
            .order_by(VoiceSegment.abs_start_time.asc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        segments = result.scalars().all()

        if not segments:
            logger.warning(f"No annotated segments found for author_id={author_id}")

        # Get unique files
        file_ids = {seg.voice_file_id for seg in segments}
        files = {}
        for file_id in file_ids:
            file = await self.query_service.get_voice_file(file_id)
            if file:
                files[file_id] = file

        items = []
        for seg in segments:
            file = files.get(seg.voice_file_id)
            items.append(
                {
                    "segment_id": seg.id,
                    "voice_file_id": seg.voice_file_id,
                    "file_name": file.file_name if file else "unknown",
                    "author_id": seg.author_id,
                    "abs_start_time": seg.abs_start_time.isoformat(),
                    "abs_end_time": seg.abs_end_time.isoformat(),
                    "duration": seg.duration,
                    "asr_content": seg.asr_content,
                    "annotation_text": seg.annotation_text,
                    "is_annotated": seg.is_annotated,
                    "label_type": seg.label_type,
                }
            )

        return {
            "author_id": author_id,
            "annotation_count": len(segments),
            "segments": items,
        }

    async def sync_annotations_to_a5(self, voice_file_id: int) -> dict:
        """
        Synchronize annotation data to A-5 database.

        Exports all segments with their annotation metadata for A-5 storage.
        
        RQ-A-5-50: Push annotation updates back to A-5 module.
        """
        voice_file = await self.query_service.get_voice_file(voice_file_id)
        if not voice_file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice file not found")

        query = select(VoiceSegment).where(VoiceSegment.voice_file_id == voice_file_id)
        result = await self.db.execute(query)
        segments = result.scalars().all()

        # In real implementation, POST to A-5 API:
        # response = await httpx_client.post(f"{A5_API_URL}/sync/annotations", json={...})

        synced_count = 0
        for seg in segments:
            if seg.is_annotated or seg.annotation_text:
                synced_count += 1
                logger.info(f"Synced segment_id={seg.id} to A-5 (author_id={seg.author_id}, label={seg.label_type})")

        logger.info(f"A-5 sync complete for voice_file_id={voice_file_id}: {synced_count}/{len(segments)} segments")

        return {
            "voice_file_id": voice_file_id,
            "total_segments": len(segments),
            "synced_count": synced_count,
            "message": f"Synchronized {synced_count} annotations to A-5 database",
            "timestamp": datetime.now(datetime.now().astimezone().tzinfo).isoformat(),
        }

    async def sync_annotations_from_a5(self, voice_file_id: int, sync_data: dict) -> dict:
        """
        Receive and apply annotation updates from A-5 database.

        Updates segment annotations based on A-5 source of truth.
        """
        voice_file = await self.query_service.get_voice_file(voice_file_id)
        if not voice_file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice file not found")

        annotations = sync_data.get("annotations", [])
        updated_count = 0

        for anno in annotations:
            segment_id = anno.get("segment_id")
            author_id = anno.get("author_id")
            annotation_text = anno.get("annotation_text")
            label_type = anno.get("label_type")

            stmt = select(VoiceSegment).where(VoiceSegment.id == segment_id, VoiceSegment.voice_file_id == voice_file_id)
            result = await self.db.execute(stmt)
            segment = result.scalar_one_or_none()

            if segment:
                if author_id:
                    segment.author_id = author_id
                if annotation_text:
                    segment.annotation_text = annotation_text
                if label_type:
                    segment.label_type = label_type
                segment.is_annotated = True

                self.db.add(segment)
                updated_count += 1
                logger.info(f"Updated segment_id={segment_id} with A-5 annotation data")

        await self.db.commit()

        logger.info(f"Applied {updated_count} annotation updates from A-5 for voice_file_id={voice_file_id}")

        return {
            "voice_file_id": voice_file_id,
            "updated_count": updated_count,
            "message": f"Applied {updated_count} annotation updates from A-5",
            "timestamp": datetime.now(datetime.now().astimezone().tzinfo).isoformat(),
        }

    async def get_cross_module_report(self, start_time: datetime, end_time: datetime) -> dict:
        """
        Generate cross-module report combining A-2, A-3, A-5 data.

        RQ-A-5-50: Provide aggregated system status to A-5.
        """
        # Get all voice files in time range
        query = select(VoiceFile).where(VoiceFile.start_time_utc >= start_time, VoiceFile.end_time_utc <= end_time)

        result = await self.db.execute(query)
        files = result.scalars().all()

        total_segments = 0
        annotated_segments = 0
        processed_files = 0
        failed_files = 0

        for file in files:
            if file.a3_process_status == 2:
                processed_files += 1
            elif file.a3_process_status == 3:
                failed_files += 1

            seg_query = select(VoiceSegment).where(VoiceSegment.voice_file_id == file.id)
            seg_result = await self.db.execute(seg_query)
            segments = seg_result.scalars().all()

            total_segments += len(segments)
            annotated_segments += sum(1 for seg in segments if seg.is_annotated)

        return {
            "time_range": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "file_count": len(files),
            "processed_files": processed_files,
            "failed_files": failed_files,
            "total_segments": total_segments,
            "annotated_segments": annotated_segments,
            "annotation_rate": (annotated_segments / total_segments * 100) if total_segments > 0 else 0,
            "generated_at": datetime.now(datetime.now().astimezone().tzinfo).isoformat(),
        }
