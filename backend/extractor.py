"""Unit Extraction Engine (single source of truth — frontend/lib/units.ts mirrors this).

Priority:
  1. multipack ("2 x 500 g") — authoritative
  2. best scored single quantity (candidate scoring, see below)
  3. servings/count ("50 Portionen") as last resort
  4. normalise to base units (g->kg, ml->l); imperial -> metric

Scoring (the "simple ML" part, deterministic and explainable):
  - unit plausibility range check (a 0.95 g olive oil pack does not exist)
  - unit weight: kg/l/gb > g/ml > pcs (pack sizes are physical, claims are not)
  - position: the real pack size sits at the END of the title; claims
    ("950 mg/kg Polyphenole", "1 Esslöffel/Tag") sit in the middle
  - anything followed by "/unit" (mg/kg, €/kg, Esslöffel/Tag) is a per-claim,
    never a package size
  - numbers directly attached to a unit with no space ("500ml") beat loose ones
LLM is deliberately NOT in the hot path: too slow/expensive. Use it offline
to label titles and generate regression tests for this file.
"""
import re
from dataclasses import dataclass
from typing import Optional

MULTIPACK = re.compile(
    r"(\d+)\s*(?:x|×|\*)\s*(\d+(?:[.,]\d+)?)\s*"
    r"(kg|g|mg|ml|l|liter|litre|cl|oz|lb|lbs|fl\s?oz|stk|stück|stueck|pcs|pack|tb|gb|mb|kb)\b",
    re.I,
)
QTY = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(kg|kilogramm(?:e)?|kilograms?|g|gramm|grams?|mg|milligramm|l|liter|litre|liters?|"
    r"ml|milliliter|cl|oz|ounces?|unzen?|lb|lbs|pounds?|pfund|fl\s?oz|stk\.?|stück|stueck|"
    r"pcs|pack(?:ung)?|tb|gb|mb|kb)\b",
    re.I,
)
SERVINGS = re.compile(r"(\d+)\s*(?:servings?|portionen|kapseln|capsules?|tabletten|tabs?)\b", re.I)
# Amazon.de Grundpreis e.g. "7,49 € / kg", "(14,98 €/kg)"
GRUNDPREIS = re.compile(r"(\d+(?:[.,]\d+)?)\s*€\s*/\s*(kg|g|100\s?g|l|ml|100\s?ml|stk|stück|stueck)\b", re.I)
# "950 mg/kg", "1 Esslöffel/Tag": a quantity directly followed by "/unit" is a
# per-claim, never the package size
PER_CLAIM = re.compile(
    r"^\s*/\s*(?:kg|g|100\s?g|l|100\s?ml|ml|stk|stück|stueck|pcs|tag|tage|day|days|portion|portionen)\b",
    re.I,
)


@dataclass
class Qty:
    value: float
    unit: str  # g|kg|ml|l|pcs|tb|gb|mb
    kind: str  # mass|volume|count|storage


def _num(s: str) -> float:
    t = s.strip()
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)


def _norm(raw: str) -> Optional[Qty | tuple]:
    u = raw.lower().replace(" ", "")
    if u.startswith("kg") or u.startswith("kilo"):
        return ("kg", "mass")
    if u == "t" or u.startswith("ton"):
        return ("kg", "mass", 1000.0)
    if u == "g" or u.startswith("gram"):
        return ("g", "mass")
    if u == "mg" or "milligram" in raw.lower():
        return ("mg->g", "mass")
    if u == "ml" or u.startswith("millili"):
        return ("ml", "volume")
    if u == "l" or u.startswith("liter") or u.startswith("litre"):
        return ("l", "volume")
    if u == "cl":
        return ("cl->ml", "volume")
    if u.startswith("fl"):
        return ("floz->ml", "volume")
    if u.startswith("oz") or u.startswith("unz") or u.startswith("ounc"):
        return ("oz->g", "mass")
    if u.startswith("lb") or u.startswith("pound") or u.startswith("pfund"):
        return ("lb->g", "mass")
    if u.startswith("st") or u.startswith("pc") or u.startswith("pack") or u.startswith("serv") \
       or u.startswith("port") or u.startswith("kaps") or u.startswith("caps") or u.startswith("tab"):
        return ("pcs", "count")
    if u == "tb":
        return ("tb", "storage")
    if u == "gb":
        return ("gb", "storage")
    if u == "mb":
        return ("mb", "storage")
    if u == "kb":
        return ("kb", "storage")
    if u.startswith("100g"):
        return ("100g", "mass")
    if u.startswith("100ml"):
        return ("100ml", "volume")
    return None


