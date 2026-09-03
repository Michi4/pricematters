<template>
  <main style="max-width: 900px; margin: 2rem auto; padding: 0 1rem; font-family: system-ui, sans-serif">
    <h1>{{ brand.name }}</h1>
    <p>{{ locale.startsWith('de') ? brand.sloganDE : brand.sloganEN }}</p>
    <form @submit.prevent="search">
      <input v-model="q" placeholder="Reis, Kaffee, organic protein, variable Sattelstütze …" style="width: 70%; padding: 0.6rem" />
      <button type="submit" style="padding: 0.6rem 1rem">Calculate!</button>
    </form>
    <p v-if="pending">Loading…</p>
    <table v-if="results.length" border="1" cellpadding="8" style="margin-top: 1rem; border-collapse: collapse; width: 100%">
      <thead>
        <tr><th>Product</th><th>Store</th><th>Price</th><th>Qty</th><th>Unit price</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="r in results" :key="r.asin">
          <td>{{ r.title }}</td>
          <td>{{ r.store || 'Amazon' }}</td>
          <td>{{ (r.priceCents / 100).toFixed(2) }} €</td>
          <td>{{ r.qty ? `${r.qty.value.toFixed(2)} ${r.qty.unit}` : '–' }}</td>
          <td><strong v-if="r.unitPrice">{{ (r.unitPrice.per / 100).toFixed(2) }} € / {{ r.unitPrice.base }}</strong><span v-else>–</span></td>
          <td><a :href="r.url" target="_blank" rel="nofollow sponsored noopener">Amazon</a></td>
        </tr>
      </tbody>
    </table>
  </main>
</template>

<script setup lang="ts">
const appConfig = useAppConfig() as any;
const config = useRuntimeConfig();
const locale = config.public.defaultLocale as string;
const host = useRequestURL().host;
const brand = computed(() => {
  const brands = appConfig.brands as Record<string, any>;
  const aliases = (appConfig.aliases as Record<string, string>) || {};
  const key = aliases[host] || host;
  return brands[key] || brands.default;
});
const q = ref('');
const results = ref<any[]>([]);
const pending = ref(false);
// SEO: SSR-rendered per-brand tags (useRequestURL works on server + client)
// Canonical + og:url always point at the MAIN domain (alias domains stay
// usable for campaigns but don't split SEO juice / duplicate content).
const url = useRequestURL();
const canonical = computed(() => `https://${config.public.canonicalHost}${url.pathname}`);
const pageTitle = computed(() => `${brand.value?.name || 'PriceMatters'} – Grundpreise vergleichen (€/kg, €/l, €/Stück)`);
const pageDesc = computed(() => locale.startsWith('de') ? brand.value?.sloganDE : brand.value?.sloganEN);
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
async function search() {
  if (!q.value.trim()) return;
  pending.value = true;
  try {
    const data = await $fetch('/api/search', { query: { q: q.value } });
    results.value = (data as any).items || [];
  } finally {
    pending.value = false;
  }
}
</script>
