import hashlib
import io
import math
import wave

MAX_BYTES = 20 * 1024 * 1024
MAX_SECONDS = 15 * 60


def inspect_audio(data: bytes, filename: str) -> dict:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Audio must be nonempty and no larger than 20 MB")
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "wav":
        try:
            with wave.open(io.BytesIO(data)) as wav:
                channels = wav.getnchannels()
                rate = wav.getframerate()
                duration = wav.getnframes() / rate
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise ValueError("Invalid WAV recording") from exc
    elif suffix == "mp3":
        if not (data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)):
            raise ValueError("Invalid MP3 recording")
        try:
            from tinytag import TinyTag, TinyTagException
            tag = TinyTag.get(file_obj=io.BytesIO(data))
            rate, channels, duration = int(tag.samplerate), int(tag.channels), float(tag.duration)
        except (TinyTagException, TypeError, ValueError) as exc:
            raise ValueError("Invalid MP3 recording or unreadable metadata") from exc
    else:
        raise ValueError("Supported formats: WAV and MP3")
    if channels != 1:
        raise ValueError("The MVP accepts mono audio only")
    if not math.isfinite(duration) or duration <= 0 or duration > MAX_SECONDS:
        raise ValueError("Audio duration must be between 0 and 15 minutes")
    return {"duration_seconds": round(duration, 2), "sample_rate": rate, "channels": channels,
            "sha256": hashlib.sha256(data).hexdigest(), "mime": "audio/wav" if suffix == "wav" else "audio/mpeg"}
