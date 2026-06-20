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
"""


def get_conn(db_path: str) -> sqlite3.Connection:
    """Baglanti acar (foreign_keys ON, Row factory)."""
    path = resolve_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    """Semayi (idempotent) olusturur."""
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


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
