"""Signal alerts for PriceMatters.

Alerts are pushed to a Redis queue; a small cron on Michi's home server
polls GET /alerts (admin-key) and forwards them to Signal via the existing
notify_queue.sh pipeline (which handles night-time digesting).

Design rules:
- never raise: alerting must not break searches
- cooldown per alert kind so one bad night can't spam
- fire-and-forget: if Redis is down, alerts are silently skipped
"""
import json
import os
import time


PFX = "pm:v2"  # namespace only; independent of main.CACHE_VERSION on purpose


def _redis():
    try:
        from cache import _redis
        return _redis()
    except Exception:
        return None


def emit(kind: str, text: str, severity: str = "warn", cooldown_s: int = 21600):
    """Queue an alert, deduped by kind for cooldown_s. Never raises."""
    try:
        r = _redis()
        if r is None:
            return
        ck = f"{PFX}:alertcd:{kind}"
        if not r.set(ck, "1", ex=cooldown_s, nx=True):
            return  # still cooling down
        item = json.dumps({"ts": int(time.time()), "kind": kind,
                           "severity": severity, "text": text})
        rk = f"{PFX}:alerts"
        r.rpush(rk, item)
        r.ltrim(rk, -100)  # cap the backlog
        r.expire(rk, 604800)  # a week unread = nobody is polling; drop it
        print(f"[alert] {kind}: {text}", flush=True)
    except Exception as e:
        print(f"[alert] emit failed: {e}", flush=True)


def pending():
    """Pop and return all queued alerts (fire-and-forget by design)."""
    r = _redis()
    if r is None:
        return []
    rk = f"{PFX}:alerts"
    try:
        items = r.lrange(rk, 0, -1)
        r.delete(rk)
        return [json.loads(i) for i in items if i]
    except Exception:
        return []


def _ym() -> str:
    return time.strftime("%Y%m", time.gmtime())


def serpapi_key_failed(index: int, err: str):
    """A SerpApi key hit a hard error (usually monthly quota)."""
    emit(f"serpkey{index}",
         f"SerpApi key #{index + 1} failed: {err[:120]}. Rotating to the next key.",
         severity="warn", cooldown_s=43200)


def serpapi_usage_check(index: int, used: int, quota: int):
    """Warn when a key approaches its monthly limit (80% / 95%)."""
    if quota <= 0:
        return
    pct = used / quota
    if pct >= 0.95:
        emit(f"serp95-{index}-{_ym()}",
             f"SerpApi key #{index + 1} at {used}/{quota} monthly requests (95%+). "
             f"Add another SERPAPI_API_KEYS entry or upgrade the plan.",
             severity="warn", cooldown_s=604800)
    elif pct >= 0.80:
        emit(f"serp80-{index}-{_ym()}",
             f"SerpApi key #{index + 1} at {used}/{quota} monthly requests (80%).",
             severity="info", cooldown_s=604800)


def provider_switch(marketplace: str, last: str, now: str):
    emit(f"prov-{marketplace}",
         f"Provider switched for {marketplace}: {last} → {now}. "
         f"Results may differ; check the admin System panel.",
         severity="warn", cooldown_s=21600)


def mock_fallback(marketplace: str):
    emit("mockfall",
         f"All providers failed for {marketplace} — serving mock demo data. "
         f"Something is badly broken; check backend logs.",
         severity="crit", cooldown_s=3600)


def inquiry_received(name: str, email: str, slot: str):
    emit("inq",
         f"New ad inquiry: {name} <{email}> ({slot or 'general'}). "
         f"Also in your inbox + admin dashboard.",
         severity="info", cooldown_s=60)


def contact_limited():
    emit("ctlim",
         "Someone hit the 1/day contact-form limit (possible spam or a very "
         "eager advertiser). Nothing stored, nothing to do.",
         severity="info", cooldown_s=43200)


# searched from small to large; alert only the highest newly-crossed rung
_LADDER = [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000,
           250000, 500000, 1000000]


def check_milestones():
    """Called on each /alerts poll: celebrate total search/click milestones
    and record traffic days. Self-contained DB access, never raises."""
    import os
    import psycopg
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return
    r = _redis()
    if r is None:
        return
    with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM events WHERE kind='search'")
        searches = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM events WHERE kind='click'")
        clicks = int(cur.fetchone()[0])
        cur.execute("""SELECT COUNT(*) FROM events WHERE kind='search'
                       AND ts >= date_trunc('day', now())""")
        today = int(cur.fetchone()[0])

    def crossed(kind: str, total: int):
        mk = f"{PFX}:ms:{kind}"
        try:
            seen = int(r.get(mk) or 0)
        except Exception:
            return
        rungs = [x for x in _LADDER if x <= total and x > seen]
        if rungs:
            r.set(mk, rungs[-1])
            emit(f"ms-{kind}-{rungs[-1]}",
                 f"Milestone: {rungs[-1]}+ total {kind} on PriceMatters!",
                 severity="info", cooldown_s=60)

    crossed("searches", searches)
    crossed("clicks", clicks)

    # record day: quiet baseline on first ever run
    rk = f"{PFX}:recday"
    try:
        best = int(r.get(rk) or 0)
    except Exception:
        best = 0
    if best == 0:
        if today >= 10:
            r.set(rk, today)
    elif today > best:
        r.set(rk, today)
        emit(f"recday-{today}",
             f"Record day: {today} searches (previous best {best}). "
             f"Something is resonating!",
             severity="info", cooldown_s=3600)


def usage_snapshot() -> list:
    """Per-key monthly usage for the admin System panel: [{index, used, quota}]."""
    r = _redis()
    if r is None:
        return []
    keys = _serpapi_keys()
    quota = int(os.getenv("SERPAPI_QUOTA", "250") or 250)
    out = []
    ym = _ym()
    try:
        for i in range(len(keys)):
            raw = r.get(f"{PFX}:serpq:{i}:{ym}")
            out.append({"index": i + 1, "used": int(raw or 0), "quota": quota})
    except Exception:
        pass
    return out


def _serpapi_keys() -> list:
    """SERPAPI_API_KEYS (comma list) wins; SERPAPI_API_KEY stays first for compat."""
    keys = [k.strip() for k in os.getenv("SERPAPI_API_KEYS", "").split(",") if k.strip()]
    legacy = os.getenv("SERPAPI_API_KEY", "").strip()
    if legacy and legacy not in keys:
        keys.insert(0, legacy)
    return keys
