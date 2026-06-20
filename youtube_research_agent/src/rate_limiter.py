"""STT hiz-siniri guvenligi: gunluk sayac + rastgele gecikme + cooldown.

Amac: trafigi insan-benzeri DAMLAMAYA cevirmek (bot-benzeri sel degil) -> IP banindan kacin.
Tum limitler config.stt.rate_limit'ten okunur (hardcode yok). Gunluk sayac dosyasi gitignore'da.
(Normal CLI modulu; workflow degil -> date/random kullanilabilir.)
"""
from __future__ import annotations

import json
import random
import time
from datetime import date

from src.utils import resolve_path


def _rl(config: dict) -> dict:
    return config.get("stt", {}).get("rate_limit", {})


def _count_path(config: dict):
    return resolve_path(_rl(config).get("daily_count_file", "data/.stt_daily_count.json"))


def _read(config: dict) -> tuple[str, int]:
    p = _count_path(config)
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return d.get("date", ""), int(d.get("count", 0))
        except Exception:
            pass
    return "", 0


def max_per_run(config: dict) -> int:
    return int(_rl(config).get("max_videos_per_run", 5))


def daily_cap(config: dict) -> int:
    return int(_rl(config).get("daily_video_cap", 20))


def check_daily_cap(config: dict) -> tuple[bool, int, int]:
    """(izin_var, bugun_kullanilan, kalan). Yeni gune gecince sayac sifirlanir."""
    cap = daily_cap(config)
    today = date.today().isoformat()
    d, count = _read(config)
    used = count if d == today else 0
    remaining = max(0, cap - used)
    return (used < cap, used, remaining)


def record_video_processed(config: dict) -> int:
    """Bugunku sayaci +1 yazar, yeni degeri dondurur."""
    p = _count_path(config)
    today = date.today().isoformat()
    d, count = _read(config)
    count = (count if d == today else 0) + 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"date": today, "count": count}), encoding="utf-8")
    return count


def get_random_delay(config: dict) -> int:
    """Video arasi RASTGELE saniye (sabit gecikme bot-benzeri; rastgele insan-benzeri)."""
    rl = _rl(config)
    lo = int(rl.get("min_delay_between_videos", 45))
    hi = int(rl.get("max_delay_between_videos", 90))
    if hi < lo:
        hi = lo
    return random.randint(lo, hi)


def trigger_cooldown(config: dict) -> int:
    """429/hata sonrasi cooldown_on_error_sec kadar bekler."""
    sec = int(_rl(config).get("cooldown_on_error_sec", 300))
    print(f"  ... COOLDOWN: hiz-siniri/hata sonrasi {sec} sn bekleniyor")
    time.sleep(sec)
    return sec
