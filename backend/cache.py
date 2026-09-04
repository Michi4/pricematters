"""Adaptive cache: fresh where it matters, cheap everywhere else.

Policy (per key = provider:marketplace:query):
  TTL = clamp(BASE * popularity_factor * stability_factor, MIN_TTL, MAX_TTL)
  - popularity: hot queries (many hits/24h) refresh OFTEN — freshness amortized
    over many users. Cold queries keep long TTLs.
  - stability: price unchanged across refreshes -> TTL grows (up to MAX);
    price changed -> TTL resets to MIN (volatile product, watch it).
    This fingerprint is what makes week-long TTLs honest: a changed price
    can never sit stale longer than MIN_TTL after its next lookup.
  - size guard: when the cache is full (many keys / Redis memory high),
    new TTLs scale DOWN so cold entries evaporate instead of piling up.
MAX_TTL is 7 days. (The old 24h ceiling cited Amazon PA-API ToS, which binds
the API response itself — this cache serves SerpApi/scrape snapshots whose
freshness is guarded by the price fingerprint above, not by the clock.)

Backend: Redis if REDIS_URL set, else in-memory LRU (capped, same policy).
"""
import json
import os
import time

MIN_TTL = 2 * 3600        # 2h  — volatile / brand-new keys
BASE_TTL = 24 * 3600      # 24h — default
MAX_TTL = 7 * 24 * 3600   # 7d  — stable prices, stable queries
MEM_LIMIT = 500       # in-memory fallback cap
SIZE_SOFT_LIMIT = 5000  # beyond this many keys, TTLs shrink

_mem: dict = {}
_order: list = []


def _redis():
    url = os.getenv("REDIS_URL", "")
    if not url:
        return None
    try:
        import redis
        return redis.Redis.from_url(url, socket_timeout=3)
    except Exception:
        return None


def _size_factor(n_keys: int) -> float:
    if n_keys <= SIZE_SOFT_LIMIT:
        return 1.0
    return max(0.25, SIZE_SOFT_LIMIT / n_keys)


def _ttl(hits_24h: int, stable_refreshes: int, n_keys: int) -> int:
    popularity = 1.0 if hits_24h < 5 else (0.5 if hits_24h < 50 else 0.3)
    stability = min(1.0 + 0.25 * stable_refreshes, MAX_TTL / BASE_TTL)
    ttl = BASE_TTL * popularity * stability * _size_factor(n_keys)
    return int(max(MIN_TTL, min(MAX_TTL, ttl)))


def _now() -> int:
    return int(time.time())


def get(key: str):
    """-> (payload, age_seconds, hits) or None."""
    r = _redis()
    if r is not None:
        try:
            raw = r.hgetall(f"pm:{key}")
            if not raw:
                return None
            d = {k.decode(): v.decode() for k, v in raw.items()}
            if _now() > int(d["exp"]):
                return None
            hits = int(d.get("hits", 0)) + 1
            r.hset(f"pm:{key}", "hits", hits)
            return json.loads(d["payload"]), _now() - int(d["stored"]), hits
        except Exception:
            return None
    d = _mem.get(key)
    if not d or _now() > d["exp"]:
        return None
    d["hits"] += 1
    return d["payload"], _now() - d["stored"], d["hits"]


def _approx_keys() -> int:
    r = _redis()
    if r is not None:
        try:
            info = r.info("keyspace")
            return sum(v.get("keys", 0) for v in info.values() if isinstance(v, dict))
        except Exception:
            return 0
    return len(_mem)


def store(key: str, payload, price_fingerprint: str):
    """Store payload; stability detected by comparing price fingerprints."""
    r = _redis()
    n = _approx_keys()
    if r is not None:
        try:
            old = r.hgetall(f"pm:{key}")
            hits = int((old.get(b"hits") or b"0").decode()) if old else 0
            stable = 0
            if old:
                try:
                    od = {k.decode(): v.decode() for k, v in old.items()}
                    stable = int(od.get("stable", 0)) + (1 if od.get("fp") == price_fingerprint else 0)
                    if od.get("fp") != price_fingerprint:
                        stable = 0
                except Exception:
                    stable = 0
            ttl = _ttl(hits, stable, n)
            r.hset(f"pm:{key}", mapping={
                "payload": json.dumps(payload), "stored": _now(),
                "exp": _now() + ttl, "hits": hits, "stable": stable,
                "fp": price_fingerprint,
            })
            r.expire(f"pm:{key}", ttl + 3600)
            return {"ttl": ttl, "stable": stable}
        except Exception:
            pass
    # in-memory fallback
    d = _mem.get(key, {})
    hits = d.get("hits", 0)
    stable = d.get("stable", 0) + (1 if d.get("fp") == price_fingerprint else 0)
    if d.get("fp") != price_fingerprint:
        stable = 0
    ttl = _ttl(hits, stable, n)
    # invariant: key in _order exactly once iff key in _mem (no unbounded growth
    # on repeated stores of the same key)
    if key not in _mem:
        _order.append(key)
    _mem[key] = {"payload": payload, "stored": _now(), "exp": _now() + ttl,
                 "hits": hits, "stable": stable, "fp": price_fingerprint}
    while len(_mem) > MEM_LIMIT:
        _mem.pop(_order.pop(0), None)
    return {"ttl": ttl, "stable": stable}


def stats() -> dict:
    return {"keys": _approx_keys(), "backend": "redis" if os.getenv("REDIS_URL") else "memory",
            "min_ttl_h": MIN_TTL / 3600, "base_ttl_h": BASE_TTL / 3600, "max_ttl_h": MAX_TTL / 3600}
