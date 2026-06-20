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
import sys

from src import (analyzer, channel_sync, db, product_insight_analyzer,
                 product_insight_import, product_intelligence_scorer,
                 product_report_builder, product_transcript_captions,
                 product_transcript_import, query_builder, report_builder,
                 scorer, transcript_captions, transcript_import, video_search)
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

    p_list = sub.add_parser("list", help="Statu/source_mode'e gore videolari listele")
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--source-mode", default=None, help="CHANNEL | PRODUCT_SEARCH")
    p_list.add_argument("--min-score", type=float, default=None,
                        help="relevance_score >= bu deger (parti filtresi)")

    # --- Sprint 2: urun/kategori komutlari ---
    p_bq = sub.add_parser("build-queries", help="Kategori/urun arama sorgularini uret (API yok)")
    p_bq.add_argument("--category", required=True)
    p_bq.add_argument("--dry-run", action="store_true")

    p_sp = sub.add_parser("search-products", help="Data API search.list ile video adaylari")
    p_sp.add_argument("--category", required=True)
    p_sp.add_argument("--limit", type=int, default=5, help="MAX sorgu (guvenlik freni)")
    p_sp.add_argument("--dry-run", action="store_true")

    p_scp = sub.add_parser("score-products", help="Urun videolarini relevance_score ile skorla")
    p_scp.add_argument("--category", required=True)

    p_rp = sub.add_parser("report-products", help="Kategori/urun raporu")
    p_rp.add_argument("--category", required=True)

    # --- Sprint 3: urun transcript + icgoru ---
    p_ipt = sub.add_parser("import-product-transcript", help="Urun videosuna manuel transcript")
    p_ipt.add_argument("--video-id", required=True)
    p_ipt.add_argument("--file", required=True)
    p_ipt.add_argument("--lang", default="tr")

    p_pc = sub.add_parser("product-captions", help="(gri/opsiyonel) urun videolarinda altyazi dene")
    p_pc.add_argument("--min-score", type=float, default=8.0)
    p_pc.add_argument("--limit", type=int, default=5)

    p_ap = sub.add_parser("analyze-products", help="Transcript'li urun videolari icin prompt uret (Claude routine girdisi)")
    p_ap.add_argument("--min-score", type=float, default=8.0)
    p_ap.add_argument("--limit", type=int, default=10)

    p_ipi = sub.add_parser("import-product-insight", help="Claude routine JSON icgorusunu DB'ye al")
    p_ipi.add_argument("--video-id", required=True)
    p_ipi.add_argument("--file", required=True)

    return p


def main() -> None:
    # Windows konsolu/pipe cp1254 olabilir -> Turkce/ozel karakterde cokmesin
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
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
            where, params = [], []
            if args.status:
                where.append("status = ?")
                params.append(args.status)
            if getattr(args, "source_mode", None):
                where.append("source_mode = ?")
                params.append(args.source_mode)
            if getattr(args, "min_score", None) is not None:
                where.append("relevance_score >= ?")
                params.append(args.min_score)
            if not where:
                raise SystemExit("list: en az --status, --source-mode veya --min-score verin.")
            rows = conn.execute(
                "SELECT video_id, score, relevance_score, status, source_mode, title "
                "FROM videos WHERE " + " AND ".join(where) +
                " ORDER BY COALESCE(relevance_score, score) DESC, published_at DESC",
                params,
            ).fetchall()
            print(f"{len(rows)} video")
            for r in rows:
                val = r["relevance_score"] if r["relevance_score"] is not None else r["score"]
                sc = f"{val:.1f}" if val is not None else "-"
                print(f"  [{sc:>4}] {r['source_mode']:<14} {r['status']:<16} "
                      f"{r['video_id']}  {(r['title'] or '')[:55]}")

        elif args.cmd == "build-queries":
            qs = query_builder.build_queries(config, args.category)
            print(f"build-queries: {len(qs)} sorgu | tahmini quota (hepsi calisirsa): "
                  f"{len(qs) * 100} unit"
                  + ("  [DRY-RUN: API/DB yok]" if args.dry_run else ""))
            for q in qs:
                print(f"  - {q['search_query']}   [intent={q['search_intent']}]")

        elif args.cmd == "search-products":
            video_search.search_products(conn, config, args.category, args.limit, args.dry_run)

        elif args.cmd == "score-products":
            product_intelligence_scorer.score_products(conn, config, args.category)

        elif args.cmd == "report-products":
            product_report_builder.build_product_report(conn, config, args.category)

        elif args.cmd == "import-product-transcript":
            product_transcript_import.import_product_transcript(
                conn, args.video_id, args.file, args.lang)

        elif args.cmd == "product-captions":
            product_transcript_captions.fetch_product_captions(
                conn, config, args.min_score, args.limit)

        elif args.cmd == "analyze-products":
            product_insight_analyzer.analyze_products(
                conn, config, args.min_score, args.limit)

        elif args.cmd == "import-product-insight":
            product_insight_import.import_product_insight(
                conn, args.video_id, args.file)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