# plausible pack-size range per display unit (values AFTER conversion)
PLAUSIBLE = {
    "kg": (0.05, 50.0),   # 50 g  … 50 kg (bulk ok)
    "g":  (50.0, 50000.0),
    "l":  (0.05, 50.0),   # 50 ml … 50 l (canister ok)
    "ml": (50.0, 50000.0),
    "pcs": (1, 500),
    "tb": (0.5, 512.0),
    "gb": (1, 4096.0),
    "mb": (64, 262144.0),
}


def _scale(val: float, unit: str, kind: str) -> Qty:
    if unit == "mg->g":
        return Qty(val / 1000, "g", kind)
    if unit == "cl->ml":
        return Qty(val * 10, "ml", kind)
    if unit == "floz->ml":
        return Qty(val * 29.5735, "ml", kind)
    if unit == "oz->g":
        return Qty(val * 28.3495, "g", kind)
    if unit == "lb->g":
        return Qty(val * 453.592, "g", kind)
    if unit == "100g":
        return Qty(val * 100, "g", kind)
    if unit == "100ml":
        return Qty(val * 100, "ml", kind)
    return Qty(val, unit, kind)


def _plausible(q: Qty) -> bool:
    r = PLAUSIBLE.get(q.unit)
    if not r:
        return True
    return r[0] <= q.value <= r[1]


def _score(m, text: str) -> float:
    """Higher = more likely the real package size. Deterministic 'ML-lite'."""
    val = _num(m.group(1))
    raw = m.group(2)
    n = _norm(raw)
    if not n:
        return -1.0
    unit, kind = n[0], n[1]
    mult = n[2] if len(n) > 2 else None
    if unit == "kg" and mult:
        q = Qty(val * mult, "kg", kind)
    else:
        q = _scale(val, unit, kind)
    if not _plausible(q):
        return -1.0
    s = 0.0
    # claims lose before they start ("950 mg/kg", "€ 7,49/kg")
    tail = text[m.end():m.end() + 4]
    if PER_CLAIM.match(tail):
        return -1.0
    # unit weight: big physical units beat small ones
    s += {"kg": 3.0, "l": 3.0, "gb": 3.0, "tb": 3.0,
          "g": 2.0, "ml": 2.0, "mb": 2.0, "pcs": 1.0}.get(q.unit, 0.5)
    # pack size sits at the END of the title (weight by relative position)
    rel = m.start() / max(len(text), 1)
    s += 2.0 * rel
    # avoid pure single-digit counts early in the title ("12 Stück …" less likely than "… 12 Stück")
    if q.unit == "pcs" and rel < 0.3:
        s -= 1.0
    return s


def extract_quantity(title: str, description: str = "") -> Optional[Qty]:
    text = f"{title} {description}"
    m = MULTIPACK.search(text)
    if m:
        count, per, raw = int(m.group(1)), _num(m.group(2)), m.group(3)
        n = _norm(raw)
        if n:
            unit, kind = n[0], n[1]
            mult = n[2] if len(n) > 2 else None
            if unit == "kg" and mult:
                q = Qty(int(count) * per * mult, "kg", kind)
            else:
                q = _scale(count * per, unit, kind)
            if _plausible(q):
                return q
    # score every single-quantity candidate, pick the best
    best, best_s = None, 0.0
    for m in QTY.finditer(text):
        s = _score(m, text)
        if s > best_s:
            best, best_s = m, s
    if best:
        val, raw = _num(best.group(1)), best.group(2)
        n = _norm(raw)
        if n:
            unit, kind = n[0], n[1]
            mult = n[2] if len(n) > 2 else None
            if unit == "kg" and mult:
                return Qty(val * mult, "kg", kind)
            return _scale(val, unit, kind)
    m = SERVINGS.search(text)
    if m:
        return Qty(value=float(m.group(1)), unit="pcs", kind="count")
    return None


def unit_price(price_cents: int, q: Qty):
    """-> (cents per base unit, base unit). Base: kg, l, pcs, gb."""
    conv = {"kg": ("kg", 1), "g": ("kg", 1000), "l": ("l", 1), "ml": ("l", 1000),
            "pcs": ("pcs", 1),
            # 1 tb = 1000 gb -> per-gb = per-tb / 1000; 1000 mb = 1 gb -> per-gb = per-mb * 1000
            "tb": ("gb", 0.001), "gb": ("gb", 1), "mb": ("gb", 1000)}
    c = conv.get(q.unit)
    if not c or not q.value:
        return None
    base, mult = c
    return (price_cents / q.value) * mult, base
