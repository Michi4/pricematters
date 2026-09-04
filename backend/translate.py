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

# Domain glossary: MT services mangle grocery terms (Erdnussmus -> "peanut sauce").
# These are checked first, MyMemory is only the fallback.
GLOSSARY = {
    ("de", "en"): {
        "erdnussmus": "peanut butter",
        "erdnussbutter": "peanut butter",
        "erdnuss creme": "peanut butter",
        "bio": "organic",
        "haferflocken": "oats",
        "kaffee": "coffee",
        "kaffeebohnen": "coffee beans",
        "reis": "rice",
        "basmati": "basmati rice",
        "linsen": "lentils",
        "quinoa": "quinoa",
        "olivenoel": "olive oil",
        "olivenöl": "olive oil",
        "honig": "honey",
        "marmelade": "jam",
        "nutella": "nutella",
        "schokolade": "chocolate",
        "mehl": "flour",
        "zucker": "sugar",
        "salz": "salt",
        "pfeffer": "pepper",
        "nudeln": "pasta",
        "spaghetti": "spaghetti",
        "muesli": "muesli",
        "müsli": "muesli",
        "cornflakes": "cornflakes",
        "milch": "milk",
        "butter": "butter",
        "kaese": "cheese",
        "käse": "cheese",
        "joghurt": "yogurt",
        "eier": "eggs",
        "toast": "toast bread",
        "brot": "bread",
        "tee": "tea",
        "saft": "juice",
        "wasser": "water",
        "proteinpulver": "protein powder",
        "protein": "protein",
        "kreativ": "creative",
        "waschmittel": "laundry detergent",
        "spuelmittel": "dish soap",
        "spülmittel": "dish soap",
        "toilettenpapier": "toilet paper",
        "windeln": "diapers",
        "zahnpasta": "toothpaste",
        "shampoo": "shampoo",
        "duschgel": "shower gel",
        "klopapier": "toilet paper",
    },
    ("en", "de"): {
        "peanut butter": "Erdnussmus",
        "organic": "Bio",
        "oats": "Haferflocken",
        "coffee": "Kaffee",
        "coffee beans": "Kaffeebohnen",
        "rice": "Reis",
        "lentils": "Linsen",
        "olive oil": "Olivenöl",
        "honey": "Honig",
        "jam": "Marmelade",
        "chocolate": "Schokolade",
        "flour": "Mehl",
        "sugar": "Zucker",
        "pasta": "Nudeln",
        "milk": "Milch",
        "cheese": "Käse",
        "yogurt": "Joghurt",
        "eggs": "Eier",
        "bread": "Brot",
        "tea": "Tee",
        "juice": "Saft",
        "protein powder": "Proteinpulver",
        "protein": "Protein",
        "laundry detergent": "Waschmittel",
        "dish soap": "Spülmittel",
        "toilet paper": "Toilettenpapier",
        "diapers": "Windeln",
        "toothpaste": "Zahnpasta",
        "shampoo": "Shampoo",
        "shower gel": "Duschgel",
    },
}


def glossary_lookup(query: str, src: str, dst: str) -> str | None:
    """Word/phrase match against the grocery glossary. None = no hit."""
    g = GLOSSARY.get((src, dst))
    if not g:
        return None
    low = query.strip().lower()
    if low in g:
        return g[low]
    import re
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(p) for p in sorted(g, key=len, reverse=True)) + r")\b")
    out = pattern.sub(lambda m: g[m.group(0)], low)
    return out if out != low else None


def _redis_hget(key: str) -> str | None:
    """Translations never change: persist across restarts (30d) so repeat
    queries skip the network entirely. Fail-open, like everything here."""
    try:
        import os
        import redis
        url = os.getenv("REDIS_URL", "")
        if not url:
            return None
        return redis.Redis.from_url(url, socket_timeout=2).hget("pm:i18n", key)
    except Exception:
        return None


def _redis_hset(key: str, val: str):
    try:
        import os
        import redis
        url = os.getenv("REDIS_URL", "")
        if not url:
            return
        r = redis.Redis.from_url(url, socket_timeout=2)
        r.hset("pm:i18n", key, val)
        r.expire("pm:i18n", 30 * 86400)
    except Exception:
        pass


def translate(query: str, src: str = "de", dst: str = "en") -> str:
    key = f"{src}|{dst}|{query.lower()}"
    if key in _cache:
        return _cache[key]
    hit = _redis_hget(key)
    if hit is not None:
        out = hit.decode() if isinstance(hit, bytes) else hit
        _cache[key] = out
        return out
    out = query
    hit = glossary_lookup(query, src, dst)
    if hit:
        out = hit
    else:
        try:
            params = urllib.parse.urlencode({"q": query, "langpair": f"{src}|{dst}"})
            req = urllib.request.Request(
                "https://api.mymemory.translated.net/get?" + params,
                headers={"User-Agent": "pricematters/0.1"},
            )
            # 3s cap: MyMemory answers in <1s when healthy; an outage must not
            # stall a fresh search for 8s (glossary + original query cover it)
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read().decode())
            t = (data.get("responseData") or {}).get("translatedText", "").strip()
            # MyMemory returns the query uppercased / with warnings on rate limit — ignore those
            if t and t.lower() != query.lower() and "QUERY LENGTH LIMIT" not in t:
                out = t
        except Exception:
            pass
    _cache[key] = out
    _redis_hset(key, out)
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
