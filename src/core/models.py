from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Segment(BaseModel):
    segment_id: str
    speaker_id: str
    role: str = "unknown"
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    channel: int | None = None

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("Segment ends before it starts")
        return self


class Transcript(BaseModel):
    call_id: str
    source: str
    recording_scope: Literal["unknown", "full", "opening_excerpt"] = "unknown"
    language: str = "en"
    duration_seconds: float = Field(ge=0)
    audio_channels: int | None = Field(default=None, ge=1)
    transcription_provider: str
    transcription_model: str
    speaker_mapping: dict[str, str] = Field(default_factory=dict)
    segments: list[Segment] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_segments(self):
        ids = [s.segment_id for s in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate segment IDs")
        return self


class CriterionFinding(BaseModel):
    criterion_id: str
    status: Status
    explanation: str = Field(min_length=3)
    evidence_segment_ids: list[str]
    suggested_correction: str = ""


class Coaching(BaseModel):
    title: str
    why_it_matters: str
    example_response: str
    next_step: str
    evidence_segment_ids: list[str]


class LLMJudgment(BaseModel):
    primary_intent: str
    classification_reason: str
    findings: list[CriterionFinding]
    coaching: list[Coaching]


class Analysis(BaseModel):
    call_id: str
    agent_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    origin: str
    primary_intent: str
    classification_reason: str
    findings: list[CriterionFinding]
    coaching: list[Coaching]
    score: float | None
    score_coverage: float
    critical_failure: bool
    review_priority: str
    review_reason: str
    transcript: Transcript
    rubric_version: str = "banking-v1"
    prompt_version: str = "evaluation-v2"
    llm_provider: str
    llm_model: str
