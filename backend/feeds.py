"""Shop feeds (Awin & co): how "all stores" REALLY works.

There is no live "search every shop" API. Price comparison portals (idealo,
geizhals, Google Shopping) all run on PRODUCT FEEDS: shops push CSV/XML catalogs,
the portal imports them nightly and searches LOCALLY. We do exactly the same:

  1. Get a free Awin publisher account (awin.com), join advertiser programs
     (OTTO, MediaMarkt/Saturn via partner programs, dm, Rossmann, ...).
  2. Toolbox > Create-a-Feed > choose "Google format", copy the feed URL(s).
  3. Set FEED_URLS="https://...csv,https://...csv" and run:
       python feeds.py import
     (nightly via cron/systemd timer; Postgres full-text index does the search)
  4. /search with stores=all merges feed results with live Amazon results and
     sorts everything by unit price. Commission via Awin deeplinks (affiliate.py).

Any Google-format feed works (Awin, Tradedoubler, direct shop exports) because
column mapping is configurable via FEED_COLUMNS_JSON. No working key/feed ->
/search just returns Amazon results and says so in meta. Nothing fake, ever.
"""
import csv
import json
import os
import urllib.request

DEFAULT_COLUMNS = {
    "id": ["id", "product id", "aw_product_id", "offer id"],
    "title": ["title", "product name", "product_name", "name"],
    "price": ["price", "product price", "sale price", "preis"],
    "url": ["link", "deep link", "deep_link", "merchant deep link", "url"],
    "brand": ["brand", "manufacturer", "marke"],
    "image": ["image link", "image_link", "image url", "image"],
    "gtin": ["gtin", "ean", "upc"],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS shop_products (
  id TEXT PRIMARY KEY,
  shop TEXT NOT NULL,
  title TEXT NOT NULL,
  brand TEXT,
  price_cents INTEGER NOT NULL,
  currency TEXT DEFAULT 'EUR',
  url TEXT NOT NULL,
  image_url TEXT,
  gtin TEXT,
  search TSVECTOR GENERATED ALWAYS AS (to_tsvector('german', coalesce(title,'') || ' ' || coalesce(brand,''))) STORED,
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_shop_search ON shop_products USING GIN (search);
CREATE INDEX IF NOT EXISTS idx_shop_gtin ON shop_products (gtin);
"""


def db():
    import psycopg
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL not set — feed import needs Postgres (see .env.example)")
    return psycopg.connect(url)


def column_map():
    try:
        return json.loads(os.getenv("FEED_COLUMNS_JSON", "{}")) | DEFAULT_COLUMNS
    except ValueError:
        return DEFAULT_COLUMNS


def _pick(row: dict, keys: list[str]) -> str:
    low = {k.lower().strip(): v for k, v in row.items()}
    for k in keys:
        if k in low and low[k]:
            return str(low[k]).strip()
    return ""


def _cents(raw: str) -> int | None:
    s = raw.replace("€", "").replace("EUR", "").strip().split(" ")[0]
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return int(round(float(s) * 100))
    except ValueError:
        return None


def import_feed(url: str, shop: str) -> int:
    """Download one CSV feed URL, upsert rows. Returns imported row count."""
    req = urllib.request.Request(url, headers={"User-Agent": "pricematters/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = r.read().decode("utf-8-sig")
    cols = column_map()
    n = 0
    with db() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        for row in csv.DictReader(text.splitlines()):
            pid = _pick(row, cols["id"]) or _pick(row, cols["url"])
            title = _pick(row, cols["title"])
            cents = _cents(_pick(row, cols["price"]))
            link = _pick(row, cols["url"])
            if not pid or not title or cents is None or not link:
                continue
            cur.execute(
                """INSERT INTO shop_products (id, shop, title, brand, price_cents, url, image_url, gtin, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())
                   ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, price_cents=EXCLUDED.price_cents,
                       url=EXCLUDED.url, updated_at=now()""",
                (f"{shop}:{pid}", shop, title, _pick(row, cols["brand"]) or None,
                 cents, link, _pick(row, cols["image"]) or None, _pick(row, cols["gtin"]) or None),
            )
            n += 1
    return n


def search_feeds(query: str, limit: int = 30):
    """Full-text search over imported feeds. Returns provider-style rows."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, title, price_cents, url, shop, image_url FROM shop_products
               WHERE search @@ plainto_tsquery('german', %s)
               ORDER BY ts_rank(search, plainto_tsquery('german', %s)) DESC LIMIT %s""",
            (query, query, limit),
        )
        return [(i, t, p, u, s, im) for i, t, p, u, s, im in cur.fetchall()]


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in ("import", "init"):
        print('usage: python feeds.py [init|import]  (FEED_URLS="url1,url2", FEED_SHOP="awin")')
        raise SystemExit(1)
    if sys.argv[1] == "init":
        with db() as conn, conn.cursor() as cur:
            cur.execute(SCHEMA)
        print("shop_products ready")
    else:
        shop = os.getenv("FEED_SHOP", "awin")
        total = 0
        for u in [x.strip() for x in os.getenv("FEED_URLS", "").split(",") if x.strip()]:
            c = import_feed(u, shop)
            print(f"{u[:60]}... -> {c} rows")
            total += c
        print(f"total: {total} rows")
