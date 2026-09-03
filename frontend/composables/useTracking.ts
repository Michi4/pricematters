// Anonymous first-party analytics: no cookies, no localStorage, no fingerprints.
// Sends page views, searches and outbound affiliate clicks to /api/track.
const DEVICE_RE = /(mobile|android|iphone|ipad|tablet)/i;

function deviceKind(): string {
  try {
    if (DEVICE_RE.test(navigator.userAgent)) return 'mobile';
    if (matchMedia('(pointer: coarse)').matches) return 'tablet';
  } catch { /* jsdom etc */ }
  return 'desktop';
}

export function trackEvent(kind: string, data: Record<string, unknown> = {}) {
  try {
    const payload = {
      kind,
      lang: navigator.language || '',
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
      device: deviceKind(),
      w: window.innerWidth,
      ...data,
    };
    return $fetch('/api/track', { method: 'POST', body: payload }).catch(() => null);
  } catch { return null; }
}

export function useTracking() {
  const route = useRoute();
  const t0 = Date.now();
  const trackedView = ref('');

  onMounted(() => {
    if (trackedView.value === route.fullPath) return;
    trackedView.value = route.fullPath;
    trackEvent('view', { ref: document.referrer || '' });
  });

  // outbound affiliate clicks: capture before the tab navigates away
  const onClick = (e: MouseEvent) => {
    const a = (e.target as HTMLElement)?.closest?.('a[href]');
    if (!a) return;
    const href = (a as HTMLAnchorElement).href;
    if (!/amazon\.[a-z.]+\/|\/dp\//.test(href)) return;
    const card = a.closest('article');
    const title = card?.querySelector('h2')?.textContent?.slice(0, 120) || '';
    const price = card?.querySelector('.price')?.textContent || '';
    trackEvent('click', {
      asin: (href.match(/\/dp\/([A-Z0-9]{10})/i) || [])[1] || '',
      title,
      price_cents: Math.round(parseFloat(price.replace(',', '.')) * 100) || 0,
      pos: [...(card?.parentElement?.children || [])].indexOf(card) + 1,
      query: new URLSearchParams(window.location.search).get('q') || '',
    });
  };
  onMounted(() => document.addEventListener('click', onClick));
  onUnmounted(() => document.removeEventListener('click', onClick));

  return { trackEvent, t0 };
}
