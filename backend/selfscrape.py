"""EXPERIMENTAL self-scrape provider (free proxies). Read this first.

Honest status: free proxy lists (e.g. proxyscrape) are burned IPs — expect
10-40% request success on a good day, CAPTCHAs the rest. This is NOT a primary
data source. It exists so you can experiment for 0 EUR.

Safety (so YOU don't get banned):
  - Disabled unless SELFSCRAPE_CONSENT=1 is set explicitly. Setting it means
    you accept that scraping violates Amazon's ToS and you take that risk.
  - Your server IP NEVER touches Amazon: all requests go through proxies.
  - Hard throttle: max 1 request / 10s globally, max SELFSCRAPE_DAILY_BUDGET
    (default 50) requests/day. Cache-first: cached rows are served without
    any request at all.
  - No affiliate identity is sent with scrape requests (plain UA, no tag,
    no account cookies). Tags are added to LINKS afterwards, like everywhere.
  - If you get your PartnerNet account one day, keep this OFF and use the
    Creators API. Scraping + affiliate account = unnecessary risk.

Recommended stack stays: Awin feeds (free, legal) + Creators API (free once
approved) + this cache. This provider is the last resort, not the plan.
"""
import os
import re
import threading
import time
import urllib.parse
import urllib.request

PROXY_SOURCE = ("https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
                "&timeout=8000&country=all&ssl=all&anonymity=all")
POOL_TTL = 600
_last_fetch = 0.0
_pool: list[str] = []
_lock = threading.Lock()
_last_req = 0.0
_used_today = 0
_day = ""


def _enabled() -> bool:
    return os.getenv("SELFSCRAPE_CONSENT", "") == "1"


def _budget_left() -> bool:
    global _used_today, _day
    today = time.strftime("%Y-%m-%d")
    if today != _day:
        _day, _used_today = today, 0
    return _used_today < int(os.getenv("SELFSCRAPE_DAILY_BUDGET", "50"))


def _pool() -> list[str]:
    global _last_fetch, _pool
    with _lock:
        if time.time() - _last_fetch < POOL_TTL and _pool:
            return list(_pool)
    try:
        req = urllib.request.Request(PROXY_SOURCE, headers={"User-Agent": "pricematters/0.1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            lines = r.read().decode(errors="ignore").splitlines()
        proxies = [l.strip() for l in lines if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", l.strip())]
    except Exception:
        proxies = []
    with _lock:
        _pool, _last_fetch = proxies[:200], time.time()
        return list(_pool)


def _fetch(url: str) -> str | None:
    """One throttled, budgeted request through a rotating free proxy."""
    global _last_req, _used_today
    with _lock:
        wait = 10 - (time.time() - _last_req)
        if wait > 0:
            time.sleep(wait)
        _last_req = time.time()
        if not _budget_left():
            return None
        _used_today += 1
    import random
    pool = _pool()
    random.shuffle(pool)
    for px in pool[:6]:  # try up to 6 proxies per search, then give up honestly
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            })
            req.set_proxy(px, "http")
            req.set_proxy(px, "https")
            with urllib.request.urlopen(req, timeout=12) as r:
                html = r.read().decode("utf-8", errors="ignore")
            if "Enter the characters you see" in html or len(html) < 20000:
                continue  # captcha or block page, next proxy
            return html
        except Exception:
            continue
    return None


ASIN_RE = re.compile(r'data-asin="(B0[A-Z0-9]{8})"')
PRICE_RE = re.compile(r"€\s*(\d{1,4}[.,]\d{2})")


def _cents(s: str) -> int | None:
    s = s.replace(".", "").replace(",", ".") if "," in s else s
    try:
        return int(round(float(s) * 100))
    except ValueError:
        return None


def selfscrape_search(query: str, marketplace: str):
    if not _enabled():
        raise RuntimeError("SELFSCRAPE_CONSENT=1 not set — enable explicitly (see selfscrape.py header).")
    domain = {"de": "www.amazon.de", "at": "www.amazon.de", "com": "www.amazon.com",
              "co.uk": "www.amazon.co.uk", "fr": "www.amazon.fr"}.get(marketplace, "www.amazon.de")
    url = f"https://{domain}/s?k=" + urllib.parse.quote_plus(query)
    html = _fetch(url)
    if not html:
        raise RuntimeError("self-scrape failed (proxies blocked or budget spent) — try mock/scrapingbee.")
    out, seen = [], set()
    blocks = re.split(r'data-asin="', html)
    for b in blocks[1:]:
        m = re.match(r"(B0[A-Z0-9]{8})", b)
        if not m or m.group(1) in seen:
            continue
        asin = m.group(1)
        t = re.search(r"<h2[^>]*>.*?<span>(.*?)</span>", b, re.S)
        title = re.sub(r"<[^>]+>", "", t.group(1)).strip() if t else ""
        p = PRICE_RE.search(b[:8000])
        cents = _cents(p.group(1)) if p else None
        if not title or cents is None:
            continue
        seen.add(asin)
        out.append((asin, title, cents, f"https://{domain}/dp/{asin}", "Amazon", None))
        if len(out) >= 20:
            break
    if not out:
        raise RuntimeError("self-scrape parsed 0 products (page shape changed or blocked).")
    return out
