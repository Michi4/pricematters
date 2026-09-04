import { getHeader, type H3Event } from 'h3';

// Forward the client IP chain to the backend so its rate limiter and analytics
// see the real user, not the frontend container's IP ($fetch sets no
// forwarding headers on its own). Values are the inbound ones Traefik set;
// direct-to-backend is impossible (no published ports), so they are trustworthy.
export function fwdClientIp(event: H3Event): Record<string, string> {
  const out: Record<string, string> = {};
  const xff = getHeader(event, 'x-forwarded-for');
  const real = getHeader(event, 'x-real-ip');
  if (xff) out['x-forwarded-for'] = xff;
  if (real) out['x-real-ip'] = real;
  return out;
}
