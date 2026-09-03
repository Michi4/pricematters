export default defineEventHandler((event) => {
  const host = useRuntimeConfig(event).public?.canonicalHost || 'pricematters.websters.at';
  const base = `https://${host}`;
  const urls = [
    { loc: `${base}/`, priority: '1.0', changefreq: 'daily' },
    { loc: `${base}/en`, priority: '0.8', changefreq: 'daily' },
  ];
  setHeader(event, 'content-type', 'application/xml');
  setHeader(event, 'cache-control', 'public, max-age=86400');
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u.loc}</loc><changefreq>${u.changefreq}</changefreq><priority>${u.priority}</priority></url>`).join('\n')}
</urlset>`;
});
