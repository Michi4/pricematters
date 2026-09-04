"""FastAPI backend: /search + /extract + /health.

Amazon data: DATA_PROVIDER=mock (default, no keys) | scrapingbee | rainforest | creators
Whole web:   + serpapapi via providers=serpapi, or stores=all fan-out
Feed shops:  Awin & co via nightly CSV import (feeds.py) into Postgres,
             searched locally and merged when stores=all (default).
Query:       searched as-is + auto-translated (DE<->EN), merged, deduped.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import time
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from affiliate import monetize, affiliate_url
from extractor import extract_quantity, unit_price
from providers import PROVIDERS
from translate import query_variants

app = FastAPI(title="PriceMatters API")
DEFAULT_TAG = "websters02-21"
# cache stores RAW rows; qty/unit-price are re-enriched per request, so extractor
# fixes apply to cached data without bumping this. Bump only for provider-param changes.
CACHE_VERSION = "v2"

MAX_QUERY_LEN = 120

# per-IP rate limits for /search: what a normal user never hits, bots do
RATE_MIN = int(os.getenv("RATE_SEARCH_PER_MIN", "20"))
RATE_HOUR = int(os.getenv("RATE_SEARCH_PER_HOUR", "100"))


def _client_ip(request: Request) -> str:
    # Traefik sets X-Real-Ip to the verified client IP; XFF's leftmost entry is
    # attacker-controlled, so it must never win.
    real = request.headers.get("x-real-ip", "").strip()
    if real:
        return real
    xff = request.headers.get("x-forwarded-for", "")
    # rightmost XFF entry = closest trusted proxy hop (added by our own Traefik)
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "anon"


def _rate_retry_after(request: Request) -> int:
    """Fixed-window counters in Redis. Returns seconds to wait, 0 = allowed."""
    try:
        from cache import _redis
        r = _redis()
        if r is None:
            return 0
        ip = _client_ip(request)
        now = int(time.time())
        mk = f"{CACHE_VERSION}:rlm:{ip}:{now // 60}"
        hk = f"{CACHE_VERSION}:rlh:{ip}:{now // 3600}"
        p = r.pipeline()
        p.incr(mk); p.expire(mk, 90)
        p.incr(hk); p.expire(hk, 3700)
        out = p.execute()
        per_min, per_hour = out[0], out[2]
        if per_min > RATE_MIN:
            return max(61 - now % 60, 1)
        if per_hour > RATE_HOUR:
            return max(3601 - now % 3600, 1)
        return 0
    except Exception:
        return 0  # never block search because the limiter broke


# log_search: DDL once per process (not per request), bounded concurrency —
# a search burst must never exhaust threads or DB connections; drops instead.
_search_log_sem = threading.Semaphore(8)
_search_log_ddl_done = False


def log_search(query: str, marketplace: str, count: int):
    """Fire-and-forget in a daemon thread: feeds the 'Popular' row. No DB -> silently skipped."""
    def _run():
        global _search_log_ddl_done
        try:
            import psycopg
            url = os.getenv("DATABASE_URL", "")
            if not url:
                return
            with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
                if not _search_log_ddl_done:
                    cur.execute("""CREATE TABLE IF NOT EXISTS searches (
                        id BIGSERIAL PRIMARY KEY,
                        created_at TIMESTAMPTZ DEFAULT now(),
                        query TEXT, marketplace TEXT, result_count INT)""")
                    cur.execute("CREATE INDEX IF NOT EXISTS searches_market_ts ON searches (marketplace, created_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS searches_created_ts ON searches (created_at DESC)")
                    _search_log_ddl_done = True
                cur.execute(
                    "INSERT INTO searches (query, marketplace, result_count) VALUES (%s,%s,%s)",
                    (query[:120], marketplace, count),
                )
        except Exception:
            pass
        finally:
            _search_log_sem.release()
    if _search_log_sem.acquire(blocking=False):
        threading.Thread(target=_run, daemon=True).start()
    # else: saturated — skip logging rather than queuing unbounded threads

def enrich(pid: str, title: str, price_cents: int, url: str, shop: str, image: str | None, marketplace: str) -> dict:
    # regex only here: the AI fallback runs separately in a bounded pool with a
    # deadline (see _ai_fill), so one slow model call can't stall the request.
    q = extract_quantity(title)
    up = unit_price(price_cents, q) if q else None
    return {
        "asin": pid,
        "title": title,
        "priceCents": price_cents,
        "url": monetize(url, shop, marketplace, os.getenv("AMAZON_PARTNER_TAG", DEFAULT_TAG)),
        "store": shop,
        "image": image,
        "qty": {"value": q.value, "unit": q.unit, "kind": q.kind} if q else None,
        "unitPrice": {"per": up[0], "base": up[1]} if up else None,
    }


def _ai_fill(items: list[dict], titles: list[str | None], budget_s: float = 8.0):
    """Resolve regex-misses via AI with bounded parallelism + overall deadline.
    Items still unresolved after the budget keep qty=None (degrade, don't hang)."""
    from ai_extract import ai_quantity
    pending = [(i, t) for i, t in enumerate(titles) if t is not None]
    if not pending:
        return
    # no `with` block: executor exit would join hung threads and reintroduce
    # the stall we're avoiding; shutdown(wait=False) detaches stragglers
    # (each ai_quantity has its own 6s timeout, so they die on their own)
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        futs = {pool.submit(ai_quantity, t): i for i, t in pending}
        deadline = time.time() + budget_s
        for fut, i in futs.items():
            try:
                q = fut.result(timeout=max(deadline - time.time(), 0.1))
            except Exception:
                continue
            if q and items[i].get("qty") is None:
                price = items[i]["priceCents"]
                up = unit_price(price, q)
                items[i]["qty"] = {"value": q.value, "unit": q.unit, "kind": q.kind}
                items[i]["unitPrice"] = {"per": up[0], "base": up[1]} if up else None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _fetch_rows(cand: str, marketplace: str, variants: list[str], seen: set[str], timeout_s: float = 55.0) -> list:
    """Run one provider candidate with an overall deadline so a stalled source
    (living-room proxies, hung API) degrades to the next provider, not a hung worker."""
    pages = max(1, min(3, int(os.getenv("SEARCH_PAGES", "2"))))
    def _run():
        out = []
        for v in variants:
            for pg in range(1, pages + 1):
                fn = PROVIDERS[cand]
                try:
                    rows = fn(v, marketplace, pg) if pg > 1 else fn(v, marketplace)
                except TypeError:
                    # provider without page support (mock) — fetch once
                    rows = fn(v, marketplace)
                for row in rows:
                    if row[0] in seen:
                        continue
                    seen.add(row[0])
                    out.append(row)
                # an empty first page means there is no second — stop early
                if pg == 1 and not rows:
                    break
        return out
    # no `with` block: its exit would join the hung thread and reintroduce the
    # stall; detach instead (internal per-call timeouts kill it on their own)
    pool = ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(_run)
    try:
        return fut.result(timeout=timeout_s)
    except FuturesTimeout:
        print(f"[search] provider {cand} exceeded {timeout_s}s, skipping", flush=True)
        return []
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


@app.get("/health")
def health():
    return {"ok": True, "provider": os.getenv("DATA_PROVIDER", "mock")}


@app.delete("/inquiries/{inq_id}")
def delete_inquiry(inq_id: int, request: Request):
    """Admin-only: remove a single ad inquiry (spam, tests, typos)."""
    if not _admin_ok(request):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return JSONResponse(status_code=503, content={"ok": False, "error": "no database"})
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM ad_inquiries WHERE id = %s", (inq_id,))
            deleted = cur.rowcount
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        print(f"[inquiries] delete failed: {e}", flush=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": "internal"})


@app.get("/ready")
def ready():
    """Readiness: can this instance actually serve /search right now?
    Checks Redis (rate limiter) and Postgres (popular/track) without writing."""
    checks: dict = {}
    try:
        from cache import _redis
        r = _redis()
        # unconfigured Redis = degraded (limiters fail open by design), not down
        checks["redis"] = bool(r.ping()) if r is not None else None
    except Exception:
        checks["redis"] = False
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if url:
            with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            checks["db"] = True
        else:
            checks["db"] = None  # unconfigured: degraded, not down
    except Exception:
        checks["db"] = False
    ok = checks.get("redis", False) is not False and checks.get("db", None) is not False
    # Redis down only fails open the limiters (documented) — still report it
    status = 200 if ok else 503
    return JSONResponse(status_code=status, content={"ok": ok, **checks})


@app.get("/extract")
def extract(title: str = Query(..., max_length=2000), description: str = Query("", max_length=2000)):
    q = extract_quantity(title, description)
    return {"qty": q.__dict__ if q else None}


@app.get("/search")
def search(request: Request, q: str = Query(..., max_length=MAX_QUERY_LEN), marketplace: str = Query("de"),
           provider: str | None = Query(None), stores: str = Query("all"),
           lang: str = Query(""), tz: str = Query(""), w: int = Query(0)):
    # BIO = bio = Bio: searches & cache keys are case-insensitive,
    # display keeps the user's casing
    q = " ".join(q.split()).lower()[:MAX_QUERY_LEN]
    ql = q
    if not ql:
        return {"items": [], "meta": {}}
    # marketplace whitelist: anything unknown means junk cache keys / bad links
    from providers import AMAZON
    if marketplace not in AMAZON:
        marketplace = "de"
    wait = _rate_retry_after(request)
    if wait:
        try:
            from track import ip_hash, track
            track({"kind": "rate_limited", "query": ql, "marketplace": marketplace,
                   "ipd": ip_hash(_client_ip(request)), "w": w})
        except Exception:
            pass
        return JSONResponse(
            status_code=429,
            content={"items": [], "meta": {}, "error": "rate_limited", "retry_after": wait},
            headers={"Retry-After": str(wait)},
        )
    single = provider or None
    if single:
        chain = [single]
    else:
        env_chain = [p.strip() for p in os.getenv("DATA_PROVIDERS", "").split(",") if p.strip()]
        if env_chain:
            chain = env_chain
        else:
            # seamless fallback even when only DATA_PROVIDER is pinned:
            # start there, then walk the rest of the default chain, mock last
            from providers import DEFAULT_CHAIN as _dc
            first = os.getenv("DATA_PROVIDER", "")
            chain = ([first] if first in PROVIDERS else []) + [p for p in _dc if p != first and p != "mock"]
            if "mock" in _dc:
                chain.append("mock")
    chain = [c for c in chain if c in PROVIDERS]
    if not chain:
        return {"items": [], "meta": {"chain": chain}, "error": "no known provider in chain"}
    meta: dict = {"chain": chain, "feed_shops": "skipped",
                  "demo": chain == ["mock"], "queries": [ql]}
    try:
        from providers import ZONES  # noqa (zone labels documented there)
        meta["zone"] = marketplace
    except ImportError:
        pass
    name = chain[0]
    from cache import get as cache_get, store as cache_store
    from providers import DEFAULT_CHAIN  # noqa (keeps default order documented)
    seen: set[str] = set()
    items: list[dict] = []
    errors: dict = {}
    used = "mock"
    rows: list = []
    for cand in chain:
        ckey = f"{CACHE_VERSION}:{cand}:{marketplace}:{ql}"
        cached = cache_get(ckey) if cand != "mock" else None
        if cached:
            rows, age, hits = cached
            meta["cache"] = f"hit ({age // 60}m old, {hits} hits)"
            used = cand
            break
        try:
            variants = query_variants(ql, marketplace) if cand != "mock" else [ql]
            meta["queries"] = variants
            rows = _fetch_rows(cand, marketplace, variants, seen)
            if not rows:
                raise RuntimeError("no rows")
            fp = "|".join(f"{r[0]}:{r[2]}" for r in rows)
            info = cache_store(ckey, rows, fp)
            meta["cache"] = f"fresh (ttl {info['ttl'] // 3600}h)"
            used = cand
            break
        except RuntimeError as e:
            # log details server-side only; raw provider strings must not reach clients
            print(f"[search] provider {cand} failed for {ql!r}: {e}", flush=True)
            errors[cand] = "unavailable"
            rows = []
            continue
    if not rows and "mock" not in chain:
        rows = PROVIDERS["mock"](q, marketplace)
        used = "mock-fallback"
    if errors:
        meta["provider_errors"] = errors
    meta["provider_used"] = used
    meta["demo"] = used in ("mock", "mock-fallback")
    name = used
    ai_titles: list[str | None] = []

    def _add(row):
        seen.add(row[0])
        items.append(enrich(*row, marketplace))
        # row layout: (pid, title, price_cents, url, shop, image)
        ai_titles.append(row[1] if items[-1].get("qty") is None else None)

    for row in rows:
        _add(row)

    if stores == "all":
        try:
            from feeds import search_feeds
            for row in search_feeds(q):
                if row[0] in seen:
                    continue
                _add(row)
            meta["feed_shops"] = "included"
        except (RuntimeError, ImportError) as e:
            print(f"[search] feeds unavailable: {e}", flush=True)
            meta["feed_shops"] = "unavailable"

    # AI fallback for regex-misses only, bounded pool + deadline (degrades, never hangs)
    _ai_fill(items, ai_titles)

    items.sort(key=lambda i: (i["unitPrice"] is None,
                              (i["unitPrice"] or {}).get("base", "?"),
                              (i["unitPrice"] or {}).get("per", 1e18)))
    log_search(ql, marketplace, len(items))
    return {"items": items, "meta": meta}


@app.get("/cache/stats")
def cache_stats(request: Request):
    if not _admin_ok(request):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    from cache import stats
    return stats()


# Michi's personal favorites on the front page (no ranking, just love).
# Static fallback = his real products/prices; live SerpApi data whenever possible.
CURATED = [
    {"asin": "B08NCPB1SM", "title": "Volksshake Veganes Protein Schoko, 1000g",
     "price_cents": 2878, "rating": 4.0, "reviews": 267, "qty_value": 1, "qty_unit": "kg"},
    {"asin": "B00I5ABIFI", "title": "WMF Kult X Mix & Go Mini Smoothie Maker, 0,6l",
     "price_cents": 3024, "rating": 4.5, "reviews": 36822, "qty_value": 1, "qty_unit": "pcs"},
    {"asin": "B0D9H7PLK4", "title": "UGREEN LAN Switch Gigabit, 8-Port",
     "price_cents": 1410, "rating": 4.7, "reviews": 1710, "qty_value": 1, "qty_unit": "pcs"},
    {"asin": "B08HVR86TR", "title": "Oclean X Pro Schallzahnbürste, Dunkellila",
     "price_cents": 6509, "rating": 3.7, "reviews": 1060, "qty_value": 1, "qty_unit": "pcs"},
    {"asin": "B09B836TTQ", "title": "Corsair HS80 RGB Wireless Gaming-Headset, Carbon",
     "price_cents": 10084, "rating": 4.1, "reviews": 5704, "qty_value": 1, "qty_unit": "pcs"},
]


@app.get("/curated")
def curated(marketplace: str = Query("de")):
    from cache import get as cache_get, store as cache_store
    from providers import serpapi_product
    items = []
    for c in CURATED:
        key, data = f"{CACHE_VERSION}:curated:{c['asin']}", None
        hit = cache_get(key)
        if hit:
            data, _age, _hits = hit
        else:
            try:
                live = serpapi_product(c["asin"])
                data = {
                    "title": live["title"] or c["title"],
                    "price_cents": live["price_cents"] or c["price_cents"],
                    "image": live["image"],
                    # sanity: live rating shouldn't differ wildly from static
                    "rating": live["rating"] if live["rating"] and abs(live["rating"] - c["rating"]) < 2.0 else c["rating"],
                    "reviews": live["reviews"] if live["reviews"] and live["reviews"] > c["reviews"] * 0.5 else c["reviews"],
                    "live": True,
                }
                cache_store(key, data, f"{c['asin']}:{data['price_cents']}")
            except RuntimeError:
                data = {**c, "image": None, "live": False}
        tag = os.getenv("AMAZON_PARTNER_TAG", DEFAULT_TAG)
        from affiliate import MARKETPLACES
        domain = MARKETPLACES.get(marketplace, "www.amazon.de")
        items.append({**data, "asin": c["asin"], "store": "Amazon",
                      "qty": {"value": c.get("qty_value", 1), "unit": c.get("qty_unit", "pcs"), "kind": "count"},
                      "url": affiliate_url(f"https://{domain}/dp/{c['asin']}", tag, marketplace)})
    return {"items": items}


class Contact(BaseModel):
    name: str = Field("", max_length=120)
    email: str = Field("", max_length=160)
    message: str = Field("", max_length=2000)
    slot: str = Field("", max_length=40)


@app.post("/contact")
def contact(c: Contact, request: Request):
    """Ad-slot inquiry: Postgres if available, stdout log otherwise. Always honest ok-flag."""
    # spam guard: 1 message per IP per day — a real person never hits this,
    # and the 429 tells them the honest fallback (email us directly)
    try:
        from cache import _redis
        r = _redis()
        if r is not None:
            day = int(time.time()) // 86400
            mk = f"{CACHE_VERSION}:ctl:{_client_ip(request)}:{day}"
            if r.incr(mk) == 1:
                r.expire(mk, 90000)  # 25h: survives the UTC rollover cleanly
            if int(r.get(mk) or 0) > 1:
                return JSONResponse(status_code=429, content={
                    "ok": False, "error": "daily_limit",
                    "contact": "office@websters.at",
                })
    except Exception:
        pass
    if not (c.name.strip() or c.email.strip()) or not c.message.strip():
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid"})
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            raise RuntimeError("no db")
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS ad_inquiries
                   (id SERIAL PRIMARY KEY, name TEXT, email TEXT, slot TEXT,
                    message TEXT, created_at TIMESTAMPTZ DEFAULT now())"""
            )
            cur.execute(
                "INSERT INTO ad_inquiries (name, email, slot, message) VALUES (%s,%s,%s,%s)",
                (c.name[:120], c.email[:160], c.slot[:40], c.message[:2000]),
            )
        _send_inquiry_mail(c)  # best-effort; DB row is the source of truth
        return {"ok": True, "stored": "db"}
    except Exception as e:
        # no PII in logs: acknowledge without content
        print(f"[contact] inquiry stored to log ({e})", flush=True)
        return {"ok": True, "stored": "log"}


def _send_inquiry_mail(c: Contact) -> bool:
    """Best-effort SMTP (purelymail works with plain STARTTLS creds).
    Env: SMTP_HOST, SMTP_PORT (default 465=SSL, 587=STARTTLS),
    SMTP_USER, SMTP_PASS, SMTP_TO (default office@websters.at)."""
    host = os.getenv("SMTP_HOST", "")
    user = os.getenv("SMTP_USER", "")
    pwd = os.getenv("SMTP_PASS", "")
    if not (host and user and pwd):
        return False
    to = os.getenv("SMTP_TO", "office@websters.at")
    port = int(os.getenv("SMTP_PORT", "465"))
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = f"PriceMatters Anfrage [{c.slot or 'allgemein'}] {c.name[:60]}"
    msg["From"] = "PriceMatters <pricematters@websters.at>"
    msg["To"] = to
    reply = c.email.strip() or None
    if reply:
        msg["Reply-To"] = reply
    msg.set_content(f"Name: {c.name}\nE-Mail: {c.email}\nSlot: {c.slot}\n\n{c.message}")
    import smtplib
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as s:
                s.starttls()
                s.login(user, pwd)
                s.send_message(msg)
        return True
    except Exception as e:
        print(f"[contact] smtp send failed ({type(e).__name__})", flush=True)
        return False


@app.get("/popular")
def popular(marketplace: str = Query("all"), lang: str = Query("de"), limit: int = Query(4, le=20)):
    """Top real user queries, last 30 days. marketplace=all merges every
    marketplace/language; a specific code filters. Translated to the UI language.
    [] -> frontend shows nothing (no placeholders)."""
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return {"items": []}
        all_mk = marketplace in ("", "all", "*")
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            if all_mk:
                # merge all markets: same string typed anywhere sums up;
                # marketplaces kept per query so we know the source language
                cur.execute(
                    """SELECT query, COUNT(*) AS c, array_agg(DISTINCT marketplace) AS mps
                       FROM searches
                       WHERE created_at > now() - interval '30 days' AND query <> ''
                       GROUP BY query ORDER BY c DESC, MAX(created_at) DESC LIMIT %s""",
                    (max(limit * 2, 8),),
                )
                rows = cur.fetchall()
            else:
                cur.execute(
                    """SELECT query, COUNT(*) AS c, array_agg(DISTINCT marketplace) AS mps
                       FROM searches
                       WHERE marketplace = %s AND created_at > now() - interval '30 days'
                         AND query <> ''
                       GROUP BY query ORDER BY c DESC, MAX(created_at) DESC LIMIT %s""",
                    (marketplace, max(limit * 2, 8)),
                )
                rows = cur.fetchall()
        # translate chips to the selected UI language.
        # source language per query: de-ish markets store German queries,
        # everything else English; a mixed query keeps the majority side
        dst = "de" if lang.lower().startswith("de") else "en"
        seen: set[str] = set()
        out: list[str] = []
        for query, _c, mps in rows:
            src = "de" if mps and all(str(m) in ("de", "at", "ch") for m in mps) else "en"
            text = query
            if src != dst:
                from translate import translate
                text = translate(query, src, dst).rstrip(' ?.!').strip() or query
            k = text.lower()
            if k not in seen:
                seen.add(k)
                out.append(text)
        return {"items": out[:limit]}
    except Exception:
        return {"items": []}


# ---------- anonymous first-party analytics (DSGVO-safe) ----------

class Track(BaseModel):
    kind: str = Field("", max_length=40)
    query: str = Field("", max_length=180)
    marketplace: str = Field("", max_length=40)
    result_count: int = 0
    country: str = Field("", max_length=16)
    lang: str = Field("", max_length=32)
    tz: str = Field("", max_length=64)
    device: str = Field("", max_length=32)
    w: int = 0
    asin: str = Field("", max_length=32)
    store: str = Field("", max_length=40)
    pos: int = 0
    title: str = Field("", max_length=180)
    price_cents: int = 0
    ms: int = 0
    ref: str = Field("", max_length=180)


@app.post("/track")
def track_event(t: Track, request: Request):
    """Fire-and-forget collector. No cookies, no raw IPs (daily-salted hash only)."""
    # same shared-limiter style as /contact: 30/min per IP keeps the events
    # table safe from bloat bots; fail-open like the rest (never lose analytics
    # because the limiter broke)
    try:
        from cache import _redis
        r = _redis()
        if r is not None:
            mk = f"{CACHE_VERSION}:trl:{_client_ip(request)}:{int(time.time()) // 60}"
            n = r.incr(mk)
            if n == 1:
                r.expire(mk, 90)
            if n > 30:
                return JSONResponse(status_code=429, content={"ok": False, "error": "rate_limited"})
    except Exception:
        pass
    from track import ip_hash, track
    ok = track({"kind": t.kind[:40], "query": t.query, "marketplace": t.marketplace,
                "result_count": t.result_count, "ipd": ip_hash(_client_ip(request)),
                "country": t.country, "lang": t.lang, "tz": t.tz, "device": t.device,
                "w": t.w, "asin": t.asin, "store": t.store, "pos": t.pos,
                "title": t.title, "price_cents": t.price_cents, "ms": t.ms, "ref": t.ref})
    return {"ok": ok}


def _admin_ok(request: Request) -> bool:
    import hmac
    key = os.getenv("ADMIN_KEY", "")
    # header only: a ?key= URL param would land in Traefik/uvicorn access logs
    supplied = request.headers.get("x-admin-key", "")
    return bool(key) and hmac.compare_digest(supplied, key)


@app.get("/stats")
def stats(request: Request, days: int = Query(30), hours: int = Query(48, ge=12, le=168)):
    """Admin-only aggregates for the /admin page."""
    if not _admin_ok(request):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    days = max(1, min(days, 3650))  # 3650 ≈ all-time
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return {"error": "no database configured"}
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            def rows(sql, args=()):
                cur.execute(sql, args)
                return cur.fetchall()
            out: dict = {"days": days}
            out["totals"] = rows("""SELECT kind, COUNT(*) FROM events
                WHERE ts > now() - make_interval(days => %s) GROUP BY kind ORDER BY 2 DESC""", (days,))
            out["daily"] = rows("""SELECT date_trunc('day', ts)::date::text,
                COUNT(*) FILTER (WHERE kind='search'), COUNT(*) FILTER (WHERE kind='click'),
                COUNT(DISTINCT ipd) FROM events
                WHERE ts > now() - make_interval(days => %s)
                GROUP BY 1 ORDER BY 1 DESC LIMIT 60""", (days,))
            out["topQueries"] = rows("""SELECT query, COUNT(*) FROM events
                WHERE kind='search' AND ts > now() - make_interval(days => %s) AND query <> ''
                GROUP BY query ORDER BY 2 DESC LIMIT 30""", (days,))
            out["zeroResults"] = rows("""SELECT query, COUNT(*) FROM events
                WHERE kind='search' AND ts > now() - make_interval(days => %s)
                  AND COALESCE(result_count, 0) = 0 AND query <> ''
                GROUP BY query ORDER BY 2 DESC LIMIT 20""", (days,))
            out["topClicks"] = rows("""SELECT COALESCE(NULLIF(title, ''), asin), asin, store,
                COUNT(*) FROM events WHERE kind='click'
                AND ts > now() - make_interval(days => %s)
                GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT 30""", (days,))
            out["ctrByQuery"] = rows("""SELECT query,
                COUNT(*) FILTER (WHERE kind='search') AS searches,
                COUNT(*) FILTER (WHERE kind='click') AS clicks
                FROM events WHERE kind IN ('search','click')
                AND ts > now() - make_interval(days => %s) AND query <> ''
                GROUP BY query HAVING COUNT(*) FILTER (WHERE kind='search') > 0
                ORDER BY 2 DESC LIMIT 25""", (days,))
            out["visitors"] = rows("""SELECT date_trunc('day', ts)::date::text,
                COUNT(DISTINCT ipd) FROM events
                WHERE ts > now() - make_interval(days => %s) GROUP BY 1 ORDER BY 1 DESC LIMIT 60""", (days,))
            for name, col in [("markets", "marketplace"), ("langs", "lang"), ("tzs", "tz"),
                              ("devices", "device"), ("widths", "w"), ("refs", "ref")]:
                out[name] = rows(f"""SELECT COALESCE(NULLIF({col}::text, ''), '?'), COUNT(*),
                    COUNT(DISTINCT ipd) FROM events
                    WHERE ts > now() - make_interval(days => %s)
                    GROUP BY 1 ORDER BY 2 DESC LIMIT 20""", (days,))
            out["avgMs"] = rows("""SELECT kind, ROUND(AVG(ms)),
                COALESCE(ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ms)), 0)
                FROM events WHERE ms > 0 AND ts > now() - make_interval(days => %s)
                GROUP BY kind""", (days,))
            # hourly activity, zero-filled so the chart never shows gaps
            out["hourly"] = rows(f"""SELECT gs.h::text,
                COUNT(e.kind) FILTER (WHERE e.kind = 'search'),
                COUNT(e.kind) FILTER (WHERE e.kind = 'click')
                FROM generate_series(date_trunc('hour', now()) - interval '{int(hours) - 1} hours',
                                     date_trunc('hour', now()), interval '1 hour') AS gs(h)
                LEFT JOIN events e ON date_trunc('hour', e.ts) = gs.h
                GROUP BY 1 ORDER BY 1""")
            out["clickStores"] = rows("""SELECT COALESCE(NULLIF(store, ''), '?'), COUNT(*)
                FROM events WHERE kind='click' AND ts > now() - make_interval(days => %s)
                GROUP BY 1 ORDER BY 2 DESC LIMIT 8""", (days,))
            out["avgResults"] = rows("""SELECT ROUND(AVG(result_count)::numeric, 1)
                FROM events WHERE kind='search' AND ts > now() - make_interval(days => %s)""", (days,))
            try:
                out["adInquiries"] = rows("""SELECT id, name, email, slot,
                    left(message, 500) AS message, created_at::text
                    FROM ad_inquiries ORDER BY created_at DESC LIMIT 50""")
            except Exception:
                out["adInquiries"] = []
            # non-secret runtime facts for the admin system panel
            try:
                from providers import DEFAULT_CHAIN as _dc
                default_chain = ",".join(_dc)
            except Exception:
                default_chain = ""
            out["system"] = {
                "smtp": bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS")),
                "smtpTo": os.getenv("SMTP_TO", "office@websters.at") if os.getenv("SMTP_USER") else None,
                "pages": max(1, min(3, int(os.getenv("SEARCH_PAGES", "2")))),
                "providerDefault": os.getenv("DATA_PROVIDER", "auto-chain"),
                "providerChain": os.getenv("DATA_PROVIDERS", "") or default_chain,
            }
            return out
    except Exception as e:
        # log details server-side only; raw DB errors must not reach clients
        print(f"[stats] {e}", flush=True)
        return {"error": "internal"}
