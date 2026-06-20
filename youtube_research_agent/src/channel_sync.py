"""Config'teki kanallari Data API ile cekip videos tablosuna idempotent yazar.

Upsert: yeni video -> insert (status=DISCOVERED). Var olan -> sadece metadata
(title/description/stats/thumbnail) guncellenir; status/score/transcript/analysis
KORUNUR. Boylece ayni sync tekrar calisinca veri bozulmaz, duplicate olmaz.
"""
from __future__ import annotations

from src import db, youtube_api

UPSERT = """
INSERT INTO videos (
    video_id, channel_id, channel_key, channel_name, title, description,
    published_at, duration_sec, view_count, like_count, comment_count,
    thumbnail_url, url, language_hint, status
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'DISCOVERED')
ON CONFLICT(video_id) DO UPDATE SET
    title=excluded.title,
    description=excluded.description,
    duration_sec=excluded.duration_sec,
    view_count=excluded.view_count,
    like_count=excluded.like_count,
    comment_count=excluded.comment_count,
    thumbnail_url=excluded.thumbnail_url,
    url=excluded.url,
    channel_name=excluded.channel_name,
    language_hint=excluded.language_hint,
    updated_at=datetime('now');
"""


def _find_channel(config: dict, key: str) -> dict | None:
    for ch in config.get("channels", []):
        if ch.get("key") == key:
            return ch
    return None


def sync_channel(conn, channel_cfg: dict, limit: int) -> int:
    """Tek kanali senkronize eder. Eklenen/guncellenen video sayisini dondurur."""
    cid = (channel_cfg.get("channel_id") or "").strip()
    key = channel_cfg.get("key")
    if not cid:
        msg = (f"channel_id bos: '{key}'. config.yaml'a kanal ID girin "
               f"(README'deki 'Kanal ID bulma'ya bakin).")
        db.log_job(conn, None, "sync", "error", msg)
        print("  ! " + msg)
        return 0

    uploads, api_title = youtube_api.get_uploads_playlist_id(cid)
    name = channel_cfg.get("name") or api_title
    lang = channel_cfg.get("language_hint", "")

    video_ids = youtube_api.list_upload_playlist_items(uploads, limit)
    details = youtube_api.get_video_details(video_ids)

    n = 0
    for v in details:
        conn.execute(UPSERT, (
            v["video_id"], cid, key, name, v["title"], v["description"],
            v["published_at"], v["duration_sec"], v["view_count"],
            v["like_count"], v["comment_count"], v["thumbnail_url"],
            v["url"], lang,
        ))
        n += 1
    conn.commit()
    db.log_job(conn, None, "sync", "ok", f"{key}: {n} video upsert")
    print(f"  {key}: {n} video islendi ({name})")
    return n


def sync_one(conn, config: dict, key: str, limit: int) -> int:
    ch = _find_channel(config, key)
    if not ch:
        raise SystemExit(f"Config'te kanal yok: '{key}'. config.yaml channels listesine bakin.")
    return sync_channel(conn, ch, limit)


def sync_all(conn, config: dict, limit: int) -> int:
    total = 0
    for ch in config.get("channels", []):
        if ch.get("enabled", True):
            total += sync_channel(conn, ch, limit)
    return total
