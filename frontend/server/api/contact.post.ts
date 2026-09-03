// POST /api/contact — ad-slot inquiry, proxied to backend (which stores or logs it)
export default defineEventHandler(async (event) => {
  const body = await readBody(event);
  const config = useRuntimeConfig();
  try {
    const res = await $fetch(`${config.backendUrl}/contact`, { method: 'POST', body }) as any;
    return { ok: !!res?.ok };
  } catch {
    return { ok: false };
  }
});
