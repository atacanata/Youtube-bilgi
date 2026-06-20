"""Transcript'i olan PRODUCT_SEARCH videolari icin ANALIZ GIRDISI (prompt) uretir.

SISTEMDE API YOK. Analizi Claude Code'un kendisi (routine) yapar:
  1) Bu modul her video icin data/analyses/{video_id}_product_prompt.md uretir.
  2) Claude prompt'u (transcript dahil) okur, JSON icgoru cikarir.
  3) Sonuc 'import-product-insight' ile analyses.product_insights_json'a yazilir.
Bu modul analyses satiri YAZMAZ (analiz henuz yapilmadi); sadece girdi hazirlar.
"""
from __future__ import annotations

from src import db
from src.utils import resolve_path


def _template_for(category_key: str) -> str:
    """Kategoriye ozel prompt (prompts/product_insight_prompt_<kategori>.md) varsa onu,
    yoksa varsayilani okur. Boylece dikey supurge robot'tan FARKLI kriterlerle analiz edilir."""
    p = resolve_path(f"prompts/product_insight_prompt_{category_key}.md")
    if not p.exists():
        p = resolve_path("prompts/product_insight_prompt.md")
    return p.read_text(encoding="utf-8")


def _build(template: str, row) -> str:
    return (template
            .replace("{{product}}", row["product_name"] or "")
            .replace("{{category}}", row["category_name"] or "")
            .replace("{{title}}", row["title"] or "")
            .replace("{{url}}", row["url"] or "")
            .replace("{{transcript}}", row["text"] or ""))


def analyze_products(conn, config: dict, min_score: float, limit: int = 10) -> int:
    """Parti (TRANSCRIBED + PRODUCT_SEARCH + skor>=min) icin prompt dosyalari uretir."""
    rows = conn.execute(
        "SELECT v.video_id, v.product_name, v.category_name, v.category_key, v.title, v.url, tr.text "
        "FROM videos v JOIN transcripts tr ON tr.video_id = v.video_id "
        "WHERE v.source_mode = 'PRODUCT_SEARCH' AND v.status = 'TRANSCRIBED' "
        "AND v.relevance_score >= ? ORDER BY v.relevance_score DESC LIMIT ?",
        (min_score, limit),
    ).fetchall()
    if not rows:
        print("  Analiz edilecek video yok (PRODUCT_SEARCH + TRANSCRIBED + skor>=esik).")
        print("  Once transcript girin: import-product-transcript (veya product-captions).")
        return 0

    out_dir = resolve_path("data/analyses")
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    tmpl_cache: dict = {}
    for r in rows:
        ck = r["category_key"] or ""
        tmpl = tmpl_cache.setdefault(ck, _template_for(ck))
        out = out_dir / f"{r['video_id']}_product_prompt.md"
        out.write_text(_build(tmpl, r), encoding="utf-8")
        db.log_job(conn, r["video_id"], "analyze-products", "info", "prompt uretildi (Claude routine bekliyor)")
        print(f"  Prompt: data/analyses/{r['video_id']}_product_prompt.md")
        n += 1
    print(f"\n  {n} prompt uretildi. Sirada (Claude routine): prompt -> JSON icgoru "
          f"-> 'import-product-insight --video-id ID --file icgoru.json'")
    return n
