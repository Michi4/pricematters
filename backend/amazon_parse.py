"""Shared Amazon search-HTML parser (used by selfscrape + zenrows).

Amazon's search markup is stable enough for: data-asin="B0..." blocks,
<h2> title spans, and €/$/£ price strings nearby. Defensive by design:
returns [] instead of raising, callers decide fallback.
"""
import re

ASIN_RE = re.compile(r'B0[A-Z0-9]{8}')
PRICE_RE = re.compile(r"(?:€|\$|£)\s*(\d{1,4}(?:[.,]\d{3})*[.,]\d{2})")


def _cents(s: str) -> int | None:
    s = s.strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return int(round(float(re.sub(r"[^\d.]", "", s)) * 100))
    except ValueError:
        return None


def parse_search(html: str, domain: str, limit: int = 20):
    """-> [(asin, title, price_cents, url, 'Amazon', None), ...]"""
    out, seen = [], set()
    for b in re.split(r'data-asin="', html)[1:]:
        m = re.match(r"(B0[A-Z0-9]{8})", b)
        if not m or m.group(1) in seen:
            continue
        asin = m.group(1)
        t = re.search(r"<h2[^>]*>.*?<span>(.*?)</span>", b, re.S)
        title = re.sub(r"<[^>]+>", "", t.group(1)).strip() if t else ""
        p = PRICE_RE.search(b[:8000])
        cents = _cents(p.group(1)) if p else None
        if not title or cents is None:
            continue
        seen.add(asin)
        out.append((asin, title, cents, f"https://{domain}/dp/{asin}", "Amazon", None))
        if len(out) >= limit:
            break
    return out
