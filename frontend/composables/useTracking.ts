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
    // clicks are tracked explicitly by the affiliate-link @click handlers
    // (index.vue) — a global DOM listener would double-count every click
    // and attribute it to the stale ?q= in the URL instead of the search
    // that actually produced the clicked product
    trackEvent('view', { ref: document.referrer || '', marketplace: String(route.query.marketplace || '') });
  });

  return { trackEvent, t0 };
}
