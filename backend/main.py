"""FastAPI backend: /search + /extract + /health.

Amazon data: DATA_PROVIDER=mock (default, no keys) | scrapingbee | rainforest | creators
Whole web:   + serpapapi via providers=serpapi, or stores=all fan-out
Feed shops:  Awin & co via nightly CSV import (feeds.py) into Postgres,
             searched locally and merged when stores=all (default).
Query:       searched as-is + auto-translated (DE<->EN), merged, deduped.
"""
import os
from fastapi import FastAPI, Query
from pydantic import BaseModel
from affiliate import monetize, affiliate_url
from extractor import extract_quantity, unit_price
from providers import PROVIDERS
from translate import query_variants

app = FastAPI(title="PriceMatters API")
DEFAULT_TAG = "websters02-21"
# bump to invalidate all cached rows (e.g. after provider param changes like delivery zones)
CACHE_VERSION = "v2"


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
    single = provider or None
    if single:
        chain = [single]
    else:
        chain = [p.strip() for p in os.getenv("DATA_PROVIDERS", "").split(",") if p.strip()]
        chain = chain or [os.getenv("DATA_PROVIDER", "mock")]
    chain = [c for c in chain if c in PROVIDERS]
    if not chain:
        return {"items": [], "meta": {"chain": chain}, "error": "no known provider in chain"}
    meta: dict = {"chain": chain, "feed_shops": "skipped",
                  "demo": chain == ["mock"], "queries": [q]}
    try:
        from providers import ZONES  # noqa (zone labels documented there)
        meta["zone"] = marketplace
    except ImportError:
        pass
    name = chain[0]
    from cache import get as cache_get, store as cache_store
    from providers import DEFAULT_CHAIN  # noqa (keeps default order documented)
    seen: set[str] = set()
    items: list[dict] = []
    errors: dict = {}
    used = "mock"
    rows: list = []
    for cand in chain:
        ckey = f"{CACHE_VERSION}:{cand}:{marketplace}:{q}"
        cached = cache_get(ckey) if cand != "mock" else None
        if cached:
            rows, age, hits = cached
            meta["cache"] = f"hit ({age // 60}m old, {hits} hits)"
            used = cand
            break
        try:
            variants = query_variants(q, marketplace) if cand != "mock" else [q]
            meta["queries"] = variants
            rows = []
            for v in variants:
                for row in PROVIDERS[cand](v, marketplace):
                    if row[0] in seen:
                        continue
                    seen.add(row[0])
                    rows.append(row)
            if not rows:
                raise RuntimeError("no rows")
            fp = "|".join(f"{r[0]}:{r[2]}" for r in rows)
            info = cache_store(ckey, rows, fp)
            meta["cache"] = f"fresh (ttl {info['ttl'] // 3600}h)"
            used = cand
            break
        except RuntimeError as e:
            errors[cand] = str(e)
            rows = []
            continue
    if not rows and "mock" not in chain:
        rows = PROVIDERS["mock"](q, marketplace)
        used = "mock-fallback"
    if errors:
        meta["provider_errors"] = errors
    meta["provider_used"] = used
    meta["demo"] = used in ("mock", "mock-fallback")
    name = used
    for row in rows:
        seen.add(row[0])
        items.append(enrich(*row, marketplace))

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


@app.get("/cache/stats")
def cache_stats():
    from cache import stats
    return stats()


# Michi's personal favorites on the front page (no ranking, just love).
# Static fallback = his real products/prices; live SerpApi data whenever possible.
CURATED = [
    {"asin": "B08NCPB1SM", "title": "Volksshake Veganes Protein Schoko, 1000g",
     "price_cents": 2878, "rating": 4.0, "reviews": 267, "qty_value": 1, "qty_unit": "kg"},
    {"asin": "B00I5ABIFI", "title": "WMF Kult X Mix & Go Mini Smoothie Maker, 0,6l",
     "price_cents": 3024, "rating": 4.5, "reviews": 36822, "qty_value": 1, "qty_unit": "pcs"},
    {"asin": "B0D9H7PLK4", "title": "UGREEN LAN Switch Gigabit, 8-Port",
     "price_cents": 1410, "rating": 4.7, "reviews": 1710, "qty_value": 1, "qty_unit": "pcs"},
    {"asin": "B08HVR86TR", "title": "Oclean X Pro Schallzahnbürste, Dunkellila",
     "price_cents": 6509, "rating": 3.7, "reviews": 1060, "qty_value": 1, "qty_unit": "pcs"},
    {"asin": "B09B836TTQ", "title": "Corsair HS80 RGB Wireless Gaming-Headset, Carbon",
     "price_cents": 10084, "rating": 4.1, "reviews": 5704, "qty_value": 1, "qty_unit": "pcs"},
]


@app.get("/curated")
def curated(marketplace: str = Query("de")):
    from cache import get as cache_get, store as cache_store
    from providers import serpapi_product
    items = []
    for c in CURATED:
        key, data = f"v2:curated:{c['asin']}", None
        hit = cache_get(key)
        if hit:
            data, _age, _hits = hit
        else:
            try:
                live = serpapi_product(c["asin"])
                data = {
                    "title": live["title"] or c["title"],
                    "price_cents": live["price_cents"] or c["price_cents"],
                    "image": live["image"],
                    # sanity: live rating shouldn't differ wildly from static
                    "rating": live["rating"] if live["rating"] and abs(live["rating"] - c["rating"]) < 2.0 else c["rating"],
                    "reviews": live["reviews"] if live["reviews"] and live["reviews"] > c["reviews"] * 0.5 else c["reviews"],
                    "live": True,
                }
                cache_store(key, data, f"{c['asin']}:{data['price_cents']}")
            except RuntimeError:
                data = {**c, "image": None, "live": False}
        tag = os.getenv("AMAZON_PARTNER_TAG", DEFAULT_TAG)
        from affiliate import MARKETPLACES
        domain = MARKETPLACES.get(marketplace, "www.amazon.de")
        items.append({**data, "asin": c["asin"], "store": "Amazon",
                      "qty": {"value": c.get("qty_value", 1), "unit": c.get("qty_unit", "pcs"), "kind": "count"},
                      "url": affiliate_url(f"https://{domain}/dp/{c['asin']}", tag, marketplace)})
    return {"items": items}


class Contact(BaseModel):
    name: str = ""
    email: str = ""
    message: str = ""
    slot: str = ""


@app.post("/contact")
def contact(c: Contact):
    """Ad-slot inquiry: Postgres if available, stdout log otherwise. Always honest ok-flag."""
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            raise RuntimeError("no db")
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS ad_inquiries
                   (id SERIAL PRIMARY KEY, name TEXT, email TEXT, slot TEXT,
                    message TEXT, created_at TIMESTAMPTZ DEFAULT now())"""
            )
            cur.execute(
                "INSERT INTO ad_inquiries (name, email, slot, message) VALUES (%s,%s,%s,%s)",
                (c.name[:120], c.email[:160], c.slot[:40], c.message[:2000]),
            )
        return {"ok": True, "stored": "db"}
    except Exception as e:
        print(f"[contact] {c.slot} {c.name} <{c.email}>: {c.message[:200]} ({e})", flush=True)
        return {"ok": True, "stored": "log"}


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
