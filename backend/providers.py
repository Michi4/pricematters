"""Data providers behind ONE row shape: (id, title, price_cents, url, shop)

Live Amazon:
  mock         free, no key, deterministic — default, works right now
  scrapingbee  1000 credits free at scrapingbee.com, no CC -> best free start
  rainforest   trial at rainforestapi.com, then paid -> best structure
  creators     Amazon Creators API -> 501-style error until PartnerNet approved

Whole-web live:
  serpapi      Google Shopping via serpapi.com (needs SERPAPI_API_KEY, paid).
               The only realistic "whole internet" live API. Optional.

Feed shops (Awin & co):
  NOT live — feeds are imported nightly into Postgres by feeds.py, then
  searched locally in main.py. See feeds.py for the how/why.
"""
import json
import os
import urllib.parse
import urllib.request

TIMEOUT = 25


def mock_search(query: str, marketplace: str):
    domain = "www.amazon.de" if marketplace in ("de", "at") else f"www.amazon.{marketplace}"
    return [
        ("MOCK1", f"Bio Basmati Reis, 2 x 1kg ({query})", 1299, f"https://{domain}/dp/MOCK1", "Amazon"),
        ("MOCK2", f"Optimum Whey Double Rich Chocolate 2.27kg (5 lbs), 71 Servings ({query})", 6499, f"https://{domain}/dp/MOCK2", "Amazon"),
        ("MOCK3", f"Bio Kaffee Bohnen 500g ({query})", 899, f"https://{domain}/dp/MOCK3", "Amazon"),
    ]


def _get(url: str, params: dict) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "pricematters/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def _price_to_cents(price) -> int | None:
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return int(round(float(price) * 100))
    s = str(price).replace("€", "").replace("EUR", "").replace("$", "").strip()
    # "12,99" (DE) vs "12.99" (EN) — last separator is the decimal one
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return int(round(float("".join(c for c in s if c.isdigit() or c in ".-")) * 100))
    except ValueError:
        return None


def scrapingbee_search(query: str, marketplace: str):
    """1000 credits free, no credit card. domain=de -> amazon.de prices."""
    key = os.getenv("SCRAPINGBEE_API_KEY", "")
    if not key:
        raise RuntimeError("SCRAPINGBEE_API_KEY not set")
    domain = {"de": "de", "at": "de", "com": "com", "co.uk": "co.uk", "fr": "fr"}.get(marketplace, "de")
    data = _get("https://app.scrapingbee.com/api/v1/amazon/search", {
        "api_key": key, "query": query, "domain": domain,
        "country": "de" if domain == "de" else "us", "language": "de" if domain == "de" else "en",
        "currency": "EUR" if domain == "de" else "USD", "pages": 1,
    })
    out = []
    for p in data.get("search_results", data.get("results", [])):
        asin = p.get("asin", "")
        price = _price_to_cents((p.get("price") or {}).get("value", p.get("price")))
        if not asin or price is None:
            continue
        out.append((asin, p.get("name") or p.get("title", ""), price,
                    p.get("url") or p.get("link", ""), "Amazon"))
    return out


def rainforest_search(query: str, marketplace: str):
    """Trial, then paid. Best structure (offers/sellers)."""
    key = os.getenv("RAINFOREST_API_KEY", "")
    if not key:
        raise RuntimeError("RAINFOREST_API_KEY not set")
    domain = {"de": "amazon.de", "at": "amazon.de", "com": "amazon.com",
              "co.uk": "amazon.co.uk", "fr": "amazon.fr"}.get(marketplace, "amazon.de")
    data = _get("https://api.rainforestapi.com/request", {
        "api_key": key, "type": "search", "amazon_domain": domain,
        "search_term": query, "language": "de_DE" if domain == "amazon.de" else "en_US",
    })
    out = []
    for p in data.get("search_results", []):
        asin = p.get("asin", "")
        price = _price_to_cents((p.get("price") or {}).get("value", p.get("price")))
        if not asin or price is None:
            continue
        out.append((asin, p.get("title", ""), price, p.get("link", ""), "Amazon"))
    return out


def serpapi_search(query: str, marketplace: str):
    """Google Shopping live search (whole web). Needs SERPAPI_API_KEY (paid, serpapi.com).
    Defensive parsing: unknown fields are skipped, never crash the whole search."""
    key = os.getenv("SERPAPI_API_KEY", "")
    if not key:
        raise RuntimeError("SERPAPI_API_KEY not set")
    gl = {"de": "de", "at": "at", "com": "us", "co.uk": "uk", "fr": "fr"}.get(marketplace, "de")
    data = _get("https://serpapi.com/search.json", {
        "api_key": key, "engine": "google_shopping", "q": query,
        "gl": gl, "hl": "de" if gl in ("de", "at") else "en",
    })
    out = []
    for p in data.get("shopping_results", []):
        price = p.get("extracted_price")
        price_cents = int(round(float(price) * 100)) if isinstance(price, (int, float)) else _price_to_cents(p.get("price"))
        if price_cents is None:
            continue
        pid = str(p.get("product_id") or p.get("link", ""))
        out.append((f"serp:{pid}", p.get("title", ""), price_cents,
                    p.get("link", ""), p.get("source", "Shop")))
    return out


def keepa_history(asin: str, marketplace: str = "de"):
    """Price history for the fake-discount detector. Needs KEEPA_API_KEY (~EUR 19/mo)."""
    key = os.getenv("KEEPA_API_KEY", "")
    if not key:
        raise RuntimeError("KEEPA_API_KEY not set")
    domain_id = {"de": 3, "at": 3, "com": 1, "co.uk": 2, "fr": 4}.get(marketplace, 3)
    return _get("https://api.keepa.com/product", {
        "key": key, "domain": domain_id, "asin": asin, "history": 1,
    })


def creators_search(query: str, marketplace: str):
    raise RuntimeError(
        "Amazon Creators API needs an approved PartnerNet account (~10 shipped sales "
        "in trailing 30 days). Until then use DATA_PROVIDER=mock|scrapingbee|rainforest."
    )


PROVIDERS = {
    "mock": mock_search,
    "scrapingbee": scrapingbee_search,
    "rainforest": rainforest_search,
    "serpapi": serpapi_search,
    "creators": creators_search,
}
