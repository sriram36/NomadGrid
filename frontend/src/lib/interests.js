// S1: interest tags and the deterministic rules that match an attraction to them.
// An attraction is matched by its catalog category and by keywords in its name. No AI, no network.

export const INTERESTS = [
  { key: 'history', label: 'History & Culture' },
  { key: 'nature', label: 'Nature' },
  { key: 'family', label: 'Family' },
  { key: 'art', label: 'Art & Museums' },
  { key: 'food', label: 'Food & Markets' },
  { key: 'adventure', label: 'Adventure' },
];

const RULES = {
  history: {
    categories: ['TEMPLE', 'SHRINE', 'CASTLE', 'PALACE', 'MOSQUE', 'MONUMENT'],
    words: ['heritage', 'historical', 'imperial', 'edo', 'national museum', 'etihad'],
  },
  nature: {
    categories: ['NATURE', 'PARK', 'BEACH'],
    words: ['garden', 'bamboo', 'mangrove', 'path', 'seaside'],
  },
  family: {
    categories: ['THEME_PARK', 'AQUARIUM'],
    words: ['toy', 'science', 'railway', 'zoo', 'disney', 'universal', 'global village'],
  },
  art: {
    categories: ['MUSEUM'],
    words: ['teamlab', 'louvre', 'craft', 'art', 'future'],
  },
  food: {
    categories: ['MARKET'],
    words: ['market', 'souk', 'ichiba', 'ameyoko', 'tsukiji'],
  },
  adventure: {
    categories: ['THEME_PARK', 'VIEWPOINT'],
    words: ['kayak', 'ski', 'sky', 'tower', 'frame', 'top'],
  },
};

const norm = (s) => String(s || '').toUpperCase().replaceAll(' ', '_');

// attraction: { name, category } (an option from the API) or a package item (title + details.category).
export function attractionCategory(a) {
  return norm(a.category || a.details?.category || '');
}

export function matchesInterest(attraction, key) {
  const rule = RULES[key];
  if (!rule) return false;
  const category = attractionCategory(attraction);
  const name = String(attraction.name || attraction.title || '').toLowerCase();
  if (rule.categories.includes(category)) return true;
  return rule.words.some((w) => new RegExp(`\\b${w}`).test(name));
}

// Which of the selected interest keys this attraction matches.
export function matchedInterests(attraction, selected) {
  return (selected || []).filter((key) => matchesInterest(attraction, key));
}

export const interestLabel = (key) => INTERESTS.find((i) => i.key === key)?.label || key;
