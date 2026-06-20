"""Manuel transcript import (en temiz/ToS-uyumlu metin alma yolu).

Dosyadan UTF-8 metin okur, transcripts tablosuna upsert eder,
videos.status='TRANSCRIBED' yapar, data/transcripts/{video_id}.txt'e yazar.
"""
from __future__ import annotations

from pathlib import Path

from src import db
from src.utils import content_hash, resolve_path

# transcripts.source_type CHECK ile birebir ayni kume
ALLOWED_SOURCES = {
    "CAPTION_TRANSCRIPT", "AUDIO_STT", "MANUAL_TRANSCRIPT",
    "USER_UPLOADED_AUDIO", "AUTHORIZED_VIDEO",
}

UPSERT_TRANSCRIPT = """
INSERT INTO transcripts (video_id, source_type, language, text, char_count, content_hash)
VALUES (?,?,?,?,?,?)
ON CONFLICT(video_id) DO UPDATE SET
    source_type=excluded.source_type,
    language=excluded.language,
    text=excluded.text,
    char_count=excluded.char_count,
    content_hash=excluded.content_hash,
    updated_at=datetime('now');
"""


def save_transcript(conn, video_id: str, source_type: str, language: str, text: str) -> None:
    """transcripts'e upsert + status=TRANSCRIBED + dosyaya yaz (ortak yardimci)."""
    conn.execute(UPSERT_TRANSCRIPT, (
        video_id, source_type, language, text, len(text), content_hash(text),
    ))
    db.set_status(conn, video_id, "TRANSCRIBED")
    out = resolve_path("data/transcripts") / f"{video_id}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def import_transcript(conn, video_id: str, file_path: str, source: str, lang: str) -> None:
    """CLI: manuel transcript dosyasini sisteme alir."""
    if source not in ALLOWED_SOURCES:
        raise SystemExit(f"Gecersiz source: '{source}'. Izinli: {sorted(ALLOWED_SOURCES)}")

    if not conn.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,)).fetchone():
        raise SystemExit(f"Video DB'de yok: {video_id}. Once 'sync' calistirin.")

    p = Path(file_path)
    if not p.exists():
        raise SystemExit(f"Dosya bulunamadi: {file_path}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("Transcript dosyasi bos olamaz.")

    save_transcript(conn, video_id, source, lang, text)
    db.log_job(conn, video_id, "import-transcript", "ok", f"{source}, {len(text)} krk")
    print(f"  Import OK: {video_id} ({source}, {len(text)} karakter)")
