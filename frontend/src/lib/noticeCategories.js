// How each kind of notice is named and described, in one place so the board,
// the filter tabs, the map pins and the compose form can never drift apart. The
// server owns which of these a given account may actually post — see
// /api/notices/meta — this file only says how they read.
//
// There is deliberately no crime-or-safety type. See the module docstring in
// backend/app/core/notices.py for the reasoning.

export const NOTICE_CATEGORIES = {
  giveaway: {
    label: "Giveaway",
    short: "Giveaway",
    // The prompt does real work here: a vague giveaway wastes everyone's time.
    hint: "What it is, what condition it's in, and how someone can collect it.",
  },
  lost_found: {
    label: "Lost & Found",
    short: "Lost & found",
    hint: "What was lost or found, and roughly where.",
    // Types where a map pin genuinely helps get the compass prompt in the form.
    suggestsPin: true,
  },
  question: {
    label: "Question",
    short: "Question",
    hint: "What you need to know, and anything that narrows it down.",
  },
  news: {
    label: "Local news",
    short: "News",
    hint: "What happened, where, and why it matters to people here.",
    longForm: true,
  },
  shoutout: {
    label: "Shoutout",
    short: "Shoutout",
    hint: "Who deserves the credit, and what they did.",
  },
  blog: {
    label: "Writing",
    short: "Writing",
    hint: "Take the space you need — a story, a reflection, a write-up.",
    longForm: true,
  },
  announcement: {
    label: "Announcement",
    short: "Notice",
    hint: "What's happening and who it's for.",
    orgOnly: true,
  },
  service_change: {
    label: "Service change or closure",
    short: "Change",
    hint: "What's changing, where, and for how long.",
    orgOnly: true,
    suggestsPin: true,
  },
};

// Filter strip order. Keeps the "somebody wants / is offering something" types
// first, since those are the ones that end at a doorstep.
export const CATEGORY_ORDER = Object.keys(NOTICE_CATEGORIES);

export function categoryLabel(category) {
  return NOTICE_CATEGORIES[category]?.label ?? "Notice";
}

export function categoryShort(category) {
  return NOTICE_CATEGORIES[category]?.short ?? "Notice";
}

export function categoryHint(category) {
  return NOTICE_CATEGORIES[category]?.hint ?? "";
}

export function isLongForm(category) {
  return Boolean(NOTICE_CATEGORIES[category]?.longForm);
}

export function suggestsPin(category) {
  return Boolean(NOTICE_CATEGORIES[category]?.suggestsPin);
}

// Turns "2026-08-10T…" into "3 days left" — the board leads with how long
// something has rather than when it was posted, because that's what decides
// whether it's worth acting on.
export function timeLeft(expiresAt) {
  const ms = new Date(expiresAt) - new Date();
  if (ms <= 0) return "expired";
  const days = Math.floor(ms / 86_400_000);
  if (days >= 1) return `${days} day${days === 1 ? "" : "s"} left`;
  const hours = Math.max(1, Math.floor(ms / 3_600_000));
  return `${hours} hour${hours === 1 ? "" : "s"} left`;
}
