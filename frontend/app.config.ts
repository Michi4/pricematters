// Multi-brand: ONE docker image, N domains.
// The layout reads window.location.hostname and picks the brand below.
export default defineAppConfig({
  brands: {
    'pricematters.app': {
      name: 'PriceMatters',
      sloganEN: "Because unlike size, pricematters.",
      sloganDE: 'Denn anders als die Größe zählt hier der Preis.',
    },
    'dothemath.app': {
      name: 'DoTheMath',
      sloganEN: 'With your hard-earned money you always gotta do the math.',
      sloganDE: 'Bei deinem hart verdienten Geld musst du immer nachrechnen.',
    },
    'moneysworth.app': {
      name: 'MoneysWorth',
      sloganEN: 'Because here you get your moneysworth.',
      sloganDE: "Hier bekommst du was für dein Geld.",
    },
    default: {
      name: 'PriceMatters',
      sloganEN: "Don't look at the price tag – know the unit price.",
      sloganDE: 'Schau nicht auf den Preis – schau auf den Grundpreis.',
    },
  },
});
