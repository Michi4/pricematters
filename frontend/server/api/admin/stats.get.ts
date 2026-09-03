// GET /api/admin/stats?key -> backend /stats (key via header, never logged in URLs)
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const key = getQuery(event).key as string || getHeader(event, 'x-admin-key') || '';
  try {
    return await $fetch(`${config.backendUrl}/stats`, {
      query: { days: getQuery(event).days || 30 },
      headers: { 'x-admin-key': key },
    });
  } catch (e: any) {
    setResponseStatus(event, e?.status || e?.response?.status || 502);
    return { error: 'unauthorized' };
  }
});
