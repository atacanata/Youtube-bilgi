"""Analiz katmani.

Transcript'i olan (status=TRANSCRIBED) videolar icin:
  - ANTHROPIC_API_KEY YOKSA: data/analyses/{video_id}_prompt.md uretir (elle/sonra kullanilir),
    status TRANSCRIBED kalir.
  - ANTHROPIC_API_KEY VARSA: _call_claude_api iskeleti ile analiz eder, analyses'e yazar,
    status=ANALYZED. (Bu sprintte iskelet; ciktiyi detailed_summary'e koyar.)
"""
from __future__ import annotations

import os

from src import db
from src.utils import resolve_path


def _load_template() -> str:
    return resolve_path("prompts/analysis_prompt.md").read_text(encoding="utf-8")


def _build_prompt(template: str, row) -> str:
    return (template
            .replace("{{title}}", row["title"] or "")
            .replace("{{channel}}", row["channel_name"] or "")
            .replace("{{url}}", row["url"] or "")
            .replace("{{language}}", row["language"] or "")
            .replace("{{transcript}}", row["text"] or ""))


def analyze(conn, config: dict, limit: int = 10) -> int:
    """TRANSCRIBED videolari analiz eder veya prompt dosyasi uretir."""
    template = _load_template()
    rows = conn.execute(
        """SELECT v.video_id, v.title, v.channel_name, v.url, t.text, t.language
           FROM videos v JOIN transcripts t ON t.video_id = v.video_id
           WHERE v.status = 'TRANSCRIBED'
           ORDER BY v.score DESC
           LIMIT ?""", (limit,),
    ).fetchall()
    if not rows:
        print("  Analiz edilecek video yok (TRANSCRIBED + transcript gerekli).")
        return 0

    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    n = 0
    for r in rows:
        prompt = _build_prompt(template, r)
        if api_key:
            try:
                text = _call_claude_api(prompt, model, api_key)
                _save_analysis(conn, r["video_id"], text, model)
                db.set_status(conn, r["video_id"], "ANALYZED")
                db.log_job(conn, r["video_id"], "analyze", "ok", "claude api")
                print(f"  Analiz OK (API): {r['video_id']}")
                n += 1
                continue
            except Exception as e:
                db.log_job(conn, r["video_id"], "analyze", "error", f"api: {e}")
                print(f"  ! API hatasi {r['video_id']}: {e} -> prompt dosyasina dusuluyor")

        # API yok / hata -> prompt dosyasi uret (status TRANSCRIBED kalir)
        out = resolve_path("data/analyses") / f"{r['video_id']}_prompt.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(prompt, encoding="utf-8")
        db.log_job(conn, r["video_id"], "analyze", "info", "prompt uretildi (API yok)")
        print(f"  Prompt uretildi: data/analyses/{r['video_id']}_prompt.md")
        n += 1
    return n


def _save_analysis(conn, video_id: str, text: str, model: str) -> None:
    """analyses tablosuna upsert (iskelet: tam metni detailed_summary'e koyar)."""
    conn.execute(
        """INSERT INTO analyses (video_id, detailed_summary, model)
           VALUES (?,?,?)
           ON CONFLICT(video_id) DO UPDATE SET
             detailed_summary=excluded.detailed_summary,
             model=excluded.model, updated_at=datetime('now')""",
        (video_id, text, model),
    )
    conn.commit()


def _call_claude_api(prompt: str, model: str, api_key: str) -> str:
    """ISKELET: gercek Claude API cagrisi (Sprint 2'de bolumlere ayristirilacak)."""
    import requests
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]
