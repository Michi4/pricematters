<template>
  <div class="page">
    <header class="top">
      <NuxtLink :to="localePath('/')" class="logo">
        <img src="/logo.svg" alt="logo" width="28" height="28" />
        <span>{{ brand.name }}</span>
      </NuxtLink>
      <nav class="lang">
        <NuxtLink
          v-for="l in (locales as any[])"
          :key="l.code"
          :to="switchLocalePath(l.code)"
          :class="{ active: locale === l.code }"
        >{{ l.code.toUpperCase() }}</NuxtLink>
      </nav>
    </header>

    <main>
      <section class="hero">
        <h1>{{ t('hero.headline') }}</h1>
        <Transition name="fade" mode="out-in">
          <p class="slogan" :key="sloganIdx">{{ slogans[sloganIdx] }}</p>
        </Transition>
        <form class="search" @submit.prevent="search">
          <input v-model="q" :placeholder="t('hero.searchPlaceholder')" autofocus />
          <select v-model="marketplace" :title="t('hero.marketplace')">
            <option value="de">{{ t('hero.markets.de') }}</option>
            <option value="at">{{ t('hero.markets.at') }}</option>
            <option value="com">{{ t('hero.markets.com') }}</option>
            <option value="co.uk">{{ t('hero.markets.couk') }}</option>
            <option value="fr">{{ t('hero.markets.fr') }}</option>
          </select>
          <button type="submit">{{ pending ? t('hero.searching') : t('hero.searchButton') }}</button>
        </form>
        <p class="popular">{{ t('hero.popular') }}
          <button v-for="p in popular" :key="p" @click="q = p; search()">{{ p }}</button>
        </p>
      </section>

      <section v-if="searched" class="results">
        <div class="meta-row">
          <span>{{ t('results.count', { n: sorted.length }) }}</span>
          <span v-if="meta.demo" class="demo">{{ t('results.demo') }}</span>
          <span v-if="meta.queries?.length > 1" class="also">
            {{ t('results.alsoSearched') }} {{ meta.queries.slice(1).join(', ') }}
          </span>
        </div>

        <div v-if="sorted.length" class="controls">
          <label>{{ t('results.sort.label') }}
            <select v-model="sortKey">
              <option value="unit">{{ t('results.sort.unit') }}</option>
              <option value="priceAsc">{{ t('results.sort.priceAsc') }}</option>
              <option value="priceDesc">{{ t('results.sort.priceDesc') }}</option>
              <option value="name">{{ t('results.sort.name') }}</option>
            </select>
          </label>
          <label>{{ t('results.unit.label') }}
            <select v-model="displayUnit">
              <option v-for="u in unitOptions" :key="u" :value="u">€ / {{ u }}</option>
            </select>
          </label>
          <div class="stores">
            <span>{{ t('results.store.label') }}:</span>
            <button :class="{ active: storeFilter === 'all' }" @click="storeFilter = 'all'">{{ t('results.store.all') }}</button>
            <button
              v-for="s in stores" :key="s"
              :class="{ active: storeFilter === s }" @click="storeFilter = s"
            >{{ s }}</button>
          </div>
        </div>

        <div v-if="sorted.length" class="controls filters">
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

        <p v-if="!sorted.length && !pending" class="empty">{{ t('results.empty') }}</p>

        <article v-for="(r, i) in sorted" :key="r.asin" class="card" :class="{ best: i === 0 && sortKey === 'unit' && shownUnit(r) }">
          <div class="card-top">
            <span v-if="i === 0 && sortKey === 'unit' && shownUnit(r)" class="best-badge">{{ t('results.best') }}</span>
            <span class="store">{{ r.store || 'Amazon' }}</span>
          </div>
          <h2>{{ r.title }}</h2>
          <div class="numbers">
            <span class="price">{{ money(r.priceCents) }}</span>
            <span v-if="r.qty" class="qty">{{ r.qty.value }} {{ r.qty.unit }}</span>
            <span v-if="shownUnit(r)" class="unitprice">
              {{ moneyBare(shownUnit(r)) }} {{ sym }} / {{ displayUnit }}
            </span>
          </div>
          <a :href="r.url" target="_blank" rel="nofollow sponsored noopener" class="cta">
            {{ r.store === 'Amazon' || !r.store ? t('results.atAmazon') : t('results.atShop') }}
          </a>
        </article>
      </section>

      <section v-if="!searched" class="marketing">
        <h2>{{ t('example.title') }}</h2>
        <p class="mut">{{ t('example.note') }}</p>
        <article v-for="e in examples" :key="e.t" class="card" :class="{ best: e.best }">
          <div class="card-top">
            <span v-if="e.best" class="best-badge">{{ t('results.best') }}</span>
            <span class="store">Amazon</span>
          </div>
          <h2>{{ e.t }}</h2>
          <div class="numbers">
            <span class="price">{{ money(e.price) }}</span>
            <span class="qty">{{ e.qty }}</span>
            <span class="unitprice">{{ moneyBare(e.per) }} {{ sym }} / {{ e.base }}</span>
          </div>
        </article>
        <h2>{{ t('how.title') }}</h2>
        <div class="steps">
          <div><strong>1 · {{ t('how.s1t') }}</strong><p>{{ t('how.s1d') }}</p></div>
          <div><strong>2 · {{ t('how.s2t') }}</strong><p>{{ t('how.s2d') }}</p></div>
          <div><strong>3 · {{ t('how.s3t') }}</strong><p>{{ t('how.s3d') }}</p></div>
        </div>
        <div class="trust">
          <div><strong>{{ t('trust.t1') }}</strong><p>{{ t('trust.d1') }}</p></div>
          <div><strong>{{ t('trust.t2') }}</strong><p>{{ t('trust.d2') }}</p></div>
          <div><strong>{{ t('trust.t3') }}</strong><p>{{ t('trust.d3') }}</p></div>
        </div>
      </section>
    </main>

    <footer>
      <p class="disclosure">{{ t('footer.disclosure') }}</p>
      <p>{{ t('footer.made') }} · {{ brand.name }}</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { convertPer, DISPLAY_TARGETS } from '../lib/units';

