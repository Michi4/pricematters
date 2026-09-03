// Unit Extraction Engine — client-safe mirror of backend/extractor.py
// Strategy: structured fields first, then regex cascade (DE+EN), then unit normalisation.
// NO LLM in the hot path (cost/latency). LLM only offline to generate test cases.

export type UnitKind = 'mass' | 'volume' | 'count' | 'storage' | 'unknown';

export interface ExtractedQty {
  value: number;
  unit: string; // normalised: g, kg, ml, l, pcs, tb, gb, mb
  kind: UnitKind;
}

const MULTIPACK = /(\d+)\s*(?:x|×|\*)\s*(\d+(?:[.,]\d+)?)\s*(kg|g|mg|ml|l|liter|litre|cl|oz|lb|lbs|fl\s?oz|stk|stück|stueck|pcs|pack|tb|gb|mb)\b/i;
const QTY = /(\d+(?:[.,]\d+)?)\s*(kg|kilogramm(?:e)?|kilograms?|g|gramm|grams?|mg|milligramm|l|liter|litre|liters?|ml|milliliter|cl|oz|ounces?|unzen?|lb|lbs|pounds?|pfund|fl\s?oz|stk\.?|stück|stueck|pcs|pack(?:ung)?|tb|gb|mb)\b/i;
const SERVINGS = /(\d+)\s*(?:servings?|portionen|kapseln|capsules?|tabletten|tabs?)\b/i;

const UNIT_MAP: Record<string, { unit: string; kind: UnitKind; factor: number }> = {
  kg: { unit: 'kg', kind: 'mass', factor: 1000 },
  g: { unit: 'g', kind: 'mass', factor: 1 },
  mg: { unit: 'g', kind: 'mass', factor: 0.001 },
  ml: { unit: 'ml', kind: 'volume', factor: 1 },
  l: { unit: 'l', kind: 'volume', factor: 1000 },
  pcs: { unit: 'pcs', kind: 'count', factor: 1 },
  tb: { unit: 'tb', kind: 'storage', factor: 1 },
  gb: { unit: 'gb', kind: 'storage', factor: 1 },
  mb: { unit: 'mb', kind: 'storage', factor: 1 },
};

function normUnit(raw: string): string {
  const u = raw.toLowerCase().replace(/\s+/g, '');
  if (u.startsWith('kg') || u.startsWith('kilo')) return 'kg';
  if (u.startsWith('gramm') || u === 'g' || u.startsWith('gram')) return 'g';
  if (u === 'mg' || u.startsWith('milli') && u.includes('gram')) return 'mg';
  if (u === 'ml' || u.startsWith('millili')) return 'ml';
  if (u === 'l' || u.startsWith('liter') || u.startsWith('litre') || u === 'cl') return u === 'cl' ? 'ml' : 'l';
  if (u.includes('fl')) return 'ml';
  if (u.startsWith('oz') || u.startsWith('unz') || u.startsWith('ounc')) return 'oz';
  if (u.startsWith('lb') || u.startsWith('pound') || u.startsWith('pfund')) return 'lb';
  if (u.startsWith('st')) return 'pcs';
  if (u.startsWith('pc') || u.startsWith('pack') || u.startsWith('kaps') || u.startsWith('caps') || u.startsWith('tab') || u.startsWith('serv') || u.startsWith('port')) return 'pcs';
  if (u === 'tb') return 'tb';
  if (u === 'gb') return 'gb';
  if (u === 'mb') return 'mb';
  return u;
}

function parseNum(s: string): number {
  // "2,27" (DE) vs "2.27" (EN) — if both separators present, last one is decimal
  let t = s.trim();
  if (t.includes(',') && t.includes('.')) {
    const lastComma = t.lastIndexOf(',');
    const lastDot = t.lastIndexOf('.');
    if (lastComma > lastDot) t = t.replace(/\./g, '').replace(',', '.');
    else t = t.replace(/,/g, '');
  } else if (t.includes(',')) {
    t = t.replace('.', '').replace(',', '.');
  }
  return parseFloat(t);
}

export function extractQuantity(title: string, description = ''): ExtractedQty | null {
  const text = `${title} ${description}`;
  let m = text.match(MULTIPACK);
  if (m) {
    const count = parseInt(m[1], 10);
    const per = parseNum(m[2]);
    const unit = normUnit(m[3]);
    const mapped = UNIT_MAP[unit];
    if (mapped) return { value: count * per, unit: mapped.unit, kind: mapped.kind };
    if (unit === 'oz') return { value: count * per * 28.3495, unit: 'g', kind: 'mass' };
    if (unit === 'lb') return { value: count * per * 453.592, unit: 'g', kind: 'mass' };
  }
  m = text.match(QTY);
  if (m) {
    const val = parseNum(m[1]);
    const unit = normUnit(m[2]);
    const mapped = UNIT_MAP[unit];
    if (mapped) {
      // mg/cl need scaling to base display unit
      if (m[2].toLowerCase() === 'mg') return { value: val / 1000, unit: 'g', kind: 'mass' };
      if (m[2].toLowerCase() === 'cl') return { value: val * 10, unit: 'ml', kind: 'volume' };
      return { value: val, unit: mapped.unit, kind: mapped.kind };
    }
    if (unit === 'oz') return { value: val * 28.3495, unit: 'g', kind: 'mass' };
    if (unit === 'lb') return { value: val * 453.592, unit: 'g', kind: 'mass' };
  }
  m = text.match(SERVINGS);
  if (m) return { value: parseInt(m[1], 10), unit: 'pcs', kind: 'count' };
  return null;
}

// priceCents (int) / qty -> cents per base unit (kg, l, pcs, gb …)
export function unitPrice(priceCents: number, qty: ExtractedQty): { per: number; base: string } | null {
  const conv: Record<string, { base: string; mult: number }> = {
    kg: { base: 'kg', mult: 1 },
    g: { base: 'kg', mult: 1000 },
    l: { base: 'l', mult: 1 },
    ml: { base: 'l', mult: 1000 },
    pcs: { base: 'pcs', mult: 1 },
    tb: { base: 'tb', mult: 1 },
    gb: { base: 'gb', mult: 1 },
    mb: { base: 'gb', mult: 1000 },
  };
  const c = conv[qty.unit];
  if (!c || !qty.value) return null;
  // value is in qty.unit; convert: price per `base` = price / value * mult
  return { per: (priceCents / qty.value) * c.mult, base: c.base };
}
