"""FastAPI backend: /search + /extract.

DATA_PROVIDER=mock      -> works today, no keys, deterministic (UI dev)
DATA_PROVIDER=rainforest -> needs RAINFOREST_API_KEY (start here for real data)
DATA_PROVIDER=scrapingbee -> needs SCRAPINGBEE_API_KEY
DATA_PROVIDER=creators   -> Amazon Creators API (PA-API 5 successor, needs approval + sales)
"""
import os
from fastapi import FastAPI, Query
from pydantic import BaseModel
from extractor import extract_quantity, unit_price

app = FastAPI(title="PriceMatters API")
PROVIDER = os.getenv("DATA_PROVIDER", "mock")
TAG = os.getenv("AMAZON_PARTNER_TAG", "websters0a-21")


class Item(BaseModel):
    asin: str
    title: str
    priceCents: int
    url: str
    qty: dict | None = None
    unitPrice: dict | None = None


def enrich(asin: str, title: str, price_cents: int, url: str) -> dict:
    q = extract_quantity(title)
    up = unit_price(price_cents, q) if q else None
    return {
        "asin": asin,
        "title": title,
        "priceCents": price_cents,
        "url": url,
        "qty": {"value": q.value, "unit": q.unit, "kind": q.kind} if q else None,
        "unitPrice": {"per": up[0], "base": up[1]} if up else None,
    }


@app.get("/health")
def health():
    return {"ok": True, "provider": PROVIDER}


@app.get("/extract")
def extract(title: str = Query(...), description: str = ""):
    q = extract_quantity(title, description)
    return {"qty": q.__dict__ if q else None}


@app.get("/search")
def search(q: str = Query(...)):
    if PROVIDER == "mock" or True:  # keep mock until a real provider is wired
        mocks = [
            ("MOCK1", f"Bio Basmati Reis, 2 x 1kg ({q})", 1299, "https://www.amazon.de/dp/MOCK1"),
            ("MOCK2", f"Optimum Whey Double Rich Chocolate 2.27kg (5 lbs), 71 Servings ({q})", 6499, "https://www.amazon.de/dp/MOCK2"),
            ("MOCK3", f"Bio Kaffee Bohnen 500g ({q})", 899, "https://www.amazon.de/dp/MOCK3"),
        ]
        items = [enrich(*m) for m in mocks]
        items.sort(key=lambda i: (i["unitPrice"] is None, (i["unitPrice"] or {}).get("per", 1e18)))
        return {"items": items, "provider": PROVIDER}