const appConfig = useAppConfig() as any;
const config = useRuntimeConfig();
const { t, tm, locale, locales } = useI18n();
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
const sloganIdx = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  timer = setInterval(() => { sloganIdx.value = (sloganIdx.value + 1) % Math.max(slogans.value.length, 1); }, 5000);
  if (route.query.q) { q.value = String(route.query.q); search(); }
});
onUnmounted(() => { if (timer) clearInterval(timer); });

const q = ref('');
const marketplace = ref('de');
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

const popular = computed(() => locale.value === 'de'
  ? ['Reis', 'Kaffee', 'Protein', 'Erdnussmus']
  : ['Rice', 'Coffee', 'Protein', 'Peanut butter']);
const examples = computed(() => tm('example.items') as any[]);

const CURRENCY: Record<string, string> = { de: '€', at: '€', fr: '€', com: '$', 'co.uk': '£' };
const sym = computed(() => CURRENCY[marketplace.value] || '€');
const money = (cents: number) => `${(cents / 100).toFixed(2)} ${sym.value}`;
const moneyBare = (cents: number) => (cents / 100).toFixed(2);

async function search() {
  if (!q.value.trim()) return;
  pending.value = true;
  try {
    await navigateTo({ query: { q: q.value } }, { replace: true });
    const data = await $fetch('/api/search', { query: { q: q.value, marketplace: marketplace.value } });
    results.value = (data as any).items || [];
    meta.value = (data as any).meta || {};
    searched.value = true;
    storeFilter.value = 'all';
    // sensible default display unit from result kinds
    const bases = new Set(results.value.map((r: any) => r.unitPrice?.base));
    displayUnit.value = bases.has('kg') ? 'kg' : bases.has('l') ? 'l' : bases.has('pcs') ? 'pcs' : 'kg';
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
    name: (a: any, b: any) => String(a.title).localeCompare(String(b.title)),
  }[sortKey.value] as (a: any, b: any) => number;
  return [...arr].sort(by);
});

// ---- SEO (SSR, per brand + locale) ----
const url = useRequestURL();
const canonical = computed(() => `https://${config.public.canonicalHost}${url.pathname}`);
const pageTitle = computed(() => locale.value === 'de'
  ? `${brand.value?.name} – Grundpreise vergleichen (€/kg, €/l, €/Stück)`
  : `${brand.value?.name} – Compare unit prices (€/kg, €/L, €/pc)`);
