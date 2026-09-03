import { extractQuantity, unitPrice } from '../../lib/units';

// GET /api/search?q=Reis
// MVP: proxies to the FastAPI backend; falls back to mock data if backend is down
// so you can develop the UI today without any Amazon approval.
export default defineEventHandler(async (event) => {
  const q = (getQuery(event).q as string || '').trim();
  if (!q) return { items: [] };
  const config = useRuntimeConfig();
  const tag = config.public.affiliateTag || 'websters0a-21';

  try {
    const backend = await $fetch(`${config.backendUrl}/search`, { query: { q } }) as any;
    return {
      items: (backend.items || []).map((it: any) => ({
        ...it,
        url: `${it.url}${it.url.includes('?') ? '&' : '?'}tag=${tag}`,
      })),
    };
  } catch {
    // mock fallback for UI dev
    const mocks = [
      { asin: 'MOCK1', title: `Bio Basmati Reis, 2 x 1kg (${q})`, priceCents: 1299, url: 'https://www.amazon.de/dp/MOCK1' },
      { asin: 'MOCK2', title: `Premium Langkorn Reis 500g (${q})`, priceCents: 499, url: 'https://www.amazon.de/dp/MOCK2' },
    ];
    return {
      items: mocks.map((m) => {
        const qty = extractQuantity(m.title);
        return { ...m, qty, unitPrice: qty ? unitPrice(m.priceCents, qty) : null, url: `${m.url}?tag=${tag}` };
      }),
    };
  }
});
