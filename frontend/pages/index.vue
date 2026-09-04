<template>
  <div class="page">
    <header class="top">
      <NuxtLink :to="localePath('/')" class="logo" @click="goHome">
        <img src="/logo.svg" alt="logo" width="28" height="28" class="logo-light" />
        <img src="/logo-dark.svg" alt="logo" width="28" height="28" class="logo-dark" />
        <span>{{ brand.name }}</span>
      </NuxtLink>
      <div class="top-right">
        <button class="theme-btn" @click="toggleTheme" aria-label="Theme">
          <svg v-if="theme === 'dark'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5 5l1.8 1.8M17.2 17.2L19 19M19 5l-1.8 1.8M6.8 17.2L5 19"/></svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4a6.5 6.5 0 0 0 9.5 9.5z"/></svg>
        </button>
        <nav class="lang">
        <NuxtLink
          v-for="l in (locales as any[])"
          :key="l.code"
          :to="switchLocalePath(l.code)"
          :class="{ active: locale === l.code }"
        >{{ l.code.toUpperCase() }}</NuxtLink>
        </nav>
      </div>
    </header>

    <div class="layout">
      <aside class="rail" aria-hidden="false">
        <div class="ad">
          <span class="ad-label">{{ t('ads.label') }}</span>
          <p><strong>{{ t('ads.sidebar') }}</strong></p>
          <a href="#" @click.prevent="adOpen = true">{{ t('ads.cta') }}</a>
        </div>
      </aside>

    <main>
      <section class="hero">
        <p class="eyebrow">{{ brand.name }}</p>
        <Transition name="fade" mode="out-in">
          <h1 :key="sloganIdx" v-html="fmtSlogan(slogans[sloganIdx] || '')"></h1>
        </Transition>
        <form class="search" @submit.prevent="search">
          <input v-model="q" :placeholder="t('hero.searchPlaceholder')" autofocus @keydown.enter.prevent="search" />
          <select v-model="marketplace" :title="t('hero.marketplace')" @change="saveMarket">
            <optgroup :label="t('results.groups.eu')">
              <option v-for="m in MARKETS.filter((x) => x.group === 'eu')" :key="m.code" :value="m.code">{{ countryName(m.cc) }} · {{ m.domain }}</option>
            </optgroup>
            <optgroup :label="t('results.groups.world')">
              <option v-for="m in MARKETS.filter((x) => x.group === 'world')" :key="m.code" :value="m.code">{{ countryName(m.cc) }} · {{ m.domain }}</option>
            </optgroup>
          </select>
          <button type="submit" :disabled="pending" :aria-busy="pending">
            <svg v-if="pending" class="spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="rgba(255,255,255,0.35)" stroke-width="3"/>
              <path d="M21 12a9 9 0 0 0-9-9" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
            </svg>
            <span class="btn-label">{{ pending ? t('hero.searching') : t('hero.searchButton') }}</span>
          </button>
        </form>
        <p v-if="popular.length" class="popular">{{ t('hero.popular') }}
          <TransitionGroup name="fade">
            <button v-for="p in popular" :key="p" @click="q = p; search()">{{ p }}</button>
          </TransitionGroup>
        </p>
      </section>

      <section v-if="faves.length && !searched" class="faves">
        <h2>{{ t('faves.title') }}</h2>
        <p class="mut">{{ t('faves.sub') }}</p>
        <article v-for="(f, fi) in faves" :key="f.asin" class="card">
          <div class="card-main">
            <img v-if="f.image" :src="thumbUrl(f.image)" :alt="f.title" width="84" height="84" class="thumb" />
            <div v-else class="thumb placeholder"><img src="/logo.svg" alt="" width="44" height="44" /></div>
            <div class="card-body">
              <h2>{{ f.title }}</h2>
              <div class="numbers">
                <span class="price">{{ money(f.price_cents) }}</span>
                <span v-if="faveQtyLabel(f)" class="qty fave-unit">{{ faveQtyLabel(f) }}</span>
                <span v-if="f.rating" class="qty">★ {{ f.rating }} ({{ f.reviews }})</span>
              </div>
            </div>
          </div>
          <div class="card-actions">
            <a :href="f.url" target="_blank" rel="nofollow sponsored noopener" class="cta" :aria-label="`${t('results.atAmazon')}: ${f.title.slice(0, 80)}`">{{ t('results.atAmazon') }}</a>
            <span class="paid">{{ t('results.paidLink') }}</span>
          </div>
        </article>
      </section>

      <!-- skeleton keeps layout stable while searching (no jumping) -->
      <section v-if="pending && !searched" class="results" aria-hidden="true">
        <div class="skel meta-row"><span class="skel-bar" style="width: 30%"></span></div>
        <div v-for="n in 4" :key="n" class="card skel">
          <div class="card-main">
            <div class="thumb skel-thumb"></div>
            <div class="card-body">
              <div class="skel-bar" style="width: 85%; height: 1rem"></div>
              <div class="skel-bar" style="width: 55%; height: 1rem; margin-top: 0.5rem"></div>
              <div class="skel-bar" style="width: 40%; height: 1.6rem; margin-top: 0.8rem"></div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="searched" class="results" aria-live="polite">
        <div class="meta-row">
          <span>{{ t('results.count', { n: sorted.length }) }}</span>
          <span v-if="meta.demo" class="demo">{{ t('results.demo') }}</span>
          <span v-if="meta.queries?.length > 1" class="also">
            {{ t('results.alsoSearched') }} {{ meta.queries.slice(1).join(', ') }}
          </span>
          <span v-if="meta.zone" class="zone">{{ t('results.zone', { zone: zoneLabel }) }}</span>
          <span v-if="shipHint" class="ship">
            {{ t('results.shipNote') }}
            <button class="linklike" @click="marketplace = 'de'; saveMarket(); search()">{{ t('results.shipSwitch') }}</button>
          </span>
        </div>

        <div v-if="sorted.length" class="controls">
          <div class="segmented" role="tablist" :aria-label="t('results.sort.label')">
            <button :class="{ active: sortKey === 'unit' }" @click="sortKey = 'unit'">{{ t('results.sort.shortUnit') }}</button>
            <button :class="{ active: sortKey === 'priceAsc' }" @click="sortKey = 'priceAsc'">{{ t('results.sort.shortAsc') }}</button>
            <button :class="{ active: sortKey === 'priceDesc' }" @click="sortKey = 'priceDesc'">{{ t('results.sort.shortDesc') }}</button>
          </div>
        </div>

        <details v-if="sorted.length" class="filters-wrap">
          <summary>{{ t('results.filterTitle') }}</summary>
          <div class="controls">
          <label>{{ t('results.unit.label') }}
            <select v-model="displayUnit">
              <option v-for="u in unitOptions" :key="u" :value="u">{{ sym }} / {{ u }}</option>
            </select>
          </label>
          <div v-if="stores.length > 1" class="stores">
            <span>{{ t('results.store.label') }}:</span>
            <button :class="{ active: storeFilter === 'all' }" @click="storeFilter = 'all'">{{ t('results.store.all') }}</button>
            <button
              v-for="s in stores" :key="s"
              :class="{ active: storeFilter === s }" @click="storeFilter = s"
            >{{ s }}</button>
          </div>
          <label>{{ t('results.filter.min') }}
            <input v-model="minPrice" type="number" min="0" step="0.01" placeholder="0.00" />
          </label>
          <label>{{ t('results.filter.max') }}
            <input v-model="maxPrice" type="number" min="0" step="0.01" placeholder="∞" />
          </label>
          <label>{{ t('results.filter.kind') }}
            <select v-model="kindFilter">
              <option value="all">{{ t('results.filter.kinds.all') }}</option>
              <option value="mass">{{ t('results.filter.kinds.mass') }}</option>
              <option value="volume">{{ t('results.filter.kinds.volume') }}</option>
              <option value="count">{{ t('results.filter.kinds.count') }}</option>
              <option value="storage">{{ t('results.filter.kinds.storage') }}</option>
            </select>
          </label>
          <label class="check">
            <input v-model="onlyUnit" type="checkbox" />
            {{ t('results.filter.onlyUnit') }}
          </label>
          </div>
        </details>

        <p v-if="searchError" class="error banner">{{ t('results.rateLimited', { s: searchRetry }) }}</p>

        <p v-if="!sorted.length && !pending" class="empty">{{ t('results.empty') }}</p>

        <template v-for="(r, i) in paged" :key="r.asin">
        <article class="card" :class="{ best: i === 0 && page === 1 && sortKey === 'unit' && shownUnit(r) }">
          <div class="card-top">
            <span v-if="i === 0 && page === 1 && sortKey === 'unit' && shownUnit(r)" class="best-badge">{{ t('results.best') }}</span>
            <span class="store">{{ r.store || 'Amazon' }}</span>
          </div>
          <div class="card-main">
            <img v-if="r.image" :src="thumbUrl(r.image)" :alt="r.title" loading="lazy" width="84" height="84" class="thumb" />
            <div v-else class="thumb placeholder"><img src="/logo.svg" alt="" width="44" height="44" /></div>
            <div class="card-body">
          <h2>{{ r.title }}</h2>
          <div class="numbers">
            <span class="price">{{ money(r.priceCents) }}</span>
            <span v-if="r.qty" class="qty">{{ fmtQty(r.qty.value) }} {{ r.qty.unit }}</span>
            <span v-if="shownUnit(r)" class="unitprice">
              {{ moneyBare(shownUnit(r)) }} {{ sym }} / {{ displayUnit }}
            </span>
          </div>
            </div>
          </div>
          <div class="card-actions">
            <a :href="r.url" target="_blank" rel="nofollow sponsored noopener" class="cta" :aria-label="`${(r.store === 'Amazon' || !r.store ? t('results.atAmazon') : t('results.atShop'))}: ${r.title.slice(0, 80)}`">
              {{ r.store === 'Amazon' || !r.store ? t('results.atAmazon') : t('results.atShop') }}
            </a>
            <span class="paid">{{ t('results.paidLink') }}</span>
          </div>
        </article>
        <div v-if="i === 1 && sorted.length > 3" class="ad infeed">
          <span class="ad-label">{{ t('ads.label') }}</span>
          <p>{{ t('ads.infeed') }} <a href="#" @click.prevent="adOpen = true">{{ t('ads.cta') }}</a></p>
        </div>
        </template>

        <div v-if="totalPages > 1" class="pager">
          <button :disabled="page <= 1" @click="page--">‹</button>
          <span>{{ t('results.pageOf', { p: page, n: totalPages }) }}</span>
          <button :disabled="page >= totalPages" @click="page++">›</button>
          <label>{{ t('results.perPage') }}
            <select v-model.number="perPage">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </label>
        </div>
      </section>

    </main>

      <aside class="rail" aria-hidden="false">
        <div class="ad">
          <span class="ad-label">{{ t('ads.label') }}</span>
          <p><strong>{{ t('ads.sidebar') }}</strong></p>
          <a href="#" @click.prevent="adOpen = true">{{ t('ads.cta') }}</a>
        </div>
      </aside>
    </div>

    <Transition name="fade">
      <div v-if="showDarkHint" class="dark-hint" role="status">
        <p>{{ t('theme.darkHint') }}</p>
        <button class="linklike" @click="dismissDarkHint">{{ t('theme.ok') }}</button>
      </div>
    </Transition>

    <footer>
      <p class="disclosure">{{ t('footer.disclosure') }}</p>
      <p>{{ t('footer.by') }} <a href="https://websters.at" target="_blank" rel="noopener">websters.at</a> · <button class="linklike" @click="adOpen = true">{{ t('ads.title') }}</button></p>
    </footer>

    <div v-if="adOpen" class="modal-backdrop" @click.self="adOpen = false">
      <div ref="modalEl" class="modal" role="dialog" aria-modal="true" :aria-label="t('ads.title')">
        <button class="modal-x" @click="adOpen = false" aria-label="Close">✕</button>
        <h2>{{ t('ads.title') }}</h2>
        <p class="mut">{{ t('ads.text') }}</p>
        <form v-if="!adSent" class="ad-form" @submit.prevent="submitContact">
          <div class="row">
            <label>{{ t('ads.name') }}<input v-model="adName" required maxlength="120" /></label>
            <label>{{ t('ads.email') }}<input v-model="adEmail" type="email" required maxlength="160" /></label>
          </div>
          <label>{{ t('ads.slot') }}
            <select v-model="adSlot">
              <option value="rail">{{ t('ads.slots.rail') }}</option>
              <option value="infeed">{{ t('ads.slots.infeed') }}</option>
            </select>
          </label>
          <label>{{ t('ads.message') }}<textarea v-model="adMsg" rows="3" required maxlength="2000"></textarea></label>
          <button type="submit" :disabled="adSending">{{ adSending ? t('ads.sending') : t('ads.send') }}</button>
          <p v-if="adError" class="error">{{ t('ads.error') }}</p>
        </form>
        <p v-else class="done">{{ t('ads.done') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { convertPer, DISPLAY_TARGETS, extractQuantity, unitPrice } from '../lib/units';

const appConfig = useAppConfig() as any;
const config = useRuntimeConfig();
const { t, tm, locale, locales } = useI18n();
const { trackEvent, t0 } = useTracking();
const localePath = useLocalePath();
const switchLocalePath = useSwitchLocalePath();
const route = useRoute();

const host = useRequestURL().host;
const brand = computed(() => {
  const brands = appConfig.brands as Record<string, any>;
  const aliases = (appConfig.aliases as Record<string, string>) || {};
  return brands[aliases[host] || host] || brands.default;
});
const slogans = computed<string[]>(() =>
  brand.value[locale.value === 'de' ? 'slogansDE' : 'slogansEN'] || brand.value.slogansEN || []);
// *word* markers in slogans become underlined emphasis in HTML, plain text in meta tags
const fmtSlogan = (s: string) => s.replace(/\*([^*]+)\*/g, '<u>$1</u>');
const plainSlogan = (s: string) => s.replaceAll('*', '');
const sloganIdx = ref(0);
const theme = ref('light');
const showDarkHint = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;
function applyTheme(t: string) {
  theme.value = t;
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem('pm_theme', t); } catch { /* private mode */ }
}
function toggleTheme() {
  const next = theme.value === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  // honest one-time hint: light is the polished default, dark works but isn't perfect
  if (next === 'dark') {
    try { showDarkHint.value = !localStorage.getItem('pm_dark_hint'); } catch { showDarkHint.value = true; }
  } else {
    showDarkHint.value = false;
  }
  trackEvent('theme', { ref: next });
}
function dismissDarkHint() {
  showDarkHint.value = false;
  try { localStorage.setItem('pm_dark_hint', '1'); } catch { /* private mode */ }
}
const { data: favesData } = await useAsyncData('faves', () =>
  $fetch('/api/curated', { query: { marketplace: 'de' } }).catch(() => ({ items: [] })));
const faves = computed(() => (favesData.value as any)?.items || []);
async function loadFaves() {
  try {
    const data = await $fetch('/api/curated', { query: { marketplace: marketplace.value } }) as any;
    if (data?.items?.length) favesData.value = data;
  } catch { /* SSR data stays */ }
}
function faveQtyLabel(f: any) {
  // actual package unit (e.g. "1 kg", "600 ml"), not a computed unit price
  if (f.qty?.value && f.qty?.unit) return `${fmtQty(f.qty.value)} ${f.qty.unit}`;
  try {
    const q = extractQuantity(f.title || '');
    return q ? `${fmtQty(q.value)} ${q.unit}` : null;
  } catch { return null; }
}

function faveUnit(f: any) {
  // prefer backend-provided qty (manual override), fall back to title extraction
  if (f.qty?.value && f.qty?.unit) {
    const per = unitPrice(f.price_cents, { value: f.qty.value, unit: f.qty.unit, kind: 'count' });
    if (per) return per;
  }
  try {
    const qty = extractQuantity(f.title || '');
    return qty ? unitPrice(f.price_cents, qty) : null;
  } catch { return null; }
}
async function loadPopular() {
  try {
    // marketplace=all merges every market/language on the backend
    const data = await $fetch('/api/popular', { query: { marketplace: 'all', lang: locale.value } }) as any;
    popularApi.value = data?.items || [];
  } catch { popularApi.value = []; }
}
onMounted(() => {
  timer = setInterval(() => { sloganIdx.value = (sloganIdx.value + 1) % Math.max(slogans.value.length, 1); }, 5000);
  try {
    const saved = localStorage.getItem('pm_theme');
    // light is the default; respect an explicit user choice only
    applyTheme(saved === 'dark' ? 'dark' : 'light');
  } catch { applyTheme('light'); }
  loadPopular();
  marketplace.value = guessMarketplace();
  // SSR faves always render marketplace 'de'; re-fetch for the guessed locale
  loadFaves();
  try { userTz.value = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch { /* ignore */ }
  if (route.query.q) { q.value = String(route.query.q); search(); }
});
onUnmounted(() => { if (timer) clearInterval(timer); });

const q = ref('');
const marketplace = ref('de');
// Auto: amazon address by user locale (de-AT -> at, en-GB -> co.uk, fr -> fr, en -> com),
// persisted in a cookie once chosen; ?marketplace= overrides everything.
function readCookie(name: string): string {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : '';
}
function guessMarketplace(): string {
  try {
    const forced = String(route.query.marketplace || '');
    if (CODES.includes(forced)) return forced;
    const saved = readCookie('pm_market');
    if (CODES.includes(saved)) return saved;
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    const city = (tz.split('/')[1] || '').toLowerCase();
    const cityMap: Record<string, string> = {
      vienna: 'at', zurich: 'ch', berlin: 'de', paris: 'fr', london: 'co.uk',
      madrid: 'es', rome: 'it', amsterdam: 'nl', stockholm: 'se', warsaw: 'pl',
      brussels: 'be', dublin: 'ie', tokyo: 'co.jp',
    };
    if (cityMap[city]) return cityMap[city];
    if (/^America\//i.test(tz)) return 'com';
    const l = navigator.language || '';
    if (/^de-AT/i.test(l)) return 'at';
    if (/^de/i.test(l)) return 'de';
    if (/^en-GB/i.test(l)) return 'co.uk';
    if (/^fr/i.test(l)) return 'fr';
    if (/^en/i.test(l)) return 'com';
  } catch { /* SSR: default */ }
  return 'de';
}
function saveMarket() {
  try { document.cookie = `pm_market=${marketplace.value};max-age=31536000;path=/;SameSite=Lax`; } catch { /* ignore */ }
}
const results = ref<any[]>([]);
const meta = ref<any>({});
const pending = ref(false);
const searched = ref(false);
const sortKey = ref('unit');
const displayUnit = ref('kg');
const storeFilter = ref('all');
const minPrice = ref('');
const maxPrice = ref('');
const kindFilter = ref('all');
const onlyUnit = ref(true);
const page = ref(1);
const perPage = ref(25);
const userTz = ref('');
const shipHint = computed(() => {
  if (['de', 'at', 'ch'].includes(marketplace.value)) return false;
  try { return /^Europe\//i.test(userTz.value || Intl.DateTimeFormat().resolvedOptions().timeZone || ''); }
  catch { return false; }
});
const adName = ref('');
const adEmail = ref('');
const adMsg = ref('');
const adSlot = ref('rail');
const adSending = ref(false);
const adSent = ref(false);
const adError = ref(false);
const adOpen = ref(false);
const searchError = ref(false);
const searchRetry = ref(0);
const modalEl = ref<HTMLElement | null>(null);

// refresh faves + popular when marketplace changes (registered once, not per search)
watch(marketplace, () => { loadFaves(); });
watch(locale, () => { loadPopular(); });

function onModalKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && adOpen.value) adOpen.value = false;
}
onMounted(() => window.addEventListener('keydown', onModalKey));
onUnmounted(() => window.removeEventListener('keydown', onModalKey));
watch(adOpen, (open) => {
  if (open) nextTick(() => (modalEl.value?.querySelector('button, input, select, textarea') as HTMLElement | null)?.focus());
});

async function submitContact() {
  adSending.value = true;
  adError.value = false;
  try {
    const res = await $fetch('/api/contact', {
      method: 'POST',
      body: { name: adName.value, email: adEmail.value, message: adMsg.value, slot: adSlot.value },
    }) as any;
    if (res?.ok) adSent.value = true;
    else adError.value = true;
  } catch {
    adError.value = true;
  } finally {
    adSending.value = false;
  }
}

const popularApi = ref<string[]>([]);
// real user searches only — no placeholders; empty until the backend has data
const popular = computed(() => popularApi.value);
const MARKETS = [
  { code: 'de', cc: 'DE', domain: 'amazon.de', group: 'eu' },
  { code: 'at', cc: 'AT', domain: 'amazon.de', group: 'eu' },
  { code: 'ch', cc: 'CH', domain: 'amazon.de', group: 'eu' },
  { code: 'fr', cc: 'FR', domain: 'amazon.fr', group: 'eu' },
  { code: 'it', cc: 'IT', domain: 'amazon.it', group: 'eu' },
  { code: 'es', cc: 'ES', domain: 'amazon.es', group: 'eu' },
  { code: 'nl', cc: 'NL', domain: 'amazon.nl', group: 'eu' },
  { code: 'se', cc: 'SE', domain: 'amazon.se', group: 'eu' },
  { code: 'pl', cc: 'PL', domain: 'amazon.pl', group: 'eu' },
  { code: 'be', cc: 'BE', domain: 'amazon.com.be', group: 'eu' },
  { code: 'co.uk', cc: 'GB', domain: 'amazon.co.uk', group: 'eu' },
  { code: 'ie', cc: 'IE', domain: 'amazon.ie', group: 'eu' },
  { code: 'com', cc: 'US', domain: 'amazon.com', group: 'world' },
  { code: 'ca', cc: 'CA', domain: 'amazon.ca', group: 'world' },
  { code: 'com.mx', cc: 'MX', domain: 'amazon.com.mx', group: 'world' },
  { code: 'com.br', cc: 'BR', domain: 'amazon.com.br', group: 'world' },
  { code: 'com.au', cc: 'AU', domain: 'amazon.com.au', group: 'world' },
  { code: 'co.jp', cc: 'JP', domain: 'amazon.co.jp', group: 'world' },
  { code: 'in', cc: 'IN', domain: 'amazon.in', group: 'world' },
  { code: 'ae', cc: 'AE', domain: 'amazon.ae', group: 'world' },
  { code: 'sa', cc: 'SA', domain: 'amazon.sa', group: 'world' },
  { code: 'sg', cc: 'SG', domain: 'amazon.sg', group: 'world' },
  { code: 'com.tr', cc: 'TR', domain: 'amazon.com.tr', group: 'world' },
];
const CODES = MARKETS.map((m) => m.code);
const CURRENCY: Record<string, string> = {
  de: '€', at: '€', ch: '€', fr: '€', it: '€', es: '€', nl: '€', be: '€', ie: '€',
  se: 'kr', pl: 'zł', 'co.uk': '£', com: '$', ca: 'CA$', 'com.mx': 'MX$', 'com.br': 'R$',
  'com.au': 'A$', 'co.jp': '¥', in: '₹', ae: 'AED', sa: 'SAR', sg: 'S$', 'com.tr': '₺',
};
const countryName = (cc: string) => {
  try { return new Intl.DisplayNames([locale.value], { type: 'region' }).of(cc) || cc; }
  catch { return cc; }
};
const sym = computed(() => CURRENCY[marketplace.value] || '€');
const zoneLabel = computed(() => {
  const m = MARKETS.find((x) => x.code === marketplace.value);
  return m ? `${countryName(m.cc)} · ${m.domain}` : marketplace.value;
});
const thumbUrl = (src: string | undefined) =>
  src ? src.replace(/\._[^.]+_\./, '._AC_SY160_.') : src;
const money = (cents: number) => `${(cents / 100).toFixed(2)} ${sym.value}`;
const moneyBare = (cents: number) => (cents / 100).toFixed(2);
// quantities: max 2 decimals, no float artifacts (2721.551999999997 -> 2721.55)
const fmtQty = (v: number) => String(parseFloat(Number(v).toFixed(2)));

function goHome() {
  // logo click: back to fresh homepage with favorites
  searched.value = false;
  results.value = [];
  q.value = '';
  page.value = 1;
  if (window.scrollY > 0) window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function search() {
  if (!q.value.trim() || pending.value) return;
  pending.value = true;
  searchError.value = false;
  const started = Date.now();
  try {
    await navigateTo({ query: { q: q.value, marketplace: marketplace.value } }, { replace: true });
    const data = await $fetch('/api/search', { query: { q: q.value, marketplace: marketplace.value } });
    results.value = (data as any).items || [];
    meta.value = (data as any).meta || {};
    searched.value = true;
    // a new search must not silently inherit the previous search's filters
    storeFilter.value = 'all';
    minPrice.value = '';
    maxPrice.value = '';
    kindFilter.value = 'all';
    onlyUnit.value = true;
    page.value = 1;
    trackEvent('search', {
      query: q.value, marketplace: marketplace.value,
      result_count: results.value.length, ms: Date.now() - started,
    });
    // sensible default display unit from result kinds
    const bases = new Set(results.value.map((r: any) => r.unitPrice?.base));
    displayUnit.value = bases.has('kg') ? 'kg' : bases.has('l') ? 'l' : bases.has('pcs') ? 'pcs' : 'kg';
  } catch (e: any) {
    const status = e?.status || e?.response?.status;
    if (status === 429) {
      searchRetry.value = e?.data?.retry_after || 60;
      trackEvent('search', { query: q.value, marketplace: marketplace.value, result_count: -429, ms: Date.now() - started });
    } else {
      searchRetry.value = 0;
      trackEvent('search', { query: q.value, marketplace: marketplace.value, result_count: -1, ms: Date.now() - started });
    }
    searchError.value = true;
    searched.value = true;
  } finally {
    pending.value = false;
  }
}

// per-item unit value in the selected display unit (cents), or null
function shownUnit(r: any): number | null {
  if (!r.unitPrice) return null;
  return convertPer(r.unitPrice.per, r.unitPrice.base, displayUnit.value);
}

const stores = computed(() => [...new Set(results.value.map((r: any) => r.store || 'Amazon'))]);
const unitOptions = computed(() => {
  const bases = new Set(results.value.map((r: any) => r.unitPrice?.base).filter(Boolean));
  const opts = DISPLAY_TARGETS.filter((u: any) => u.bases.some((b: string) => bases.has(b))).map((u: any) => u.id);
  return opts.length ? opts : ['kg'];
});

const sorted = computed(() => {
  const min = parseFloat(minPrice.value) * 100;
  const max = parseFloat(maxPrice.value) * 100;
  const arr = results.value.filter((r: any) => {
    if (storeFilter.value !== 'all' && (r.store || 'Amazon') !== storeFilter.value) return false;
    if (onlyUnit.value && !r.unitPrice) return false;
    if (kindFilter.value !== 'all' && r.qty?.kind !== kindFilter.value) return false;
    if (!isNaN(min) && minPrice.value !== '' && r.priceCents < min) return false;
    if (!isNaN(max) && maxPrice.value !== '' && r.priceCents > max) return false;
    return true;
  });
  const by = {
    unit: (a: any, b: any) => (shownUnit(a) ?? Infinity) - (shownUnit(b) ?? Infinity),
    priceAsc: (a: any, b: any) => a.priceCents - b.priceCents,
    priceDesc: (a: any, b: any) => b.priceCents - a.priceCents,
  }[sortKey.value] as (a: any, b: any) => number;
  return [...arr].sort(by);
});

const totalPages = computed(() => Math.max(1, Math.ceil(sorted.value.length / perPage.value)));
const paged = computed(() => sorted.value.slice((page.value - 1) * perPage.value, page.value * perPage.value));
watch([sortKey, storeFilter, kindFilter, minPrice, maxPrice, onlyUnit, displayUnit, perPage], () => { page.value = 1; });

// ---- SEO (SSR, per brand + locale) ----
const url = useRequestURL();
const canonical = computed(() => `https://${config.public.canonicalHost}${url.pathname}`);
const pageTitle = computed(() => locale.value === 'de'
  ? `${brand.value?.name} – Grundpreise vergleichen (€/kg, €/l, €/Stück)`
  : `${brand.value?.name} – Compare unit prices (€/kg, €/L, €/pc)`);
const pageDesc = computed(() => plainSlogan(slogans.value[0] || ''));
useSeoMeta({
  title: () => pageTitle.value,
  description: () => pageDesc.value,
  ogTitle: () => pageTitle.value,
  ogDescription: () => pageDesc.value,
  ogUrl: () => canonical.value,
  ogImage: () => `https://${config.public.canonicalHost}/og.png`,
  twitterTitle: () => pageTitle.value,
  twitterDescription: () => pageDesc.value,
  twitterImage: () => `https://${config.public.canonicalHost}/og.png`,
});
useHead({
  link: [{ rel: 'canonical', href: () => canonical.value }],
  script: [{
    type: 'application/ld+json',
    children: () => JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: brand.value?.name || 'PriceMatters',
      url: canonical.value,
      potentialAction: {
        '@type': 'SearchAction',
        target: `${canonical.value}?q={query}`,
        'query-input': 'required name=query',
      },
    }),
  }],
});
</script>

<style>
:root { --green: #12813c; --green-d: #0d6a30; --ink: #1a2e1f; --mut: #55655a; --bg: #f6faf7; --card: #fff; --line: #e3ece4; --input-line: #d5e2d7; color-scheme: light; }
[data-theme="dark"] { --ink: #e9f1ea; --mut: #a9bbad; --bg: #0d140f; --card: #141d17; --line: #26332b; --input-line: #31402f; color-scheme: dark; }
[data-theme="dark"] .unitprice, [data-theme="dark"] .popular button { color: #4ade80; }
[data-theme="dark"] .demo { background: #453304; color: #fcd34d; }
[data-theme="dark"] .store { background: #223028; }
* { box-sizing: border-box; }
body { margin: 0; }
html { scrollbar-gutter: stable; }
:focus-visible { outline: 3px solid var(--green); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}
.page { font-family: system-ui, -apple-system, sans-serif; color: var(--ink); background: var(--bg); min-height: 100vh; display: flex; flex-direction: column; }
.top { display: flex; justify-content: space-between; align-items: center; padding: 0.9rem 1.4rem; background: var(--card); border-bottom: 1px solid var(--line); }
.logo { display: flex; gap: 0.5rem; align-items: center; font-weight: 800; font-size: 1.15rem; color: var(--ink); text-decoration: none; }
.top-right { display: flex; align-items: center; gap: 0.5rem; }
.theme-btn { display: flex; align-items: center; justify-content: center; width: 2rem; height: 2rem; border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 8px; cursor: pointer; }
.theme-btn svg { width: 1.1rem; height: 1.1rem; }
.theme-btn:hover { border-color: var(--green); color: var(--green-d); }
.lang a { text-decoration: none; color: var(--ink); font-weight: 700; font-size: 0.85rem; padding: 0.25rem 0.5rem; border-radius: 6px; }
.lang a.active { background: var(--green); color: #fff; }
.logo-light { display: block; }
.logo-dark { display: none; }
[data-theme="dark"] .logo-light { display: none; }
[data-theme="dark"] .logo-dark { display: block; }
.hero h1 u { text-decoration: underline; text-decoration-color: var(--green); text-decoration-thickness: 0.09em; text-underline-offset: 0.12em; }
.layout { display: flex; justify-content: center; gap: 1.5rem; align-items: flex-start; flex: 1; width: 100%; }
.layout main { flex: 1; width: 100%; max-width: 860px; margin: 0 auto; padding: 0 1rem 3rem; min-width: 0; }
.rail { width: 170px; min-width: 170px; position: sticky; top: 50vh; transform: translateY(-50%); align-self: flex-start; display: flex; }
.rail .ad { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.35rem; }
.ad { border: none; border-radius: 12px; padding: 0.9rem; background: transparent; color: var(--mut); font-size: 0.85rem; text-align: center; opacity: 0.85; transition: opacity 0.2s; }
.ad:hover { opacity: 1; }
.ad-label { display: inline-block; font-size: 0.65rem; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; border: 1px solid var(--line); border-radius: 6px; padding: 0.1rem 0.4rem; margin-bottom: 0.5rem; }
.ad a { color: var(--green-d); font-weight: 700; }
.ad.infeed { margin-bottom: 0.8rem; }
.linklike { background: none; border: none; padding: 0; color: var(--green-d); font: inherit; font-weight: 700; cursor: pointer; text-decoration: underline; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 1rem; }
.modal { position: relative; background: var(--card); color: var(--ink); border: 1px solid var(--line); border-radius: 16px; padding: 1.6rem; width: 100%; max-width: 520px; max-height: 90vh; overflow: auto; }
.modal h2 { margin-top: 0; text-align: center; }
.modal > p { text-align: center; }
.modal-x { position: absolute; top: 0.7rem; right: 0.9rem; background: none; border: none; font-size: 1.1rem; cursor: pointer; color: var(--mut); }
.ad-form { display: flex; flex-direction: column; gap: 0.7rem; max-width: 520px; margin: 0 auto; }
.ad-form .row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; }
.ad-form label { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.9rem; font-weight: 600; }
.ad-form input, .ad-form select, .ad-form textarea { padding: 0.6rem 0.8rem; border: 2px solid var(--input-line); border-radius: 10px; background: var(--card); color: var(--ink); font: inherit; }
.ad-form button { padding: 0.7rem; font-weight: 700; background: var(--green); color: #fff; border: none; border-radius: 10px; cursor: pointer; }
.ad-form button:hover { background: var(--green-d); }
.done { text-align: center; color: var(--green-d); font-weight: 700; }
.error { text-align: center; color: #dc2626; }
.small { font-size: 0.78rem; }
@media (max-width: 1250px) { .rail { display: none; } }
.hero { text-align: center; padding: 3rem 0 1.5rem; }
.eyebrow { text-transform: uppercase; letter-spacing: 0.18em; font-size: 0.8rem; font-weight: 800; color: var(--green-d); margin: 0 0 0.6rem; }
.hero h1 { font-size: 2.4rem; margin: 0 auto 1.4rem; letter-spacing: -0.02em; max-width: 640px; height: 2.5em; display: flex; align-items: center; justify-content: center; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.4s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.search { display: flex; gap: 0.5rem; max-width: 640px; margin: 0 auto; }
.search input { flex: 1; padding: 0.85rem 1rem; font-size: 1.05rem; border: 2px solid var(--input-line); border-radius: 12px; background: var(--card); color: var(--ink); }
.search input:focus { outline: none; border-color: var(--green); }
.search select, .controls select { padding: 0.85rem 0.6rem; border: 2px solid var(--input-line); border-radius: 12px; background: var(--card); color: var(--ink); }
.search button { display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.85rem 1.6rem; min-width: 9.5rem; font-size: 1.05rem; font-weight: 700; background: var(--green); color: #fff; border: none; border-radius: 12px; cursor: pointer; transition: background 0.15s; }
.search button:hover:not(:disabled) { background: var(--green-d); }
.search button:disabled { opacity: 0.75; cursor: wait; }
.spin { width: 1.1rem; height: 1.1rem; animation: rot 0.7s linear infinite; }
@keyframes rot { to { transform: rotate(1turn); } }
.skel { pointer-events: none; }
.skel-thumb { background: linear-gradient(90deg, var(--line) 25%, var(--bg) 50%, var(--line) 75%); background-size: 200% 100%; animation: shine 1.2s infinite; }
.skel-bar { border-radius: 6px; background: linear-gradient(90deg, var(--line) 25%, var(--bg) 50%, var(--line) 75%); background-size: 200% 100%; animation: shine 1.2s infinite; }
.skel .skel-bar { height: 0.9rem; }
@keyframes shine { to { background-position: -200% 0; } }
.error.banner { background: #fef3c7; color: #92400e; font-weight: 600; padding: 0.7rem 1rem; border-radius: 12px; text-align: center; }
[data-theme="dark"] .error.banner { background: #453304; color: #fcd34d; }
.popular { color: var(--mut); font-size: 0.9rem; }
.popular button { background: var(--card); border: 1px solid var(--line); border-radius: 20px; padding: 0.2rem 0.8rem; margin: 0.15rem; cursor: pointer; color: var(--green-d); }
.popular button:hover { border-color: var(--green); }
.meta-row { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; color: var(--mut); font-size: 0.9rem; margin: 1rem 0; min-height: 1.8em; }
.demo { background: #fef3c7; color: #92400e; padding: 0.3rem 0.7rem; border-radius: 8px; font-weight: 600; }
.controls { display: flex; gap: 1rem; flex-wrap: wrap; align-items: center; background: var(--card); padding: 0.8rem 1rem; border-radius: 12px; border: 1px solid var(--line); margin-bottom: 1rem; font-size: 0.92rem; }
.controls label { display: flex; gap: 0.4rem; align-items: center; }
.controls select { padding: 0.4rem 0.5rem; border-radius: 8px; }
.controls input[type="number"] { width: 6rem; padding: 0.4rem 0.5rem; border: 2px solid var(--input-line); border-radius: 8px; background: var(--card); color: var(--ink); }
.controls .check { display: flex; gap: 0.35rem; align-items: center; cursor: pointer; }
.filters-wrap { background: var(--card); border: 1px solid var(--line); border-radius: 12px; margin-bottom: 1rem; font-size: 0.92rem; }
.filters-wrap summary { cursor: pointer; padding: 0.7rem 1rem; font-weight: 700; color: var(--mut); list-style-position: inside; }
.filters-wrap .controls { border: none; margin-bottom: 0; }
.card-main { display: flex; gap: 1rem; align-items: flex-start; }
.thumb { width: 84px; height: 84px; min-width: 84px; object-fit: contain; border-radius: 10px; background: #fff; border: 1px solid var(--line); }
.card:not(.skel) .thumb { content-visibility: auto; }
.thumb.placeholder { display: flex; align-items: center; justify-content: center; background: var(--bg); }
.card-body { flex: 1; min-width: 0; }
.stores button { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 20px; padding: 0.25rem 0.8rem; margin: 0.1rem; cursor: pointer; }
.stores button.active { background: var(--ink); color: #fff; border-color: var(--ink); }
.pager { display: flex; gap: 0.8rem; align-items: center; justify-content: center; margin: 1.2rem 0; color: var(--mut); font-size: 0.92rem; }
.pager button { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 9px; padding: 0.35rem 0.9rem; font-size: 1rem; cursor: pointer; }
.pager button:disabled { opacity: 0.35; cursor: default; }
.pager label { display: flex; gap: 0.4rem; align-items: center; }
.pager select { padding: 0.35rem 0.5rem; border-radius: 8px; border: 2px solid var(--input-line); background: var(--card); color: var(--ink); }
.zone, .also { font-size: 0.85rem; }
.ship { background: #fef3c7; color: #92400e; padding: 0.3rem 0.7rem; border-radius: 8px; font-weight: 600; font-size: 0.85rem; }
[data-theme="dark"] .ship { background: #453304; color: #fcd34d; }
.segmented { display: inline-flex; background: var(--bg); border: 1px solid var(--line); border-radius: 12px; padding: 3px; gap: 2px; }
.segmented button { border: none; background: transparent; color: var(--mut); font: inherit; font-size: 0.9rem; font-weight: 700; padding: 0.45rem 1rem; border-radius: 9px; cursor: pointer; }
.segmented button.active { background: var(--card); color: var(--ink); box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
.empty { text-align: center; color: var(--mut); padding: 2rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 1.1rem 1.2rem; margin-bottom: 0.8rem; }
.card.best { border: 2px solid var(--green); }
.card-top { display: flex; gap: 0.5rem; margin-bottom: 0.4rem; }
.best-badge { background: var(--green); color: #fff; font-size: 0.75rem; font-weight: 800; padding: 0.2rem 0.6rem; border-radius: 20px; text-transform: uppercase; }
.store { background: #eef4ee; color: var(--mut); font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 20px; }
.card h2 { margin: 0.2rem 0 0.6rem; font-size: 1.05rem; font-weight: 600; }
.numbers { display: flex; gap: 1.2rem; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.8rem; }
.price { color: var(--mut); }
.qty { color: var(--mut); font-size: 0.9rem; }
.fave-unit { font-weight: 600; color: var(--ink); display: inline-block; min-width: 5.5rem; }
.unitprice { font-size: 1.25rem; font-weight: 800; color: var(--green-d); }
.cta { display: inline-block; background: var(--green); color: #fff; font-weight: 700; text-decoration: none; padding: 0.6rem 1.4rem; border-radius: 10px; }
.cta:hover { background: var(--green-d); }
.card-actions { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; }
.card-body > .numbers { contain: inline-size; }
.paid { color: var(--mut); font-size: 0.75rem; margin-left: auto; }
.marketing { text-align: center; padding: 1rem 0; }
.mut { color: var(--mut); }
.steps, .trust { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1.5rem 0; }
.steps div, .trust div { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 1rem; }
.steps p, .trust p { color: var(--mut); font-size: 0.92rem; }
footer { text-align: center; padding: 1.5rem 1rem 2rem; color: var(--mut); font-size: 0.85rem; border-top: 1px solid var(--line); background: var(--card); }
.dark-hint { position: fixed; bottom: 1rem; left: 50%; transform: translateX(-50%); z-index: 40; background: #0d140f; color: #e9f1ea; border-radius: 12px; padding: 0.8rem 1.1rem; max-width: 430px; width: calc(100% - 2rem); font-size: 0.88rem; box-shadow: 0 6px 24px rgba(0,0,0,0.35); }
.dark-hint p { margin: 0 0 0.4rem; }
.dark-hint .linklike { color: inherit; }
.disclosure { max-width: 640px; margin: 0 auto 0.5rem; }
@media (max-width: 600px) { .hero h1 { font-size: 1.9rem; height: 3.6em; } .search { flex-direction: column; } }
</style>
