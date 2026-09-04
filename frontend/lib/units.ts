// Unit Extraction Engine — client-safe mirror of backend/extractor.py
// Priority: multipack > best-scored single quantity > servings/count.
// Scoring: plausibility range, unit weight, position (pack size at END of title),
// per-claim rejection ("950 mg/kg", "1 Esslöffel/Tag" are NOT package sizes).
// NO LLM in the hot path (cost/latency). LLM only offline to generate test cases.

export type UnitKind = 'mass' | 'volume' | 'count' | 'storage' | 'unknown';

export interface ExtractedQty {
  value: number;
  unit: string; // normalised: g, kg, ml, l, pcs, tb, gb, mb
  kind: UnitKind;
}

const MULTIPACK = /(\d+)\s*(?:x|×|\*)\s*(\d+(?:[.,]\d+)?)\s*(kg|g|mg|ml|l|liter|litre|cl|oz|lb|lbs|fl\s?oz|stk|stück|stueck|pcs|pack|tb|gb|mb)\b/i;
const QTY = /(\d+(?:[.,]\d+)?)\s*(kg|kilogramm(?:e)?|kilograms?|g|gramm|grams?|mg|milligramm|l|liter|litre|liters?|ml|milliliter|cl|oz|ounces?|unzen?|lb|lbs|pounds?|pfund|fl\s?oz|stk\.?|stück|stueck|pcs|pack(?:ung)?|tb|gb|mb)\b/gi;
const SERVINGS = /(\d+)\s*(?:servings?|portionen|kapseln|capsules?|tabletten|tabs?)\b/i;
// "950 mg/kg", "€ 7,49/kg", "1 Esslöffel/Tag": a quantity directly followed by
// "/unit" is a per-claim, never the package size
const PER_CLAIM = /^\s*\/\s*(?:kg|g|100\s?g|l|100\s?ml|ml|stk|stück|stueck|pcs|tag|tage|day|days|portion|portionen)\b/i;

// plausible pack-size range per normalised unit (physical bounds)
const PLAUSIBLE: Record<string, [number, number]> = {
  kg: [0.05, 50],
  g: [50, 50000],
  l: [0.05, 50],
  ml: [50, 50000],
  pcs: [1, 500],
  tb: [0.5, 512],
  gb: [1, 4096],
  mb: [64, 262144],
};

const UNIT_WEIGHT: Record<string, number> = {
  kg: 3, l: 3, gb: 3, tb: 3,
  g: 2, ml: 2, mb: 2,
  pcs: 1,
};

function parseNum(s: string): number {
  let t = s.trim();
  if (t.includes(',') && t.includes('.')) {
    const lastComma = t.lastIndexOf(',');
    const lastDot = t.lastIndexOf('.');
    if (lastComma > lastDot) t = t.replace(/\./g, '').replace(',', '.');
    else t = t.replace(/,/g, '');
  } else if (t.includes(',')) {
    t = t.replace('.', '').replace(',', '.');
  } else if (t.includes('.')) {
    // DACH-first: "1.500 ml" = 1500 ml (thousand separator), "1.5" stays decimal
    const parts = t.split('.');
    if (parts.length > 1 && parts.slice(1).every((p) => /^\d{3}$/.test(p))) t = parts.join('');
  }
  return parseFloat(t);
}

type Norm = { unit: string; kind: UnitKind; factor?: number };

function normUnit(raw: string): Norm | null {
  const u = raw.toLowerCase().replace(/\s+/g, '');
  if (u === 'mg' || (u.startsWith('milli') && u.includes('gram'))) return { unit: 'mg', kind: 'mass' };
  if (u === 'cl') return { unit: 'cl', kind: 'volume' };
  if (u.startsWith('fl')) return { unit: 'floz', kind: 'volume' };
  if (u.startsWith('oz') || u.startsWith('unz') || u.startsWith('ounc')) return { unit: 'oz', kind: 'mass' };
  if (u.startsWith('lb') || u.startsWith('pound') || u.startsWith('pfund')) return { unit: 'lb', kind: 'mass' };
  if (u === 't' || u.startsWith('ton')) return { unit: 'kg', kind: 'mass', factor: 1000 };
  if (u.startsWith('kg') || u.startsWith('kilo')) return { unit: 'kg', kind: 'mass' };
  if (u === 'g' || u.startsWith('gram')) return { unit: 'g', kind: 'mass' };
  if (u === 'ml' || u.startsWith('millili')) return { unit: 'ml', kind: 'volume' };
  if (u === 'l' || u.startsWith('liter') || u.startsWith('litre')) return { unit: 'l', kind: 'volume' };
  if (u.startsWith('st') || u.startsWith('pc') || u.startsWith('pack') || u.startsWith('kaps') ||
      u.startsWith('caps') || u.startsWith('tab') || u.startsWith('serv') || u.startsWith('port'))
    return { unit: 'pcs', kind: 'count' };
  if (u === 'tb') return { unit: 'tb', kind: 'storage' };
  if (u === 'gb') return { unit: 'gb', kind: 'storage' };
  if (u === 'mb') return { unit: 'mb', kind: 'storage' };
  if (u === 'kb') return { unit: 'mb', kind: 'storage', factor: 0.001 };
  return null;
}

