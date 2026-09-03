// GET /api/popular?marketplace=de — top real user searches, [] on any failure
export default defineEventHandler(async (event) => {
  const marketplace = ((getQuery(event).marketplace as string) || 'de').trim();
  const config = useRuntimeConfig();
  try {
    const backend = await $fetch(`${config.backendUrl}/popular`, { query: { marketplace } }) as any;
    return { items: backend.items || [] };
  } catch {
    return { items: [] };
  }
});
