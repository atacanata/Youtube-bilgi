"""Konu basligindan YouTube videolarini ANAHTARSIZ bulur (yt-dlp ytsearch).

YouTube Data API anahtari GEREKMEZ. yt-dlp'nin kendi aramasini (ytsearchN)
kullanir; --flat-playlist sayesinde her videoyu tek tek acmadan hizli liste verir.

NOT: Filtreleme zayiftir (yalnizca alaka sirasi). Goruntulenme/tarih filtresi
gerekiyorsa Data API'li akis (eski src/search.py) gerekir.
"""
from __future__ import annotations

import json
import subprocess
import sys


def konu_ara(konu: str, sayi: int = 10) -> list[dict]:
    """Konu basligi icin video listesi dondurur.

    Donus: list[dict] -> {video_id, baslik, kanal, sure, url}
    Hata -> RuntimeError (Turkce).
    """
    if not konu or not konu.strip():
        raise RuntimeError("Bos konu basligi verilemez.")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        f"ytsearch{int(sayi)}:{konu}",
        "--flat-playlist",      # videolari tek tek acma -> hizli
        "--dump-json",          # her video icin tek satir JSON
        "--no-warnings",
        "--ignore-errors",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 and not proc.stdout.strip():
        tail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"yt-dlp arama hatasi: {tail[-300:]}")

    videolar = []
    for satir in proc.stdout.splitlines():
        satir = satir.strip()
        if not satir:
            continue
        try:
            e = json.loads(satir)
        except json.JSONDecodeError:
            continue
        vid = e.get("id")
        if not vid:
            continue
        videolar.append({
            "video_id": vid,
            "baslik": e.get("title") or "",
            "kanal": e.get("channel") or e.get("uploader") or "",
            "sure": e.get("duration"),                # saniye (olmayabilir)
            "url": e.get("url") or f"https://www.youtube.com/watch?v={vid}",
        })
    return videolar


if __name__ == "__main__":
    import sys as _s
    konu = _s.argv[1] if len(_s.argv) > 1 else "yerelde calisan yapay zeka"
    for i, v in enumerate(konu_ara(konu, 5), 1):
        print(f"{i}. {v['baslik'][:60]}  ({v['kanal']})  {v['url']}")
