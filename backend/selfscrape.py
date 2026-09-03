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

PROXY_SOURCES = [
    # (name, url, format) — all free, no key, verified 2026-09
    ("proxyscrape", "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
                    "&timeout=8000&country=all&ssl=all&anonymity=all", "text"),
    ("iplocate-http", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt", "text"),
    ("iplocate-https", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/https.txt", "text"),
    ("iplocate-de", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/countries/DE/proxies.txt", "text"),
    ("iplocate-all", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/all-proxies.txt", "prefixed"),
    ("thespeedx", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", "text"),
    ("clarketm", "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", "text"),
    ("geonode", "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked"
                "&sort_type=desc&protocols=http%2Chttps", "geonode"),
]
# Keyed quality proxies (free signups, YOURS — tried before any free pool):
#   WEBSHARE_PROXIES="user:pass@host:port,user:pass@host2:port2"  (10 free + 1GB/mo at webshare.io)
#   IPVANISH_USER / IPVANISH_PASS / IPVANISH_HOST (default fra.socks.ipvanish.com:1080, SOCKS5)
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


def _keyed_http_proxies() -> list[str]:
    """Your private quality proxies: 'user:pass@host:port,...' (Webshare free 10)."""
    out = []
    for part in os.getenv("WEBSHARE_PROXIES", "").split(","):
        part = part.strip()
        if part and ":" in part:
            out.append(part if "://" in part else f"http://{part}")
    return out


def _ipvanish() -> tuple[str, str, str] | None:
    u, p = os.getenv("IPVANISH_USER", ""), os.getenv("IPVANISH_PASS", "")
    h = os.getenv("IPVANISH_HOST", "fra.socks.ipvanish.com:1080")
    return (u, p, h) if u and p else None


def _fetch_source(name: str, url: str, fmt: str) -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pricematters/0.1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode(errors="ignore")
        if fmt == "geonode":
            import json as _json
            items = _json.loads(body).get("data", [])
            return [f"{d['ip']}:{d['port']}" for d in items if d.get("ip") and d.get("port")]
        if fmt == "prefixed":
            # e.g. "socks5://1.2.3.4:1080" / "http://1.2.3.4:8080" (iplocate all-proxies.txt)
            out = []
            for l in body.splitlines():
                m = re.match(r"^(socks5|socks4|https?)://(\d+\.\d+\.\d+\.\d+:\d+)\s*$", l.strip())
                if m:
                    scheme, addr = m.groups()
                    out.append(addr if scheme in ("http", "https") else f"{scheme}://{addr}")
            return out
        return [l.strip() for l in body.splitlines()
                if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", l.strip())]
    except Exception:
        return []


_good: list[str] = []  # proxies that worked recently go first


def _pool() -> list[str]:
    global _last_fetch, _pool
    with _lock:
        if time.time() - _last_fetch < POOL_TTL and _pool:
            return _good + [p for p in _pool if p not in _good]
    merged: list[str] = []
    for name, url, fmt in PROXY_SOURCES:
        for px in _fetch_source(name, url, fmt)[:150]:  # per-source quota: diversity beats depth
            if px not in merged:
                merged.append(px)
    with _lock:
        _pool, _last_fetch = merged[:400], time.time()
        return _good + [p for p in _pool if p not in _good]


def _remember_good(px: str):
    with _lock:
        if px in _good:
            _good.remove(px)
        _good.insert(0, px)
        del _good[20:]


UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _open(url: str, opener=None) -> str | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    })
    try:
        if opener:
            with opener.open(req, timeout=12) as r:
                html = r.read().decode("utf-8", errors="ignore")
        else:
            with urllib.request.urlopen(req, timeout=12) as r:
                html = r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    if "Enter the characters you see" in html or len(html) < 20000:
        return None  # captcha or block page
    return html


_socks_lock = threading.Lock()


def _via_socks(url: str, host: str, port: int, user: str = "", pw: str = "", version=None) -> str | None:
    """Generic SOCKS fetch (PySocks). Used for IPVanish AND free socks pools."""
    try:
        import socket
        import socks
    except ImportError:
        return None
    import socket as _sockmod
    orig = _sockmod.socket
    with _socks_lock:
        try:
            socks.set_default_proxy(version or socks.SOCKS5, host, port,
                                    username=user or None, password=pw or None)
            _sockmod.socket = socks.socksocket
            return _open(url)
        except Exception:
            return None
        finally:
            _sockmod.socket = orig


def _via_ipvanish(url: str) -> str | None:
    """Your private IPVanish SOCKS5 (Frankfurt for amazon.de). Needs PySocks."""
    creds = _ipvanish()
    if not creds:
        return None
    user, pw, hostport = creds
    host, _, port = hostport.partition(":")
    return _via_socks(url, host, int(port or 1080), user, pw)


def _fetch(url: str) -> str | None:
    """Tiered: Webshare (yours) -> IPVanish SOCKS5 (yours) -> free pools."""
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
    for px in _keyed_http_proxies()[:10]:
        try:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": px, "https": px}))
            html = _open(url, opener)
            if html:
                return html
        except Exception:
            continue
    html = _via_ipvanish(url)
    if html:
        return html
    pool = _pool()
    random.shuffle(pool)
    for px in pool[:10]:
        try:
            if px.startswith("socks"):
                m = re.match(r"(socks[45]?)://(\d+\.\d+\.\d+\.\d+):(\d+)", px)
                if not m:
                    continue
                import socks as _socks
                ver = _socks.SOCKS4 if m.group(1) == "socks4" else _socks.SOCKS5
                html = _via_socks(url, m.group(2), int(m.group(3)), version=ver)
                if html:
                    _remember_good(px)
                    return html
                continue
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            req.set_proxy(px if "://" in px else f"http://{px}", "http")
            req.set_proxy(px if "://" in px else f"http://{px}", "https")
            with urllib.request.urlopen(req, timeout=12) as r:
                html = r.read().decode("utf-8", errors="ignore")
            if "Enter the characters you see" in html or len(html) < 20000:
                continue
            _remember_good(px)
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
