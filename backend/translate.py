"""Query translation so users find everything (DE<->EN).

Uses MyMemory free API (no key needed, graceful degradation to the original
query on any failure). Results really shine once a real product provider
(ScrapingBee/Rainforest/...) is configured — with mock data it just merges.
Translated queries are cached in-memory.
"""
import urllib.parse
import urllib.request
import json

_cache: dict[str, str] = {}


def translate(query: str, src: str = "de", dst: str = "en") -> str:
    key = f"{src}|{dst}|{query.lower()}"
    if key in _cache:
        return _cache[key]
    out = query
    try:
        params = urllib.parse.urlencode({"q": query, "langpair": f"{src}|{dst}"})
        req = urllib.request.Request(
            "https://api.mymemory.translated.net/get?" + params,
            headers={"User-Agent": "pricematters/0.1"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        t = (data.get("responseData") or {}).get("translatedText", "").strip()
        # MyMemory returns the query uppercased / with warnings on rate limit — ignore those
        if t and t.lower() != query.lower() and "QUERY LENGTH LIMIT" not in t:
            out = t
    except Exception:
        pass
    _cache[key] = out
    return out


def query_variants(query: str, marketplace: str) -> list[str]:
    """Original + translation (if different). Dedupe preserves order."""
    variants = [query]
    if marketplace in ("de", "at", "fr"):
        t = translate(query, "de", "en")
        if t != query:
            variants.append(t)
    else:
        t = translate(query, "en", "de")
        if t != query:
            variants.append(t)
    return variants
