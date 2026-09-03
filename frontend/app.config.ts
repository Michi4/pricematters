// Multi-brand: ONE docker image, N domains.
// The page reads the hostname (SSR-safe) and picks brand + rotating slogans.
// app.config.ts
export default defineAppConfig({
  brands: {
    'pricematters.app': {
      name: 'PriceMatters',
      slogansEN: [
        'Because unlike size, pricematters.',
        "Don't look at the price tag – know the unit price.",
        'Amazon makes it complicated. We make it simple.',
      ],
      slogansDE: [
        'Denn anders als die Größe zählt hier der Preis.',
        'Schau nicht auf den Preis – schau auf den Grundpreis.',
        'Es kommt nicht auf die Größe an, sondern auf den Preis.',
      ],
    },
    'dothemath.app': {
      name: 'DoTheMath',
      slogansEN: [
        'With your hard-earned money you always gotta do the math.',
        'Marketing is a lie. Math is not.',
      ],
      slogansDE: [
        'Bei deinem hart verdienten Geld musst du immer nachrechnen.',
        'Marketing lügt. Mathe nicht.',
      ],
    },
    'moneysworth.app': {
      name: 'MoneysWorth',
      slogansEN: [
        'Because here you get your moneysworth.',
        "Stop guessing what things really cost.",
      ],
      slogansDE: [
        'Hier bekommst du was für dein Geld.',
        'Schluss mit Raten, was Dinge wirklich kosten.',
      ],
    },
    default: {
      name: 'PriceMatters',
      slogansEN: [
        "Don't look at the price tag – know the unit price.",
        'Because unlike size, pricematters.',
      ],
      slogansDE: [
        'Denn anders als die Größe zählt hier der Preis.',
        'Schau nicht auf den Preis – schau auf den Grundpreis.',
      ],
    },
  },
  // hostname -> brand key (prod subdomains + bare .app domains, one image)
  aliases: {
    'pricematters.websters.at': 'pricematters.app',
    'deals.websters.at': 'pricematters.app',
    'preiswertist.websters.at': 'pricematters.app',
    'dothemath.websters.at': 'dothemath.app',
    'moneysworth.websters.at': 'moneysworth.app',
    'valueformoney.websters.at': 'moneysworth.app',
  },
});
