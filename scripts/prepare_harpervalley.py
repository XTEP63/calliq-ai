"""Fetch a small public CC BY 4.0 HarperValleyBank subset and build aligned mono calls.

Requires an authenticated GitHub CLI and FFmpeg. Original streams stay in ignored raw/.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import wave
from array import array
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.core.models import Segment, Transcript

REPO = "cricketclub/gridspace-stanford-harper-valley"
DEST = ROOT / "data/harpervalley"
TASKS = {"replace card", "transfer money", "check balance", "order checks", "pay bill", "reset password", "schedule appointment", "get branch hours"}


def api(path: str):
    output = subprocess.check_output(["gh", "api", f"repos/{REPO}/contents/data/{path}"], timeout=45)
    return json.loads(output)


def blob(path: str) -> bytes:
    item = api(path)
    if item.get("encoding") != "base64":
        output = subprocess.check_output(["gh", "api", f"repos/{REPO}/git/blobs/{item['sha']}"], timeout=60)
        item = json.loads(output)
        if item.get("encoding") != "base64":
            raise RuntimeError(f"GitHub did not return base64 content for {path}")
    return base64.b64decode(item["content"])


def read_wav(path: Path):
    with wave.open(str(path), "rb") as recording:
        if recording.getnchannels() != 1 or recording.getsampwidth() != 2:
            raise ValueError(f"Unsupported source WAV: {path}")
        return recording.getframerate(), array("h", recording.readframes(recording.getnframes()))


def mix(agent_path: Path, caller_path: Path, output: Path):
    agent_rate, agent = read_wav(agent_path)
    caller_rate, caller = read_wav(caller_path)
    if agent_rate != caller_rate:
        raise ValueError("Source sample rates differ; resample before mixing")
    # Corpus source streams are parallel channel recordings. Preserve their sample
    # positions, padding the shorter channel; never concatenate speakers in series.
    mixed = array("h", (max(-32768, min(32767, (a + b) // 2)) for a, b in zip_longest(agent, caller, fillvalue=0)))
    with wave.open(str(output), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(agent_rate)
        target.writeframes(mixed.tobytes())
    return len(mixed) / agent_rate


def main():
    raw = DEST / "raw"
    audio_dir = DEST / "audio"
    transcript_dir = DEST / "transcripts"
    for directory in (raw, audio_dir, transcript_dir): directory.mkdir(parents=True, exist_ok=True)
    entries = api("metadata")
    selected = {}
    for entry in entries[:100]:
        sid = entry["name"].removesuffix(".json")
        metadata = json.loads(blob(f"metadata/{sid}.json"))
        task = metadata.get("tasks", [{}])[0].get("task_type")
        if task in TASKS and task not in selected:
            selected[task] = (sid, metadata)
            print(f"Selected {task}: {sid}", flush=True)
        if len(selected) == len(TASKS): break
    if len(selected) < 6:
        raise RuntimeError("Could not find enough varied calls in the first 100 metadata files")
    index = []
    for task, (sid, metadata) in selected.items():
        agent_path = raw / f"{sid}-agent.wav"
        caller_path = raw / f"{sid}-caller.wav"
        if not agent_path.exists(): agent_path.write_bytes(blob(f"audio/agent/{sid}.wav"))
        if not caller_path.exists(): caller_path.write_bytes(blob(f"audio/caller/{sid}.wav"))
        source_transcript = json.loads(blob(f"transcript/{sid}.json"))
        mixed_path = raw / f"{sid}-mixed.wav"
        duration = mix(agent_path, caller_path, mixed_path)
        mp3_path = audio_dir / f"{sid}.mp3"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mixed_path), "-b:a", "64k", str(mp3_path)], check=True)
        segments = []
        for i, row in enumerate(source_transcript, 1):
            text = (row.get("human_transcript") or row.get("transcript") or "").strip()
            if not text: continue
            start = float(row.get("offset_ms", row.get("start_ms", 0))) / 1000
            end = start + float(row.get("duration_ms", 0)) / 1000
            role = row.get("speaker_role", "unknown")
            segments.append(Segment(segment_id=f"s{i}", speaker_id=role, role="customer" if role == "caller" else role,
                                    start_seconds=start, end_seconds=end, text=text,
                                    channel=row.get("channel_index")))
        transcript = Transcript(call_id=sid, source="HarperValleyBank human-corrected transcript (CC BY 4.0)",
                                duration_seconds=round(duration, 2), audio_channels=1,
                                transcription_provider="dataset human transcript", transcription_model="none",
                                speaker_mapping={"agent": "agent", "caller": "customer"}, segments=segments)
        (transcript_dir / f"{sid}.json").write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
        index.append({"call_id": sid, "task": task, "agent_speaker_id": metadata.get("agent", {}).get("speaker_id"),
                      "audio": f"audio/{sid}.mp3", "transcript": f"transcripts/{sid}.json"})
    (DEST / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(index)} calls in {DEST}")


if __name__ == "__main__": main()
