import { extractQuantity, unitPrice } from '../../lib/units';

// GET /api/search?q=Reis
// MVP: proxies to the FastAPI backend; falls back to mock data if backend is down
// so you can develop the UI today without any Amazon approval.
export default defineEventHandler(async (event) => {
  const query = getQuery(event);
  const q = ((query.q as string) || '').trim();
  const marketplace = ((query.marketplace as string) || 'de').trim();
  if (!q) return { items: [], meta: {} };
  const config = useRuntimeConfig();
  const tag = config.public.affiliateTag || 'websters02-21';

  try {
    const backend = await $fetch(`${config.backendUrl}/search`, { query: { q, marketplace } }) as any;
    return {
      items: (backend.items || []).map((it: any) => ({
        ...it,
        url: `${it.url}${it.url.includes('?') ? '&' : '?'}tag=${tag}`,
      })),
      meta: backend.meta || {},
    };
  } catch {
    // mock fallback for UI dev
    const mocks = [
      { asin: 'MOCK1', title: 'Bio Basmati Reis, 2 x 1kg', priceCents: 1299, url: 'https://www.amazon.de/dp/MOCK1', store: 'Amazon' },
      { asin: 'MOCK2', title: 'Bio Kaffee Bohnen 500g', priceCents: 899, url: 'https://www.amazon.de/dp/MOCK2', store: 'Amazon' },
    ];
    return {
      items: mocks.map((m) => {
        const qty = extractQuantity(m.title);
        return { ...m, qty, unitPrice: qty ? unitPrice(m.priceCents, qty) : null, url: `${m.url}?tag=${tag}` };
      }),
      meta: { demo: true, queries: [q] },
    };
  }
});
