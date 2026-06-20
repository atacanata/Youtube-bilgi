"""Deterministik metadata skoru (1-10) ve statu gecisi.

Skor >= min_score_for_transcript  -> NEEDS_TRANSCRIPT
Skor <  min_score_for_transcript  -> SKIPPED
Sadece status='DISCOVERED' videolar skorlanir (idempotent; ilerlemis statuyu bozmaz).
"""
from __future__ import annotations

from src import db


def _matched(text: str | None, keywords: list[str]) -> list[str]:
    t = (text or "").lower()
    return [k for k in keywords if k.lower() in t]


def score_one(title: str, description: str, duration_sec: int, scoring: dict) -> tuple[float, str]:
    """Tek video icin (skor, gerekce) hesaplar."""
    high = scoring.get("keywords_high", [])
    med = scoring.get("keywords_medium", [])
    score = 0.0
    reasons: list[str] = []

    ht, hd = _matched(title, high), _matched(description, high)
    mt, md = _matched(title, med), _matched(description, med)
    if ht:
        score += 3.0
        reasons.append(f"baslikta yuksek anahtar +3 ({', '.join(ht[:3])})")
    if hd:
        score += 2.0
        reasons.append("aciklamada yuksek anahtar +2")
    if mt:
        score += 1.5
        reasons.append(f"baslikta orta anahtar +1.5 ({', '.join(mt[:3])})")
    if md:
        score += 1.0
        reasons.append("aciklamada orta anahtar +1")

    dmin = (duration_sec or 0) / 60.0
    if 5 <= dmin <= 90:
        score += 1.0
        reasons.append("sure 5-90 dk +1")
    elif 0 < dmin < 2:
        score -= 2.0
        reasons.append("cok kisa video -2")

    score = max(1.0, min(10.0, score))
    return round(score, 1), "; ".join(reasons) or "anahtar eslesme yok"


def score_videos(conn, config: dict, channel_key: str | None = None) -> int:
    """DISCOVERED videolari skorlar, statulerini gunceller."""
    scoring = config.get("scoring", {})
    threshold = config.get("settings", {}).get("min_score_for_transcript", 7)

    query = ("SELECT video_id, title, description, duration_sec "
             "FROM videos WHERE status = 'DISCOVERED' AND source_mode = 'CHANNEL'")
    params: list = []
    if channel_key:
        query += " AND channel_key = ?"
        params.append(channel_key)
    rows = conn.execute(query, params).fetchall()

    n_t = n_s = 0
    for r in rows:
        sc, reason = score_one(r["title"], r["description"], r["duration_sec"], scoring)
        new_status = "NEEDS_TRANSCRIPT" if sc >= threshold else "SKIPPED"
        db.set_status(conn, r["video_id"], new_status, score=sc, score_reason=reason)
        if new_status == "NEEDS_TRANSCRIPT":
            n_t += 1
        else:
            n_s += 1

    db.log_job(conn, None, "score", "ok",
               f"{len(rows)} skorlandi; NEEDS_TRANSCRIPT={n_t}, SKIPPED={n_s}")
    print(f"  Skorlandi: {len(rows)} | NEEDS_TRANSCRIPT: {n_t} | SKIPPED: {n_s}")
    return len(rows)
