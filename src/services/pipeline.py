import hashlib
import json
import os

from src.core.models import Analysis, Transcript
from src.evaluation.providers import groq_evaluate, ollama_evaluate
from src.evaluation.scoring import build_analysis
from src.ingestion.audio import inspect_audio
from src.storage.sqlite import Store
from src.transcription.providers import assign_roles, deepgram_transcribe, faster_whisper_transcribe


def _key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def transcribe_audio(data: bytes, filename: str, store: Store) -> tuple[Transcript, str]:
    audio = inspect_audio(data, filename)
    provider = os.getenv("TRANSCRIPTION_PROVIDER", "deepgram")
    model = "nova-3" if provider == "deepgram" else os.getenv("WHISPER_MODEL", "small.en")
    key = _key(audio["sha256"], provider, model, "diarize-latest", "en")
    persist = os.getenv("APP_MODE", "online") == "local"
    cached = store.cache_get(key, "transcript") if persist else None
    if cached:
        return Transcript.model_validate(cached), "Cached transcription"
    call_id = audio["sha256"][:16]
    if provider == "deepgram":
        transcript = deepgram_transcribe(data, audio["mime"], call_id, audio["duration_seconds"])
    elif provider == "faster-whisper":
        transcript = faster_whisper_transcribe(data, filename.rsplit(".", 1)[-1].lower(), call_id, audio["duration_seconds"])
    else:
        raise ValueError(f"Unsupported transcription provider: {provider}")
    if persist:
        store.cache_put(key, "transcript", transcript)
    return transcript, "Fresh transcription"


def evaluate_transcript(transcript: Transcript, agent_id: str, store: Store, origin: str = "Fresh live analysis") -> tuple[Analysis, str]:
    provider = os.getenv("LLM_PROVIDER", "groq")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b") if provider == "groq" else os.getenv("OLLAMA_MODEL", "qwen3:4b")
    key = _key(transcript.model_dump(mode="json"), provider, model, "evaluation-v2", "banking-v1", agent_id, origin)
    persist = os.getenv("APP_MODE", "online") == "local"
    cached = store.cache_get(key, "analysis") if persist else None
    if cached:
        return Analysis.model_validate(cached), "Cached evaluation"
    if provider == "groq":
        judgment = groq_evaluate(transcript)
    elif provider == "ollama":
        judgment = ollama_evaluate(transcript)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    analysis = build_analysis(transcript, judgment, agent_id=agent_id, origin=origin,
                              llm_provider=provider, llm_model=model)
    if persist:
        store.cache_put(key, "analysis", analysis)
        store.save(analysis)
    return analysis, "Fresh live analysis"


def confirm_roles(transcript: Transcript, agent_speaker: str) -> Transcript:
    speakers = {segment.speaker_id for segment in transcript.segments}
    if len(speakers) < 2 or "unknown" in speakers:
        raise ValueError("Speaker roles cannot be confirmed from this transcript; obtain diarization or an authorized role-labeled transcript")
    if agent_speaker not in speakers:
        raise ValueError("Agent speaker must exist in transcript")
    return assign_roles(transcript, {speaker: "agent" if speaker == agent_speaker else "customer" for speaker in speakers})
