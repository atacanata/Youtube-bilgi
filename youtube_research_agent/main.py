"""YouTube Research Agent — CLI (Sprint 1).

Komutlar:
  init-db
  sync --channel <key> --limit N   |   sync --all --limit N
  score [--channel <key>]
  captions [--min-score X] [--limit N]   (gri/opsiyonel; config ile kapali)
  import-transcript --video-id ID --file path --source MANUAL_TRANSCRIPT --lang tr
  analyze [--limit N]
  report --channel <key>
  list --status <STATUS>
"""
from __future__ import annotations

import argparse

from src import (analyzer, channel_sync, db, report_builder, scorer,
                 transcript_captions, transcript_import)
from src.utils import ensure_data_dirs, load_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="youtube_research_agent",
        description="YouTube arastirma/analiz MVP (Sprint 1)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="SQLite semasini olustur")

    p_sync = sub.add_parser("sync", help="Kanal metadata cek (Data API)")
    g = p_sync.add_mutually_exclusive_group(required=True)
    g.add_argument("--channel", help="config'teki kanal key")
    g.add_argument("--all", action="store_true", help="tum enabled kanallar")
    p_sync.add_argument("--limit", type=int, default=None,
                        help="max video (varsayilan: config max_videos_per_channel)")

    p_score = sub.add_parser("score", help="Videolari skorla (DISCOVERED -> NEEDS_TRANSCRIPT/SKIPPED)")
    p_score.add_argument("--channel", default=None, help="sadece bu kanal key")

    p_cap = sub.add_parser("captions", help="(gri/opsiyonel) altyazi metni dene")
    p_cap.add_argument("--min-score", type=float, default=None)
    p_cap.add_argument("--limit", type=int, default=5)

    p_imp = sub.add_parser("import-transcript", help="Manuel transcript import")
    p_imp.add_argument("--video-id", required=True)
    p_imp.add_argument("--file", required=True)
    p_imp.add_argument("--source", default="MANUAL_TRANSCRIPT")
    p_imp.add_argument("--lang", default="tr")

    p_an = sub.add_parser("analyze", help="Transcript'li videolari analiz et / prompt uret")
    p_an.add_argument("--limit", type=int, default=10)

    p_rep = sub.add_parser("report", help="Kanal raporu uret")
    p_rep.add_argument("--channel", required=True)

    p_list = sub.add_parser("list", help="Statuye gore videolari listele")
    p_list.add_argument("--status", required=True)

    return p


def main() -> None:
    config = load_config()
    db_path = config["settings"]["db_path"]
    default_limit = config["settings"].get("max_videos_per_channel", 30)

    args = build_parser().parse_args()
    ensure_data_dirs()

    if args.cmd == "init-db":
        db.init_db(db_path)
        print("init-db OK:", db_path)
        return

    conn = db.get_conn(db_path)
    try:
        if args.cmd == "sync":
            limit = args.limit or default_limit
            if args.all:
                total = channel_sync.sync_all(conn, config, limit)
            else:
                total = channel_sync.sync_one(conn, config, args.channel, limit)
            print(f"sync OK: {total} video")

        elif args.cmd == "score":
            scorer.score_videos(conn, config, args.channel)

        elif args.cmd == "captions":
            ms = (args.min_score if args.min_score is not None
                  else config["settings"].get("min_score_for_transcript", 7))
            transcript_captions.fetch_captions(conn, config, ms, args.limit)

        elif args.cmd == "import-transcript":
            transcript_import.import_transcript(
                conn, args.video_id, args.file, args.source, args.lang)

        elif args.cmd == "analyze":
            analyzer.analyze(conn, config, args.limit)

        elif args.cmd == "report":
            report_builder.build_report(conn, config, args.channel)

        elif args.cmd == "list":
            rows = conn.execute(
                "SELECT video_id, score, status, title FROM videos "
                "WHERE status = ? ORDER BY score DESC, published_at DESC",
                (args.status,),
            ).fetchall()
            print(f"status={args.status}: {len(rows)} video")
            for r in rows:
                sc = f"{r['score']:.1f}" if r["score"] is not None else "-"
                print(f"  [{sc}] {r['video_id']}  {(r['title'] or '')[:70]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
