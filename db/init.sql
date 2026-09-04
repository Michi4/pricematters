CREATE TABLE IF NOT EXISTS products (
  id SERIAL PRIMARY KEY,
  asin TEXT UNIQUE NOT NULL,
  marketplace TEXT NOT NULL DEFAULT 'www.amazon.de',
  title TEXT NOT NULL,
  brand TEXT,
  price_cents INTEGER,
  currency TEXT DEFAULT 'EUR',
  quantity_value DOUBLE PRECISION,
  quantity_unit TEXT,
  unit_price_cents DOUBLE PRECISION,
  base_unit TEXT,
  image_url TEXT,
  detail_url TEXT,
  rating DOUBLE PRECISION,
  review_count INTEGER,
  raw JSONB,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Canonical schema for FRESH installs (first volume boot only).
-- Runtime CREATE TABLE/INDEX IF NOT EXISTS in main.py/track.py keeps EXISTING
-- DBs aligned; keep both copies in sync when changing columns. Single source
-- of truth for what the tables look like = this file.

CREATE TABLE IF NOT EXISTS searches (
  id BIGSERIAL PRIMARY KEY,
  query TEXT NOT NULL,
  marketplace TEXT NOT NULL DEFAULT 'de',
  result_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_searches_query ON searches(query);
-- filtered branch (/popular?marketplace=de)
CREATE INDEX IF NOT EXISTS searches_market_ts ON searches (marketplace, created_at DESC);
-- merged branch (/popular?marketplace=all, the default): time-range + group-by-count
CREATE INDEX IF NOT EXISTS searches_created_ts ON searches (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_products_unit_price ON products(unit_price_cents);

-- Shop feeds (Awin & co, imported nightly by backend/feeds.py, searched locally)
CREATE TABLE IF NOT EXISTS shop_products (
  id TEXT PRIMARY KEY,
  shop TEXT NOT NULL,
  title TEXT NOT NULL,
  brand TEXT,
  price_cents INTEGER NOT NULL,
  currency TEXT DEFAULT 'EUR',
  url TEXT NOT NULL,
  image_url TEXT,
  gtin TEXT,
  search TSVECTOR GENERATED ALWAYS AS (to_tsvector('german', coalesce(title,'') || ' ' || coalesce(brand,''))) STORED,
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_shop_search ON shop_products USING GIN (search);

-- Ad-slot inquiries (contact form)
CREATE TABLE IF NOT EXISTS ad_inquiries (
  id SERIAL PRIMARY KEY,
  name TEXT,
  email TEXT,
  slot TEXT,
  message TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Anonymous first-party analytics (/track). Raw IPs are NEVER stored, only a
-- daily-rotated salted hash (see backend/track.py). Also created lazily by
-- track.py on existing DBs; this copy documents the shape for fresh installs.
CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  kind TEXT NOT NULL,
  query TEXT, marketplace TEXT, result_count INT,
  ipd TEXT, country TEXT, lang TEXT, tz TEXT, device TEXT, w INT,
  asin TEXT, store TEXT, pos INT, title TEXT, price_cents INT,
  ms INT, ref TEXT
);
CREATE INDEX IF NOT EXISTS events_kind_ts ON events (kind, ts);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);
CREATE INDEX IF NOT EXISTS events_kind_ts_query ON events (kind, ts, query);
