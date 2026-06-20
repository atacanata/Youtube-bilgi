"""Claim/Evidence veri omurgası — SQLite DDL (YTI-F0B).

F0A sözleşmesindeki 6 yeni tabloyu EKLEMELI ve IDEMPOTENT şekilde kurar:
  product_runs, evidence_segments, insight_claims,
  claim_evidence_links, agent_runs, audit_events

Kurallar (F0A v1.1 + F0B):
- Yalnız `CREATE TABLE/INDEX IF NOT EXISTS` (tekrar-koşulabilir).
- Mevcut 5 tabloya (videos/transcripts/analyses/job_log/search_cache) DOKUNMAZ; ALTER yok.
- TEXT birincil anahtarlar açıkça `TEXT NOT NULL PRIMARY KEY`.
- evidence_segments.run_id ve insight_claims.run_id: `NOT NULL` + product_runs FK (ON DELETE CASCADE).
- audit_events.event_id: `INTEGER PRIMARY KEY AUTOINCREMENT` (job_log ile tutarlı).
- İŞ MANTIĞI YOK — bu modül sadece şema kurar.
"""
from __future__ import annotations

import sqlite3

CLAIM_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS product_runs (
    run_id               TEXT NOT NULL PRIMARY KEY,
    category_key         TEXT NOT NULL,
    product_name         TEXT NOT NULL,
    run_type             TEXT NOT NULL
        CHECK (run_type IN ('EVIDENCE_EXTRACTION','CLAIM_SYNTHESIS',
                            'CONFLICT_RESOLUTION','EXPORT')),
    input_video_count    INTEGER DEFAULT 0,
    analyzed_video_count INTEGER DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING','DONE','PARTIAL','FAILED')),
    agent_run_id         TEXT,
    schema_version       TEXT NOT NULL DEFAULT 'f0',
    started_at           TEXT DEFAULT (datetime('now')),
    finished_at          TEXT,
    notes                TEXT
);

CREATE TABLE IF NOT EXISTS evidence_segments (
    segment_id            TEXT NOT NULL PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES product_runs(run_id) ON DELETE CASCADE,
    video_id              TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    transcript_id         TEXT,
    start_sec             REAL,
    end_sec               REAL,
    text                  TEXT NOT NULL,
    source_quality        TEXT NOT NULL
        CHECK (source_quality IN ('INDEPENDENT_PURCHASE','INDEPENDENT_EDITORIAL',
                            'REVIEW_UNIT','SPONSORED','BRAND_OFFICIAL','RETAILER','UNKNOWN')),
    category_attribute    TEXT NOT NULL,
    polarity              TEXT DEFAULT 'NEUTRAL'
        CHECK (polarity IN ('POSITIVE','NEGATIVE','NEUTRAL')),
    extraction_confidence REAL,
    created_by_agent_run  TEXT,
    created_at            TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS insight_claims (
    claim_id                 TEXT NOT NULL PRIMARY KEY,
    run_id                   TEXT NOT NULL REFERENCES product_runs(run_id) ON DELETE CASCADE,
    category_key             TEXT NOT NULL,
    product_name             TEXT NOT NULL,
    claim_type               TEXT NOT NULL
        CHECK (claim_type IN ('FEATURE_PRESENT','PRO','CON','PROBLEM',
                            'COMPARISON','PURCHASE_FACTOR','SPEC','RELIABILITY')),
    canonical_attribute      TEXT NOT NULL,
    claim_text               TEXT NOT NULL,
    video_count              INTEGER NOT NULL DEFAULT 0,
    independent_count        INTEGER NOT NULL DEFAULT 0,
    sponsored_count          INTEGER NOT NULL DEFAULT 0,
    unknown_count            INTEGER NOT NULL DEFAULT 0,
    conflict_status          TEXT NOT NULL DEFAULT 'NONE'
        CHECK (conflict_status IN ('NONE','MINOR','MAJOR')),
    conflict_note            TEXT,
    deterministic_confidence REAL NOT NULL DEFAULT 0,
    hemensec_ready           INTEGER NOT NULL DEFAULT 0,
    created_at               TEXT DEFAULT (datetime('now')),
    updated_at               TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS claim_evidence_links (
    claim_id    TEXT NOT NULL REFERENCES insight_claims(claim_id) ON DELETE CASCADE,
    segment_id  TEXT NOT NULL REFERENCES evidence_segments(segment_id) ON DELETE CASCADE,
    relation    TEXT NOT NULL DEFAULT 'SUPPORTS'
        CHECK (relation IN ('SUPPORTS','CONTRADICTS','QUALIFIES')),
    created_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (claim_id, segment_id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    agent_run_id TEXT NOT NULL PRIMARY KEY,
    agent_name   TEXT NOT NULL,
    agent_role   TEXT,
    model        TEXT,
    input_ref    TEXT,
    output_ref   TEXT,
    status       TEXT NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING','DONE','FAILED')),
    started_at   TEXT DEFAULT (datetime('now')),
    finished_at  TEXT,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT DEFAULT (datetime('now')),
    actor       TEXT NOT NULL,
    event_type  TEXT NOT NULL
        CHECK (event_type IN ('EVIDENCE_ADDED','CLAIM_CREATED','CLAIM_UPDATED',
                            'CONFLICT_FLAGGED','HEMENSEC_MARKED_READY','EXPORTED','OVERRIDE')),
    entity_type TEXT NOT NULL CHECK (entity_type IN ('segment','claim','run','export')),
    entity_id   TEXT NOT NULL,
    detail_json TEXT,
    reason      TEXT
);

CREATE INDEX IF NOT EXISTS idx_evidence_video  ON evidence_segments(video_id);
CREATE INDEX IF NOT EXISTS idx_evidence_attr   ON evidence_segments(category_attribute);
CREATE INDEX IF NOT EXISTS idx_evidence_run    ON evidence_segments(run_id);
CREATE INDEX IF NOT EXISTS idx_claims_product  ON insight_claims(product_name, category_key);
CREATE INDEX IF NOT EXISTS idx_claims_ready    ON insight_claims(hemensec_ready);
CREATE INDEX IF NOT EXISTS idx_claims_run      ON insight_claims(run_id);
CREATE INDEX IF NOT EXISTS idx_links_segment   ON claim_evidence_links(segment_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity    ON audit_events(entity_type, entity_id);
"""

# Bu paketin kurduğu yeni tablolar (test/doğrulama için tek kaynak).
NEW_TABLES = (
    "product_runs", "evidence_segments", "insight_claims",
    "claim_evidence_links", "agent_runs", "audit_events",
)


def ensure_claim_evidence_schema(conn: sqlite3.Connection) -> None:
    """6 claim/evidence tablosunu idempotent kurar (mevcut tablolara DOKUNMAZ)."""
    conn.executescript(CLAIM_EVIDENCE_SCHEMA)
    conn.commit()
