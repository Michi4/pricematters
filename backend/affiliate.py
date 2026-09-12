"""Affiliate link builder — the important insight:

Commission does NOT need any API approval. Your PartnerNet PartnerTag
in the URL is enough for the 24h cookie + commission.
Only *product data* (titles/prices via API) needs Creators API approval.

Same for other shops: Awin deeplinks just wrap the merchant URL, no API call.
So: build links via this script from day 1, get data from mock/free-tier
providers/feeds, swap the data source later without touching a single link.

Each Amazon EU program issues its own Partner ID — tags are resolved per
marketplace via tag_for() (DACH shares the .de ID, all shop on amazon.de).
Locales without a program ID get plain links (no dead ?tag= param).
"""
import urllib.parse
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

MARKETPLACES = {
    # DACH has no .at/.ch stores: Austria & Switzerland shop on amazon.de
    "de": "www.amazon.de",
    "at": "www.amazon.de",
    "ch": "www.amazon.de",
    "fr": "www.amazon.fr",
    "it": "www.amazon.it",
    "es": "www.amazon.es",
    "nl": "www.amazon.nl",
    "se": "www.amazon.se",
    "pl": "www.amazon.pl",
    "be": "www.amazon.com.be",
    "co.uk": "www.amazon.co.uk",
    "ie": "www.amazon.ie",
    "com": "www.amazon.com",
    "ca": "www.amazon.ca",
    "com.mx": "www.amazon.com.mx",
    "com.br": "www.amazon.com.br",
    "com.au": "www.amazon.com.au",
    "co.jp": "www.amazon.co.jp",
    "in": "www.amazon.in",
    "ae": "www.amazon.ae",
    "sa": "www.amazon.sa",
    "sg": "www.amazon.sg",
    "com.tr": "www.amazon.com.tr",
}


def affiliate_url(url_or_asin: str, tag: str, marketplace: str = "de") -> str:
    domain = MARKETPLACES.get(marketplace, MARKETPLACES["de"])
    value = url_or_asin.strip()
    # no program ID for this locale -> plain link, never a dead ?tag=
    if not tag:
        if len(value) == 10 and "/" not in value:
            return f"https://{domain}/dp/{value}"
        return value if "://" in value else f"https://{domain}/{value.lstrip('/')}"
    # pure ASIN -> canonical dp URL
    if len(value) == 10 and "/" not in value:
        return f"https://{domain}/dp/{value}?tag={tag}"
    # otherwise force/overwrite the tag param, keep the rest
    parts = urlparse(value if "://" in value else f"https://{domain}/{value.lstrip('/')}")
    q = dict(parse_qsl(parts.query))
    q["tag"] = tag
    return urlunparse((parts.scheme, parts.netloc or domain, parts.path, "", urlencode(q), ""))


# Marketplace code -> program env var (kept for reference; resolution goes
# through PROGRAMS/tag_for so /admin edits apply).
TAG_ENVS = {
    "de": "AMAZON_TAG_DE", "at": "AMAZON_TAG_DE", "ch": "AMAZON_TAG_DE",
    "co.uk": "AMAZON_TAG_UK", "fr": "AMAZON_TAG_FR",
    "es": "AMAZON_TAG_ES", "it": "AMAZON_TAG_IT",
}

# Every EU Associates/PartnerNet program we can join, with its console URL.
# code = short settings key suffix; locales = backend marketplace codes covered.
PROGRAMS = [
    {"code": "de", "name": "Amazon.de PartnerNet", "console": "https://partnernet.amazon.de/",
     "env": "AMAZON_TAG_DE", "locales": ["de", "at", "ch"]},
    {"code": "es", "name": "Afiliados Amazon.es", "console": "https://afiliados.amazon.es/",
     "env": "AMAZON_TAG_ES", "locales": ["es"]},
    {"code": "uk", "name": "Amazon.co.uk Associates", "console": "https://affiliate-program.amazon.co.uk/",
     "env": "AMAZON_TAG_UK", "locales": ["co.uk"]},
    {"code": "fr", "name": "Club Partenaires Amazon", "console": "https://partenaires.amazon.fr/",
     "env": "AMAZON_TAG_FR", "locales": ["fr"]},
    {"code": "it", "name": "Programma Affiliazione Amazon.it", "console": "https://programma-affiliazione.amazon.it/",
     "env": "AMAZON_TAG_IT", "locales": ["it"]},
    {"code": "us", "name": "Amazon.com Associates", "console": "https://affiliate-program.amazon.com/",
     "env": "AMAZON_TAG_US", "locales": ["com"]},
]
PROGRAM_CODES = {p["code"] for p in PROGRAMS}

