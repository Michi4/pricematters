// PATCH /api/admin/inquiries/:id -> backend PATCH /inquiries/:id (mark resolved/read)
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const id = getRouterParam(event, 'id');
  const body = await readBody(event).catch(() => ({ ack: true }));
  try {
    return await $fetch(`${config.backendUrl}/inquiries/${id}`, {
      method: 'PATCH',
      body: { ack: body?.ack !== false },
      headers: { 'x-admin-key': getHeader(event, 'x-admin-key') || '' },
    }) as any;
  } catch {
    return { ok: false };
  }
});
