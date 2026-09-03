<template>
  <div class="adm">
    <header class="top">
      <NuxtLink :to="localePath('/')" class="logo">
        <img src="/logo.svg" alt="logo" width="28" height="28" />
        <span>{{ brandName }}</span>
      </NuxtLink>
    </header>

    <main>
      <section v-if="!unlocked" class="gate">
        <form @submit.prevent="unlock">
          <input v-model="key" type="password" placeholder="Admin Key" autofocus autocomplete="off" />
          <button type="submit">Open</button>
        </form>
        <p v-if="wrong" class="err">Wrong key.</p>
      </section>

      <template v-else>
        <div class="krow">
          <div v-for="k in kpis" :key="k.label" class="kpi">
            <span class="kv">{{ k.value }}</span>
            <span class="kl">{{ k.label }}</span>
          </div>
        </div>

        <section v-if="data?.daily?.length" class="panel">
          <h2>Searches &amp; clicks per day (last {{ data.daily.length }}d)</h2>
          <table>
            <thead><tr><th>Day</th><th>Searches</th><th>Clicks</th><th>Visitors</th></tr></thead>
            <tbody>
              <tr v-for="d in data.daily" :key="d[0]">
                <td>{{ d[0] }}</td><td>{{ d[1] }}</td><td>{{ d[2] }}</td><td>{{ d[3] }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <div class="cols">
          <section class="panel">
            <h2>Top queries</h2>
            <table>
              <tbody>
                <tr v-for="r in data?.topQueries || []" :key="r[0]">
                  <td>{{ r[0] }}</td><td class="num">{{ r[1] }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section class="panel">
            <h2>Top clicked products</h2>
            <table>
              <tbody>
                <tr v-for="r in data?.topClicks || []" :key="r[1]">
                  <td class="tt">{{ r[0] }} <span class="mut small">· {{ r[2] }}</span></td>
                  <td class="num">{{ r[3] }}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <div class="cols">
          <section class="panel">
            <h2>CTR by query</h2>
            <table>
              <tbody>
                <tr v-for="r in data?.ctrByQuery || []" :key="r[0]">
                  <td>{{ r[0] }}</td><td class="num">{{ r[1] }}s → {{ r[2] }}c</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section class="panel">
            <h2>Zero-result queries</h2>
            <table>
              <tbody>
                <tr v-for="r in data?.zeroResults || []" :key="r[0]">
                  <td>{{ r[0] }}</td><td class="num">{{ r[1] }}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <div class="cols">
          <section v-for="(rows, name) in breakdowns" :key="name" class="panel">
            <h2>{{ name }}</h2>
            <table>
              <tbody>
                <tr v-for="r in rows" :key="r[0]">
                  <td class="tt">{{ r[0] }}</td>
                  <td class="num">{{ r[1] }} · {{ r[2] }}v</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <div class="cols">
          <section class="panel">
            <h2>Referrers</h2>
            <table>
              <tbody>
                <tr v-for="r in data?.refs || []" :key="r[0]">
                  <td class="tt">{{ r[0] }}</td><td class="num">{{ r[1] }} · {{ r[2] }}v</td>
                </tr>
              </tbody>
            </table>
          </section>
          <section class="panel">
            <h2>Avg latency</h2>
            <table>
              <tbody>
                <tr v-for="r in data?.avgMs || []" :key="r[0]">
                  <td>{{ r[0] }}</td><td class="num">{{ r[1] }} ms</td>
                </tr>
              </tbody>
            </table>
          </section>
          <section class="panel">
            <h2>Ad inquiries</h2>
            <table>
              <tbody>
                <tr v-for="r in data?.adInquiries || []" :key="r[1]">
                  <td class="tt">{{ r[0] }} <span class="mut small">&lt;{{ r[1] }}&gt; · {{ r[2] }}</span></td>
                  <td class="num">{{ r[3] }}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <p class="mut small foot">
          Privacy: no cookies, no raw IPs — daily-rotated salted hashes only, aggregates for Websters e.U.
          <button class="linklike" @click="reload">refresh</button>
          <button class="linklike" @click="lock">lock</button>
        </p>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
useSeoMeta({ title: 'PriceMatters', robots: 'noindex, nofollow' });

const appConfig = useAppConfig() as any;
const host = useRequestURL().host;
const brandName = computed(() => {
  const brands = appConfig.brands as Record<string, any>;
  const aliases = (appConfig.aliases as Record<string, string>) || {};
  return brands[aliases[host] || host]?.name || brands.default?.name || 'PriceMatters';
});
const localePath = useLocalePath();

const key = ref('');
const unlocked = ref(false);
const wrong = ref(false);
const data = ref<any>(null);

const kpis = computed(() => {
  const d = data.value;
  if (!d) return [];
  const tot = Object.fromEntries((d.totals || []).map((r: any[]) => [r[0], Number(r[1])]));
  const searches = tot.search || 0;
  const clicks = tot.click || 0;
  const views = tot.view || 0;
  const todayVisitors = d.visitors?.[0]?.[1] ?? 0;
  const ctr = searches ? ((clicks / searches) * 100).toFixed(1) + '%' : '–';
  return [
    { label: 'searches (30d)', value: searches },
    { label: 'clicks (30d)', value: clicks },
    { label: 'CTR', value: ctr },
    { label: 'page views', value: views },
    { label: 'visitors today', value: todayVisitors },
    { label: 'ad inquiries', value: d.adInquiries?.length || 0 },
  ];
});

const breakdowns = computed(() => {
  const d = data.value;
  if (!d) return {};
  const pretty: Record<string, string> = {
    markets: 'Marketplaces', langs: 'Browser languages', tzs: 'Timezones',
    devices: 'Devices', widths: 'Screen widths', refs: 'Referrers',
  };
  const out: Record<string, any[]> = {};
  for (const [k, label] of Object.entries(pretty)) {
    if (d[k]?.length) out[label] = d[k];
  }
  return out;
});

async function load() {
  try {
    data.value = await $fetch('/api/admin/stats', {
      query: { days: 30 },
      headers: { 'x-admin-key': key.value },
    }) as any;
    if (data.value?.error === 'unauthorized') { wrong.value = true; unlocked.value = false; return; }
    unlocked.value = true;
    wrong.value = false;
    try { sessionStorage.setItem('pm_admin_key', key.value); } catch { /* private mode */ }
  } catch (e: any) {
    if (e?.status === 401 || e?.response?.status === 401) {
      wrong.value = true;
      unlocked.value = false;
      return;
    }
    data.value = { error: 'backend not reachable' };
    unlocked.value = true;
  }
}
function unlock() { if (key.value.trim()) load(); }
function reload() { load(); }
function lock() {
  key.value = '';
  data.value = null;
  unlocked.value = false;
  try { sessionStorage.removeItem('pm_admin_key'); } catch { /* ignore */ }
}
onMounted(() => {
  try {
    const saved = sessionStorage.getItem('pm_admin_key');
    if (saved) { key.value = saved; load(); }
  } catch { /* ignore */ }
});
</script>

<style>
.adm { font-family: system-ui, -apple-system, sans-serif; color: #1a2e1f; background: #f6faf7; min-height: 100vh; }
.adm .top { display: flex; align-items: center; padding: 0.9rem 1.4rem; background: #fff; border-bottom: 1px solid #e3ece4; }
.adm .logo { display: flex; gap: 0.5rem; align-items: center; font-weight: 800; color: inherit; text-decoration: none; }
.adm main { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
.adm .gate { text-align: center; padding: 3rem 0; }
.adm .gate form { display: flex; gap: 0.5rem; justify-content: center; margin-top: 1rem; }
.adm .gate input { padding: 0.7rem 1rem; border: 2px solid #d5e2d7; border-radius: 10px; font-size: 1rem; }
.adm .gate button { padding: 0.7rem 1.4rem; font-weight: 700; background: #12813c; color: #fff; border: none; border-radius: 10px; cursor: pointer; }
.adm .err { color: #dc2626; margin-top: 0.7rem; }
.adm .krow { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.8rem; margin-bottom: 1.4rem; }
.adm .kpi { background: #fff; border: 1px solid #e3ece4; border-radius: 12px; padding: 1rem; text-align: center; }
.adm .kv { display: block; font-size: 1.7rem; font-weight: 800; color: #12813c; font-variant-numeric: tabular-nums; }
.adm .kl { color: #55655a; font-size: 0.85rem; }
.adm .panel { background: #fff; border: 1px solid #e3ece4; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; min-width: 0; }
.adm .panel h2 { margin: 0 0 0.6rem; font-size: 1rem; }
.adm .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 0.8rem; }
.adm table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.adm td, .adm th { padding: 0.35rem 0.4rem; border-bottom: 1px solid #eef3ee; text-align: left; vertical-align: top; }
.adm .num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; color: #55655a; }
.adm .tt { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.adm .mut { color: #55655a; }
.adm .small { font-size: 0.8rem; }
.adm .linklike { background: none; border: none; color: #12813c; font: inherit; font-weight: 700; cursor: pointer; text-decoration: underline; margin-left: 0.6rem; }
.adm .foot { margin-top: 2rem; }
.adm [data-theme] { color-scheme: light; }
</style>
