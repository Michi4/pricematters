// GET /api/admin/alerts -> backend /alerts (pops the Signal queue; home bridge polls this)
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const key = getQuery(event).key as string || getHeader(event, 'x-admin-key') || '';
  try {
    return await $fetch(`${config.backendUrl}/alerts`, {
      headers: { 'x-admin-key': key },
    });
  } catch (e: any) {
    setResponseStatus(event, e?.status || e?.response?.status || 502);
    return { alerts: [], error: 'unauthorized' };
  }
});
