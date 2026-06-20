"""Claim/Evidence repository layer (YTI-F0B) — TEMEL CRUD, İŞ MANTIĞI YOK.

Yalnız insert/select. AŞAĞIDAKİLER BU PAKETTE YOK (sonraki paketler):
  confidence hesabı · claim extraction · evidence üretimi · agent · Hemensec export.

ID'ler stdlib `uuid4` ile üretilir (yeni bağımlılık yok). Şema `claim_evidence_schema.py`'de.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Optional


def _new_id(prefix: str) -> str:
    """Önek + uuid4 hex (örn. 'run_3f2a...'). Deterministik iş mantığı değil; sadece kimlik."""
    return f"{prefix}_{uuid.uuid4().hex}"


def _maybe_json(value: Any) -> Optional[str]:
    """dict/list ise JSON'a çevirir; str/None ise olduğu gibi bırakır."""
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


# --- product_runs -----------------------------------------------------------

def create_product_run(conn: sqlite3.Connection, category_key: str, product_name: str,
                       run_type: str, *, input_video_count: int = 0,
                       analyzed_video_count: int = 0, status: str = "RUNNING",
                       agent_run_id: Optional[str] = None, schema_version: str = "f0",
                       notes: Optional[str] = None) -> str:
    """Bir ürün analiz koşusu oluşturur; run_id döner."""
    run_id = _new_id("run")
    conn.execute(
        "INSERT INTO product_runs (run_id, category_key, product_name, run_type, "
        "input_video_count, analyzed_video_count, status, agent_run_id, schema_version, notes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (run_id, category_key, product_name, run_type, input_video_count,
         analyzed_video_count, status, agent_run_id, schema_version, notes),
    )
    conn.commit()
    return run_id


def get_product_run(conn: sqlite3.Connection, run_id: str) -> Optional[sqlite3.Row]:
    """run_id ile tek koşu döner (yoksa None)."""
    return conn.execute("SELECT * FROM product_runs WHERE run_id = ?", (run_id,)).fetchone()


# --- evidence_segments ------------------------------------------------------

def insert_evidence_segment(conn: sqlite3.Connection, run_id: str, video_id: str, text: str,
                            source_quality: str, category_attribute: str, *,
                            transcript_id: Optional[str] = None,
                            start_sec: Optional[float] = None,
                            end_sec: Optional[float] = None, polarity: str = "NEUTRAL",
                            extraction_confidence: Optional[float] = None,
                            created_by_agent_run: Optional[str] = None) -> str:
    """Bir kanıt segmenti ekler; segment_id döner. (run_id + video_id mevcut olmalı — FK.)"""
    segment_id = _new_id("seg")
    conn.execute(
        "INSERT INTO evidence_segments (segment_id, run_id, video_id, transcript_id, "
        "start_sec, end_sec, text, source_quality, category_attribute, polarity, "
        "extraction_confidence, created_by_agent_run) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (segment_id, run_id, video_id, transcript_id, start_sec, end_sec, text,
         source_quality, category_attribute, polarity, extraction_confidence,
         created_by_agent_run),
    )
    conn.commit()
    return segment_id


# --- insight_claims ---------------------------------------------------------

def insert_insight_claim(conn: sqlite3.Connection, run_id: str, category_key: str,
                         product_name: str, claim_type: str, canonical_attribute: str,
                         claim_text: str, *, video_count: int = 0, independent_count: int = 0,
                         sponsored_count: int = 0, unknown_count: int = 0,
                         conflict_status: str = "NONE", conflict_note: Optional[str] = None,
                         deterministic_confidence: float = 0.0, hemensec_ready: int = 0) -> str:
    """Bir iddia satırı ekler; claim_id döner. (Sayım/güven değerleri çağırana ait — hesap YOK.)"""
    claim_id = _new_id("clm")
    conn.execute(
        "INSERT INTO insight_claims (claim_id, run_id, category_key, product_name, claim_type, "
        "canonical_attribute, claim_text, video_count, independent_count, sponsored_count, "
        "unknown_count, conflict_status, conflict_note, deterministic_confidence, hemensec_ready) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (claim_id, run_id, category_key, product_name, claim_type, canonical_attribute,
         claim_text, video_count, independent_count, sponsored_count, unknown_count,
         conflict_status, conflict_note, deterministic_confidence, hemensec_ready),
    )
    conn.commit()
    return claim_id


# --- claim_evidence_links ---------------------------------------------------

def link_claim_evidence(conn: sqlite3.Connection, claim_id: str, segment_id: str,
                        relation: str = "SUPPORTS") -> None:
    """Bir iddiayı bir kanıt segmentine bağlar (çok-çok).

    Tekrar (claim_id, segment_id) bağı HEDEFLİ olarak yok sayılır (ON CONFLICT DO NOTHING).
    Geçersiz `relation` gibi CHECK ihlalleri sessizce YUTULMAZ — LOUD hata (IntegrityError) verir.
    (Geniş IGNORE bastırması yerine hedefli ON CONFLICT; CHECK/FK hataları yine yükselir.)
    """
    conn.execute(
        "INSERT INTO claim_evidence_links (claim_id, segment_id, relation) "
        "VALUES (?,?,?) ON CONFLICT(claim_id, segment_id) DO NOTHING",
        (claim_id, segment_id, relation),
    )
    conn.commit()


# --- agent_runs -------------------------------------------------------------

def insert_agent_run(conn: sqlite3.Connection, agent_name: str, *,
                     agent_role: Optional[str] = None, model: Optional[str] = None,
                     input_ref: Optional[str] = None, output_ref: Any = None,
                     status: str = "RUNNING", notes: Optional[str] = None) -> str:
    """Bir ajan/routine yürütmesi kaydeder; agent_run_id döner. (output_ref dict/list ise JSON'lanır.)"""
    agent_run_id = _new_id("ar")
    conn.execute(
        "INSERT INTO agent_runs (agent_run_id, agent_name, agent_role, model, input_ref, "
        "output_ref, status, notes) VALUES (?,?,?,?,?,?,?,?)",
        (agent_run_id, agent_name, agent_role, model, input_ref, _maybe_json(output_ref),
         status, notes),
    )
    conn.commit()
    return agent_run_id


# --- audit_events -----------------------------------------------------------

def insert_audit_event(conn: sqlite3.Connection, actor: str, event_type: str,
                       entity_type: str, entity_id: str, *, detail_json: Any = None,
                       reason: Optional[str] = None) -> int:
    """Append-only denetim olayı ekler; event_id (INTEGER) döner. (detail_json dict/list ise JSON'lanır.)"""
    cur = conn.execute(
        "INSERT INTO audit_events (actor, event_type, entity_type, entity_id, detail_json, reason) "
        "VALUES (?,?,?,?,?,?)",
        (actor, event_type, entity_type, entity_id, _maybe_json(detail_json), reason),
    )
    conn.commit()
    return cur.lastrowid


# --- okuma ------------------------------------------------------------------

def list_claims_for_product(conn: sqlite3.Connection, product_name: str,
                            category_key: Optional[str] = None) -> list:
    """Bir ürünün iddialarını döner (opsiyonel kategori filtresi). Toplulaştırma/hesap YOK."""
    if category_key is None:
        rows = conn.execute(
            "SELECT * FROM insight_claims WHERE product_name = ? ORDER BY created_at, claim_id",
            (product_name,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM insight_claims WHERE product_name = ? AND category_key = ? "
            "ORDER BY created_at, claim_id",
            (product_name, category_key),
        ).fetchall()
    return list(rows)
