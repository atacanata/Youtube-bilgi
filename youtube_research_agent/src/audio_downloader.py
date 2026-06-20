"""yt-dlp ile TEK videonun audio'sunu indirir (16kHz mono WAV).

ToS NOTU: yt-dlp ile YouTube audio indirme YouTube ToS'unda GRI alandir. Burada
kisisel STT amacli, TEK video, yeniden-yayin yok. Playlist/proxy/cookie/toplu indirme YOK.
ffmpeg sistemde kurulu olmali (wav cikarma + 16kHz mono donusumu icin).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import which

from src.utils import resolve_path


def ffmpeg_var_mi() -> bool:
    """ffmpeg PATH'te mi?"""
    return which("ffmpeg") is not None


def download_audio(video_id: str, url: str, tmp_dir: str = "tmp/audio") -> Path:
    """bestaudio -> 16kHz mono WAV indirir; wav yolunu dondurur. Hata -> RuntimeError."""
    out_dir = resolve_path(tmp_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{video_id}.wav"
    if wav.exists():
        wav.unlink()

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio", "--no-playlist",
        "--extract-audio", "--audio-format", "wav",
        "--postprocessor-args", "-ar 16000 -ac 1",
        "-o", str(out_dir / f"{video_id}.%(ext)s"),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"yt-dlp indirme hatasi (kod {proc.returncode}): {tail[-300:]}")
    if not wav.exists():
        raise RuntimeError("yt-dlp bitti ama WAV olusmadi — ffmpeg kurulu mu?")
    return wav
