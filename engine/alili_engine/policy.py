"""Fail-closed free-first route eligibility."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    route: str
    reason: str


class FreePolicyGate:
    """Reject paid/unknown routes and require explicit operator evidence for hosted tiers."""

    def evaluate(
        self,
        route: str,
        *,
        free_terms_confirmed: bool = False,
        billing_disabled: bool = False,
        quota_verified: bool = False,
        license_approved: bool = False,
    ) -> PolicyDecision:
        normalized = (route or "").strip().lower()

        if normalized == "local_builtin":
            return PolicyDecision(True, normalized, "local_builtin_no_external_billing")

        if normalized == "local_open_source":
            if license_approved:
                return PolicyDecision(True, normalized, "local_open_source_license_reviewed")
            return PolicyDecision(False, normalized, "local_license_not_reviewed")

        if normalized in {"paid", "subscription", "metered_paid"}:
            return PolicyDecision(False, normalized, "paid_routes_forbidden")

        if normalized in {"hosted_free", "approved_free_hosted"}:
            if free_terms_confirmed and billing_disabled and quota_verified:
                return PolicyDecision(True, normalized, "operator_verified_free_tier")
            return PolicyDecision(False, normalized, "hosted_free_tier_not_fully_verified")

        return PolicyDecision(False, normalized or "unknown", "unknown_route_denied")
