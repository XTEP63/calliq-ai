"""Validate an explicitly supplied, role-labeled transcript without inventing audio metadata."""

import hashlib
import math

from src.core.models import Segment, Transcript

MAX_SEGMENTS = 300
MAX_CHARS = 30000
MAX_DURATION_SECONDS = 15 * 60


def parse_manual_transcript(raw: str) -> Transcript:
    if not raw.strip() or len(raw) > MAX_CHARS:
        raise ValueError("Enter a transcript of at most 30,000 characters")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) > MAX_SEGMENTS:
        raise ValueError("The transcript may contain at most 300 segments")
    segments = []
    previous_start = -1.0
    for number, line in enumerate(lines, 1):
        parts = line.split("|", 3)
        if len(parts) != 4:
            raise ValueError(f"Line {number}: use start|end|agent-or-customer|text")
        start_raw, end_raw, role_raw, text = (part.strip() for part in parts)
        try:
            start, end = float(start_raw), float(end_raw)
        except ValueError as exc:
            raise ValueError(f"Line {number}: times must be seconds as numbers") from exc
        role = role_raw.lower()
        if role not in {"agent", "customer"}:
            raise ValueError(f"Line {number}: role must be agent or customer")
        if start < previous_start:
            raise ValueError(f"Line {number}: segments must be ordered by start time")
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start or end > MAX_DURATION_SECONDS:
            raise ValueError(f"Line {number}: timestamps must be within 0–900 seconds and end after start")
        if not text:
            raise ValueError(f"Line {number}: text cannot be empty")
        segments.append(Segment(segment_id=f"s{number}", speaker_id=role, role=role,
                                start_seconds=start, end_seconds=end, text=text))
        previous_start = start
    if {s.role for s in segments} != {"agent", "customer"}:
        raise ValueError("Include both agent and customer turns before evaluating agent quality")
    canonical = "\n".join(f"{s.start_seconds}|{s.end_seconds}|{s.role}|{s.text}" for s in segments)
    call_id = "manual-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return Transcript(call_id=call_id, source="Authorized manual transcript", language="en",
                      duration_seconds=max(s.end_seconds for s in segments), audio_channels=None,
                      transcription_provider="manual", transcription_model="none",
                      speaker_mapping={"agent": "agent", "customer": "customer"}, segments=segments)
