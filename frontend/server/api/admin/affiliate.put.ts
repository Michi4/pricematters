// PUT /api/admin/affiliate -> backend PUT /admin/affiliate (save Partner ID)
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event).catch(() => ({}));
  try {
    return await $fetch(`${config.backendUrl}/admin/affiliate`, {
      method: 'PUT',
      body: { code: body?.code || '', tag: body?.tag || '' },
      headers: { 'x-admin-key': getHeader(event, 'x-admin-key') || '' },
    }) as any;
  } catch {
    return { ok: false };
  }
});
