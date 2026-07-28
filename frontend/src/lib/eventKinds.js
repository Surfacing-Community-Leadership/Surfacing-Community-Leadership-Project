// One place for how each kind of listing is named and coloured, so the map,
// the lists, the detail page and the form can never drift apart.
//
//   gathering      — anyone: come spend time together
//   help_request   — a person asking a neighbour for a personal favour
//   volunteer_work — an organization recruiting for a shift (org accounts only)

export const EVENT_KINDS = {
  gathering: { label: "Gathering", short: "Gathering" },
  help_request: { label: "Help request", short: "Help" },
  volunteer_work: { label: "Volunteer work", short: "Volunteer" },
};

export function kindLabel(kind) {
  return EVENT_KINDS[kind]?.label ?? "Gathering";
}

// The choices offered when creating something, which depend on who you are:
// an organization recruits volunteers, a person asks for a hand.
export function kindsFor(accountType) {
  return accountType === "organization"
    ? ["gathering", "volunteer_work"]
    : ["gathering", "help_request"];
}

// Both of these mean "someone turned up to lend a hand", so the host confirms
// who did and it counts toward their public helped tally.
export function isHelpKind(kind) {
  return kind === "help_request" || kind === "volunteer_work";
}
