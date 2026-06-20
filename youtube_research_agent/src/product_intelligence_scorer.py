"""Urun videolarini URUN-ISTIHBARAT degerine gore skorlar (relevance_score 1-10).

Kanal scorer.py'den AYRI dosya/mantik. SHORTS CEZASI YOK (kisa test videolari degerli).
Esik config'ten (product_research.min_relevance_score). relevance_score != (kanal) score.
"""
from __future__ import annotations

from src import db

INTENT_HIGH = {"sorunları", "uzun kullanım", "karşılaştırma", "vs", "pişman"}
INTENT_MID = {"inceleme", "review", "test"}
INTENT_LOW = {"kutudan çıkarma", "unboxing", "tanıtım", "reklam"}

TITLE_DEPTH = ["sorun", "şikayet", "pişman", "uzun kullan", "karşılaştır", " vs ", "alınır mı"]
TITLE_PROMO = ["unboxing", "kutudan çıkar", "reklam", "tanıtım", "sponsor"]
TITLE_TECH = ["test", "emiş", "paspas", "batarya", "ses", "performans", "halı", "watt", " pa", " db"]


def _has(text: str | None, term: str) -> bool:
    return term.lower() in (text or "").lower()


def _product_match(text: str | None, product: str | None) -> float:
    """Tam eslesme 3.0; cogu token 2.0; tek token 1.0; yok 0."""
    if not product:
        return 0.0
    t = (text or "").lower()
    p = product.lower()
    if p in t:
        return 3.0
    tokens = [w for w in p.split() if len(w) > 1]
    hit = sum(1 for w in tokens if w in t)
    if hit >= 2:
        return 2.0
    if hit == 1:
        return 1.0
    return 0.0


def score_one(row) -> tuple[float, str]:
    title, desc = row["title"], row["description"]
    product, category = row["product_name"], row["category_name"]
    intent = (row["search_intent"] or "").lower()
    dur = row["duration_sec"] or 0
    views = row["view_count"] or 0

    score = 0.0
    reasons: list[str] = []

    pt = _product_match(title, product)
    if pt:
        score += pt
        reasons.append(f"urun adi baslikta +{pt}")
    pd = min(1.5, _product_match(desc, product))
    if pd:
        score += pd
        reasons.append(f"urun adi aciklamada +{pd}")
    if category and _has((title or "") + " " + (desc or ""), category):
        score += 1.0
        reasons.append("kategori adi geciyor +1")

    if intent in INTENT_HIGH:
        score += 2.0
        reasons.append(f"degerli intent +2 ({intent})")
    elif intent in INTENT_MID:
        score += 1.5
        reasons.append(f"inceleme/test intent +1.5 ({intent})")
    elif intent in INTENT_LOW:
        score += 0.5
        reasons.append(f"tanitim intent +0.5 ({intent})")

    if any(_has(title, k) for k in TITLE_DEPTH):
        score += 1.0
        reasons.append("baslik derinlik vadediyor +1")
    if any(_has(title, k) for k in TITLE_PROMO):
        score -= 0.5
        reasons.append("baslik tanitim/unboxing -0.5")
    if any(_has(title, k) for k in TITLE_TECH):
        score += 0.5
        reasons.append("baslik teknik sinyal +0.5")

    if 4 * 60 <= dur <= 40 * 60:                 # ideal inceleme suresi (Shorts cezasi YOK)
        score += 1.0
        reasons.append("sure 4-40 dk +1")
    if views >= 50000:
        score += 0.5
        reasons.append("populer (>=50k) +0.5")

    score = max(1.0, min(10.0, round(score, 1)))
    return score, "; ".join(reasons) or "belirgin sinyal yok"


def score_products(conn, config: dict, category_key: str) -> int:
    """PRODUCT_SEARCH + DISCOVERED videolari skorlar; statu gunceller; dagilimi yazar."""
    threshold = config.get("product_research", {}).get("min_relevance_score", 6)
    rows = conn.execute(
        "SELECT video_id, title, description, product_name, category_name, search_intent, "
        "duration_sec, view_count FROM videos "
        "WHERE source_mode = 'PRODUCT_SEARCH' AND category_key = ? "
        "AND status IN ('DISCOVERED','NEEDS_TRANSCRIPT','SKIPPED')",  # esik degisince yeniden skorla
        (category_key,),
    ).fetchall()

    n_t = n_s = 0
    dist: dict[float, int] = {}
    for r in rows:
        sc, reason = score_one(r)
        new_status = "NEEDS_TRANSCRIPT" if sc >= threshold else "SKIPPED"
        db.set_status(conn, r["video_id"], new_status,
                      relevance_score=sc, relevance_reason=reason)
        dist[sc] = dist.get(sc, 0) + 1
        if new_status == "NEEDS_TRANSCRIPT":
            n_t += 1
        else:
            n_s += 1

    db.log_job(conn, None, "score-products", "ok",
               f"{len(rows)} skorlandi; esik={threshold}; NEEDS={n_t}, SKIP={n_s}")
    print(f"  Skorlandi: {len(rows)} | esik={threshold} | "
          f"NEEDS_TRANSCRIPT={n_t} | SKIPPED={n_s}")
    print("  relevance_score dagilimi:")
    for sc in sorted(dist, reverse=True):
        print(f"    {sc:>4} -> {dist[sc]} video")
    return len(rows)
