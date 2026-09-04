<template>
  <div class="adm" :class="{ dark: isDark }">
    <header class="top">
      <NuxtLink :to="localePath('/')" class="logo">
        <img src="/logo.svg" alt="logo" width="28" height="28" />
        <span>{{ brandName }}</span>
      </NuxtLink>
      <span class="hint" v-if="unlocked">last refresh {{ lastRefresh }}</span>
      <button v-if="unlocked" class="linklike" @click="reload">↻ refresh</button>
      <button v-if="unlocked" class="linklike" @click="lock">lock</button>
    </header>

    <main>
      <section v-if="!unlocked" class="gate">
        <h1>{{ brandName }} · Admin</h1>
        <form @submit.prevent="unlock">
          <input v-model="key" type="password" placeholder="Admin Key" autofocus autocomplete="off" />
          <button type="submit">Open</button>
        </form>
        <p v-if="wrong" class="err">Wrong key.</p>
      </section>

      <template v-else-if="data && !data.error">
        <div class="krow">
          <div v-for="k in kpis" :key="k.label" class="kpi">
            <span class="kv">{{ k.value }}</span>
            <span class="kl">{{ k.label }}</span>
          </div>
        </div>

        <section v-if="data.daily?.length" class="panel">
          <h2>Searches &amp; clicks per day <span class="mut small">({{ data.daily.length }}d, newest first)</span></h2>
          <table>
            <thead><tr><th>Day</th><th class="num">Searches</th><th class="num">Clicks</th><th class="num">Visitors</th></tr></thead>
            <tbody>
              <tr v-for="d in data.daily" :key="d[0]">
                <td>{{ d[0] }}</td><td class="num">{{ d[1] }}</td><td class="num">{{ d[2] }}</td><td class="num">{{ d[3] }}</td>
              </tr>
            </tbody>
        </table>
        </section>

        <div class="cols">
          <section class="panel">
            <h2>Top queries</h2>
            <table>
              <tbody>
                <tr v-for="r in data.topQueries || []" :key="r[0]">
                  <td>{{ r[0] }}</td><td class="num">{{ r[1] }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section class="panel">
            <h2>Top clicked products</h2>
            <table>
              <tbody>
                <tr v-for="r in data.topClicks || []" :key="r[1]">
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
                <tr v-for="r in data.ctrByQuery || []" :key="r[0]">
                  <td>{{ r[0] }}</td><td class="num">{{ r[1] }}s → {{ r[2] }}c</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section class="panel">
            <h2>Zero-result queries</h2>
            <table>
              <tbody>
                <tr v-for="r in data.zeroResults || []" :key="r[0]">
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
                <tr v-for="r in data.refs || []" :key="r[0]">
                  <td class="tt">{{ r[0] }}</td><td class="num">{{ r[1] }} · {{ r[2] }}v</td>
                </tr>
              </tbody>
            </table>
          </section>
          <section class="panel">
            <h2>Avg latency</h2>
            <table>
              <tbody>
                <tr v-for="r in data.avgMs || []" :key="r[0]">
                  <td>{{ r[0] }}</td><td class="num">{{ r[1] }} ms</td>
                </tr>
              </tbody>
            </table>
          </section>
          <section class="panel">
            <h2>System</h2>
            <table class="sys">
              <tbody>
                <tr><td>Mail (SMTP)</td><td class="num"><span class="dot" :class="data.system?.smtp ? 'ok' : 'bad'"></span>{{ data.system?.smtp ? `on → ${data.system.smtpTo}` : 'off (DB only)' }}</td></tr>
                <tr><td>Search pages</td><td class="num">{{ data.system?.pages ?? 2 }} / search</td></tr>
                <tr><td>Provider</td><td class="num">{{ data.system?.providerDefault || 'auto-chain' }}</td></tr>
                <tr><td>Backend</td><td class="num"><span class="dot ok"></span>reachable</td></tr>
              </tbody>
            </table>
          </section>
        </div>

        <section class="panel">
          <h2>Ad inquiries <span class="mut small">(newest first, click to expand)</span></h2>
          <p v-if="!data.adInquiries?.length" class="mut small">No inquiries yet.</p>
          <div v-for="(inq, ix) in data.adInquiries || []" :key="ix" class="inq" :class="{ open: openInq === ix }" @click="openInq = openInq === ix ? -1 : ix">
            <div class="inq-row">
              <strong>{{ inq[0] }}</strong>
              <span class="mut">&lt;{{ inq[1] }}&gt;</span>
              <span class="mut small">{{ inq[2] || 'general' }} · {{ inq[4] }}</span>
            </div>
            <p v-if="openInq === ix" class="inq-msg">{{ inq[3] }}</p>
          </div>
        </section>

        <p class="mut small foot">
          Privacy: no cookies, no raw IPs — daily-rotated salted hashes only, aggregates for Websters e.U.
        </p>
      </template>

      <section v-else-if="data?.error" class="gate">
        <p class="err">{{ data.error }}</p>
        <button class="linklike" @click="reload">retry</button>
        <button class="linklike" @click="lock">lock</button>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
useSeoMeta({ title: 'PriceMatters · Admin', robots: 'noindex, nofollow' });

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
const lastRefresh = ref('');
const openInq = ref(-1);

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
    lastRefresh.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
.adm.dark { color: #dbe7dd; background: #0d140f; }
.adm .top { display: flex; align-items: center; gap: 0.9rem; padding: 0.9rem 1.4rem; background: #fff; border-bottom: 1px solid #e3ece4; }
.adm.dark .top { background: #121a14; border-bottom-color: #1f2b22; }
.adm .top .hint { margin-left: auto; }
.adm .logo { display: flex; gap: 0.5rem; align-items: center; font-weight: 800; color: inherit; text-decoration: none; }
.adm main { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
.adm .gate { text-align: center; padding: 3rem 0; }
.adm .gate h1 { font-size: 1.3rem; }
.adm .gate form { display: flex; gap: 0.5rem; justify-content: center; margin-top: 1rem; }
.adm .gate input { padding: 0.7rem 1rem; border: 2px solid #d5e2d7; border-radius: 10px; font-size: 1rem; background: #fff; color: inherit; }
.adm.dark .gate input { background: #121a14; border-color: #2a3b2f; }
.adm .gate button { padding: 0.7rem 1.4rem; font-weight: 700; background: #12813c; color: #fff; border: none; border-radius: 10px; cursor: pointer; }
.adm .err { color: #dc2626; margin-top: 0.7rem; }
.adm.dark .err { color: #f87171; }
.adm .krow { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.8rem; margin-bottom: 1.4rem; }
.adm .kpi { background: #fff; border: 1px solid #e3ece4; border-radius: 12px; padding: 1rem; text-align: center; }
.adm.dark .kpi { background: #121a14; border-color: #1f2b22; }
.adm .kv { display: block; font-size: 1.7rem; font-weight: 800; color: #12813c; font-variant-numeric: tabular-nums; }
.adm.dark .kv { color: #4ade80; }
.adm .kl { color: #55655a; font-size: 0.85rem; }
.adm.dark .kl { color: #8fa897; }
.adm .panel { background: #fff; border: 1px solid #e3ece4; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; min-width: 0; }
.adm.dark .panel { background: #121a14; border-color: #1f2b22; }
.adm .panel h2 { margin: 0 0 0.6rem; font-size: 1rem; }
.adm .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 0.8rem; }
.adm table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.adm td, .adm th { padding: 0.35rem 0.4rem; border-bottom: 1px solid #eef3ee; text-align: left; vertical-align: top; }
.adm.dark td, .adm.dark th { border-bottom-color: #1f2b22; }
.adm .num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; color: #55655a; }
.adm.dark .num { color: #8fa897; }
.adm .tt { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.adm .mut { color: #55655a; }
.adm.dark .mut { color: #8fa897; }
.adm .small { font-size: 0.8rem; }
.adm .linklike { background: none; border: none; color: #12813c; font: inherit; font-weight: 700; cursor: pointer; text-decoration: underline; }
.adm.dark .linklike { color: #4ade80; }
.adm .foot { margin-top: 2rem; }
.adm .dot { display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; margin-right: 0.4rem; }
.adm .dot.ok { background: #22c55e; }
.adm .dot.bad { background: #dc2626; }
.adm .inq { border: 1px solid #eef3ee; border-radius: 10px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; cursor: pointer; transition: border-color 0.12s; }
.adm.dark .inq { border-color: #1f2b22; }
.adm .inq:hover { border-color: #12813c; }
.adm .inq-row { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: baseline; }
.adm .inq-row .mut.small { margin-left: auto; }
.adm .inq-msg { margin: 0.6rem 0 0; white-space: pre-wrap; overflow-wrap: anywhere; background: #f6faf7; border-radius: 8px; padding: 0.6rem; font-size: 0.9rem; }
.adm.dark .inq-msg { background: #0d140f; }
</style>
