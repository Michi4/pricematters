// Multi-brand: ONE docker image, N domains.
// The page reads the hostname (SSR-safe) and picks brand + rotating punchlines.
export default defineAppConfig({
  brands: {
    'pricematters.app': {
      name: 'PriceMatters',
      slogansEN: [
        'Because unlike *size*, pricematters.',
        "Don't guess. Know the price per kilo.",
        'Amazon shows the price. We show the truth.',
        'Small pack, big scam — check the unit price.',
        "Your wallet's new favorite search engine.",
        'Same Amazon. Same product. Lower price per kilo.',
      ],
      slogansDE: [
        'Denn anders als die *Größe* zählt hier der Preis.',
        'Kleinpackung, Riesen-Abzocke — check den Grundpreis.',
        'Amazon zeigt den Preis. Wir zeigen die Wahrheit.',
        'Wer nachrechnet, zahlt weniger.',
        'Dein Geldbeutel wird uns lieben.',
        'Gleiches Produkt, gleicher Shop — billiger pro Kilo.',
      ],
    },
    'dothemath.app': {
      name: 'DoTheMath',
      slogansEN: [
        'With your hard-earned money, always do the math.',
        "Marketing is a lie. Math isn't.",
        'Subscribe to savings, not to scams.',
        'Your cart called — it wants you to dothemath.',
      ],
      slogansDE: [
        'Bei deinem Geld musst du immer nachrechnen.',
        'Werbung lügt. Mathe nicht.',
        'Dein Warenkorb will, dass du nachrechnest.',
        'Spare mit System, nicht mit Glück.',
      ],
    },
    'moneysworth.app': {
      name: 'MoneysWorth',
      slogansEN: [
        'Because here you get your moneysworth.',
        'Get what you pay for. Literally.',
        'Every cent, accounted for.',
        'Stop overpaying per kilo.',
      ],
      slogansDE: [
        'Hier kriegst du was für dein Geld.',
        'Zahl, was es wert ist — nicht mehr.',
        'Jeder Cent zählt. Wir zählen ihn.',
        'Schluss mit Draufzahlen pro Kilo.',
      ],
    },
    default: {
      name: 'PriceMatters',
      slogansEN: [
        'Because unlike *size*, pricematters.',
        "Don't guess. Know the price per kilo.",
        'Amazon shows the price. We show the truth.',
        'Same Amazon. Same product. Lower price per kilo.',
      ],
      slogansDE: [
        'Denn anders als die *Größe* zählt hier der Preis.',
        'Wer nachrechnet, zahlt weniger.',
        'Amazon zeigt den Preis. Wir zeigen die Wahrheit.',
        'Gleiches Produkt, gleicher Shop — billiger pro Kilo.',
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
