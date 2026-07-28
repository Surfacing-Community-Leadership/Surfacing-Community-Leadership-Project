"""Deciding whether an organization account gets the ✓ badge at signup.

The badge is read by the trust record on every profile, so it has to mean
something. The rule: an org is auto-verified only when it registers with an
email on a domain that **cannot be casually obtained**.

  * `.gov`, `.mil`, `.edu` (and the `k12.*.us` school pattern) are issued only
    to qualifying institutions, so an address there is meaningful evidence.
  * `.org` / `.com` are not — anyone can buy one for a few dollars — so those
    orgs are created unverified and an admin grants the badge after checking the
    website they supplied. Add specific known domains to EXPLICIT_DOMAINS to
    fast-path them.

KNOWN LIMITATION: registration does not yet confirm the applicant can receive
mail at the address they typed, so a gated domain proves the *domain* is
institutional, not that this person speaks for it. Adding email confirmation
closes that gap; until then, treat auto-verification as a convenience and rely
on the admin panel to catch impostors.
"""

# Suffixes whose registration is restricted to qualifying institutions.
GATED_SUFFIXES = (
    ".gov",
    ".mil",
    ".edu",
    ".k12.us",  # e.g. ps321.k12.ny.us also matches via the state check below
    ".ac.uk",
)

# Specific domains a human has already vetted — e.g. a library on a .org.
# Add entries here rather than loosening GATED_SUFFIXES.
EXPLICIT_DOMAINS: tuple[str, ...] = ()


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower()


def is_gated_domain(email: str) -> bool:
    """True when the address sits on a domain that isn't open registration."""
    domain = email_domain(email)
    if not domain:
        return False
    if domain in EXPLICIT_DOMAINS:
        return True
    if any(domain.endswith(suffix) for suffix in GATED_SUFFIXES):
        return True
    # US public schools: <district>.k12.<state>.us
    parts = domain.split(".")
    return len(parts) >= 4 and parts[-1] == "us" and "k12" in parts


def should_auto_verify(account_type: str, email: str) -> bool:
    """Only organizations auto-verify, and only on a gated domain. A personal
    account never gets the badge this way."""
    return account_type == "organization" and is_gated_domain(email)
