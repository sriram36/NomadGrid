// S2 + S3: a small static "pocket guide" per city, kept completely apart from the catalog JSON files.
// It is read-only help for the traveler: it is never part of the package, the total or the exported JSON.
//
// The tips are general travel advice. The dining spots are illustrative suggestions (not live listings), and every
// meal cost is an estimate per person in INR. Anything shown from here is "out of pocket": not in the package total.

export const DINING_DISCLAIMER = 'Estimated out-of-pocket expense — excluded from package total.';

export const cityCompanionData = {
  Tokyo: {
    tagline: 'Fast, spotless and easy to get around once you have a transit card.',
    tips: [
      { topic: 'Transit', text: 'Load a Suica or Pasmo card (also in Apple/Google Wallet). It works on every metro, JR line and many buses.' },
      { topic: 'Etiquette', text: 'Keep phone calls off trains, queue in the marked lines and do not eat while walking in busy streets.' },
      { topic: 'Money & connectivity', text: 'Carry some cash for small shops and shrines. Pick up an eSIM or pocket Wi-Fi at the airport.' },
      { topic: 'Sightseeing', text: 'Visit Senso-ji and big viewpoints early in the morning to beat the crowds, and book teamLab-style venues ahead.' },
    ],
    dining: [
      { name: 'Shinjuku Ramen Counter', area: 'Shinjuku', cuisine: 'Japanese ramen', tags: ['Quick Bite'], walkMin: 6, costInr: 700 },
      { name: 'Green Table Kitchen', area: 'Shibuya', cuisine: 'Japanese vegan', tags: ['Vegetarian-Friendly', 'Family-Friendly'], walkMin: 9, costInr: 1200 },
      { name: 'Asakusa Halal Noodle House', area: 'Asakusa', cuisine: 'Halal ramen', tags: ['Halal', 'Family-Friendly'], walkMin: 5, costInr: 900 },
      { name: 'Ginza Tempura Hall', area: 'Ginza', cuisine: 'Tempura', tags: ['Family-Friendly'], walkMin: 7, costInr: 1800 },
    ],
  },
  Kyoto: {
    tagline: 'Temples, tea houses and quiet lanes. Plan for walking and buses.',
    tips: [
      { topic: 'Transit', text: 'Buses reach most temples but get crowded. Use the subway and trains where you can, and consider a one-day bus pass.' },
      { topic: 'Etiquette', text: 'Speak softly in temples and gardens, remove shoes where asked, and do not photograph geiko or maiko in Gion without permission.' },
      { topic: 'Money & connectivity', text: 'Many small restaurants and temples take cash only. Keep coins for offerings and lockers.' },
      { topic: 'Sightseeing', text: 'Go to Fushimi Inari and Arashiyama at sunrise. Spend the afternoon in Higashiyama and Gion.' },
    ],
    dining: [
      { name: 'Kawaramachi Obanzai Kitchen', area: 'Kawaramachi', cuisine: 'Kyoto home-style small plates', tags: ['Vegetarian-Friendly', 'Family-Friendly'], walkMin: 6, costInr: 1300 },
      { name: 'Nishiki Street Bites', area: 'Kawaramachi', cuisine: 'Market snacks', tags: ['Quick Bite', 'Family-Friendly'], walkMin: 8, costInr: 600 },
      { name: 'Station Soba House', area: 'Kyoto Station', cuisine: 'Soba noodles', tags: ['Family-Friendly'], walkMin: 4, costInr: 800 },
      { name: 'Gion Tea & Sweets Room', area: 'Gion', cuisine: 'Matcha and sweets', tags: ['Vegetarian-Friendly'], walkMin: 5, costInr: 700 },
    ],
  },
  Osaka: {
    tagline: 'Japan\'s food capital: relaxed, loud and very good value.',
    tips: [
      { topic: 'Transit', text: 'An ICOCA or Suica card covers the subway, JR loop and private lines. The Namba and Umeda areas link well to everything.' },
      { topic: 'Etiquette', text: 'Stand on the right on escalators here (the left in Tokyo) and queue at popular street-food stalls.' },
      { topic: 'Money & connectivity', text: 'Street-food stalls often prefer cash. Free Wi-Fi is common in Dotonbori but patchy, so an eSIM is easier.' },
      { topic: 'Sightseeing', text: 'See Osaka Castle in the morning, then eat your way through Dotonbori and Kuromon Market. Book Universal Studios early.' },
    ],
    dining: [
      { name: 'Namba Takoyaki Stand', area: 'Namba', cuisine: 'Takoyaki', tags: ['Quick Bite', 'Family-Friendly'], walkMin: 4, costInr: 500 },
      { name: 'Umeda Okonomiyaki Griddle', area: 'Umeda', cuisine: 'Okonomiyaki', tags: ['Family-Friendly'], walkMin: 7, costInr: 1000 },
      { name: 'Kuromon Seafood Counter', area: 'Namba', cuisine: 'Market seafood', tags: [], walkMin: 10, costInr: 1500 },
      { name: 'Tennoji Veggie Curry', area: 'Tennoji', cuisine: 'Japanese curry', tags: ['Vegetarian-Friendly', 'Halal'], walkMin: 6, costInr: 850 },
    ],
  },
  Dubai: {
    tagline: 'Big, air-conditioned and spread out. Plan around the heat and the metro.',
    tips: [
      { topic: 'Transit', text: 'Get a Nol card for the metro, tram and buses. Taxis are cheap and plentiful, but allow extra time in rush hour.' },
      { topic: 'Etiquette', text: 'Dress modestly in malls, souks and mosques, and avoid public displays of affection. Do not photograph people without asking.' },
      { topic: 'Money & connectivity', text: 'Cards work almost everywhere. Use a UAE-licensed eSIM, because some calling apps are restricted.' },
      { topic: 'Sightseeing', text: 'Visit outdoor places in the morning or evening, and book Burj Khalifa and Ski Dubai in advance.' },
    ],
    dining: [
      { name: 'Deira Spice Kitchen', area: 'Deira', cuisine: 'Indian and Arabic', tags: ['Halal', 'Vegetarian-Friendly', 'Family-Friendly'], walkMin: 6, costInr: 900 },
      { name: 'Downtown Shawarma Corner', area: 'Downtown', cuisine: 'Shawarma and grills', tags: ['Halal', 'Quick Bite'], walkMin: 5, costInr: 600 },
      { name: 'Marina Waterfront Grill', area: 'Dubai Marina', cuisine: 'Grill and seafood', tags: ['Halal', 'Family-Friendly'], walkMin: 8, costInr: 2200 },
      { name: 'Al Barsha Garden Cafe', area: 'Al Barsha', cuisine: 'Mediterranean', tags: ['Halal', 'Vegetarian-Friendly', 'Family-Friendly'], walkMin: 7, costInr: 1100 },
    ],
  },
  'Abu Dhabi': {
    tagline: 'Calmer and greener than Dubai, with grand landmarks and waterfronts.',
    tips: [
      { topic: 'Transit', text: 'Taxis and ride-hailing are the easiest way around. City buses use the Hafilat card.' },
      { topic: 'Etiquette', text: 'The Sheikh Zayed Grand Mosque needs covered shoulders and legs; abayas are lent at the entrance. Stay quiet inside.' },
      { topic: 'Money & connectivity', text: 'Cards are accepted nearly everywhere. Keep small notes for tips and parking meters.' },
      { topic: 'Sightseeing', text: 'See the mosque at sunset, then take a walk on the Corniche. Book the Louvre and mangrove kayaking ahead.' },
    ],
    dining: [
      { name: 'Corniche Arabic Breakfast House', area: 'Corniche', cuisine: 'Arabic breakfast', tags: ['Halal', 'Vegetarian-Friendly', 'Family-Friendly'], walkMin: 5, costInr: 800 },
      { name: 'Corniche Fish Grill', area: 'Corniche', cuisine: 'Grilled fish', tags: ['Halal', 'Family-Friendly'], walkMin: 9, costInr: 1800 },
      { name: 'Saadiyat Beach Cafe', area: 'Saadiyat', cuisine: 'Cafe and brunch', tags: ['Halal', 'Vegetarian-Friendly'], walkMin: 6, costInr: 1400 },
      { name: 'Yas Island Family Diner', area: 'Yas Island', cuisine: 'International', tags: ['Halal', 'Family-Friendly'], walkMin: 4, costInr: 1000 },
    ],
  },
};

export const getCityCompanion = (city) => cityCompanionData[city] || null;
