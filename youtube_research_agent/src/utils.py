"""Ortak yardimcilar: yapilandirma, yollar, zaman, hash, sure donusumu.

Tum yollar paket kokune (youtube_research_agent/) gore cozulur; boylece
komut hangi dizinden calistirilirsa calistirilsin tutarli olur.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
import isodate
from dotenv import load_dotenv

# youtube_research_agent/  (src/ -> bir ust)
BASE_DIR = Path(__file__).resolve().parent.parent

# .env'i bir kez yukle (YOUTUBE_API_KEY, ANTHROPIC_API_KEY)
load_dotenv(BASE_DIR / ".env")


def resolve_path(rel: str | Path) -> Path:
    """Goreli yolu paket kokune gore mutlak yola cevirir."""
    p = Path(rel)
    return p if p.is_absolute() else (BASE_DIR / p)


def load_config(path: str | Path = "config.yaml") -> dict:
    """config.yaml'i okur ve sozluk dondurur."""
    with open(resolve_path(path), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_data_dirs() -> None:
    """data/ alt klasorlerini olusturur (yoksa)."""
    for d in ("data/transcripts", "data/analyses", "data/reports"):
        resolve_path(d).mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    """UTC ISO-8601 zaman damgasi (saniye hassasiyetinde)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_str() -> str:
    """Bugunun tarihi (YYYY-MM-DD) — search_cache anahtari icin."""
    return date.today().isoformat()


def content_hash(text: str) -> str:
    """Metnin SHA-256 ozeti (transcript tekrarini saptamak icin)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iso8601_duration_to_sec(duration: str | None) -> int:
    """YouTube ISO-8601 sure (orn. PT12M3S) -> saniye."""
    if not duration:
        return 0
    try:
        return int(isodate.parse_duration(duration).total_seconds())
    except Exception:
        return 0


def video_url(video_id: str) -> str:
    """Standart izleme URL'si."""
    return f"https://www.youtube.com/watch?v={video_id}"
