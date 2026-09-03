// GET /api/curated?marketplace=de — Michi's favorites, live when possible
export default defineEventHandler(async (event) => {
  const marketplace = ((getQuery(event).marketplace as string) || 'de').trim();
  const config = useRuntimeConfig();
  try {
    const backend = await $fetch(`${config.backendUrl}/curated`, { query: { marketplace } }) as any;
    return { items: backend.items || [] };
  } catch {
    return { items: [] };
  }
});
