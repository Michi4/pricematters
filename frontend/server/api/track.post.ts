const FWD = [];

// POST /api/track -> backend /track (adds server-observed headers)
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const body = await readBody(event).catch(() => ({}));
  const server = {
    ref: getHeader(event, 'referer') || '',
    ua: getHeader(event, 'user-agent') || '',
    lang: getHeader(event, 'accept-language') || '',
    platform: getHeader(event, 'sec-ch-ua-platform') || '',
  };
  void FWD;
  try {
    return await $fetch(`${config.backendUrl}/track`, {
      method: 'POST',
      body: { ...body, ...server },
    });
  } catch {
    return { ok: false };
  }
});
