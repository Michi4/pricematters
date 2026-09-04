// DELETE /api/admin/inquiries/:id -> backend DELETE /inquiries/:id (admin key via header only)
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const id = getRouterParam(event, 'id');
  try {
    return await $fetch(`${config.backendUrl}/inquiries/${id}`, {
      method: 'DELETE',
      headers: { 'x-admin-key': getHeader(event, 'x-admin-key') || '' },
    }) as any;
  } catch {
    return { ok: false };
  }
});
