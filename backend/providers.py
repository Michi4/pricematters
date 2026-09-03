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
from selfscrape import selfscrape_search

TIMEOUT = 25


def mock_search(query: str, marketplace: str):
    # Static demo catalog on purpose: NEVER interpolate the query into titles
    # (that looks broken). meta.demo=true tells the UI to show a "Demo" badge
    # until a real provider key is configured.
    domain = "www.amazon.de" if marketplace in ("de", "at") else f"www.amazon.{marketplace}"
    return [
        ("MOCK1", "Bio Basmati Reis, 2 x 1kg", 1299, f"https://{domain}/dp/MOCK1", "Amazon", None),
        ("MOCK2", "Optimum Whey Double Rich Chocolate 2.27kg (5 lbs), 71 Servings", 6499, f"https://{domain}/dp/MOCK2", "Amazon", None),
        ("MOCK3", "Bio Kaffee Bohnen 500g", 899, f"https://{domain}/dp/MOCK3", "Amazon", None),
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
    # ScrapingBee rule: when country matches the amazon domain, send zip_code instead
    zips = {"de": "10115", "com": "90210", "co.uk": "SW1A 1AA", "fr": "75001"}
    data = _get("https://app.scrapingbee.com/api/v1/amazon/search", {
        "api_key": key, "query": query, "domain": domain,
        "zip_code": zips.get(domain, "10115"), "language": "de" if domain == "de" else "en",
        "currency": "EUR" if domain == "de" else "USD", "pages": 1,
    })
    out = []
    for p in data.get("search_results", data.get("results", [])):
        asin = p.get("asin", "")
        price = _price_to_cents((p.get("price") or {}).get("value", p.get("price")))
        if not asin or price is None:
            continue
        out.append((asin, p.get("name") or p.get("title", ""), price,
                    p.get("url") or p.get("link", ""), "Amazon",
                    (p.get("image") or p.get("thumbnail")) or None))
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
        out.append((asin, p.get("title", ""), price, p.get("link", ""), "Amazon",
                    (p.get("image") or p.get("thumbnail")) or None))
    return out


def serpapi_search(query: str, marketplace: str):
    """SerpApi amazon engine (250 free searches/mo). organic_results -> rows."""
    key = os.getenv("SERPAPI_API_KEY", "")
    if not key:
        raise RuntimeError("SERPAPI_API_KEY not set")
    domain = {"de": "amazon.de", "at": "amazon.de", "com": "amazon.com",
              "co.uk": "amazon.co.uk", "fr": "amazon.fr"}.get(marketplace, "amazon.de")
    lang = {"amazon.de": "de_DE", "amazon.com": "en_US",
            "amazon.co.uk": "en_GB", "amazon.fr": "fr_FR"}.get(domain, "de_DE")
    data = _get("https://serpapi.com/search.json", {
        "api_key": key, "engine": "amazon", "k": query,
        "amazon_domain": domain, "language": lang,
    })
    if data.get("error"):
        raise RuntimeError(f"serpapi: {data['error']}")
    out = []
    for p in data.get("organic_results", []):
        asin = p.get("asin", "")
        price = p.get("price")
        if isinstance(price, dict):
            price = price.get("extracted") or price.get("value") or price.get("raw")
        price_cents = _price_to_cents(price)
        if not asin or price_cents is None:
            continue
        out.append((asin, p.get("title", ""), price_cents,
                    p.get("link", "") or f"https://{domain}/dp/{asin}",
                    "Amazon", p.get("thumbnail") or p.get("image")))
    if not out:
        raise RuntimeError("serpapi returned 0 priced products.")
    return out


def zenrows_search(query: str, marketplace: str):
    """Zenrows universal scrape (free tier) of the Amazon search page + shared parser."""
    key = os.getenv("ZENROWS_API_KEY", "")
    if not key:
        raise RuntimeError("ZENROWS_API_KEY not set")
    domain = {"de": "www.amazon.de", "at": "www.amazon.de", "com": "www.amazon.com",
              "co.uk": "www.amazon.co.uk", "fr": "www.amazon.fr"}.get(marketplace, "www.amazon.de")
    target = f"https://{domain}/s?k=" + urllib.parse.quote_plus(query)
    try:
        full = ("https://api.zenrows.com/v1/?" + urllib.parse.urlencode(
            {"apikey": key, "url": target}))
        req = urllib.request.Request(full, headers={"User-Agent": "pricematters/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        raise RuntimeError(f"zenrows fetch failed: {e}")
    if not html or len(html) < 20000 or "Tut uns Leid" in html:
        raise RuntimeError("zenrows returned block page / empty.")
    from amazon_parse import parse_search
    out = parse_search(html, domain)
    if not out:
        raise RuntimeError("zenrows parsed 0 products.")
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
    "zenrows": zenrows_search,
    "serpapi": serpapi_search,
    "scrapingbee": scrapingbee_search,
    "rainforest": rainforest_search,
    "selfscrape": selfscrape_search,
    "creators": creators_search,
}

# cheapest-first default chain (free tiers before paid before experimental)
DEFAULT_CHAIN = ["zenrows", "serpapi", "scrapingbee", "rainforest", "selfscrape", "mock"]
