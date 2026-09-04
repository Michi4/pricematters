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

# Canonical marketplace table: code -> Amazon domain, language, delivery zip,
# site country, display currency. Switzerland/Austria use amazon.de (no .ch/.at store).
AMAZON = {
    "de":     {"domain": "amazon.de",     "lang": "de_DE", "zip": "10115",    "cc": "DE", "cur": "EUR"},
    "at":     {"domain": "amazon.de",     "lang": "de_DE", "zip": "1010",     "cc": "AT", "cur": "EUR"},
    "ch":     {"domain": "amazon.de",     "lang": "de_DE", "zip": "8001",     "cc": "CH", "cur": "EUR"},
    "fr":     {"domain": "amazon.fr",     "lang": "fr_FR", "zip": "75001",    "cc": "FR", "cur": "EUR"},
    "it":     {"domain": "amazon.it",     "lang": "it_IT", "zip": "00100",    "cc": "IT", "cur": "EUR"},
    "es":     {"domain": "amazon.es",     "lang": "es_ES", "zip": "28001",    "cc": "ES", "cur": "EUR"},
    "nl":     {"domain": "amazon.nl",     "lang": "nl_NL", "zip": "1011",     "cc": "NL", "cur": "EUR"},
    "se":     {"domain": "amazon.se",     "lang": "sv_SE", "zip": "111 45",   "cc": "SE", "cur": "SEK"},
    "pl":     {"domain": "amazon.pl",     "lang": "pl_PL", "zip": "00-001",   "cc": "PL", "cur": "PLN"},
    "be":     {"domain": "amazon.com.be", "lang": "nl_NL", "zip": "1000",     "cc": "BE", "cur": "EUR"},
    "co.uk":  {"domain": "amazon.co.uk",  "lang": "en_GB", "zip": "SW1A 1AA", "cc": "GB", "cur": "GBP"},
    "ie":     {"domain": "amazon.ie",     "lang": "en_IE", "zip": "D01",      "cc": "IE", "cur": "EUR"},
    "com":    {"domain": "amazon.com",    "lang": "en_US", "zip": "90210",    "cc": "US", "cur": "USD"},
    "ca":     {"domain": "amazon.ca",     "lang": "en_CA", "zip": "M5H",      "cc": "CA", "cur": "CAD"},
    "com.mx": {"domain": "amazon.com.mx", "lang": "es_MX", "zip": "06000",    "cc": "MX", "cur": "MXN"},
    "com.br": {"domain": "amazon.com.br", "lang": "pt_BR", "zip": "01310",    "cc": "BR", "cur": "BRL"},
    "com.au": {"domain": "amazon.com.au", "lang": "en_AU", "zip": "2000",     "cc": "AU", "cur": "AUD"},
    "co.jp":  {"domain": "amazon.co.jp",  "lang": "ja_JP", "zip": "100-0001", "cc": "JP", "cur": "JPY"},
    "in":     {"domain": "amazon.in",     "lang": "en_IN", "zip": "110001",   "cc": "IN", "cur": "INR"},
    "ae":     {"domain": "amazon.ae",     "lang": "ar_AE", "zip": "00000",    "cc": "AE", "cur": "AED"},
    "sa":     {"domain": "amazon.sa",     "lang": "ar_SA", "zip": "12211",    "cc": "SA", "cur": "SAR"},
    "sg":     {"domain": "amazon.sg",     "lang": "en_SG", "zip": "018956",   "cc": "SG", "cur": "SGD"},
    "com.tr": {"domain": "amazon.com.tr", "lang": "tr_TR", "zip": "34000",    "cc": "TR", "cur": "TRY"},
}


def amz(marketplace: str) -> dict:
    return AMAZON.get(marketplace, AMAZON["de"])


def mock_search(query: str, marketplace: str):
    # Static demo catalog on purpose: NEVER interpolate the query into titles
    # (that looks broken). meta.demo=true tells the UI to show a "Demo" badge
    # until a real provider key is configured.
    domain = "www." + amz(marketplace)["domain"]
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


def _get_redis():
    try:
        from cache import _redis
        return _redis()
    except Exception:
        return None


def _serpapi_quota() -> int:
    return int(os.getenv("SERPAPI_QUOTA", "250") or 250)


def _serpapi_bump(r, index: int):
    """Count this month's requests per key index (best-effort, Redis only)."""
    if r is None:
        return
    try:
        import time
        ym = time.strftime("%Y%m", time.gmtime())
        k = f"pm:v2:serpq:{index}:{ym}"
        n = r.incr(k)
        if n == 1:
            r.expire(k, 3360 * 3600)  # ~35d, spans the month safely
    except Exception:
        pass


def _serpapi_used(r, index: int) -> int:
    if r is None:
        return 0
    try:
        import time
        ym = time.strftime("%Y%m", time.gmtime())
        return int(r.get(f"pm:v2:serpq:{index}:{ym}") or 0)
    except Exception:
        return 0


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


