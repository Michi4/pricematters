"""AI fallback for quantity extraction — regex first, LLM only on miss.

Called ONLY when extractor.extract_quantity() returns None, result cached
in-memory (each unique title is analyzed once per process lifetime).
Uses Google Gemini free tier (ai.google.dev -> GEMINI_API_KEY, no card).
No key set -> disabled silently, nothing breaks, no latency added.
"""
import json
import os
import urllib.request

UNITS = {"g", "kg", "ml", "l", "pcs", "tb", "gb", "mb"}
_cache: dict[str, object] = {}


def ai_quantity(title: str, description: str = ""):
    """-> extractor.Qty or None. Never raises, never slow-fails the search."""
    from extractor import Qty

    key = title.strip().lower()
    if key in _cache:
        return _cache[key]
    out = None
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        try:
            prompt = (
                "Extract the total sellable quantity from this product title. "
                "Multiply multipacks (e.g. '12 x 500g' -> 6000 g). "
                "Normalize imperial to metric (1 oz = 28.35 g, 1 lb = 453.59 g, 1 fl oz = 29.57 ml). "
                "Servings/capsules/tablets/pieces count as pcs. "
                'Reply ONLY with JSON: {"value": number, "unit": "g|kg|ml|l|pcs|tb|gb|mb"} '
                'or {"value": null} if no quantity is determinable.\n'
                f"Title: {title}\nDescription: {description[:300]}"
            )
            body = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json", "temperature": 0},
            }).encode()
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                data=body, headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(text)
            if parsed.get("value") and parsed.get("unit") in UNITS:
                kind = {"g": "mass", "kg": "mass", "ml": "volume", "l": "volume",
                        "pcs": "count", "tb": "storage", "gb": "storage", "mb": "storage"}[parsed["unit"]]
                out = Qty(value=float(parsed["value"]), unit=parsed["unit"], kind=kind)
        except Exception:
            out = None
    if len(_cache) < 5000:
        _cache[key] = out
    return out
