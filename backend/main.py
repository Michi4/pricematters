"""FastAPI backend: /search + /extract + /health.

Amazon data: DATA_PROVIDER=mock (default, no keys) | scrapingbee | rainforest | creators
Whole web:   + serpapapi via providers=serpapi, or stores=all fan-out
Feed shops:  Awin & co via nightly CSV import (feeds.py) into Postgres,
             searched locally and merged when stores=all (default).
Query:       searched as-is + auto-translated (DE<->EN), merged, deduped.
"""
import os
from fastapi import FastAPI, Query
from affiliate import monetize
from extractor import extract_quantity, unit_price
from providers import PROVIDERS
from translate import query_variants

app = FastAPI(title="PriceMatters API")
DEFAULT_TAG = "websters02-21"


def log_search(query: str, marketplace: str, count: int):
    """Fire-and-forget: feeds the 'Popular' row. No DB -> silently skipped."""
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO searches (query, marketplace, result_count) VALUES (%s,%s,%s)",
                (query[:120], marketplace, count),
            )
    except Exception:
        pass

def enrich(pid: str, title: str, price_cents: int, url: str, shop: str, image: str | None, marketplace: str) -> dict:
    from ai_extract import ai_quantity
    q = extract_quantity(title) or ai_quantity(title)
    up = unit_price(price_cents, q) if q else None
    return {
        "asin": pid,
        "title": title,
        "priceCents": price_cents,
        "url": monetize(url, shop, marketplace, os.getenv("AMAZON_PARTNER_TAG", DEFAULT_TAG)),
        "store": shop,
        "image": image,
        "qty": {"value": q.value, "unit": q.unit, "kind": q.kind} if q else None,
        "unitPrice": {"per": up[0], "base": up[1]} if up else None,
    }


@app.get("/health")
def health():
    return {"ok": True, "provider": os.getenv("DATA_PROVIDER", "mock")}


@app.get("/extract")
def extract(title: str = Query(...), description: str = ""):
    q = extract_quantity(title, description)
    return {"qty": q.__dict__ if q else None}


@app.get("/search")
def search(q: str = Query(...), marketplace: str = Query("de"),
           provider: str | None = Query(None), stores: str = Query("all")):
    name = provider or os.getenv("DATA_PROVIDER", "mock")
    fn = PROVIDERS.get(name)
    meta: dict = {"amazon_provider": name, "feed_shops": "skipped",
                  "demo": name == "mock", "queries": [q]}
    if not fn:
        return {"items": [], "meta": meta, "error": f"unknown provider '{name}'"}
    seen: set[str] = set()
    items: list[dict] = []
    try:
        variants = query_variants(q, marketplace) if name != "mock" else [q]
        meta["queries"] = variants
        for v in variants:
            for row in fn(v, marketplace):
                pid = row[0]
                if pid in seen:
                    continue
                seen.add(pid)
                items.append(enrich(*row, marketplace))
    except RuntimeError as e:
        return {"items": [], "meta": meta, "error": str(e)}

    if stores == "all":
        try:
            from feeds import search_feeds
            for row in search_feeds(q):
                if row[0] in seen:
                    continue
                seen.add(row[0])
                items.append(enrich(*row, marketplace))
            meta["feed_shops"] = "included"
        except (RuntimeError, ImportError) as e:
            meta["feed_shops"] = str(e)

    items.sort(key=lambda i: (i["unitPrice"] is None, (i["unitPrice"] or {}).get("per", 1e18)))
    log_search(q, marketplace, len(items))
    return {"items": items, "meta": meta}


@app.get("/popular")
def popular(marketplace: str = Query("de"), limit: int = Query(4)):
    """Top user queries, last 30 days. [] -> frontend falls back to static hints."""
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return {"items": []}
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT query, COUNT(*) AS c FROM searches
                   WHERE marketplace = %s AND created_at > now() - interval '30 days'
                   GROUP BY query ORDER BY c DESC, MAX(created_at) DESC LIMIT %s""",
                (marketplace, limit),
            )
            return {"items": [r[0] for r in cur.fetchall()]}
    except Exception:
        return {"items": []}