def scrapingbee_search(query: str, marketplace: str, page: int = 1):
    """1000 credits free, no credit card. domain=de -> amazon.de prices."""
    key = os.getenv("SCRAPINGBEE_API_KEY", "")
    if not key:
        raise RuntimeError("SCRAPINGBEE_API_KEY not set")
    domain = amz(marketplace)["domain"].replace("amazon.", "")
    # ScrapingBee rule: when country matches the amazon domain, send zip_code instead
    data = _get("https://app.scrapingbee.com/api/v1/amazon/search", {
        "api_key": key, "query": query, "domain": domain,
        "zip_code": amz(marketplace)["zip"], "language": "de" if domain == "de" else "en",
        "currency": amz(marketplace)["cur"], "pages": max(1, min(int(page), 3)),
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


def rainforest_search(query: str, marketplace: str, page: int = 1):
    """Trial, then paid. Best structure (offers/sellers)."""
    key = os.getenv("RAINFOREST_API_KEY", "")
    if not key:
        raise RuntimeError("RAINFOREST_API_KEY not set")
    domain = amz(marketplace)["domain"]
    data = _get("https://api.rainforestapi.com/request", {
        "api_key": key, "type": "search", "amazon_domain": domain,
        "search_term": query, "language": amz(marketplace)["lang"],
        "page": str(max(1, int(page))),
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


def _serpapi_keys() -> list:
    """SERPAPI_API_KEYS (comma list) wins; SERPAPI_API_KEY stays first for compat."""
    keys = [k.strip() for k in os.getenv("SERPAPI_API_KEYS", "").split(",") if k.strip()]
    legacy = os.getenv("SERPAPI_API_KEY", "").strip()
    if legacy and legacy not in keys:
        keys.insert(0, legacy)
    return keys


def serpapi_search(query: str, marketplace: str, page: int = 1):
    """SerpApi amazon engine (250 free searches/mo per key).

    Tries every configured key in order (SERPAPI_API_KEYS, comma-separated,
    SERPAPI_API_KEY kept as first entry for backwards compat) so a monthly
    quota can never take the provider down — and emits an alert when a key
    fails or nears its limit.
    """
    from alerts import serpapi_key_failed, serpapi_usage_check  # local: no cycles
    keys = _serpapi_keys()
    if not keys:
        raise RuntimeError("SERPAPI_API_KEY not set")
    a = amz(marketplace)
    domain = a["domain"]
    r = _get_redis()
    last_err = "no keys"
    for i, key in enumerate(keys):
        _serpapi_bump(r, i)
        try:
            data = _get("https://serpapi.com/search.json", {
                "api_key": key, "engine": "amazon", "k": query,
                "amazon_domain": domain, "language": a["lang"],
                "delivery_zip": a["zip"], "shipping_location": a["cc"],
                "page": str(max(1, int(page))),
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
            serpapi_usage_check(i, _serpapi_used(r, i), _serpapi_quota())
            return out
        except Exception as e:
            last_err = str(e)
            serpapi_key_failed(i, last_err)
            continue
    raise RuntimeError(last_err)


def serpapi_product(asin: str, domain: str = "amazon.de"):
    """Single product by ASIN (SerpApi amazon_product engine). Defensive: {} on miss."""
    key = os.getenv("SERPAPI_API_KEY", "")
    if not key:
        raise RuntimeError("SERPAPI_API_KEY not set")
    data = _get("https://serpapi.com/search.json", {
        "api_key": key, "engine": "amazon_product", "asin": asin,
        "amazon_domain": domain,
        "language": "de_DE" if domain == "amazon.de" else "en_US",
    })
    if data.get("error"):
        raise RuntimeError(f"serpapi: {data['error']}")
    pr = data.get("product_results", {}) or {}
    title = pr.get("title", "")
    price = pr.get("extracted_price", pr.get("price"))
    if isinstance(price, dict):
        price = price.get("extracted") or price.get("value") or price.get("raw")
    image = pr.get("thumbnail") or (pr.get("thumbnails") or [None])[0]
    rating = pr.get("rating")
    try:
        rating = float(str(rating).split()[0].replace(",", ".")) if rating else None
    except (ValueError, IndexError):
        rating = None
    reviews = pr.get("reviews")
    try:
        reviews = int(str(reviews).replace(".", "").replace(",", "")) if reviews else None
    except ValueError:
        reviews = None
    return {"title": title, "price_cents": _price_to_cents(price),
            "image": image, "rating": rating, "reviews": reviews}


def zenrows_search(query: str, marketplace: str, page: int = 1):
    """Zenrows universal scrape (free tier) of the Amazon search page + shared parser."""
    key = os.getenv("ZENROWS_API_KEY", "")
    if not key:
        raise RuntimeError("ZENROWS_API_KEY not set")
    domain = "www." + amz(marketplace)["domain"]
    target = f"https://{domain}/s?k=" + urllib.parse.quote_plus(query)
    if page > 1:
        # Amazon search pagination: &page=N (1-based)
        target += f"&page={page}"
    try:
        # premium_proxy (residential) beats Amazon's bot manager; plain datacenter IPs get challenged
        full = ("https://api.zenrows.com/v1/?" + urllib.parse.urlencode(
            {"apikey": key, "url": target, "premium_proxy": "true"}))
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
    domain_id = {"de": 3, "at": 3, "ch": 3, "fr": 4, "it": 8, "es": 9,
                 "co.uk": 2, "com": 1, "ca": 6, "co.jp": 5, "in": 10,
                 "com.mx": 11, "com.br": 12}.get(marketplace, 3)
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

# delivery zone labels (reference; the UI localizes marketplace codes itself)
ZONES = {"de": "Deutschland", "at": "Österreich", "ch": "Schweiz"}

# cheapest-first default chain (free tiers before paid before experimental)
DEFAULT_CHAIN = ["zenrows", "serpapi", "scrapingbee", "rainforest", "selfscrape", "mock"]
