"""YouTube Data API search.list ile urun sorgularini arar (kota disiplini + cache).

Kurallar:
- search.list = 100 quota unit. maxResults=50, SAYFALAMA YOK.
- Ayni (query + bugun) search_cache'te ise API'ye GIDILMEZ.
- --limit: islenecek MAKSIMUM sorgu (varsayilan 5) — guvenlik freni.
- --dry-run: API/DB'ye dokunmadan kac sorgu/kac quota yazdirir.
- Tek tek calisir, paralel YOK.
"""
from __future__ import annotations

import os
import time

from src import db, query_builder
from src.utils import iso8601_duration_to_sec, today_str, video_url

SEARCH_COST = 100   # search.list birim maliyeti
ENRICH_BATCH = 50   # videos.list tek cagri max id

# source_mode='PRODUCT_SEARCH'; var olan satiri KORU, eksik urun alanlarini doldur.
UPSERT = """
INSERT INTO videos (
    video_id, channel_id, channel_name, title, description, published_at, url,
    source_mode, category_key, category_name, product_name, search_query, search_intent, status
) VALUES (?,?,?,?,?,?,?, 'PRODUCT_SEARCH', ?,?,?,?,?, 'DISCOVERED')
ON CONFLICT(video_id) DO UPDATE SET
    category_key  = COALESCE(videos.category_key,  excluded.category_key),
    category_name = COALESCE(videos.category_name, excluded.category_name),
    product_name  = COALESCE(videos.product_name,  excluded.product_name),
    search_query  = COALESCE(videos.search_query,  excluded.search_query),
    search_intent = COALESCE(videos.search_intent, excluded.search_intent),
    updated_at    = datetime('now');
"""


def _client():
    from googleapiclient.discovery import build
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY yok. youtube_research_agent/.env dosyasina ekleyin.")
    return build("youtube", "v3", developerKey=key)


def search_products(conn, config: dict, category_key: str, limit: int = 5,
                    dry_run: bool = False) -> int:
    """Urun sorgularini aratir; video adaylarini DB'ye yazar."""
    queries = query_builder.build_queries(config, category_key)
    today = today_str()
    secili = queries[:limit]                       # guvenlik freni

    yapilacak, cached = [], []
    for q in secili:
        (cached if db.search_is_cached(conn, q["search_query"], today) else yapilacak).append(q)
    tahmini_quota = len(yapilacak) * SEARCH_COST

    if dry_run:
        print(f"[DRY-RUN] kategori={category_key} | uretilen sorgu={len(queries)} | "
              f"--limit={limit} -> {len(secili)} degerlendirilecek")
        print(f"  API'ye gidecek: {len(yapilacak)} | cache'ten: {len(cached)} | "
              f"tahmini quota: {tahmini_quota} unit (+ ~1 unit/50 video zenginlestirme)")
        for q in yapilacak:
            print(f"   API   -> {q['search_query']}")
        for q in cached:
            print(f"   cache -> {q['search_query']}")
        return 0

    if not yapilacak:
        print("  Tum secili sorgular bugun zaten cache'te. API cagrisi yok, quota=0.")
        return 0

    yt = _client()
    bulunan = set()
    search_quota = 0
    for q in yapilacak:
        try:
            resp = yt.search().list(
                part="snippet", q=q["search_query"], type="video",
                maxResults=50, order="relevance",
            ).execute()
        except Exception as e:
            db.log_job(conn, None, "search-products", "error", f"{q['search_query']}: {e}")
            print(f"  ! Arama hatasi '{q['search_query']}': {e}")
            continue
        items = resp.get("items", [])
        for it in items:
            vid = it.get("id", {}).get("videoId")
            if not vid:
                continue
            sn = it.get("snippet", {})
            conn.execute(UPSERT, (
                vid, sn.get("channelId", ""), sn.get("channelTitle", ""),
                sn.get("title", ""), sn.get("description", ""), sn.get("publishedAt", ""),
                video_url(vid), q["category_key"], q["category_name"],
                q["product_name"], q["search_query"], q["search_intent"],
            ))
            bulunan.add(vid)
        conn.commit()
        db.write_search_cache(conn, q["search_query"], today, len(items), SEARCH_COST)
        search_quota += SEARCH_COST
        db.log_job(conn, None, "search-products", "ok", f"{q['search_query']}: {len(items)}")
        print(f"  OK '{q['search_query']}': {len(items)} video")
        time.sleep(1.0)                             # nazik: sorgular arasi gecikme

    enrich_quota = _enrich(conn, yt, sorted(bulunan))
    print(f"\n  Benzersiz video: {len(bulunan)} | search quota: {search_quota} | "
          f"enrich quota: {enrich_quota} | TOPLAM: {search_quota + enrich_quota} unit")
    return len(bulunan)


def _enrich(conn, yt, video_ids: list[str]) -> int:
    """videos.list ile view_count/duration doldurur (ucuz: 1 unit/50). Quota dondurur."""
    cost = 0
    for i in range(0, len(video_ids), ENRICH_BATCH):
        batch = video_ids[i:i + ENRICH_BATCH]
        try:
            resp = yt.videos().list(part="statistics,contentDetails", id=",".join(batch)).execute()
        except Exception as e:
            db.log_job(conn, None, "search-enrich", "error", str(e))
            continue
        cost += 1
        for it in resp.get("items", []):
            st = it.get("statistics", {})
            cd = it.get("contentDetails", {})
            conn.execute(
                "UPDATE videos SET view_count=?, like_count=?, comment_count=?, "
                "duration_sec=?, updated_at=datetime('now') WHERE video_id=?",
                (int(st.get("viewCount", 0) or 0), int(st.get("likeCount", 0) or 0),
                 int(st.get("commentCount", 0) or 0),
                 iso8601_duration_to_sec(cd.get("duration")), it["id"]),
            )
        conn.commit()
    return cost
