"""Single-template policy for consistent AniZoneFlix verification UI."""

VERIFICATION_TEMPLATE = "verify.html"

def get_verification_template() -> str:
    return VERIFICATION_TEMPLATE

# Backwards-compatible name; intentionally deterministic.
def get_random_verification_template() -> str:
    return VERIFICATION_TEMPLATE
