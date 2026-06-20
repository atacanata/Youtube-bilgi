"""OPSIYONEL / GRI ALAN: youtube-transcript-api ile altyazi metni denemesi.

Varsayilan KAPALI (config.settings.allow_unofficial_captions=false). Resmi degildir,
IP engellenebilir. Proxy/cookie/auth-bypass/browser-otomasyon EKLENMEZ.
Temiz yol: import-transcript (manuel) veya kendi/izinli videolarda STT (Sprint 2+).
"""
from __future__ import annotations

import time

from src import db
from src.transcript_import import save_transcript


def _bump_retry(conn, video_id: str) -> int:
    conn.execute(
        "UPDATE videos SET retry_count = retry_count + 1, updated_at = datetime('now') "
        "WHERE video_id = ?", (video_id,),
    )
    conn.commit()
    row = conn.execute("SELECT retry_count FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    return row[0] if row else 0


def fetch_captions(conn, config: dict, min_score: float, limit: int = 5) -> int:
    """NEEDS_TRANSCRIPT + score>=min_score videolarda altyazi metni dener (tek tek)."""
    settings = config.get("settings", {})
    if not settings.get("allow_unofficial_captions", False):
        print("  ! allow_unofficial_captions=false -> bu hat KAPALI (gri alan).")
        print("    Acmak icin config.yaml'i degistirin. Temiz alternatif: import-transcript.")
        return 0

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled, NoTranscriptFound,
            VideoUnavailable, RequestBlocked, IpBlocked,
        )
    except Exception as e:  # paket yoksa
        print(f"  ! youtube-transcript-api yuklenemedi: {e}")
        return 0

    rows = conn.execute(
        "SELECT video_id, language_hint FROM videos "
        "WHERE status = 'NEEDS_TRANSCRIPT' AND score >= ? "
        "ORDER BY score DESC LIMIT ?", (min_score, limit),
    ).fetchall()
    if not rows:
        print("  NEEDS_TRANSCRIPT (skor>=esik) video yok.")
        return 0

    api = YouTubeTranscriptApi()
    done = 0
    for r in rows:
        vid = r["video_id"]
        diller = [d for d in [r["language_hint"], "tr", "en"] if d]
        diller = list(dict.fromkeys(diller))
        db.set_status(conn, vid, "TRANSCRIBING")

        try:
            tlist = api.list(vid)
        except (TranscriptsDisabled, NoTranscriptFound):
            db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error="altyazi yok/devre disi")
            db.log_job(conn, vid, "captions", "info", "altyazi yok")
            print(f"  -- {vid}: altyazi yok -> NEEDS_MANUAL_TRANSCRIPT")
            time.sleep(30)
            continue
        except (RequestBlocked, IpBlocked):
            _handle_block(conn, vid)
            time.sleep(30)
            continue
        except Exception as e:
            _handle_error(conn, vid, e)
            time.sleep(30)
            continue

        # Tercih dilini bul, yoksa ilk mevcut
        chosen = None
        for d in diller:
            try:
                chosen = tlist.find_transcript([d])
                break
            except NoTranscriptFound:
                continue
        if chosen is None:
            available = list(tlist)
            chosen = available[0] if available else None
        if chosen is None:
            db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error="uygun altyazi yok")
            print(f"  -- {vid}: uygun altyazi yok -> NEEDS_MANUAL_TRANSCRIPT")
            time.sleep(30)
            continue

        try:
            data = chosen.fetch()
        except (RequestBlocked, IpBlocked):
            _handle_block(conn, vid)
            time.sleep(30)
            continue
        except Exception as e:
            _handle_error(conn, vid, e)
            time.sleep(30)
            continue

        text = " ".join(s.text for s in data).strip()
        if not text:
            db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error="bos altyazi")
            print(f"  -- {vid}: bos altyazi -> NEEDS_MANUAL_TRANSCRIPT")
            time.sleep(30)
            continue

        save_transcript(conn, vid, "CAPTION_TRANSCRIPT", chosen.language_code, text)
        db.log_job(conn, vid, "captions", "ok", f"{chosen.language_code} {len(text)} krk")
        print(f"  OK {vid}: {len(text)} krk ({chosen.language_code})")
        done += 1
        time.sleep(30)  # nazik: istekler arasi bekleme

    return done


def _handle_block(conn, vid: str) -> None:
    rc = _bump_retry(conn, vid)
    if rc >= 3:
        db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error="IP engeli (3 deneme)")
        print(f"  xx {vid}: IP engeli, 3 deneme doldu -> NEEDS_MANUAL_TRANSCRIPT")
    else:
        db.set_status(conn, vid, "NEEDS_TRANSCRIPT", last_error="IP engeli")
        print(f"  xx {vid}: IP engeli (retry {rc})")
    db.log_job(conn, vid, "captions", "error", "IP engeli")


def _handle_error(conn, vid: str, e: Exception) -> None:
    rc = _bump_retry(conn, vid)
    status = "FAILED" if rc >= 3 else "NEEDS_TRANSCRIPT"
    db.set_status(conn, vid, status, last_error=f"{type(e).__name__}: {e}")
    db.log_job(conn, vid, "captions", "error", f"{type(e).__name__}")
    print(f"  xx {vid}: {type(e).__name__} (retry {rc}) -> {status}")