const pageDesc = computed(() => slogans.value[0] || '');
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
:root { --green: #16a34a; --green-d: #15803d; --ink: #1a2e1f; --mut: #5b6b5e; --bg: #f6faf7; --card: #fff; }
* { box-sizing: border-box; }
body { margin: 0; }
.page { font-family: system-ui, -apple-system, sans-serif; color: var(--ink); background: var(--bg); min-height: 100vh; display: flex; flex-direction: column; }
.top { display: flex; justify-content: space-between; align-items: center; padding: 0.9rem 1.4rem; background: var(--card); border-bottom: 1px solid #e3ece4; }
.logo { display: flex; gap: 0.5rem; align-items: center; font-weight: 800; font-size: 1.15rem; color: var(--ink); text-decoration: none; }
.lang { display: flex; gap: 0.25rem; }
.lang a { text-decoration: none; color: var(--mut); font-weight: 700; font-size: 0.85rem; padding: 0.25rem 0.5rem; border-radius: 6px; }
.lang a.active { background: var(--green); color: #fff; }
main { flex: 1; width: 100%; max-width: 860px; margin: 0 auto; padding: 0 1rem 3rem; }
.hero { text-align: center; padding: 3rem 0 1.5rem; }
.hero h1 { font-size: 2.6rem; margin: 0; letter-spacing: -0.02em; }
.slogan { font-size: 1.15rem; color: var(--mut); min-height: 2.8em; display: flex; align-items: center; justify-content: center; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.4s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.search { display: flex; gap: 0.5rem; max-width: 640px; margin: 0 auto; }
.search input { flex: 1; padding: 0.85rem 1rem; font-size: 1.05rem; border: 2px solid #d5e2d7; border-radius: 12px; }
.search input:focus { outline: none; border-color: var(--green); }
.search select, .controls select { padding: 0.85rem 0.6rem; border: 2px solid #d5e2d7; border-radius: 12px; background: #fff; }
.search button { padding: 0.85rem 1.6rem; font-size: 1.05rem; font-weight: 700; background: var(--green); color: #fff; border: none; border-radius: 12px; cursor: pointer; }
.search button:hover { background: var(--green-d); }
.popular { color: var(--mut); font-size: 0.9rem; }
.popular button { background: none; border: 1px solid #cfdccf; border-radius: 20px; padding: 0.2rem 0.8rem; margin: 0.15rem; cursor: pointer; color: var(--green-d); }
.meta-row { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; color: var(--mut); font-size: 0.9rem; margin: 1rem 0; }
.demo { background: #fef3c7; color: #92400e; padding: 0.3rem 0.7rem; border-radius: 8px; font-weight: 600; }
.controls { display: flex; gap: 1rem; flex-wrap: wrap; align-items: center; background: var(--card); padding: 0.8rem 1rem; border-radius: 12px; border: 1px solid #e3ece4; margin-bottom: 1rem; font-size: 0.92rem; }
.controls label { display: flex; gap: 0.4rem; align-items: center; }
.controls select { padding: 0.4rem 0.5rem; border-radius: 8px; }
.controls input[type="number"] { width: 6rem; padding: 0.4rem 0.5rem; border: 2px solid #d5e2d7; border-radius: 8px; }
.controls .check { display: flex; gap: 0.35rem; align-items: center; cursor: pointer; }
.filters { background: #f0f6f1; }
.stores button { border: 1px solid #cfdccf; background: #fff; border-radius: 20px; padding: 0.25rem 0.8rem; margin: 0.1rem; cursor: pointer; }
.stores button.active { background: var(--ink); color: #fff; border-color: var(--ink); }
.empty { text-align: center; color: var(--mut); padding: 2rem; }
.card { background: var(--card); border: 1px solid #e3ece4; border-radius: 14px; padding: 1.1rem 1.2rem; margin-bottom: 0.8rem; }
.card.best { border: 2px solid var(--green); }
.card-top { display: flex; gap: 0.5rem; margin-bottom: 0.4rem; }
.best-badge { background: var(--green); color: #fff; font-size: 0.75rem; font-weight: 800; padding: 0.2rem 0.6rem; border-radius: 20px; text-transform: uppercase; }
.store { background: #eef4ee; color: var(--mut); font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 20px; }
.card h2 { margin: 0.2rem 0 0.6rem; font-size: 1.05rem; font-weight: 600; }
.numbers { display: flex; gap: 1.2rem; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.8rem; }
.price { color: var(--mut); }
.qty { color: var(--mut); font-size: 0.9rem; }
.unitprice { font-size: 1.25rem; font-weight: 800; color: var(--green-d); }
.cta { display: inline-block; background: var(--green); color: #fff; font-weight: 700; text-decoration: none; padding: 0.6rem 1.4rem; border-radius: 10px; }
.cta:hover { background: var(--green-d); }
.marketing { text-align: center; padding: 1rem 0; }
.mut { color: var(--mut); }
.steps, .trust { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1.5rem 0; }
.steps div, .trust div { background: var(--card); border: 1px solid #e3ece4; border-radius: 12px; padding: 1rem; }
.steps p, .trust p { color: var(--mut); font-size: 0.92rem; }
footer { text-align: center; padding: 1.5rem 1rem 2rem; color: var(--mut); font-size: 0.85rem; border-top: 1px solid #e3ece4; background: var(--card); }
.disclosure { max-width: 640px; margin: 0 auto 0.5rem; }
@media (max-width: 600px) { .hero h1 { font-size: 2rem; } .search { flex-direction: column; } }
</style>
