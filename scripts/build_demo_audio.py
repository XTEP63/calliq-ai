"""Build four clearly synthetic sample recordings on Windows using System.Speech and FFmpeg."""
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.demo import CASES

OUT = ROOT / "data" / "demo" / "audio"
OUT.mkdir(parents=True, exist_ok=True)
timings = {}
cases = [CASES[i] for i in (0, 1, 2, 5)]

with tempfile.TemporaryDirectory() as directory:
    tmp = Path(directory)
    items = [{"id": f"{ci}-{si}", "role": role, "text": text}
             for ci, case in enumerate(cases) for si, (role, text) in enumerate(case[4])]
    source = tmp / "segments.json"
    source.write_text(json.dumps(items), encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/synthesize_segments.ps1"),
                    str(source), str(tmp)], check=True)
    for ci, case in enumerate(cases):
        call_id = case[0]
        output = tmp / f"{call_id}.wav"
        intervals = []
        with wave.open(str(output), "wb") as target:
            for si, _ in enumerate(case[4]):
                with wave.open(str(tmp / f"{ci}-{si}.wav"), "rb") as piece:
                    if si == 0:
                        target.setparams(piece.getparams())
                    else:
                        assert piece.getparams()[:3] == target.getparams()[:3]
                    start = target.getnframes() / target.getframerate()
                    target.writeframes(piece.readframes(piece.getnframes()))
                    end = target.getnframes() / target.getframerate()
                    intervals.append([round(start, 2), round(end, 2)])
                    target.writeframes(b"\0" * (target.getframerate() // 3) * target.getsampwidth())
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(output),
                        "-ac", "1", "-b:a", "64k", str(OUT / f"{call_id}.mp3")], check=True)
        timings[call_id] = intervals

(ROOT / "data/demo/audio_timings.json").write_text(json.dumps(timings, indent=2) + "\n", encoding="utf-8")
print(f"Built {len(timings)} synthetic recordings in {OUT}")
