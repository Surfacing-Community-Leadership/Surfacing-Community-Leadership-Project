// Maps an interest/category slug to the emoji shown on its map pin (and next
// to the tag elsewhere). Keys are the interest slugs seeded in the database
// (see the seed_starter_interests migration). Anything unmapped or untagged
// falls back to DEFAULT_TAG_ICON.
export const TAG_ICONS = {
  "sports-fitness": "⚽",
  "outdoors-nature": "🌳",
  gardening: "🌱",
  "cooking-food": "🍳",
  "arts-crafts": "🎨",
  music: "🎵",
  "books-reading": "📚",
  games: "🎲",
  volunteering: "🙌",
  "kids-family": "🧸",
  seniors: "🧓",
  pets: "🐾",
  technology: "💻",
  "local-history": "🏛️",
  "health-wellness": "🧘",
  "home-repair-diy": "🔧",
};

export const DEFAULT_TAG_ICON = "📍";

export function tagIcon(slug) {
  return (slug && TAG_ICONS[slug]) || DEFAULT_TAG_ICON;
}
