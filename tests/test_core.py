import io
import wave
from datetime import date
from pathlib import Path

import pytest

from src.analytics.reports import report_html, summarize
from src.core.models import LLMJudgment, Transcript
from src.demo import demo_analyses
from src.evaluation.scoring import build_analysis
from src.ingestion.audio import inspect_audio
from src.storage.sqlite import Store
from src.transcription.providers import assign_roles, normalize_deepgram
from src.transcription.manual import parse_manual_transcript
from src.services.pipeline import confirm_roles
from src.services import pipeline


def wav_bytes(channels=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000 * channels)
    return output.getvalue()


def test_audio_validation():
    info = inspect_audio(wav_bytes(), "sample.wav")
    assert info["duration_seconds"] == 1.0 and info["channels"] == 1
    with pytest.raises(ValueError): inspect_audio(b"corrupt", "sample.wav")
    with pytest.raises(ValueError): inspect_audio(wav_bytes(2), "stereo.wav")
    with pytest.raises(ValueError): inspect_audio(wav_bytes(), "sample.pdf")
    with pytest.raises(ValueError): inspect_audio(b"ID3not-a-real-audio-file", "broken.mp3")
    sample = Path(__file__).parents[1] / "data/demo/audio/demo-escalation-06.mp3"
    mp3_info = inspect_audio(sample.read_bytes(), sample.name)
    assert mp3_info["channels"] == 1 and 20 < mp3_info["duration_seconds"] < 30


def test_deepgram_normalization_and_roles():
    response = {"results": {"channels": [{"alternatives": [{"words": [
        {"word": "hello", "start": 0, "end": 0.5, "speaker": 0},
        {"word": "thanks", "start": 1, "end": 1.5, "speaker": 1}]}]}]}}
    transcript = normalize_deepgram(response, "test", 2, "test")
    assert len(transcript.segments) == 2
    assigned = assign_roles(transcript, {"0": "agent", "1": "customer"})
    assert assigned.segments[0].role == "agent"
    assert transcript.segments[0].role == "unknown"
    assert confirm_roles(transcript, "0").segments[0].role == "agent"
    with pytest.raises(ValueError, match="cannot be confirmed"):
        confirm_roles(assign_roles(transcript, {"0": "agent", "1": "agent"}).model_copy(update={"segments": [transcript.segments[0]]}), "0")


def test_manual_transcript_requires_real_roles_and_times():
    transcript = parse_manual_transcript("0|1|agent|Hello\n1.2|3|customer|Please help | with my card")
    assert transcript.audio_channels is None
    assert transcript.segments[1].text == "Please help | with my card"
    assert transcript.call_id.startswith("manual-")
    for bad in ("0|1|agent|Hello", "0|1|agent|Hello\n1|2|unknown|Hi",
                "2|3|agent|Hello\n1|2|customer|Hi", "nan|2|agent|Hello\n2|3|customer|Hi"):
        with pytest.raises(ValueError):
            parse_manual_transcript(bad)


def test_scores_evidence_and_critical():
    cases = demo_analyses()
    assert cases[0].score == 100
    assert cases[2].score == 100  # identity is not applicable for public branch hours
    assert cases[1].critical_failure and cases[1].review_priority == "High"
    assert cases[-1].score_coverage < 100
    assert cases[-1].findings[-1].evidence_segment_ids == ["s6"]
    assert cases[0].findings[-1].evidence_segment_ids == ["s7"]
    judgment = LLMJudgment(primary_intent=cases[0].primary_intent,
                           classification_reason="test", findings=[f.model_copy(deep=True) for f in cases[0].findings],
                           coaching=cases[0].coaching)
    judgment.findings[0].evidence_segment_ids = ["does-not-exist"]
    with pytest.raises(ValueError, match="nonexistent"):
        build_analysis(cases[0].transcript, judgment, agent_id="test", origin="test", llm_provider="test", llm_model="test")


def test_storage_and_report(tmp_path):
    store = Store(str(tmp_path / "calliq.sqlite3"))
    cases = demo_analyses()
    assert store.get(cases[0].call_id) is None
    store.save(cases[0])
    assert store.get(cases[0].call_id).score == 100
    store.cache_put("transcript-key", "transcript", cases[0].transcript)
    assert Transcript.model_validate(store.cache_get("transcript-key", "transcript")) == cases[0].transcript
    assert store.cache_get("missing", "transcript") is None
    store.add_review(cases[0].call_id, "analyst", "Approved", "Reviewed evidence")
    assert store.reviews(cases[0].call_id)[0][1] == "Approved"
    assert summarize(cases)["calls"] == 6
    report = report_html(cases, "Agent Maya", date(2026, 11, 14), date(2026, 11, 19))
    assert "4 calls analyzed" in report and "Next goals" in report
    assert "0 calls analyzed" in report_html(cases, "Agent Maya", date(2026, 11, 1), date(2026, 11, 2))


def test_public_mode_does_not_share_live_analysis(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "public.sqlite3"))
    sample = demo_analyses()[0]
    judgment = LLMJudgment(primary_intent=sample.primary_intent, classification_reason=sample.classification_reason,
                           findings=sample.findings, coaching=sample.coaching)
    monkeypatch.setattr(pipeline, "groq_evaluate", lambda transcript: judgment)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("APP_MODE", "online")
    analysis, _ = pipeline.evaluate_transcript(sample.transcript, "Visitor agent", store)
    assert analysis.score == 100 and store.get(sample.call_id) is None
    monkeypatch.setenv("APP_MODE", "local")
    pipeline.evaluate_transcript(sample.transcript, "Visitor agent", store)
    assert store.get(sample.call_id) is not None
