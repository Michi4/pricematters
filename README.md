# PriceMatters — bangyourbuck.com, but better (EU/DACH-first)

One Docker stack, N brand domains (`pricematters.app`, `dothemath.app`,
`moneysworth.app`, …) via multi-tenancy in `frontend/app.config.ts`.
Search Amazon products, extract the real quantity from messy titles,
sort by **unit price** — no ads, no fake discounts.

## Stack (why)

| Piece | Choice | Why |
|---|---|---|
| Frontend | Nuxt 3 (Vue, SSR) | you know Vue, SSR = SEO for a shopping engine, Nitro proxies Amazon keys safely |
| Backend | FastAPI (Python) | best regex/NLP ecosystem for the Unit Extraction Engine, easy provider swapping |
| DB | Postgres 16 | product/search cache, price history later (Keepa-style charts) |
| Cache | Redis 7 | 24h cache for provider responses — mandatory under Amazon ToS + saves money |
| Deploy | Docker Compose + Traefik | same labels pattern as your nightcrown/cuckoo: external `${TRAEFIK_NETWORK}`, Let's Encrypt |

You do **not** need the Python backend on day 1 — Nuxt server routes + `lib/units.ts`
already work. Keep FastAPI as the extraction + provider microservice.

## Deploy on Oracle (130.61.104.107, Traefik `proxy` network)

```bash
# on the server, under /home/ubuntu/websters/customers/:
git clone <your-repo> pricematters && cd pricematters
cp .env.example .env
# set in .env: DOMAIN=<sub>.websters.at  ROUTER_NAME=pricematters
#              TRAEFIK_NETWORK=proxy  POSTGRES_PASSWORD=<long random>
docker compose up -d --build
```

Amazon re-approval needs the live URL: register the subdomain in PartnerNet
*before* reapplying, then put the real tag in `AMAZON_PARTNER_TAG`.
CI: `.github/workflows/deploy.yml` does `git pull + compose up` on every push
to main. Needs repo secrets: `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY`,
`DEPLOY_PATH=/home/ubuntu/websters/customers/pricematters`.

## Quickstart

```bash
cp .env.example .env   # set POSTGRES_PASSWORD, DOMAIN, TRAEFIK_NETWORK
docker compose up -d --build
# frontend -> https://<DOMAIN> (via Traefik), backend :8000, postgres :5432, redis :6379
```

Local dev without Docker:

```bash
cd frontend && npm install && npm run dev
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
```

## Amazon API in 2026 — the honest state

- **PA-API 5.0 is deprecated (15.05.2026)**, successor is the **Creators API**
  (`affiliate-program.amazon.com/creatorsapi`). Same idea, REST-based.
- **Eligibility got stricter:** old rule "3 sales in 180 days" is gone in practice.
  Current enforcement: **~10 qualifying (shipped) sales in the trailing 30 days**,
  otherwise `AssociateNotEligible` / throttled to zero. New keys can take 24–48h.
- **Rate limit:** starts at ~1 req/s, scales with revenue. Cache aggressively
  (allowed for product data per ToS, max ~24h) in Redis + Postgres.
- **Fastest path to unlock:**
  1. Finish PartnerNet registration as **"Comparison Shopping Engine
     (Preissuchmaschine)"** with the Grundpreis/Mehrwert-text (no words like
     "exposing Amazon", "scraping" — instant reject).
  2. Take your `PartnerTag` (e.g. `websters02-21`) and hard-code it into every
     outbound link **today** (already done in `server/api/search.get.ts`).
  3. Ship the MVP with mock data + affiliate links, share with family/HTL circle,
     drive the first 10 sales of daily goods (coffee, rice, whey) — that's what
     converts. Only then apply for Creators API keys.
  4. One account per marketplace: you need `amazon.de` (DACH) separately from `.com`.

## Start coding TODAY (no approval needed)

`DATA_PROVIDER=mock` works out of the box. When ready for real data:

| Provider | Cost (mid-2026) | Good for | Bad for |
|---|---|---|---|
| Rainforest API | from ~$18/mo (500 req) | real Amazon JSON, search+product+offers, no proxy pain | $$$, Amazon-only, no history |
| ScrapingBee Amazon endpoint | 1000 credits free, then $49/mo+ | cheap start, `domain=de`, geo via `country=de` | credit math, needs parser care |
| Keepa | ~€19/mo | price **history** + BSR, the killer feature for "fake discount" detection | not a live search API (token bucket) |
| Self-scrape | proxy bills + maintenance | free-ish | against ToS, CAPTCHAs, you don't want this |

Recommendation: **mock → ScrapingBee (dev) → Rainforest (prod live) + Keepa (history
graph)**. Wire them behind `GET /search` in `backend/main.py` so the frontend
never changes.

## Unit Extraction Engine

Single source of truth: `backend/extractor.py` (Python), mirrored in
`frontend/lib/units.ts` for instant UI calc.

1. **Structured first:** Amazon.de often returns a Grundpreis string
   (`7,49 € / kg`) — trust it over parsing when present.
2. **Regex cascade:** multipack (`2 x 1kg`) → quantity (`2.27kg`, `500g`,
   `12 Stück`, `5 lbs`, `71 Servings`) → servings/count fallback.
3. **Normalise:** `mg→g`, `cl→ml`, `oz→g (×28.35)`, `lb→g (×453.59)`,
   display base `kg / l / pcs / GB`.
4. **LLM offline only:** use Gemini/DeepSeek to label 500 real titles into a
   test fixture, never in the request path (latency + cost).

Test it: `GET /extract?title=Optimum%20Whey%202.27kg%20(5%20lbs)%2071%20Servings`.

## Monetisation (fits your "free, no annoying ads" goal)

1. **Affiliate first:** every link carries `tag=`. This is 90% of revenue for such tools.
2. **Voluntary contribution:** "pay what you want (incl. 0 €)" account that only
   removes the donate banner — exactly as you sketched. One-time → keep a subtle
   banner; monthly → banner gone everywhere except account settings.
3. **Referral/partner program:** give creators a `?ref=` that splits *your*
   affiliate cut (track in `searches`/`products` tables). Cheap to build, viral.
4. Later, **not now:** Keepa-style price-drop alerts (push) as the premium hook.
   Skip display ads entirely — they kill trust in a price-trust product.

## Brands

You already own the strong ones. Recommendation: launch on **`pricematters.app`**
(EN, serious, investor-safe), keep `dothemath.app` as the cheeky campaign domain
and `preiswertist.*` for DE SEO. All point at the same container; copy lives in
`app.config.ts`. Slogans drafted there — EN/DE per domain.
