import { getRequestHost, getRequestURL, sendRedirect } from 'h3';

// One canonical origin: every alias domain (deals., dothemath., …) 308s to
// pricematters.websters.at with path + query preserved. Why here and not in
// Traefik: this is version-controlled, host-aware, and needs no proxy changes.
// Effects: single localStorage/cookie jar (saved prefs just work), no duplicate
// content for SEO, one Amazon-approved click domain. 308 (not 301) preserves
// POST bodies for /api/* callers on alias hosts.
export default defineEventHandler((event) => {
  const host = (getRequestHost(event) || '').split(':')[0].toLowerCase();
  if (!host) return;
  // local dev / docker-internal traffic never redirects
  if (host === 'localhost' || host === '127.0.0.1' || host === '::1' || host.startsWith('192.168.') || host.startsWith('10.') || host === 'backend' || host === 'frontend') return;
  const canonical = (useRuntimeConfig().public.canonicalHost || 'pricematters.websters.at').toLowerCase();
  if (host === canonical) return;
  const url = getRequestURL(event);
  return sendRedirect(event, `https://${canonical}${url.pathname}${url.search}`, 308);
});
