<template>
  <div class="adm" :class="{ dark: dark }">
    <header class="top">
      <NuxtLink :to="localePath('/')" class="logo">
        <img src="/logo.svg" alt="logo" width="28" height="28" />
        <span>{{ brandName }}</span>
      </NuxtLink>
      <span v-if="unlocked && lastRefresh" class="hint mut small">upd {{ lastRefresh }}</span>
      <button class="iconbtn" :title="dark ? 'Light mode' : 'Dark mode'" @click="toggleTheme">{{ dark ? '☀' : '☾' }}</button>
      <button v-if="unlocked" class="iconbtn" title="Refresh" @click="reload">↻</button>
      <button v-if="unlocked" class="iconbtn" title="Lock" @click="lock">⏻</button>
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
        <div class="toolbar">
          <label class="mut small">Range
            <select v-model.number="days" @change="load">
              <option :value="1">24h</option>
              <option :value="7">7d</option>
              <option :value="30">30d</option>
              <option :value="90">90d</option>
              <option :value="365">1y</option>
              <option :value="3650">All-time</option>
            </select>
          </label>
          <label class="mut small">Chart
            <select v-model.number="hours" @change="load">
              <option :value="12">12h</option>
              <option :value="24">24h</option>
              <option :value="48">48h</option>
              <option :value="72">3d</option>
              <option :value="168">7d</option>
            </select>
          </label>
          <label class="mut small auto"><input v-model="auto" type="checkbox" /> auto 60s</label>
        </div>

        <div class="krow">
          <div v-for="k in kpis" :key="k.label" class="kpi">
            <span class="kv">{{ k.value }}</span>
            <span class="kl">{{ k.label }}</span>
          </div>
        </div>

        <section class="panel">
          <h2>Activity <span class="mut small">(searches dark / clicks light, per hour — click a bar to pin details)</span></h2>
          <div class="bars" :class="{ dense: hourly.length > 72 }">
            <div v-for="(h, i) in hourly" :key="h.h" class="bcol" :class="{ sel: sel === i }"
                 :title="`${fmtHour(h.h)} — ${h.s} searches, ${h.c} clicks`"
                 @click="sel = sel === i ? -1 : i">
              <div class="bar s" :style="{ height: barH(h.s) }"></div>
              <div class="bar c" :style="{ height: barH(h.c) }"></div>
            </div>
          </div>
          <div class="baxis mut small">
            <span v-for="tk in ticks" :key="tk">{{ tk }}</span>
          </div>
          <p v-if="selBar" class="barinfo">
            <b>{{ fmtHour(selBar.h) }}</b> — {{ selBar.s }} searches · {{ selBar.c }} clicks
            <button class="linklike" @click="sel = -1">×</button>
          </p>
          <p v-else class="barinfo mut small">hover a bar for a tooltip, click to pin</p>
        </section>

        <section v-if="data.daily?.length" class="panel">
          <h2>Per day <span class="mut small">(last {{ data.daily.length }}d, newest first)</span></h2>
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
            <h2>Top queries <input v-model="fq" class="tfilter" placeholder="filter…" /></h2>
            <table>
              <tbody>
                <tr v-for="r in fTopQueries" :key="r[0]">
                  <td class="tt">{{ r[0] }}</td><td class="num">{{ r[1] }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!fTopQueries.length" class="mut small">–</p>
          </section>

          <section class="panel">
            <h2>Top clicked products <input v-model="fcl" class="tfilter" placeholder="filter…" /></h2>
            <table>
              <tbody>
                <tr v-for="r in fTopClicks" :key="r[1]">
                  <td class="tt">{{ r[0] }} <span class="mut small">· {{ r[2] }}</span></td>
                  <td class="num">{{ r[3] }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!fTopClicks.length" class="mut small">–</p>
          </section>
        </div>

        <div class="cols">
          <section class="panel">
            <h2>CTR by query <input v-model="fctr" class="tfilter" placeholder="filter…" /></h2>
            <table>
              <tbody>
                <tr v-for="r in fCtr" :key="r[0]">
                  <td class="tt">{{ r[0] }}</td><td class="num">{{ r[1] }}s → {{ r[2] }}c <b class="ctrr">{{ r[1] ? Math.round((r[2] / r[1]) * 100) : 0 }}%</b></td>
                </tr>
              </tbody>
            </table>
            <p v-if="!fCtr.length" class="mut small">–</p>
          </section>

          <section class="panel">
            <h2>Zero-result queries</h2>
            <table>
              <tbody>
                <tr v-for="r in data.zeroResults || []" :key="r[0]">
                  <td class="tt">{{ r[0] }}</td><td class="num">{{ r[1] }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!(data.zeroResults || []).length" class="mut small">none 🎉</p>
          </section>
        </div>

        <div class="cols">
          <section v-for="(rows, name) in breakdowns" :key="name" class="panel">
            <h2>{{ name }}</h2>
            <table>
              <tbody>
                <tr v-for="r in rows" :key="r[0]">
                  <td class="tt">{{ nice(r[0]) }}</td>
                  <td class="num">{{ r[1] }} · {{ r[2] }}v</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <div class="cols">
          <section class="panel">
            <h2>Clicks by store</h2>
            <table>
              <tbody>
                <tr v-for="r in data.clickStores || []" :key="r[0]">
                  <td class="tt">{{ nice(r[0]) }}</td><td class="num">{{ r[1] }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!(data.clickStores || []).length" class="mut small">–</p>
          </section>
          <section class="panel">
            <h2>Referrers <input v-model="fref" class="tfilter" placeholder="filter…" /></h2>
            <table>
              <tbody>
                <tr v-for="r in fRefs" :key="r[0]">
                  <td class="tt">{{ nice(r[0]) }}</td><td class="num">{{ r[1] }} · {{ r[2] }}v</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!fRefs.length" class="mut small">–</p>
          </section>
          <section class="panel">
            <h2>Latency</h2>
            <table>
              <tbody>
                <tr v-for="r in data.avgMs || []" :key="r[0]">
                  <td class="tt">{{ nice(r[0]) }}</td>
                  <td class="num">ø {{ r[1] }} ms · p95 {{ r[2] }} ms</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <section class="panel">
          <h2>System</h2>
          <div class="sysgrid">
            <div><span class="dot" :class="data.system?.smtp ? 'ok' : 'bad'"></span>Mail: {{ data.system?.smtp ? `on → ${data.system.smtpTo}` : 'off (DB only)' }}</div>
            <div><span class="dot ok"></span>Backend: reachable</div>
            <div>Search pages: {{ data.system?.pages ?? 2 }}</div>
            <div v-if="avgRes">ø results/search: {{ avgRes }}</div>
            <div>Provider pinned: {{ data.system?.providerDefault || 'auto' }}</div>
            <div v-for="u in data.system?.serpapiUsage || []" :key="u.index" class="serpk">
              SerpApi key #{{ u.index }}: {{ u.used }}/{{ u.quota }}
              <span class="meter"><span class="fill" :class="{ warn: u.used / u.quota > 0.8, crit: u.used / u.quota > 0.95 }" :style="{ width: Math.min(100, (u.used / u.quota) * 100) + '%' }"></span></span>
            </div>
            <div class="chain">Fallback chain: <span v-for="(p, i) in chainList" :key="p + i" class="pill" :class="{ first: i === 0 }">{{ p }}</span></div>
          </div>
        </section>

        <section class="panel">
          <h2>Ad inquiries <input v-model="finq" class="tfilter" placeholder="filter…" /></h2>
          <p v-if="!(data.adInquiries || []).length" class="mut small">No inquiries yet.</p>
          <div v-for="(inq, ix) in fInq" :key="inq[0]" class="inq" @click="openInq = openInq === ix ? -1 : ix">
            <div class="inq-row">
              <strong>{{ inq[1] }}</strong>
              <span class="mut inq-mail">&lt;{{ inq[2] }}&gt;</span>
              <span class="mut small inq-meta">{{ inq[3] || 'general' }} · {{ fmtDate(inq[5]) }}</span>
              <button class="delbtn" :class="{ sure: delSure === inq[0] }" :title="delSure === inq[0] ? 'click again to confirm' : 'delete'"
                      @click.stop="askDelete(inq[0])">{{ delSure === inq[0] ? 'sure?' : '✕' }}</button>
            </div>
            <p v-if="openInq === ix" class="inq-msg">{{ inq[4] }}</p>
          </div>
          <p v-if="!(fInq || []).length" class="mut small">–</p>
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
      <section v-else class="gate"><p class="mut">loading…</p></section>
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
const days = ref(30);
const hours = ref(48);
const auto = ref(true);
const dark = ref(false);
const sel = ref(-1);
const delSure = ref<number | null>(null);
let delTimer: any = null;

const fq = ref(''); const fcl = ref(''); const fctr = ref(''); const fref = ref(''); const finq = ref('');

const hourly = computed(() =>
  (data.value?.hourly || []).map((r: any[]) => ({ h: String(r[0]), s: Number(r[1]), c: Number(r[2]) })));
const maxBar = computed(() => Math.max(1, ...hourly.value.map(h => Math.max(h.s, h.c))));
function barH(v: number) { return `${Math.round((v / maxBar.value) * 56) + (v > 0 ? 3 : 1)}px`; }
const selBar = computed(() => (sel.value >= 0 && sel.value < hourly.value.length) ? hourly.value[sel.value] : null);

const ticks = computed(() => {
  const n = hourly.value.length;
  if (n < 4) return [];
  const idxs = [0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1];
  return [...new Set(idxs)].map(i => fmtHour(hourly.value[i].h, true));
});

function fmtHour(s: string, short = false): string {
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  const opt: any = short
    ? { month: '2-digit', day: '2-digit', hour: '2-digit' }
    : { weekday: 'short', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' };
  return d.toLocaleString(undefined, opt);
}

const chainList = computed(() =>
  String(data.value?.system?.providerChain || '').split(',').map((s: string) => s.trim()).filter(Boolean));

const avgRes = computed(() => data.value?.avgResults?.[0]?.[0]);

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
    { label: 'searches', value: searches },
    { label: 'clicks', value: clicks },
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
    devices: 'Devices', widths: 'Screen widths',
  };
  const out: Record<string, any[]> = {};
  for (const [k, label] of Object.entries(pretty)) {
    if (d[k]?.length) out[label] = d[k];
  }
  return out;
});

const match = (row: any[], i: number, f: string) => !f || String(row?.[i] || '').toLowerCase().includes(f.toLowerCase());
const fTopQueries = computed(() => (data.value?.topQueries || []).filter((r: any[]) => match(r, 0, fq.value)));
const fTopClicks = computed(() => (data.value?.topClicks || []).filter((r: any[]) => match(r, 0, fcl.value)));
const fCtr = computed(() => (data.value?.ctrByQuery || []).filter((r: any[]) => match(r, 0, fctr.value)));
const fRefs = computed(() => (data.value?.refs || []).filter((r: any[]) => match(r, 0, fref.value)));
const fInq = computed(() => (data.value?.adInquiries || []).filter((r: any[]) =>
  match(r, 1, finq.value) || match(r, 2, finq.value) || match(r, 3, finq.value) || match(r, 4, finq.value)));

function nice(v: any): string {
  const s = String(v ?? '');
  if (!s || s === '?') return 'unknown';
  return s;
}
function fmtDate(s: any): string {
  if (!s) return '';
  const d = new Date(String(s));
  return isNaN(d.getTime()) ? String(s) : d.toLocaleString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function askDelete(id: number) {
  if (delSure.value !== id) {
    delSure.value = id;
    if (delTimer) clearTimeout(delTimer);
    delTimer = setTimeout(() => { delSure.value = null; }, 4000);
    return;
  }
  delSure.value = null;
  const backup = data.value?.adInquiries || [];
  data.value.adInquiries = backup.filter((r: any[]) => r[0] !== id);
  $fetch(`/api/admin/inquiries/${id}`, { method: 'DELETE' })
    .then((res: any) => { if (!res?.ok) data.value.adInquiries = backup; })
    .catch(() => { data.value.adInquiries = backup; });
}

let timer: any = null;
async function load() {
  try {
    const res = await $fetch('/api/admin/stats', {
      query: { days: days.value, hours: hours.value },
      headers: { 'x-admin-key': key.value },
    }) as any;
    if (res?.error === 'unauthorized') { wrong.value = true; unlocked.value = false; return; }
    data.value = res;
    unlocked.value = true;
    wrong.value = false;
    sel.value = -1;
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
/* same mechanism as the main site: data-theme attr + shared pm_theme key */
function toggleTheme() {
  dark.value = !dark.value;
  document.documentElement.dataset.theme = dark.value ? 'dark' : 'light';
  try { localStorage.setItem('pm_theme', dark.value ? 'dark' : 'light'); } catch { /* ignore */ }
}
watch(auto, () => setTimer());
function setTimer() {
  if (timer) { clearInterval(timer); timer = null; }
  if (auto.value && unlocked.value) timer = setInterval(() => load(), 60000);
}
onMounted(() => {
  try {
    dark.value = localStorage.getItem('pm_theme') === 'dark';
    document.documentElement.dataset.theme = dark.value ? 'dark' : 'light';
  } catch { /* ignore */ }
  try {
    const saved = sessionStorage.getItem('pm_admin_key');
    if (saved) { key.value = saved; load(); }
  } catch { /* ignore */ }
  setTimer();
});
onUnmounted(() => { if (timer) clearInterval(timer); if (delTimer) clearTimeout(delTimer); });
</script>

<style>
.adm { font-family: system-ui, -apple-system, sans-serif; color: #1a2e1f; background: #f6faf7; min-height: 100vh; }
.adm.dark { color: #dbe7dd; background: #0d140f; }
.adm .top { display: flex; align-items: center; gap: 0.8rem; padding: 0.8rem 1.2rem; background: #fff; border-bottom: 1px solid #e3ece4; position: sticky; top: 0; z-index: 5; }
.adm.dark .top { background: #121a14; border-bottom-color: #1f2b22; }
.adm .top .hint { margin-left: auto; }
.adm .logo { display: flex; gap: 0.5rem; align-items: center; font-weight: 800; color: inherit; text-decoration: none; margin-right: auto; }
.adm main { max-width: 1200px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
.adm .gate { text-align: center; padding: 3rem 0; }
.adm .gate h1 { font-size: 1.3rem; }
.adm .gate form { display: flex; gap: 0.5rem; justify-content: center; margin-top: 1rem; flex-wrap: wrap; }
.adm .gate input { padding: 0.7rem 1rem; border: 2px solid #d5e2d7; border-radius: 10px; font-size: 1rem; background: #fff; color: inherit; max-width: 100%; }
.adm.dark .gate input { background: #121a14; border-color: #2a3b2f; }
.adm .gate button { padding: 0.7rem 1.4rem; font-weight: 700; background: #12813c; color: #fff; border: none; border-radius: 10px; cursor: pointer; }
.adm .err { color: #dc2626; margin-top: 0.7rem; }
.adm.dark .err { color: #f87171; }
.adm .toolbar { display: flex; align-items: center; gap: 1.2rem; margin-bottom: 1rem; flex-wrap: wrap; }
.adm .toolbar select { padding: 0.3rem 0.5rem; border: 1px solid #d5e2d7; border-radius: 8px; background: #fff; color: inherit; }
.adm.dark .toolbar select { background: #121a14; border-color: #2a3b2f; }
.adm .krow { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.8rem; margin-bottom: 1.4rem; }
.adm .kpi { background: #fff; border: 1px solid #e3ece4; border-radius: 12px; padding: 1rem; text-align: center; min-width: 0; }
.adm.dark .kpi { background: #121a14; border-color: #1f2b22; }
.adm .kv { display: block; font-size: 1.7rem; font-weight: 800; color: #12813c; font-variant-numeric: tabular-nums; }
.adm.dark .kv { color: #4ade80; }
.adm .kl { color: #55655a; font-size: 0.85rem; overflow-wrap: anywhere; }
.adm.dark .kl { color: #8fa897; }
.adm .panel { background: #fff; border: 1px solid #e3ece4; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; min-width: 0; overflow: hidden; }
.adm.dark .panel { background: #121a14; border-color: #1f2b22; }
.adm .panel h2 { margin: 0 0 0.6rem; font-size: 1rem; display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.adm .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 0.8rem; }
.adm table { width: 100%; border-collapse: collapse; font-size: 0.9rem; table-layout: fixed; }
.adm td, .adm th { padding: 0.35rem 0.4rem; border-bottom: 1px solid #eef3ee; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.adm.dark td, .adm.dark th { border-bottom-color: #1f2b22; }
.adm .num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; color: #55655a; }
.adm.dark .num { color: #8fa897; }
.adm .tt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.adm .mut { color: #55655a; }
.adm.dark .mut { color: #8fa897; }
.adm .small { font-size: 0.8rem; }
.adm .tfilter { margin-left: auto; padding: 0.15rem 0.5rem; border: 1px solid #d5e2d7; border-radius: 8px; font-size: 0.8rem; background: #fff; color: inherit; max-width: 9rem; }
.adm.dark .tfilter { background: #0d140f; border-color: #2a3b2f; }
.adm .ctrr { color: #12813c; margin-left: 0.35rem; }
.adm.dark .ctrr { color: #4ade80; }
.adm .bars { display: flex; align-items: flex-end; gap: 2px; height: 120px; }
.adm .bars.dense { gap: 1px; }
.adm .bcol { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; justify-content: flex-end; gap: 2px; cursor: pointer; border-radius: 3px; }
.adm .bcol:hover { background: rgba(18, 129, 60, 0.12); }
.adm .bcol.sel { background: rgba(18, 129, 60, 0.22); outline: 1px solid #12813c; }
.adm .bar { border-radius: 2px 2px 0 0; min-height: 1px; }
.adm .bar.s { background: #12813c; }
.adm .bar.c { background: #86efac; }
.adm.dark .bar.c { background: #22c55e; }
.adm .baxis { display: flex; justify-content: space-between; margin-top: 0.3rem; }
.adm .barinfo { margin: 0.5rem 0 0; font-size: 0.9rem; }
.adm .sysgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.5rem 1.2rem; overflow-wrap: anywhere; }
.adm .sysgrid .chain { grid-column: 1 / -1; }
.adm .serpk { display: flex; align-items: center; gap: 0.5rem; }
.adm .meter { flex: 0 1 6rem; height: 0.45rem; border-radius: 999px; background: #e3ece4; overflow: hidden; }
.adm.dark .meter { background: #1f2b22; }
.adm .meter .fill { display: block; height: 100%; background: #22c55e; border-radius: 999px; transition: width 0.4s; }
.adm .meter .fill.warn { background: #f59e0b; }
.adm .meter .fill.crit { background: #dc2626; }
.adm .pill { display: inline-block; border: 1px solid #d5e2d7; border-radius: 999px; padding: 0 0.5rem; font-size: 0.78rem; margin: 0.1rem 0.15rem 0.1rem 0; }
.adm.dark .pill { border-color: #2a3b2f; }
.adm .pill.first { border-color: #12813c; color: #12813c; font-weight: 700; }
.adm.dark .pill.first { border-color: #4ade80; color: #4ade80; }
.adm .dot { display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; margin-right: 0.45rem; }
.adm .dot.ok { background: #22c55e; }
.adm .dot.bad { background: #dc2626; }
.adm .inq { border: 1px solid #eef3ee; border-radius: 10px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; cursor: pointer; transition: border-color 0.12s; min-width: 0; }
.adm.dark .inq { border-color: #1f2b22; }
.adm .inq:hover { border-color: #12813c; }
.adm .inq-row { display: flex; gap: 0.4rem 0.9rem; flex-wrap: wrap; align-items: baseline; }
.adm .inq-mail { overflow-wrap: anywhere; }
.adm .inq-meta { margin-left: auto; white-space: nowrap; }
.adm .delbtn { background: none; border: 1px solid transparent; border-radius: 6px; color: #dc2626; cursor: pointer; font-size: 0.8rem; padding: 0 0.3rem; }
.adm.dark .delbtn { color: #f87171; }
.adm .delbtn:hover, .adm .delbtn.sure { border-color: #dc2626; font-weight: 700; }
.adm .inq-msg { margin: 0.6rem 0 0; white-space: pre-wrap; overflow-wrap: anywhere; background: #f6faf7; border-radius: 8px; padding: 0.6rem; font-size: 0.9rem; }
.adm.dark .inq-msg { background: #0d140f; }
.adm .linklike { background: none; border: none; color: #12813c; font: inherit; font-weight: 700; cursor: pointer; text-decoration: underline; }
.adm.dark .linklike { color: #4ade80; }
.adm .foot { margin-top: 2rem; }
.adm .iconbtn { background: none; border: 1px solid #d5e2d7; border-radius: 8px; padding: 0.2rem 0.55rem; cursor: pointer; font-size: 0.95rem; color: inherit; }
.adm.dark .iconbtn { border-color: #2a3b2f; }
.adm .iconbtn:hover { border-color: #12813c; }
@media (max-width: 640px) {
  .adm .inq-meta { margin-left: 0; }
  .adm .tfilter { max-width: 7rem; }
}
</style>
