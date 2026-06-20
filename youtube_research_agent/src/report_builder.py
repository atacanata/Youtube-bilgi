"""Kanal icin Markdown rapor uretir (skor sirali; transcript/analiz durumu)."""
from __future__ import annotations

from src.utils import resolve_path


def build_report(conn, config: dict, channel_key: str):
    """data/reports/{channel_key}_report.md uretir, yolu dondurur."""
    ch = next((c for c in config.get("channels", []) if c.get("key") == channel_key), None)
    name = ch["name"] if ch else channel_key

    rows = conn.execute(
        """SELECT v.video_id, v.title, v.score, v.status, v.url,
                  t.source_type, a.short_summary, a.detailed_summary
           FROM videos v
           LEFT JOIN transcripts t ON t.video_id = v.video_id
           LEFT JOIN analyses   a ON a.video_id = v.video_id
           WHERE v.channel_key = ?
           ORDER BY v.score DESC, v.published_at DESC""", (channel_key,),
    ).fetchall()

    lines = [
        f"# {name} — Rapor", "",
        f"- Kanal anahtari: `{channel_key}`",
        f"- Islenen video: {len(rows)}", "",
        "## Videolar (skor sirali)", "",
    ]
    for r in rows:
        sc = f"{r['score']:.1f}" if r["score"] is not None else "-"
        lines.append(f"### [{sc}] {r['title']}")
        lines.append(f"- {r['url']}")
        lines.append(f"- status: `{r['status']}`")
        if r["source_type"]:
            lines.append(f"- transcript: VAR (source_type=`{r['source_type']}`)")
        else:
            lines.append("- transcript: YOK — **manuel transcript gerekli**")
        ozet = r["short_summary"] or r["detailed_summary"]
        if ozet:
            snippet = ozet.strip().replace("\n", " ")
            lines.append(f"- ozet: {snippet[:500]}")
        lines.append("")

    out = resolve_path("data/reports") / f"{channel_key}_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Rapor: data/reports/{channel_key}_report.md ({len(rows)} video)")
    return out
