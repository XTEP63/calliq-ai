from __future__ import annotations

import os
import httpx

from src.core.models import Segment, Transcript


def normalize_deepgram(response: dict, call_id: str, duration: float, source: str) -> Transcript:
    try:
        alternative = response["results"]["channels"][0]["alternatives"][0]
        words = alternative["words"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Deepgram returned no transcript") from exc
    if not words:
        raise ValueError("No speech was detected")
    groups: list[list[dict]] = []
    for word in words:
        speaker = str(word.get("speaker", "unknown"))
        if not groups or str(groups[-1][-1].get("speaker", "unknown")) != speaker or float(word["start"]) - float(groups[-1][-1]["end"]) > 1.2 or len(groups[-1]) >= 30:
            groups.append([])
        groups[-1].append(word)
    segments = []
    for index, group in enumerate(groups, 1):
        text = " ".join(w.get("punctuated_word") or w["word"] for w in group).strip()
        if text:
            segments.append(Segment(segment_id=f"s{index}", speaker_id=str(group[0].get("speaker", "unknown")),
                                    start_seconds=group[0]["start"], end_seconds=group[-1]["end"],
                                    text=text, confidence=sum(float(w.get("confidence", 0)) for w in group) / len(group)))
    if not segments:
        raise ValueError("Deepgram returned only empty speech")
    return Transcript(call_id=call_id, source=source, duration_seconds=duration, audio_channels=1,
                      transcription_provider="deepgram", transcription_model="nova-3",
                      speaker_mapping={}, segments=segments)


def deepgram_transcribe(data: bytes, mime: str, call_id: str, duration: float) -> Transcript:
    key = os.getenv("DEEPGRAM_API_KEY")
    if not key:
        raise RuntimeError("DEEPGRAM_API_KEY is missing. Add it in environment variables or Streamlit secrets.")
    with httpx.Client(timeout=120) as client:
        response = client.post("https://api.deepgram.com/v1/listen",
                               params={"model": "nova-3", "diarize_model": "latest", "smart_format": "true", "language": "en"},
                               headers={"Authorization": f"Token {key}", "Content-Type": mime}, content=data)
        response.raise_for_status()
    return normalize_deepgram(response.json(), call_id, duration, "uploaded audio")


def faster_whisper_transcribe(data: bytes, suffix: str, call_id: str, duration: float) -> Transcript:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install requirements-local.txt to enable Faster-Whisper") from exc
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"audio.{suffix}"
        path.write_bytes(data)
        model = WhisperModel(os.getenv("WHISPER_MODEL", "small.en"), device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
        raw, _ = model.transcribe(str(path), language="en", vad_filter=True)
        segments = [Segment(segment_id=f"s{i}", speaker_id="unknown", start_seconds=s.start,
                            end_seconds=s.end, text=s.text.strip()) for i, s in enumerate(raw, 1) if s.text.strip()]
    if not segments:
        raise ValueError("No speech was detected")
    return Transcript(call_id=call_id, source="uploaded audio", duration_seconds=duration, audio_channels=1,
                      transcription_provider="faster-whisper", transcription_model=os.getenv("WHISPER_MODEL", "small.en"),
                      segments=segments)


def assign_roles(transcript: Transcript, mapping: dict[str, str]) -> Transcript:
    data = transcript.model_copy(deep=True)
    data.speaker_mapping = mapping
    for segment in data.segments:
        segment.role = mapping.get(segment.speaker_id, "unknown")
    return data
