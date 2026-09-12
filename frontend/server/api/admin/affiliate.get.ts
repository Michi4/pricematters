// GET /api/admin/affiliate -> backend GET /admin/affiliate (programs + IDs)
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  try {
    return await $fetch(`${config.backendUrl}/admin/affiliate`, {
      headers: { 'x-admin-key': getHeader(event, 'x-admin-key') || '' },
    }) as any;
  } catch (e: any) {
    setResponseStatus(event, e?.status || e?.response?.status || 502);
    return { error: 'unauthorized' };
  }
});
