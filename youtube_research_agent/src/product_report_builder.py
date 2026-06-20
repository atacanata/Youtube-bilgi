"""Kategori/urun bazli Markdown rapor. Urun icgoruleri Sprint 3 placeholder."""
from __future__ import annotations

from src import query_builder
from src.utils import resolve_path


def build_product_report(conn, config: dict, category_key: str):
    """data/reports/{category_key}_report.md uretir."""
    cat = query_builder._find_category(config, category_key)
    name = cat.get("name", category_key) if cat else category_key

    # Bu kategoriye ait sorgularin bugune kadar harcadigi quota (search_cache)
    qset = {q["search_query"] for q in query_builder.build_queries(config, category_key)}
    quota = 0
    if qset:
        ph = ",".join("?" * len(qset))
        for (cost,) in conn.execute(
                f"SELECT quota_cost FROM search_cache WHERE query IN ({ph})", tuple(qset)):
            quota += cost or 0

    rows = conn.execute(
        "SELECT * FROM videos WHERE source_mode = 'PRODUCT_SEARCH' AND category_key = ?",
        (category_key,),
    ).fetchall()

    lines = [
        f"# {name} — Urun Istihbarat Raporu", "",
        f"- Kategori: {name} (`{category_key}`)",
        f"- Toplam bulunan video: {len(rows)}",
        f"- Harcanan arama quota (search_cache): {quota} unit", "",
    ]

    products = list(cat.get("products", [])) if cat else []
    for prod in products + ["(kategori-seviyesi)"]:
        if prod == "(kategori-seviyesi)":
            prows = [r for r in rows if not r["product_name"]]
        else:
            prows = [r for r in rows if r["product_name"] == prod]
        if not prows:
            continue
        prows.sort(key=lambda r: (r["relevance_score"] or 0), reverse=True)
        lines.append(f"## {prod}  ({len(prows)} video)")
        lines.append("")
        for r in prows:
            rs = f"{r['relevance_score']:.1f}" if r["relevance_score"] is not None else "-"
            views = f"{r['view_count']:,}" if r["view_count"] else "?"
            tr = conn.execute("SELECT source_type FROM transcripts WHERE video_id = ?",
                              (r["video_id"],)).fetchone()
            t_durum = (f"VAR ({tr[0]})" if tr else "YOK — manuel transcript veya caption gerekli")
            lines.append(f"### [{rs}] {r['title']}")
            lines.append(f"- {r['url']}")
            lines.append(f"- kanal: {r['channel_name']} | tarih: {(r['published_at'] or '')[:10]} "
                         f"| izlenme: {views}")
            lines.append(f"- sorgu: `{r['search_query']}` | intent: {r['search_intent']}")
            lines.append(f"- relevance_reason: {r['relevance_reason'] or '-'}")
            lines.append(f"- transcript: {t_durum}")
            lines.append("")
        lines.append("### Urun icgoruleri")
        lines.append("(Icgoruler transcript + analiz sonrasi doldurulacak — Sprint 3)")
        lines.append("")

    out = resolve_path("data/reports") / f"{category_key}_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Rapor: data/reports/{category_key}_report.md ({len(rows)} video)")
    return out
