"""Kategori + urun + intent -> YouTube arama sorgulari (kota dostu).

Urun basina en fazla `default_intents_per_product` intent (kota kisiti).
Ek olarak az sayida kategori-seviyesi sorgu eklenir.
"""
from __future__ import annotations

# Kategori-seviyesi (urun bagimsiz) sorgular — kucuk tutuldu (kota)
CATEGORY_INTENTS = ["en iyi modeller", "karşılaştırma"]


def _find_category(config: dict, category_key: str) -> dict | None:
    for c in config.get("product_research", {}).get("categories", []):
        if c.get("key") == category_key:
            return c
    return None


def build_queries(config: dict, category_key: str) -> list[dict]:
    """Sorgu sozlukleri listesi dondurur:
    {category_key, category_name, product_name, search_query, search_intent}
    """
    cat = _find_category(config, category_key)
    if not cat:
        raise SystemExit(f"Kategori bulunamadi: '{category_key}'. config.yaml product_research'e bakin.")
    if not cat.get("enabled", False):
        raise SystemExit(f"Kategori enabled degil: '{category_key}'.")

    pr = config.get("product_research", {})
    max_intents = pr.get("default_intents_per_product", 4)
    intents = (cat.get("search_intents") or [])[:max_intents]   # kota kisiti
    name = cat.get("name", category_key)

    queries: list[dict] = []
    for product in cat.get("products", []):
        for intent in intents:
            queries.append({
                "category_key": category_key,
                "category_name": name,
                "product_name": product,
                "search_query": f"{product} {intent}",
                "search_intent": intent,
            })
    # kategori-seviyesi (urun bagimsiz) birkac sorgu
    for intent in CATEGORY_INTENTS:
        queries.append({
            "category_key": category_key,
            "category_name": name,
            "product_name": "",
            "search_query": f"{name} {intent}",
            "search_intent": intent,
        })
    return queries