_SETTINGS_DDL = "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
_TAGS_CACHE: dict = {"at": 0.0, "tags": {}}
_TAGS_TTL = 60.0


def _db_tags() -> dict:
    """Owner-edited IDs from the settings table (edited in /admin)."""
    import os
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return {}
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute(_SETTINGS_DDL)
            cur.execute("SELECT key, value FROM settings WHERE key LIKE 'tag\\_%'")
            return {k[4:]: (v or "") for k, v in cur.fetchall() if k.startswith("tag_")}
    except Exception:
        return {}


def get_tags() -> dict:
    """Resolved Partner ID per program code: settings table first, env fallback.
    Cached 60s (tag_for runs per result row); invalidate_tags() on admin edit."""
    import os
    import time
    now = time.time()
    if now - _TAGS_CACHE["at"] < _TAGS_TTL:
        return _TAGS_CACHE["tags"]
    tags = _db_tags()
    for p in PROGRAMS:
        tags.setdefault(p["code"], os.getenv(p["env"], ""))
    _TAGS_CACHE.update(at=now, tags=tags)
    return tags


def invalidate_tags() -> None:
    _TAGS_CACHE["at"] = 0.0


def program_tags() -> list:
    """Full program list with resolved ID + source for the /admin panel."""
    import os
    db = _db_tags()
    out = []
    for p in PROGRAMS:
        if p["code"] in db and db[p["code"]]:
            out.append({**p, "tag": db[p["code"]], "source": "admin"})
        elif os.getenv(p["env"], ""):
            out.append({**p, "tag": os.getenv(p["env"], ""), "source": "env"})
        else:
            out.append({**p, "tag": "", "source": ""})
    return out


def tag_for(marketplace: str) -> str:
    """Partner ID for a marketplace, or '' when we have no program there.

    Only locales with their own program ID are tagged — a foreign tag earns
    nothing, so those links stay plain until the ID lands."""
    for p in PROGRAMS:
        if marketplace in p["locales"]:
            return get_tags().get(p["code"], "")
    return ""


def awin_deeplink(merchant_url: str, advertiser_id: str, publisher_id: str) -> str:
    """Wrap a shop URL in your Awin click tracking (commission without any API).
    Needs: free Awin publisher account -> publisher_id, joined program -> advertiser_id.
    Without those set, returns the plain URL (no tracking, still works)."""
    if not advertiser_id or not publisher_id:
        return merchant_url
    return ("https://www.awin1.com/cread.php?awinmid=" + advertiser_id
            + "&awinaffid=" + publisher_id + "&ued="
            + urllib.parse.quote(merchant_url, safe=""))


def monetize(url: str, shop: str, marketplace: str, tag: str) -> str:
    """One entry point: Amazon -> PartnerTag, feed shops -> Awin, else plain link."""
    import os
    if shop.lower() == "amazon":
        return affiliate_url(url, tag, marketplace)
    adv = os.getenv("AWIN_ADVERTISER_IDS", "")  # "shop:1234,shop2:5678"
    pub = os.getenv("AWIN_PUBLISHER_ID", "")
    mapping = dict(p.split(":") for p in adv.split(",") if ":" in p)
    if shop in mapping and pub:
        return awin_deeplink(url, mapping[shop], pub)
    return url
