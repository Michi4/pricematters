// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  devtools: { enabled: true },
  runtimeConfig: {
    // server-only: never expose Amazon keys to the client
    backendUrl: process.env.BACKEND_URL || 'http://localhost:8000',
    amazonAccessKey: process.env.AMAZON_ACCESS_KEY || '',
    amazonSecretKey: process.env.AMAZON_SECRET_KEY || '',
    amazonPartnerTag: process.env.AMAZON_PARTNER_TAG || '',
    public: {
      defaultLocale: process.env.NUXT_PUBLIC_DEFAULT_LOCALE || 'de-AT',
      affiliateTag: process.env.NUXT_PUBLIC_AFFILIATE_TAG || '',
    },
  },
});
