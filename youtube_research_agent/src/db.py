"""SQLite sema + erisim katmani.

Onemli mimari ayrim:
  videos.status         -> SUREC / state machine (videonun nerede oldugu)
  transcripts.source_type -> PROVENANCE (metnin nereden geldigi)
Bu ikisi KARISTIRILMAZ. Metadata-only durum video.status ile temsil edilir;
transcripts satiri ancak gercek metin varsa olusur.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from src.utils import resolve_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    channel_key TEXT,
    channel_name TEXT,
    title TEXT,
    description TEXT,
    published_at TEXT,
    duration_sec INTEGER,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    thumbnail_url TEXT,
    url TEXT,
    language_hint TEXT,
    source_mode TEXT NOT NULL DEFAULT 'CHANNEL'
        CHECK (source_mode IN ('CHANNEL','PRODUCT_SEARCH')),
    category_key TEXT,
    category_name TEXT,
    product_name TEXT,
    search_query TEXT,
    search_intent TEXT,
    relevance_score REAL,
    relevance_reason TEXT,
    status TEXT NOT NULL DEFAULT 'DISCOVERED'
        CHECK (status IN (
            'DISCOVERED','SCORED','SKIPPED','NEEDS_TRANSCRIPT','TRANSCRIBING',
            'TRANSCRIBED','NEEDS_MANUAL_TRANSCRIPT','NEEDS_AUDIO_STT',
            'ANALYZING','ANALYZED','DONE','FAILED'
        )),
    score REAL,
    score_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcripts (
    video_id TEXT PRIMARY KEY REFERENCES videos(video_id) ON DELETE CASCADE,
    source_type TEXT NOT NULL
        CHECK (source_type IN (
            'CAPTION_TRANSCRIPT','AUDIO_STT','MANUAL_TRANSCRIPT',
            'USER_UPLOADED_AUDIO','AUTHORIZED_VIDEO'
        )),
    language TEXT,
    text TEXT NOT NULL,
    char_count INTEGER,
    content_hash TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analyses (
    video_id TEXT PRIMARY KEY REFERENCES videos(video_id) ON DELETE CASCADE,
    short_summary TEXT,
    detailed_summary TEXT,
    actionable_ideas_json TEXT,
    business_apply TEXT,
    hook_structure TEXT,
    agent_insights TEXT,
    product_insights_json TEXT,
    model TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT,
    stage TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok','error','info')),
    message TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_score ON videos(score);

CREATE TABLE IF NOT EXISTS search_cache (
    query TEXT NOT NULL,
    fetched_date TEXT NOT NULL,
    result_count INTEGER,
    quota_cost INTEGER,
    PRIMARY KEY (query, fetched_date)
);
"""


def get_conn(db_path: str) -> sqlite3.Connection:
    """Baglanti acar (foreign_keys ON, Row factory)."""
    path = resolve_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# Sprint 2'de eklenen videos kolonlari (eski DB'ler icin migration)
_NEW_VIDEO_COLUMNS = [
    ("source_mode", "TEXT NOT NULL DEFAULT 'CHANNEL' "
                    "CHECK (source_mode IN ('CHANNEL','PRODUCT_SEARCH'))"),
    ("category_key", "TEXT"),
    ("category_name", "TEXT"),
    ("product_name", "TEXT"),
    ("search_query", "TEXT"),
    ("search_intent", "TEXT"),
    ("relevance_score", "REAL"),
    ("relevance_reason", "TEXT"),
]


def migrate(conn: sqlite3.Connection) -> None:
    """Eski videos tablosuna eksik kolonlari ekler (veriyi BOZMADAN)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(videos)").fetchall()}
    for name, ddl in _NEW_VIDEO_COLUMNS:
        if name not in cols:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {name} {ddl}")
    # Sprint 3: analyses tablosuna urun icgoru JSON kolonu
    acols = {r[1] for r in conn.execute("PRAGMA table_info(analyses)").fetchall()}
    if "product_insights_json" not in acols:
        conn.execute("ALTER TABLE analyses ADD COLUMN product_insights_json TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_source_mode ON videos(source_mode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category_key)")
    conn.commit()


def init_db(db_path: str) -> sqlite3.Connection:
    """Semayi olusturur (idempotent) ve migration calistirir."""
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.commit()
    return conn


def search_is_cached(conn: sqlite3.Connection, query: str, date_str: str) -> bool:
    """query bugun (date_str) zaten arandi mi?"""
    return conn.execute(
        "SELECT 1 FROM search_cache WHERE query = ? AND fetched_date = ?",
        (query, date_str),
    ).fetchone() is not None


def write_search_cache(conn: sqlite3.Connection, query: str, date_str: str,
                       count: int, cost: int) -> None:
    """search_cache'e kayit (ayni gun ayni sorgu API'ye TEKRAR gitmesin)."""
    conn.execute(
        "INSERT OR REPLACE INTO search_cache (query, fetched_date, result_count, quota_cost) "
        "VALUES (?,?,?,?)", (query, date_str, count, cost),
    )
    conn.commit()


def set_status(conn: sqlite3.Connection, video_id: str, status: str, **extra) -> None:
    """videos.status (+ opsiyonel alanlar) gunceller, updated_at'i tazeler."""
    fields = ["status = ?", "updated_at = datetime('now')"]
    vals: list = [status]
    for k, v in extra.items():
        fields.append(f"{k} = ?")
        vals.append(v)
    vals.append(video_id)
    conn.execute(f"UPDATE videos SET {', '.join(fields)} WHERE video_id = ?", vals)
    conn.commit()


def log_job(conn: sqlite3.Connection, video_id, stage: str, status: str, message: str = "") -> None:
    """job_log'a satir ekler (status: ok|error|info)."""
    conn.execute(
        "INSERT INTO job_log (video_id, stage, status, message) VALUES (?,?,?,?)",
        (video_id, stage, status, message),
    )
    conn.commit()
