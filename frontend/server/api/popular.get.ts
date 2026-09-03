// GET /api/popular?marketplace=de&lang=de — top real user searches (translated), [] on any failure
export default defineEventHandler(async (event) => {
  const marketplace = ((getQuery(event).marketplace as string) || 'de').trim();
  const lang = ((getQuery(event).lang as string) || 'de').trim();
  const config = useRuntimeConfig();
  try {
    const backend = await $fetch(`${config.backendUrl}/popular`, { query: { marketplace, lang } }) as any;
    return { items: backend.items || [] };
  } catch {
    return { items: [] };
  }
});
