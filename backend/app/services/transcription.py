"""Groq Whisper transcription (D28, D39) with ffmpeg conversion/chunking.

Groq's speech endpoint takes mp3/mp4/mpeg/mpga/m4a/wav/webm up to 25 MB
(https://console.groq.com/docs/speech-to-text). Anything larger, or in a
format Groq does not take (ogg, flac), is converted to mono 16 kHz mp3 and
split into 10-minute segments with ffmpeg, transcribed per segment, and
stitched back together.
"""

from __future__ import annotations

import io
import logging
import subprocess
import tempfile
from pathlib import Path

from app.adapters.groq_client import groq_configured, groq_pool_from_settings
from app.core.config import Settings

log = logging.getLogger(__name__)

GROQ_AUDIO_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
GROQ_MAX_BYTES = 24 * 1024 * 1024  # stay under the documented 25 MB cap
# Chat dictation (composer mic) — short clips only; evidence uploads use MAX_AUDIO_BYTES.
MAX_TRANSCRIBE_BYTES = 10 * 1024 * 1024
SEGMENT_SECONDS = 600
WHISPER_MODEL = "whisper-large-v3"


def transcribe_audio(settings: Settings, filename: str, body: bytes) -> str:
    if not groq_configured(settings):
        return (
            f"[Scripted transcription for {filename} - set GROQ_API_KEY for Whisper. "
            "No audio was transcribed.]"
        )
    ext = Path(filename).suffix.lower() or ".wav"
    if ext in GROQ_AUDIO_FORMATS and len(body) <= GROQ_MAX_BYTES:
        return _transcribe_bytes(settings, body, ext)
    return _transcribe_via_ffmpeg(settings, body, ext)


def _transcribe_bytes(settings: Settings, body: bytes, ext: str) -> str:
    pool = groq_pool_from_settings(settings)
    assert pool is not None
    buf = io.BytesIO(body)
    buf.name = f"upload{ext}"

    def _call(client):
        result = client.audio.transcriptions.create(file=buf, model=WHISPER_MODEL)
        return (result.text or "").strip()

    return pool.execute(_call)


def _transcribe_via_ffmpeg(settings: Settings, body: bytes, ext: str) -> str:
    """Convert to mono 16 kHz mp3, segment, transcribe each segment in order."""
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / f"source{ext}"
        source.write_bytes(body)
        pattern = Path(tmp) / "segment-%04d.mp3"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", str(source),
                "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
                "-f", "segment", "-segment_time", str(SEGMENT_SECONDS),
                str(pattern),
            ],
            check=True,
            capture_output=True,
        )
        segments = sorted(Path(tmp).glob("segment-*.mp3"))
        if not segments:
            raise ValueError("ffmpeg produced no audio segments")
        parts = []
        for segment in segments:
            parts.append(_transcribe_bytes(settings, segment.read_bytes(), ".mp3"))
            log.info("transcribed %s (%d bytes)", segment.name, segment.stat().st_size)
        return "\n".join(p for p in parts if p).strip()
