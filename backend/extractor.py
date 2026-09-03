"""Unit Extraction Engine (single source of truth — frontend/lib/units.ts mirrors this).

Priority:
  1. structured API fields first (Amazon.de often ships a Grundpreis string)
  2. regex cascade DE+EN (multipack -> quantity -> servings/count)
  3. normalise to base units (g->kg, ml->l); imperial -> metric
LLM is deliberately NOT in the hot path: too slow/expensive. Use it offline
to label titles and generate regression tests for this file.
"""
import re
from dataclasses import dataclass
from typing import Optional

MULTIPACK = re.compile(
    r"(\d+)\s*(?:x|×|\*)\s*(\d+(?:[.,]\d+)?)\s*"
    r"(kg|g|mg|ml|l|liter|litre|cl|oz|lb|lbs|fl\s?oz|stk|stück|stueck|pcs|pack|tb|gb|mb)\b",
    re.I,
)
QTY = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(kg|kilogramm(?:e)?|kilograms?|g|gramm|grams?|mg|milligramm|l|liter|litre|liters?|"
    r"ml|milliliter|cl|oz|ounces?|unzen?|lb|lbs|pounds?|pfund|fl\s?oz|stk\.?|stück|stueck|"
    r"pcs|pack(?:ung)?|tb|gb|mb)\b",
    re.I,
)
SERVINGS = re.compile(r"(\d+)\s*(?:servings?|portionen|kapseln|capsules?|tabletten|tabs?)\b", re.I)
# Amazon.de Grundpreis e.g. "7,49 € / kg", "(14,98 €/kg)"
GRUNDPREIS = re.compile(r"(\d+(?:[.,]\d+)?)\s*€\s*/\s*(kg|g|100\s?g|l|ml|100\s?ml|stk|stück|stueck)\b", re.I)


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
    if u.startswith("100g"):
        return ("100g", "mass")
    if u.startswith("100ml"):
        return ("100ml", "volume")
    return None


def extract_quantity(title: str, description: str = "") -> Optional[Qty]:
    text = f"{title} {description}"
    m = MULTIPACK.search(text)
    if m:
        count, per, raw = int(m.group(1)), _num(m.group(2)), m.group(3)
        n = _norm(raw)
        if n:
            unit, kind = n
            return _scale(count * per, unit, kind)
    m = QTY.search(text)
    if m:
        val, raw = _num(m.group(1)), m.group(2)
        n = _norm(raw)
        if n:
            unit, kind = n
            return _scale(val, unit, kind)
    m = SERVINGS.search(text)
    if m:
        return Qty(value=float(m.group(1)), unit="pcs", kind="count")
    return None


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


def unit_price(price_cents: int, q: Qty):
    """-> (cents per base unit, base unit). Base: kg, l, pcs, tb/gb."""
    conv = {"kg": ("kg", 1), "g": ("kg", 1000), "l": ("l", 1), "ml": ("l", 1000),
            "pcs": ("pcs", 1), "tb": ("tb", 1), "gb": ("gb", 1), "mb": ("gb", 1000)}
    c = conv.get(q.unit)
    if not c or not q.value:
        return None
    base, mult = c
    return (price_cents / q.value) * mult, base
