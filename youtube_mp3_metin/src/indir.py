"""YouTube videosunu yt-dlp ile MP3'e indirir (ffmpeg gerekir).

yt-dlp en iyi sesi ceker (bestaudio) ve ffmpeg ile MP3'e donusturur.
MP3 saklanir (silinmez); ayni video tekrar islenirse var olan MP3 kullanilir.

ToS NOTU: yt-dlp ile YouTube ses indirme GRI alandir. Burada kisisel/yerel
STT amacli kullanim varsayilir; yeniden-yayin yoktur.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def mp3_indir(video_id: str, url: str, hedef_dir: Path) -> Path:
    """Videoyu MP3 olarak hedef_dir altina indirir; MP3 dosyasinin yolunu dondurur.

    Var olan MP3 tekrar indirilmez (onbellek). Hata -> RuntimeError (Turkce).
    """
    hedef_dir = Path(hedef_dir)
    hedef_dir.mkdir(parents=True, exist_ok=True)
    mp3_yol = hedef_dir / f"{video_id}.mp3"

    if mp3_yol.exists() and mp3_yol.stat().st_size > 0:
        return mp3_yol                              # onbellek: zaten indirilmis

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-x",                                       # sadece ses
        "--audio-format", "mp3",
        "--audio-quality", "0",                     # en iyi kalite
        "-f", "bestaudio/best",
        "--no-playlist",
        "-o", str(hedef_dir / f"{video_id}.%(ext)s"),
        "--no-warnings",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()
        if "ffmpeg" in tail.lower() or "ffprobe" in tail.lower():
            raise RuntimeError(
                "MP3 donusumu icin ffmpeg gerekli ama bulunamadi.\n"
                "  Kurulum: Linux 'sudo apt install ffmpeg' | "
                "Windows 'winget install Gyan.FFmpeg' | macOS 'brew install ffmpeg'."
            )
        raise RuntimeError(f"yt-dlp indirme hatasi (kod {proc.returncode}): {tail[-300:]}")

    if not (mp3_yol.exists() and mp3_yol.stat().st_size > 0):
        # nadiren uzanti farkli olabilir -> en buyuk ses dosyasini bul
        adaylar = [f for f in hedef_dir.glob(f"{video_id}.*")
                   if f.suffix.lower() not in (".part", ".ytdl")]
        if not adaylar:
            raise RuntimeError("yt-dlp bitti ama MP3 dosyasi bulunamadi.")
        return max(adaylar, key=lambda f: f.stat().st_size)
    return mp3_yol
