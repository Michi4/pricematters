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

CREATE TABLE IF NOT EXISTS searches (
  id SERIAL PRIMARY KEY,
  query TEXT NOT NULL,
  marketplace TEXT NOT NULL DEFAULT 'www.amazon.de',
  result_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_searches_query ON searches(query);
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
