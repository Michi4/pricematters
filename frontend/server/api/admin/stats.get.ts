// GET /api/admin/stats?key -> backend /stats (key via header, never logged in URLs)
import { fwdClientIp } from '../../utils/clientIp';

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const key = getQuery(event).key as string || getHeader(event, 'x-admin-key') || '';
  try {
    return await $fetch(`${config.backendUrl}/stats`, {
      query: {
        days: getQuery(event).days || 30,
        hours: getQuery(event).hours || 48,
        inq_page: getQuery(event).inq_page || 1,
        inq_per: getQuery(event).inq_per || 20,
        excludeme: getQuery(event).excludeme || 0,
      },
      // forward the viewer IP so the backend can exclude the viewer's own
      // visits (excludeme=1) instead of the frontend container's
      headers: { 'x-admin-key': key, ...fwdClientIp(event) },
    });
  } catch (e: any) {
    setResponseStatus(event, e?.status || e?.response?.status || 502);
    return { error: 'unauthorized' };
  }
});
