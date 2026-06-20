"""Transcript'i olan PRODUCT_SEARCH videolarini urun-istihbarat acisindan analiz eder.

Parti = TRANSCRIBED + PRODUCT_SEARCH + relevance_score >= min_score.
- ANTHROPIC_API_KEY YOKSA: data/analyses/{video_id}_product_prompt.md uretir, durur.
  (analyses satiri YAZILMAZ -> "analiz edilmemis videoya satir yok" kurali korunur.)
- VARSA: Claude API iskeleti cagrilir, JSON icgoru analyses.product_insights_json'a yazilir,
  status=ANALYZED.
Uydurma YOK: prompt 'sadece transkriptte geceni yaz' der.
"""
from __future__ import annotations

import os

from src import db
from src.utils import resolve_path


def _template() -> str:
    return resolve_path("prompts/product_insight_prompt.md").read_text(encoding="utf-8")


def _build(template: str, row) -> str:
    return (template
            .replace("{{product}}", row["product_name"] or "")
            .replace("{{category}}", row["category_name"] or "")
            .replace("{{title}}", row["title"] or "")
            .replace("{{url}}", row["url"] or "")
            .replace("{{transcript}}", row["text"] or ""))


def analyze_products(conn, config: dict, min_score: float, limit: int = 10) -> int:
    template = _template()
    rows = conn.execute(
        "SELECT v.video_id, v.product_name, v.category_name, v.title, v.url, tr.text "
        "FROM videos v JOIN transcripts tr ON tr.video_id = v.video_id "
        "WHERE v.source_mode = 'PRODUCT_SEARCH' AND v.status = 'TRANSCRIBED' "
        "AND v.relevance_score >= ? ORDER BY v.relevance_score DESC LIMIT ?",
        (min_score, limit),
    ).fetchall()
    if not rows:
        print("  Analiz edilecek video yok (PRODUCT_SEARCH + TRANSCRIBED + skor>=esik).")
        return 0

    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    n = 0
    for r in rows:
        prompt = _build(template, r)
        if api_key:
            try:
                out = _call_claude(prompt, model, api_key)
                conn.execute(
                    "INSERT INTO analyses (video_id, product_insights_json, model) VALUES (?,?,?) "
                    "ON CONFLICT(video_id) DO UPDATE SET "
                    "product_insights_json=excluded.product_insights_json, "
                    "model=excluded.model, updated_at=datetime('now')",
                    (r["video_id"], out, model),
                )
                conn.commit()
                db.set_status(conn, r["video_id"], "ANALYZED")
                db.log_job(conn, r["video_id"], "analyze-products", "ok", "claude api")
                print(f"  Analiz OK (API): {r['video_id']}")
                n += 1
                continue
            except Exception as e:
                db.log_job(conn, r["video_id"], "analyze-products", "error", f"api: {e}")
                print(f"  ! API hatasi {r['video_id']}: {e} -> prompt dosyasi")

        out_path = resolve_path("data/analyses") / f"{r['video_id']}_product_prompt.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt, encoding="utf-8")
        db.log_job(conn, r["video_id"], "analyze-products", "info", "prompt uretildi (API yok)")
        print(f"  Prompt uretildi: data/analyses/{r['video_id']}_product_prompt.md")
        n += 1
    return n


def _call_claude(prompt: str, model: str, api_key: str) -> str:
    """ISKELET: Claude API'den JSON icgoru. Cikti ham JSON metni olarak saklanir."""
    import requests
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 1500,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]
