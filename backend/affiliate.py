"""Affiliate link builder — the important insight:

Commission does NOT need any API approval. Your PartnerNet PartnerTag
(e.g. websters02-21) in the URL is enough for the 24h cookie + commission.
Only *product data* (titles/prices via API) needs Creators API approval.

Same for other shops: Awin deeplinks just wrap the merchant URL, no API call.
So: build links via this script from day 1, get data from mock/free-tier
providers/feeds, swap the data source later without touching a single link.
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
    # pure ASIN -> canonical dp URL
    if len(value) == 10 and "/" not in value:
        return f"https://{domain}/dp/{value}?tag={tag}"
    # otherwise force/overwrite the tag param, keep the rest
    parts = urlparse(value if "://" in value else f"https://{domain}/{value.lstrip('/')}")
    q = dict(parse_qsl(parts.query))
    q["tag"] = tag
    return urlunparse((parts.scheme, parts.netloc or domain, parts.path, "", urlencode(q), ""))


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
