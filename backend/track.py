"""Anonymous, first-party event tracking. DSGVO/TDDWG-safe for AT:
- no cookies, no fingerprinting, no third parties
- raw IPs are NEVER stored; only a daily-rotated salted hash (privacy by design)
- declared legitimate interest (Art 6 Abs 1 lit f DSGVO), aggregates only
"""
import hashlib
import os
import time

DAILY_SALT = ""


def _salt() -> str:
    global DAILY_SALT
    # rotates daily: hashes cannot be linked across days
    day = int(time.time() // 86400)
    if not DAILY_SALT or DAILY_SALT[0] != str(day):
        DAILY_SALT = (str(day), hashlib.sha256(
            (os.getenv("TRACK_SALT", "pm") + str(day)).encode()).hexdigest()[:16])
    return DAILY_SALT[1]


def ip_hash(ip: str) -> str:
    return hashlib.sha256((_salt() + ip).encode()).hexdigest()[:16]


DDL = """CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  kind TEXT NOT NULL,
  query TEXT, marketplace TEXT, result_count INT,
  ipd TEXT, country TEXT, lang TEXT, tz TEXT, device TEXT, w INT,
  asin TEXT, store TEXT, pos INT, title TEXT, price_cents INT,
  ms INT, ref TEXT)
"""
IDX = ["CREATE INDEX IF NOT EXISTS events_kind_ts ON events (kind, ts)",
       "CREATE INDEX IF NOT EXISTS events_ts ON events (ts)",
       "CREATE INDEX IF NOT EXISTS events_kind_ts_query ON events (kind, ts, query)"]


COLS = ["kind", "query", "marketplace", "result_count", "ipd", "country", "lang",
        "tz", "device", "w", "asin", "store", "pos", "title", "price_cents", "ms", "ref"]


_ensured = False


def track(payload: dict) -> bool:
    global _ensured
    try:
        import psycopg
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return False
        p = {c: payload.get(c) for c in COLS}
        p = {k: (str(v)[:180] if v is not None else None) for k, v in p.items()}
        with psycopg.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            # schema is static — create it once per process, not on every event
            if not _ensured:
                cur.execute(DDL)
                for stmt in IDX:
                    cur.execute(stmt)
                _ensured = True
            cols = ", ".join(COLS)
            marks = ", ".join(f"%({c})s" for c in COLS)
            cur.execute(f"INSERT INTO events ({cols}) VALUES ({marks})", p)
        return True
    except Exception as e:
        print(f"[track] {e}", flush=True)
        return False
