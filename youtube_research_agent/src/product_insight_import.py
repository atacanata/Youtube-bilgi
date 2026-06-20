"""Claude Code routine'inin urettigi urun-icgoru JSON'unu DB'ye alir.

Sistemde API yok; icgoru Claude tarafindan (prompt -> JSON) uretilir, bu komutla saklanir.
Kurallar:
- SADECE source_mode=PRODUCT_SEARCH video.
- Video'da transcript OLMALI (icgoru transcript'e dayanmali; uydurma onlenir).
- Dosya GECERLI JSON olmali.
- analyses.product_insights_json'a upsert + status=ANALYZED.
"""
from __future__ import annotations

import json
from pathlib import Path

from src import db


def import_product_insight(conn, video_id: str, file_path: str) -> None:
    v = conn.execute("SELECT source_mode FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    if not v:
        raise SystemExit(f"Video DB'de yok: {video_id}.")
    if v["source_mode"] != "PRODUCT_SEARCH":
        raise SystemExit(f"Video PRODUCT_SEARCH degil (source_mode={v['source_mode']}).")
    if not conn.execute("SELECT 1 FROM transcripts WHERE video_id = ?", (video_id,)).fetchone():
        raise SystemExit("Bu videoda transcript yok. Once transcript girin "
                         "(icgoru transcript'e dayanmali, uydurma yasak).")

    p = Path(file_path)
    if not p.exists():
        raise SystemExit(f"Dosya bulunamadi: {file_path}")
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        raise SystemExit("Icgoru dosyasi bos olamaz.")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Gecersiz JSON: {e}")

    text = json.dumps(obj, ensure_ascii=False)   # normalize
    conn.execute(
        "INSERT INTO analyses (video_id, product_insights_json, model) VALUES (?,?,?) "
        "ON CONFLICT(video_id) DO UPDATE SET "
        "product_insights_json=excluded.product_insights_json, "
        "model=excluded.model, updated_at=datetime('now')",
        (video_id, text, "claude-code-routine"),
    )
    db.set_status(conn, video_id, "ANALYZED")
    db.log_job(conn, video_id, "import-product-insight", "ok", f"{len(text)} krk JSON")
    print(f"  Icgoru alindi: {video_id} -> ANALYZED "
          f"({len(obj) if isinstance(obj, dict) else '?'} alan)")