// normalise to display units (g, kg, ml, l, pcs, tb, gb, mb)
function scale(val: number, n: Norm): ExtractedQty | null {
  const f = n.factor ?? 1;
  switch (n.unit) {
    case 'mg': return { value: val / 1000, unit: 'g', kind: 'mass' };
    case 'cl': return { value: val * 10, unit: 'ml', kind: 'volume' };
    case 'floz': return { value: val * 29.5735, unit: 'ml', kind: 'volume' };
    case 'oz': return { value: val * 28.3495, unit: 'g', kind: 'mass' };
    case 'lb': return { value: val * 453.592, unit: 'g', kind: 'mass' };
    case 'kg': case 'g': case 'ml': case 'l': case 'pcs': case 'tb': case 'gb': case 'mb':
      return { value: val * f, unit: n.unit, kind: n.kind };
    default: return null;
  }
}

function plausible(q: ExtractedQty): boolean {
  const r = PLAUSIBLE[q.unit];
  if (!r) return true;
  return q.value >= r[0] && q.value <= r[1];
}

function scoreMatch(m: RegExpExecArray, text: string): number {
  const val = parseNum(m[1]);
  const n = normUnit(m[2]);
  if (!n) return -1;
  const q = scale(val, n);
  if (!q || !plausible(q)) return -1;
  // claims lose before they start ("950 mg/kg", "€ 7,49/kg")
  if (PER_CLAIM.test(text.slice(m.index + m[0].length, m.index + m[0].length + 4))) return -1;
  let s = UNIT_WEIGHT[q.unit] ?? 0.5;
  // pack size sits at the END of the title
  s += 2 * (m.index / Math.max(text.length, 1));
  // single-digit counts early in the title ("12 Stück …") are rarely the pack size
  if (q.unit === 'pcs' && m.index / text.length < 0.3) s -= 1;
  return s;
}

function firstSingleQty(text: string): { m: RegExpExecArray; q: ExtractedQty } | null {
  // legacy first-match path kept for MULTIPACK which stays authoritative
  const m = text.match(MULTIPACK);
  if (!m) return null;
  const count = parseInt(m[1], 10);
  const per = parseNum(m[2]);
  const n = normUnit(m[3]);
  if (!n) return null;
  const q = scale(count * per, n);
  if (!q || !plausible(q)) return null;
  return { m: m as unknown as RegExpExecArray, q };
}

export function extractQuantity(title: string, description = ''): ExtractedQty | null {
  const text = `${title} ${description}`;

  // 1. multipack ("2 x 500 g") — authoritative
  const mp = firstSingleQty(text);
  if (mp) return mp.q;

  // 2. best scored single quantity
  let best: ExtractedQty | null = null;
  let bestScore = 0;
  QTY.lastIndex = 0;
  for (let m = QTY.exec(text); m; m = QTY.exec(text)) {
    const s = scoreMatch(m, text);
    if (s > bestScore) {
      const n = normUnit(m[2]);
      const q = n ? scale(parseNum(m[1]), n) : null;
      if (q) { best = q; bestScore = s; }
    }
  }
  if (best) return best;

  // 3. servings/count as last resort
  const sm = text.match(SERVINGS);
  if (sm) return { value: parseInt(sm[1], 10), unit: 'pcs', kind: 'count' };
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
    // 1 tb = 1000 gb -> per-gb = per-tb / 1000; 1000 mb = 1 gb -> per-gb = per-mb * 1000
    tb: { base: 'gb', mult: 0.001 },
    gb: { base: 'gb', mult: 1 },
    mb: { base: 'gb', mult: 1000 },
  };
  const c = conv[qty.unit];
  if (!c || !qty.value) return null;
  return { per: (priceCents / qty.value) * c.mult, base: c.base };
}

// Display targets for the UI unit selector (€/kg vs €/100g vs €/l …)
export const DISPLAY_TARGETS = [
  { id: 'kg', bases: ['kg'] },
  { id: '100g', bases: ['kg'] },
  { id: 'l', bases: ['l'] },
  { id: '100ml', bases: ['l'] },
  { id: 'pcs', bases: ['pcs'] },
  { id: 'gb', bases: ['gb', 'tb', 'mb'] },
] as const;

export function convertPer(per: number, base: string, target: string): number | null {
  if (target === base) return per;
  if (base === 'kg' && target === '100g') return per / 10;
  if (base === 'l' && target === '100ml') return per / 10;
  if (base === 'gb' && target === 'tb') return per * 1000;
  if (base === 'gb' && target === 'mb') return per / 1000;
  return null;
}
