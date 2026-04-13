from datetime import datetime

from pydantic import BaseModel, Field


class A3SegmentPayload(BaseModel):
    relative_start: float
    relative_end: float
    asr_content: str | None = None
    vad_confidence: float | None = None
    model_info: str | None = None
    storage_tag: str | None = None


class A3CallbackRequest(BaseModel):
    voice_file_id: int = Field(..., description="t_a2_voice_files.id")
    process_status: int = Field(default=2, description="2: success, 3: failure")
    error_log: str | None = None
    segments: list[A3SegmentPayload] = Field(default_factory=list)


class A3CallbackResponse(BaseModel):
    voice_file_id: int
    updated_at: datetime
    segment_count: int
