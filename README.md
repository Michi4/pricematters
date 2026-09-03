# PriceMatters — the honest price comparison

Real unit prices (€/kg, €/L, €/pc) for Amazon products. No ads in results,
no fake discounts. DE/EN, DACH-first.

**Live:** https://pricematters.websters.at (+ deals, dothemath, moneysworth,
valueformoney, preiswertist subdomains — one container, multi-brand).

## Run it

```bash
cp .env.example .env   # fill secrets, see below
docker compose up -d --build
```

Local dev: `cd frontend && npm install && npm run dev`,
`cd backend && pip install -r requirements.txt && uvicorn main:app --reload`.

## Data (no approval needed to start)

`DATA_PROVIDER` (backend): `mock` (default, demo) · `scrapingbee` ·
`rainforest` · `serpapi` · `selfscrape` (experimental, needs
`SELFSCRAPE_CONSENT=1`) · `creators` (needs approved PartnerNet account).
Provider errors fall back to demo data instead of failing.
Shop feeds (Awin & co): `FEED_URLS="https://..."` + `python feeds.py import`
(nightly). AI quantity fallback: `GEMINI_API_KEY` (free tier).

## Endpoints

- `GET /search?q=Reis&marketplace=de` — merged, unit-price sorted
- `GET /extract?title=...` — quantity parsing
- `GET /popular`, `GET /cache/stats`, `POST /contact`

## Deploy

Push to `main` → GitHub Action (`git pull` + `compose up`) on the server.
Secrets: `SERVER_HOST`, `SERVER_USER`, `SSH_PRIVATE_KEY`, `DEPLOY_PATH`.
Traefik: external `${TRAEFIK_NETWORK}`, Let's Encrypt via `ROUTER_RULE`.
