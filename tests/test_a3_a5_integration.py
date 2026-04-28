"""
Tests for A-3 and A-5 Integration Services

Covers:
- A-3 processing request/status/retry
- A-5 track and annotator queries
- Cross-module synchronization
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import VoiceFile, VoiceSegment
from app.services.a3_integration_service import A3IntegrationService
from app.services.a5_integration_service import A5IntegrationService


@pytest.mark.asyncio
async def test_a3_request_processing(db_session: AsyncSession):
    """Test A-3 processing request."""
    # Setup: Create a voice file
    now = datetime.now(timezone.utc)
    voice_file = VoiceFile(
        file_name="test_vhhh_20260428T120000Z.mp3",
        file_path="/data/audio/test.mp3",
        icao_code="VHHH",
        start_time_utc=now,
        end_time_utc=now + timedelta(seconds=1800),
        file_size=1024000,
        source_url="https://liveatc.net/test",
        status=1,  # Ready
        a3_process_status=0,  # Not started
        duration_ms=1800000,
    )
    db_session.add(voice_file)
    await db_session.commit()
    await db_session.refresh(voice_file)

    # Execute: Request A-3 processing
    svc = A3IntegrationService(db_session)
    result = await svc.request_processing(voice_file.id)

    # Verify: Status should be updated to "processing" (1)
    assert result["voice_file_id"] == voice_file.id
    assert result["status"] == 1
    assert "A-3" in result["message"]
    assert "Processing request sent" in result["message"]

    # Verify: Database updated
    await db_session.refresh(voice_file)
    assert voice_file.a3_process_status == 1


@pytest.mark.asyncio
async def test_a3_get_processing_status(db_session: AsyncSession):
    """Test getting A-3 processing status."""
    # Setup: Create voice file with segments
    now = datetime.now(timezone.utc)
    voice_file = VoiceFile(
        file_name="test_status.mp3",
        file_path="/data/audio/status.mp3",
        icao_code="VHHH",
        start_time_utc=now,
        end_time_utc=now + timedelta(seconds=1800),
        file_size=512000,
        a3_process_status=2,  # Completed
        duration_ms=1800000,
    )
    db_session.add(voice_file)
    await db_session.commit()
    await db_session.refresh(voice_file)

    # Add segments
    for i in range(3):
        segment = VoiceSegment(
            voice_file_id=voice_file.id,
            relative_start=float(i * 10),
            relative_end=float((i + 1) * 10),
            abs_start_time=now + timedelta(seconds=i * 10),
            abs_end_time=now + timedelta(seconds=(i + 1) * 10),
            asr_content=f"Test ASR content {i}",
            is_annotated=(i == 0),  # Only first is annotated
        )
        db_session.add(segment)
    await db_session.commit()

    # Execute: Get status
    svc = A3IntegrationService(db_session)
    result = await svc.get_processing_status(voice_file.id)

    # Verify
    assert result["voice_file_id"] == voice_file.id
    assert result["status_text"] == "completed"
    assert result["segment_count"] == 3
    assert result["annotated_count"] == 1


@pytest.mark.asyncio
async def test_a3_retry_processing(db_session: AsyncSession):
    """Test A-3 processing retry with backoff."""
    # Setup: Create a failed voice file
    now = datetime.now(timezone.utc)
    voice_file = VoiceFile(
        file_name="test_retry.mp3",
        file_path="/data/audio/retry.mp3",
        icao_code="VHHH",
        start_time_utc=now,
        end_time_utc=now + timedelta(seconds=1800),
        a3_process_status=3,  # Failed
        error_log="Previous processing failed",
        duration_ms=1800000,
    )
    db_session.add(voice_file)
    await db_session.commit()
    await db_session.refresh(voice_file)

    # Execute: Retry
    svc = A3IntegrationService(db_session)
    result = await svc.retry_processing(voice_file.id, attempt=0)

    # Verify: Status reset to "processing"
    assert result["voice_file_id"] == voice_file.id
    assert result["attempt"] == 1
    assert result["delay_seconds"] >= 2  # At least base delay
    assert result["status"] == 1  # Processing

    # Verify: Database updated
    await db_session.refresh(voice_file)
    assert voice_file.a3_process_status == 1
    assert voice_file.error_log is None


@pytest.mark.asyncio
async def test_a3_sync_annotation_status(db_session: AsyncSession):
    """Test annotation status synchronization."""
    # Setup: Create voice file with mixed segment states
    now = datetime.now(timezone.utc)
    voice_file = VoiceFile(
        file_name="test_anno_sync.mp3",
        file_path="/data/audio/anno_sync.mp3",
        icao_code="VHHH",
        start_time_utc=now,
        end_time_utc=now + timedelta(seconds=1800),
        a3_process_status=2,  # Completed
        duration_ms=1800000,
    )
    db_session.add(voice_file)
    await db_session.commit()
    await db_session.refresh(voice_file)

    # Add segments: some with ASR, some without
    segments_data = [
        (0, 10, "ASR text 1", True),
        (10, 20, "ASR text 2", False),
        (20, 30, None, False),
    ]

    for start, end, asr, annotated in segments_data:
        segment = VoiceSegment(
            voice_file_id=voice_file.id,
            relative_start=float(start),
            relative_end=float(end),
            abs_start_time=now + timedelta(seconds=start),
            abs_end_time=now + timedelta(seconds=end),
            asr_content=asr,
            is_annotated=annotated,
        )
        db_session.add(segment)
    await db_session.commit()

    # Execute: Sync annotations
    svc = A3IntegrationService(db_session)
    result = await svc.sync_annotation_status(voice_file.id)

    # Verify: Should report 1 ready, 1 already annotated, 1 pending
    assert result["total_segments"] == 3
    assert result["ready_for_annotation"] == 1
    assert result["already_annotated"] == 1
    assert result["pending_asr"] == 1


@pytest.mark.asyncio
async def test_a5_list_audio_by_track(db_session: AsyncSession):
    """Test querying audio by track ID."""
    # Setup: Create voice files with track IDs
    now = datetime.now(timezone.utc)
    track_id = 12345

    for i in range(3):
        voice_file = VoiceFile(
            file_name=f"flight_track_{track_id}_{i}.mp3",
            file_path=f"/data/{i}.mp3",
            icao_code="VHHH",
            track_id=track_id,
            start_time_utc=now + timedelta(hours=i),
            end_time_utc=now + timedelta(hours=i, minutes=30),
            file_size=256000,
            a3_process_status=2,
            duration_ms=1800000,
        )
        db_session.add(voice_file)

    await db_session.commit()

    # Execute: Query by track
    svc = A5IntegrationService(db_session)
    result = await svc.list_audio_by_track(track_id)

    # Verify
    assert result["track_id"] == track_id
    assert result["file_count"] == 3
    assert len(result["files"]) == 3
    for file_info in result["files"]:
        assert file_info["track_id"] == track_id


@pytest.mark.asyncio
async def test_a5_list_audio_by_annotator(db_session: AsyncSession):
    """Test querying audio by annotator."""
    # Setup: Create segments with author_id
    now = datetime.now(timezone.utc)
    author_id = 999
    voice_file = VoiceFile(
        file_name="annotated_by_user.mp3",
        file_path="/data/annotated.mp3",
        icao_code="VHHH",
        start_time_utc=now,
        end_time_utc=now + timedelta(seconds=1800),
        a3_process_status=2,
        duration_ms=1800000,
    )
    db_session.add(voice_file)
    await db_session.commit()
    await db_session.refresh(voice_file)

    # Add segments by annotator
    for i in range(2):
        segment = VoiceSegment(
            voice_file_id=voice_file.id,
            author_id=author_id,
            relative_start=float(i * 10),
            relative_end=float((i + 1) * 10),
            abs_start_time=now + timedelta(seconds=i * 10),
            abs_end_time=now + timedelta(seconds=(i + 1) * 10),
            asr_content=f"Text {i}",
            annotation_text=f"Annotated {i}",
            is_annotated=True,
            label_type="instruction",
        )
        db_session.add(segment)
    await db_session.commit()

    # Execute: Query by annotator
    svc = A5IntegrationService(db_session)
    result = await svc.list_audio_by_annotator(author_id)

    # Verify
    assert result["author_id"] == author_id
    assert result["annotation_count"] == 2
    assert len(result["segments"]) == 2
    for seg in result["segments"]:
        assert seg["author_id"] == author_id
        assert seg["is_annotated"]


@pytest.mark.asyncio
async def test_a5_sync_annotations_to_a5(db_session: AsyncSession):
    """Test syncing annotations to A-5."""
    # Setup: Create file with annotated segments
    now = datetime.now(timezone.utc)
    voice_file = VoiceFile(
        file_name="sync_to_a5.mp3",
        file_path="/data/sync.mp3",
        icao_code="VHHH",
        start_time_utc=now,
        end_time_utc=now + timedelta(seconds=1800),
        duration_ms=1800000,
    )
    db_session.add(voice_file)
    await db_session.commit()
    await db_session.refresh(voice_file)

    # Add segments
    for i in range(2):
        is_anno = i == 0  # Only first is annotated
        segment = VoiceSegment(
            voice_file_id=voice_file.id,
            relative_start=float(i * 10),
            relative_end=float((i + 1) * 10),
            abs_start_time=now + timedelta(seconds=i * 10),
            abs_end_time=now + timedelta(seconds=(i + 1) * 10),
            annotation_text="Final text" if is_anno else None,
            is_annotated=is_anno,
        )
        db_session.add(segment)
    await db_session.commit()

    # Execute: Sync to A-5
    svc = A5IntegrationService(db_session)
    result = await svc.sync_annotations_to_a5(voice_file.id)

    # Verify
    assert result["voice_file_id"] == voice_file.id
    assert result["total_segments"] == 2
    assert result["synced_count"] == 1  # Only annotated ones


@pytest.mark.asyncio
async def test_a5_sync_annotations_from_a5(db_session: AsyncSession):
    """Test receiving annotation updates from A-5."""
    # Setup: Create segments
    now = datetime.now(timezone.utc)
    voice_file = VoiceFile(
        file_name="sync_from_a5.mp3",
        file_path="/data/sync_from.mp3",
        icao_code="VHHH",
        start_time_utc=now,
        end_time_utc=now + timedelta(seconds=1800),
        duration_ms=1800000,
    )
    db_session.add(voice_file)
    await db_session.commit()
    await db_session.refresh(voice_file)

    segment = VoiceSegment(
        voice_file_id=voice_file.id,
        relative_start=0,
        relative_end=10,
        abs_start_time=now,
        abs_end_time=now + timedelta(seconds=10),
    )
    db_session.add(segment)
    await db_session.commit()
    await db_session.refresh(segment)

    # Execute: Receive updates from A-5
    svc = A5IntegrationService(db_session)
    sync_data = {
        "annotations": [
            {
                "segment_id": segment.id,
                "author_id": 777,
                "annotation_text": "Updated from A-5",
                "label_type": "clearance",
            }
        ]
    }
    result = await svc.sync_annotations_from_a5(voice_file.id, sync_data)

    # Verify
    assert result["voice_file_id"] == voice_file.id
    assert result["updated_count"] == 1

    # Verify segment updated
    await db_session.refresh(segment)
    assert segment.author_id == 777
    assert segment.annotation_text == "Updated from A-5"
    assert segment.label_type == "clearance"
    assert segment.is_annotated


@pytest.mark.asyncio
async def test_a5_cross_module_report(db_session: AsyncSession):
    """Test generating cross-module system report."""
    from datetime import timezone as tz
    
    # Setup: Create mixed data with specific timestamps
    now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=tz.utc)
    report_start_time = now
    report_end_time = now + timedelta(hours=4)

    # Create files with different statuses
    statuses = [
        (2, "completed"),  # 1 completed
        (2, "completed"),  # 1 completed
        (3, "failed"),  # 1 failed
    ]

    for idx, (status, _) in enumerate(statuses):
        voice_file = VoiceFile(
            file_name=f"report_cross_{idx}.mp3",
            file_path=f"/data/report_cross_{idx}.mp3",
            icao_code="VHHH",
            start_time_utc=report_start_time + timedelta(hours=idx),
            end_time_utc=report_start_time + timedelta(hours=idx, minutes=30),
            a3_process_status=status,
            duration_ms=1800000,
        )
        db_session.add(voice_file)
        await db_session.commit()
        await db_session.refresh(voice_file)

        # Add segments
        for seg_idx in range(2):
            segment = VoiceSegment(
                voice_file_id=voice_file.id,
                relative_start=float(seg_idx * 15),
                relative_end=float((seg_idx + 1) * 15),
                abs_start_time=voice_file.start_time_utc + timedelta(seconds=seg_idx * 15),
                abs_end_time=voice_file.start_time_utc + timedelta(seconds=(seg_idx + 1) * 15),
                is_annotated=(idx == 0 and seg_idx == 0),  # Only one annotated
            )
            db_session.add(segment)
    await db_session.commit()

    # Execute: Generate report with the specific time window
    svc = A5IntegrationService(db_session)
    # Extend the time range to ensure all created files are included
    result = await svc.get_cross_module_report(report_start_time, report_end_time + timedelta(hours=1))

    # Verify - at least the 3 files we created
    assert result["file_count"] >= 3
    assert result["total_segments"] >= 6
    assert result["annotated_segments"] >= 1
