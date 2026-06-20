"""PRODUCT_SEARCH videolari icin manuel transcript import (en temiz yol).

source_type = MANUAL_TRANSCRIPT. SADECE source_mode=PRODUCT_SEARCH videoda calisir
(kanal videosuna yanlislikla urun transcript'i yazilmaz).
"""
from __future__ import annotations

from pathlib import Path

from src import db
from src.transcript_import import save_transcript


def import_product_transcript(conn, video_id: str, file_path: str, lang: str) -> None:
    row = conn.execute("SELECT source_mode FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    if not row:
        raise SystemExit(f"Video DB'de yok: {video_id}. Once 'search-products' calistirin.")
    if row["source_mode"] != "PRODUCT_SEARCH":
        raise SystemExit(
            f"Video PRODUCT_SEARCH degil (source_mode={row['source_mode']}). "
            "Kanal videosu icin 'import-transcript' kullanin."
        )
    p = Path(file_path)
    if not p.exists():
        raise SystemExit(f"Dosya bulunamadi: {file_path}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("Transcript dosyasi bos olamaz.")

    save_transcript(conn, video_id, "MANUAL_TRANSCRIPT", lang, text)   # status -> TRANSCRIBED
    db.log_job(conn, video_id, "import-product-transcript", "ok", f"{len(text)} krk")
    print(f"  Import OK: {video_id} (MANUAL_TRANSCRIPT, {len(text)} karakter, PRODUCT_SEARCH)")
