// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  devtools: { enabled: true },
  modules: ['@nuxtjs/i18n'],
  i18n: {
    locales: [
      { code: 'de', language: 'de-AT', file: 'de.json' },
      { code: 'en', language: 'en-US', file: 'en.json' },
    ],
    defaultLocale: 'de',
    langDir: 'locales',
    strategy: 'prefix_except_default',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'pm_locale',
      redirectOn: 'root',
    },
  },
  app: {
    head: {
      htmlAttrs: { lang: 'de-AT' },
      title: 'PriceMatters – Amazon Grundpreise vergleichen (€/kg, €/l, €/Stück)',
      meta: [
        { name: 'description', content: 'Finde den echten Billigsten: Grundpreis pro kg, Liter oder Stück für Amazon-Produkte – ohne Ads, ohne Fake-Rabatte. | Compare real unit prices (€/kg, €/L, €/pc).' },
        { name: 'robots', content: 'index, follow' },
        { name: 'theme-color', content: '#16a34a' },
        { property: 'og:type', content: 'website' },
        { property: 'og:site_name', content: 'PriceMatters' },
        { property: 'og:image', content: '/og.png' },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { name: 'twitter:card', content: 'summary_large_image' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
    },
  },
  runtimeConfig: {
    // server-only: never expose Amazon keys to the client
    backendUrl: process.env.BACKEND_URL || 'http://localhost:8000',
    amazonAccessKey: process.env.AMAZON_ACCESS_KEY || '',
    amazonSecretKey: process.env.AMAZON_SECRET_KEY || '',
    amazonPartnerTag: process.env.AMAZON_PARTNER_TAG || '',
    public: {
      defaultLocale: process.env.NUXT_PUBLIC_DEFAULT_LOCALE || 'de-AT',
      affiliateTag: process.env.NUXT_PUBLIC_AFFILIATE_TAG || '',
      canonicalHost: process.env.NUXT_PUBLIC_CANONICAL_HOST || 'pricematters.websters.at',
    },
  },
});
