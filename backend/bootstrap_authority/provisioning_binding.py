"""ADR-087 strict PUBLIC policy/action/initializer comparison mechanics only.

No reader, authenticated source, persistence, witness mint or production wiring.
Matching values/history/CAS expectations NEVER prove provenance or currentness.
Callers must keep existing live custody/snapshot/lease contexts independently.
"""

from dataclasses import dataclass, fields

import rfc8785

from backend.bootstrap_authority.contracts import (
    require_digest,
    require_reference,
    require_revision,
    require_uuid,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PinComparisonFacts, PrivateFactsDenied
from backend.bootstrap_authority.source_custody import SourceCustodyPolicy
from backend.bootstrap_authority.witness_lifetime import WitnessLifetimeDenied


class ProvisioningBindingDenied(RuntimeError):
    def __init__(self):
        super().__init__("DEPLOYMENT_PROVISIONING_BINDING_DENIED")


def _text(value, validator):
    if type(value) is not str:
        raise ProvisioningBindingDenied()
    try:
        validator(value)
    except (TypeError, ValueError):
        raise ProvisioningBindingDenied() from None


def _revision(value):
    try:
        require_revision(value)
    except ValueError:
        raise ProvisioningBindingDenied() from None


def _pin(value):
    if type(value) is not PinComparisonFacts:
        raise ProvisioningBindingDenied()
    _text(value.installation_id, require_uuid)
    _text(value.installation_proof_key_fingerprint, require_digest)
    from backend.bootstrap_authority.witness_lifetime import CurrentnessBinding

    if type(value.binding) is not CurrentnessBinding:
        raise ProvisioningBindingDenied()
    try:
        value.binding.__post_init__()
    except WitnessLifetimeDenied:
        raise ProvisioningBindingDenied() from None
    if any(scope[0] != value.installation_id for scope in value.binding.affected_scopes):
        # This policy unit is explicitly single-installation, not partial scopes
        # silently filtered from a multi-installation manifest.
        raise ProvisioningBindingDenied()


@dataclass(frozen=True, slots=True, repr=False)
class PolicySnapshotFacts:
    """Complete public expected snapshot. ACL/constructor is NOT trusted origin."""

    policy_id: str
    revision: int
    installation_id: str
    installation_proof_key_fingerprint: str
    source_id: str
    custody: SourceCustodyPolicy
    profile_version: int = 1

    def __post_init__(self):
        for value in (self.policy_id, self.installation_id, self.source_id):
            _text(value, require_uuid)
        _text(self.installation_proof_key_fingerprint, require_digest)
        _revision(self.revision)
        if type(self.profile_version) is not int or self.profile_version != 1:
            raise ProvisioningBindingDenied()
        if type(self.custody) is not SourceCustodyPolicy:
            raise ProvisioningBindingDenied()
        try:
            self.custody.__post_init__()
        except PrivateFactsDenied:
            raise ProvisioningBindingDenied() from None


def _machine(value):
    """Internal digest encoding of already exact-type validated objects, no loader."""
    if type(value) is bytes:
        return value.hex()
    if type(value) is tuple:
        return [_machine(item) for item in value]
    if type(value) is int:
        # Includes native uint64 volume IDs: exact decimal avoids JCS rounding.
        return str(value)
    if value is None or type(value) is str:
        return value
    return {field.name: _machine(getattr(value, field.name)) for field in fields(value)}


def _hash(domain, value):
    raw = rfc8785.dumps(_machine(value))
    if len(raw) > 2_097_152:
        raise ProvisioningBindingDenied()
    return digest(domain + b"\x00" + raw)


def policy_snapshot_digest(policy: PolicySnapshotFacts) -> str:
    if type(policy) is not PolicySnapshotFacts:
        raise ProvisioningBindingDenied()
    policy.__post_init__()
    return _hash(b"DohaMusicPolicySnapshotComparisonV1", policy)


@dataclass(frozen=True, slots=True, repr=False)
class InitializerConfirmationFacts:
    """Historical public comparison input, NOT human/source authentication proof."""

    provenance_id: str
    original_confirmation_ref: str
    original_confirmation_digest: str
    initializer_ref: str
    action_id: str
    policy_digest: str
    pin: PinComparisonFacts

    def __post_init__(self):
        for value in (self.provenance_id, self.action_id):
            _text(value, require_uuid)
        for value in (self.original_confirmation_ref, self.initializer_ref):
            _text(value, require_reference)
        for value in (self.original_confirmation_digest, self.policy_digest):
            _text(value, require_digest)
        _pin(self.pin)


@dataclass(frozen=True, slots=True, repr=False)
class ProvisioningActionFacts:
    """Exact immutable action facts; deliberately has no accepted/verified flag."""

    action_id: str
    policy: PolicySnapshotFacts
    confirmation: InitializerConfirmationFacts
    predecessor_digest: str | None

    def __post_init__(self):
        _text(self.action_id, require_uuid)
        if type(self.policy) is not PolicySnapshotFacts:
            raise ProvisioningBindingDenied()
        if type(self.confirmation) is not InitializerConfirmationFacts:
            raise ProvisioningBindingDenied()
        self.policy.__post_init__()
        self.confirmation.__post_init__()
        pin = self.confirmation.pin
        if (
            self.confirmation.action_id != self.action_id
            or self.confirmation.policy_digest != policy_snapshot_digest(self.policy)
            or pin.installation_id != self.policy.installation_id
            or pin.installation_proof_key_fingerprint
            != self.policy.installation_proof_key_fingerprint
        ):
            raise ProvisioningBindingDenied()
        if self.predecessor_digest is not None:
            _text(self.predecessor_digest, require_digest)
        if (self.policy.revision == 1) != (self.predecessor_digest is None):
            raise ProvisioningBindingDenied()


def action_comparison_digest(action: ProvisioningActionFacts) -> str:
    if type(action) is not ProvisioningActionFacts:
        raise ProvisioningBindingDenied()
    action.__post_init__()
    return _hash(b"DohaMusicPolicyActionComparisonV1", action)


def require_action_binding(*, action, policy, pin, confirmation) -> None:
    """Necessary full equality only; independent source authenticity is REQUIRED.

    No permission/receipt/witness returned; no stale-facts/live-handoff API exists.
    """
    action_comparison_digest(action)
    policy_snapshot_digest(policy)
    _pin(pin)
    if type(confirmation) is not InitializerConfirmationFacts:
        raise ProvisioningBindingDenied()
    confirmation.__post_init__()
    if action.policy != policy or action.confirmation != confirmation or confirmation.pin != pin:
        raise ProvisioningBindingDenied()


@dataclass(frozen=True, slots=True, repr=False)
class PolicyLineageFacts:
    """Complete bounded historical comparison; NOT authoritative current pointer.

    Existing private storage/history/high-water/authenticated source must be checked
    separately. A caller supplying an old valid history does NOT make it current.
    """

    anchor_id: str
    installation_id: str
    source_id: str
    actions: tuple[ProvisioningActionFacts, ...]
    statuses: tuple[str, ...]

    def __post_init__(self):
        for value in (self.anchor_id, self.installation_id, self.source_id):
            _text(value, require_uuid)
        if (
            type(self.actions) is not tuple
            or type(self.statuses) is not tuple
            or not 0 < len(self.actions) <= 256
            or len(self.actions) != len(self.statuses)
        ):
            raise ProvisioningBindingDenied()
        action_ids, provenance_ids, previous = set(), set(), None
        for index, (action, status) in enumerate(zip(self.actions, self.statuses, strict=True)):
            head = action_comparison_digest(action)
            if (
                type(status) is not str
                or status not in ("ACTIVE", "SUPERSEDED", "REVOKED")
                or (index < len(self.actions) - 1 and status == "ACTIVE")
                or action.policy.revision != index + 1
                or action.policy.installation_id != self.installation_id
                or action.policy.source_id != self.source_id
                or action.predecessor_digest != previous
                or action.action_id in action_ids
                or action.confirmation.provenance_id in provenance_ids
            ):
                raise ProvisioningBindingDenied()
            action_ids.add(action.action_id)
            provenance_ids.add(action.confirmation.provenance_id)
            previous = head


def require_current_lineage_matches(*, observed, expected) -> None:
    """Fresh external expectations must be independently supplied; NOT currentness."""
    for value in (observed, expected):
        if type(value) is not PolicyLineageFacts:
            raise ProvisioningBindingDenied()
        value.__post_init__()
    if observed != expected or observed.statuses[-1] != "ACTIVE":
        raise ProvisioningBindingDenied()


def require_successor_matches(*, previous, expected, successor) -> None:
    """Pure stale-CAS/prefix precondition; NOT actual storage CAS or admission.

    A future private transaction owner must independently validate full history and
    perform actual atomic CAS/immutable terminal append. No mutation occurs here.
    """
    require_current_lineage_matches(observed=previous, expected=expected)
    if type(successor) is not PolicyLineageFacts:
        raise ProvisioningBindingDenied()
    successor.__post_init__()
    if (
        successor.anchor_id != previous.anchor_id
        or successor.installation_id != previous.installation_id
        or successor.source_id != previous.source_id
        or len(successor.actions) != len(previous.actions) + 1
        or successor.actions[:-1] != previous.actions
        or successor.statuses[:-2] != previous.statuses[:-1]
        or successor.statuses[-2:] != ("SUPERSEDED", "ACTIVE")
    ):
        raise ProvisioningBindingDenied()
