"""Approval authority thresholds for financial transactions.

Every financial request is routed to an authorized verifier and approver
based on the requested amount. The Admin role may verify/approve at any tier.

Tier 1  -> amount <= 10,000      Verifier: Extension Coordinator   Approver: Linkages Coordinator
Tier 2  -> 10,000 < amount       Verifier: Linkages Coordinator    Approver: Extension Director
          <= 50,000
Tier 3  -> amount > 50,000       Verifier: Extension Director      Approver: Admin
"""

APPROVAL_TIERS = [
    {
        "tier": "Tier 1",
        "label": "Low-value",
        "min": 0.01,
        "max": 10000.00,
        "verifiers": ["Extension Coordinator"],
        "approvers": ["Linkages Coordinator"],
    },
    {
        "tier": "Tier 2",
        "label": "Medium-value",
        "min": 10000.01,
        "max": 50000.00,
        "verifiers": ["Linkages Coordinator"],
        "approvers": ["Extension Director"],
    },
    {
        "tier": "Tier 3",
        "label": "High-value",
        "min": 50000.01,
        "max": None,  # up to the configured maximum allowable amount
        "verifiers": ["Extension Director"],
        "approvers": ["Admin"],
    },
]


def tier_max_amount(tier, max_amount):
    """Display maximum for a tier. Tier 3 caps at the configured max amount."""
    mx = tier.get("max")
    if mx is None:
        mx = max_amount
    return mx


def tier_for_amount(amount):
    """Return the approval tier applicable to a given amount.

    Defaults to the lowest tier for invalid/zero amounts so that permission
    checks never fail unexpectedly before the amount is validated.
    """
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0
    for tier in APPROVAL_TIERS:
        if tier["max"] is None or amount <= tier["max"]:
            return tier
    return APPROVAL_TIERS[-1]


def tier_for(amount):
    return tier_for_amount(amount)


def can_verify(user, amount):
    """Whether the user may verify a request for this amount."""
    if user is None:
        return False
    if user.role == "Admin":
        return True
    return user.role in tier_for_amount(amount)["verifiers"]


def can_approve(user, amount):
    """Whether the user may approve a request for this amount."""
    if user is None:
        return False
    if user.role == "Admin":
        return True
    return user.role in tier_for_amount(amount)["approvers"]


def can_reject(user, amount):
    """Verifier or approver authority is enough to reject a request."""
    return can_verify(user, amount) or can_approve(user, amount)