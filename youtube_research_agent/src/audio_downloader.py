"""yt-dlp ile TEK videonun HAM audio stream'ini indirir (ffmpeg'siz mod).

ffmpeg'siz: yt-dlp ham bestaudio'yu indirir (m4a/webm/opus), DONUSTURMEZ.
faster-whisper (icindeki PyAV) bu ham dosyayi dogrudan cozer ve 16kHz mono'ya KENDI cevirir.
Boylece sistemde ffmpeg gerekmez.

ToS NOTU: yt-dlp ile YouTube audio indirme YouTube ToS'unda GRI alandir. Burada
kisisel STT amacli, TEK video, yeniden-yayin yok. Playlist/proxy/cookie/toplu indirme YOK.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.utils import resolve_path


def download_audio(video_id: str, url: str, tmp_dir: str = "tmp/audio") -> Path:
    """Ham bestaudio indirir; indirilen ses dosyasinin yolunu dondurur. Hata -> RuntimeError."""
    out_dir = resolve_path(tmp_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob(f"{video_id}.*"):        # eski kalintilari temizle
        try:
            f.unlink()
        except Exception:
            pass

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio/best", "--no-playlist",
        "-o", str(out_dir / f"{video_id}.%(ext)s"),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"yt-dlp indirme hatasi (kod {proc.returncode}): {tail[-300:]}")

    dosyalar = [f for f in out_dir.glob(f"{video_id}.*")
                if f.suffix.lower() not in (".part", ".ytdl")]
    if not dosyalar:
        raise RuntimeError("yt-dlp bitti ama ses dosyasi bulunamadi.")
    return max(dosyalar, key=lambda f: f.stat().st_size)   # en buyuk = ses dosyasi
