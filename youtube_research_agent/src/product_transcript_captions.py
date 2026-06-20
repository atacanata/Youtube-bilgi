"""OPSIYONEL / GRI: PRODUCT_SEARCH videolarinda altyazi metni denemesi.

Varsayilan KAPALI (config.settings.allow_unofficial_captions). Sprint 1 captions ile
ayni disiplin: tek tek, gecikmeli, retry'li. Proxy/cookie/auth/browser YOK.
Temiz alternatif: import-product-transcript.
"""
from __future__ import annotations

import time

from src import db
from src.batch_selector import select_product_batch
from src.transcript_import import save_transcript


def _retry(conn, vid: str, err: str = "IP engeli") -> None:
    conn.execute("UPDATE videos SET retry_count = retry_count + 1, updated_at = datetime('now') "
                 "WHERE video_id = ?", (vid,))
    conn.commit()
    rc = conn.execute("SELECT retry_count FROM videos WHERE video_id = ?", (vid,)).fetchone()[0]
    if rc >= 3:
        db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error=f"{err} (3 deneme)")
        print(f"  xx {vid}: {err}, 3 deneme doldu -> NEEDS_MANUAL_TRANSCRIPT")
    else:
        db.set_status(conn, vid, "NEEDS_TRANSCRIPT", last_error=err)
        print(f"  xx {vid}: {err} (retry {rc})")
    db.log_job(conn, vid, "product-captions", "error", err)


def fetch_product_captions(conn, config: dict, min_score: float, limit: int = 5) -> int:
    if not config.get("settings", {}).get("allow_unofficial_captions", False):
        print("  ! allow_unofficial_captions=false -> bu hat KAPALI (gri alan).")
        print("    Temiz alternatif: import-product-transcript.")
        return 0
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled, NoTranscriptFound, RequestBlocked, IpBlocked)
    except Exception as e:
        print(f"  ! youtube-transcript-api yuklenemedi: {e}")
        return 0

    rows = select_product_batch(conn, min_score, status="NEEDS_TRANSCRIPT", limit=limit)
    if not rows:
        print("  Uygun video yok (NEEDS_TRANSCRIPT + PRODUCT_SEARCH + skor>=esik).")
        return 0

    api = YouTubeTranscriptApi()
    done = 0
    for r in rows:
        vid = r["video_id"]
        db.set_status(conn, vid, "TRANSCRIBING")
        try:
            tlist = api.list(vid)
        except (TranscriptsDisabled, NoTranscriptFound):
            db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error="altyazi yok/devre disi")
            print(f"  -- {vid}: altyazi yok -> NEEDS_MANUAL_TRANSCRIPT")
            time.sleep(20); continue
        except (RequestBlocked, IpBlocked):
            _retry(conn, vid); time.sleep(20); continue
        except Exception as e:
            _retry(conn, vid, type(e).__name__); time.sleep(20); continue

        chosen = None
        for d in ("tr", "en"):
            try:
                chosen = tlist.find_transcript([d]); break
            except NoTranscriptFound:
                continue
        if chosen is None:
            av = list(tlist)
            chosen = av[0] if av else None
        if chosen is None:
            db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error="uygun altyazi yok")
            print(f"  -- {vid}: uygun altyazi yok -> NEEDS_MANUAL_TRANSCRIPT")
            time.sleep(20); continue

        try:
            data = chosen.fetch()
        except (RequestBlocked, IpBlocked):
            _retry(conn, vid); time.sleep(20); continue
        except Exception as e:
            _retry(conn, vid, type(e).__name__); time.sleep(20); continue

        text = " ".join(s.text for s in data).strip()
        if not text:
            db.set_status(conn, vid, "NEEDS_MANUAL_TRANSCRIPT", last_error="bos altyazi")
            print(f"  -- {vid}: bos altyazi -> NEEDS_MANUAL_TRANSCRIPT")
            time.sleep(20); continue

        save_transcript(conn, vid, "CAPTION_TRANSCRIPT", chosen.language_code, text)
        db.log_job(conn, vid, "product-captions", "ok", f"{chosen.language_code} {len(text)}")
        print(f"  OK {vid}: {len(text)} krk ({chosen.language_code})")
        done += 1
        time.sleep(20)
    return done
