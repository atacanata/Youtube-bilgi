"""PRODUCT_SEARCH 'parti' secimi.

Parti = NEEDS_TRANSCRIPT + source_mode=PRODUCT_SEARCH + relevance_score >= esik.
Bu esik komut parametresinden (--min-score) gelir; config'teki HAVUZ esigi (7.0)
ile KARISTIRILMAZ. Varsayilan parti esigi cagirandan gelir (genelde 8.0).
"""
from __future__ import annotations


def select_product_batch(conn, min_score: float, status: str | None = None,
                         limit: int | None = None):
    """Parti kriterine uyan videolari relevance_score sirali dondurur."""
    q = "SELECT * FROM videos WHERE source_mode = 'PRODUCT_SEARCH' AND relevance_score >= ?"
    params: list = [min_score]
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY relevance_score DESC, view_count DESC"
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    return conn.execute(q, params).fetchall()
