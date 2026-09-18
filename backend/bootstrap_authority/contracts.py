"""Public verifier inputs and non-authorizing integrity receipts; no private key storage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from backend.authentication.contracts import require_safe_reference

SHA256_REFERENCE = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_SAFE_REVISION = (1 << 53) - 1


def require_uuid(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError("INVALID_UUID")
    try:
        canonical = str(UUID(value))
    except ValueError:
        raise ValueError("INVALID_UUID") from None
    if value != canonical:
        raise ValueError("INVALID_UUID")


def require_digest(value: object) -> None:
    if not isinstance(value, str) or not SHA256_REFERENCE.fullmatch(value):
        raise ValueError("INVALID_SHA256_REFERENCE")


def require_reference(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError("INVALID_REFERENCE")
    require_safe_reference(value, "reference")


def require_revision(value: object) -> None:
    if type(value) is not int or not 1 <= value <= MAX_SAFE_REVISION:
        raise ValueError("INVALID_REVISION")


@dataclass(frozen=True, slots=True)
class PinnedRootVerifier:
    """Public material supplied by trusted composition, NOT proof of provisioning/status.

    A caller can construct this value. Future trusted initialization must independently
    establish designation/key provenance and revalidate current root eligibility.
    Never load this value from the approval envelope, request or untrusted application DB.
    """

    root_key_id: str
    designation_id: str
    deployment_owner_ref: str
    designation_digest: str
    public_key_fingerprint: str
    public_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        require_reference(self.root_key_id)
        require_uuid(self.designation_id)
        require_reference(self.deployment_owner_ref)
        require_digest(self.designation_digest)
        require_digest(self.public_key_fingerprint)
        if type(self.public_key) is not bytes or len(self.public_key) != 32:
            raise ValueError("INVALID_PUBLIC_VERIFIER")


@dataclass(frozen=True, slots=True)
class ExpectedApprovalScope:
    """Independent exact issuance scope, NOT a claim/principal or possession proof."""

    approval_id: str
    installation_id: str
    installation_proof_key_fingerprint: str
    workspace_id: str
    existing_owner_id: str
    assignment_id: str
    assignment_revision: int
    custodian_ref: str
    custodian_proof_key_fingerprint: str
    governance_provenance_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.approval_id,
            self.installation_id,
            self.workspace_id,
            self.existing_owner_id,
            self.assignment_id,
        ):
            require_uuid(value)
        for value in (
            self.installation_proof_key_fingerprint,
            self.custodian_proof_key_fingerprint,
            self.governance_provenance_digest,
        ):
            require_digest(value)
        require_reference(self.custodian_ref)
        require_revision(self.assignment_revision)


@dataclass(frozen=True, slots=True)
class ApprovalIntegrityReceipt:
    """Historical mathematical check only; never a capability/current eligibility fact.

    Replaying this receipt cannot consume claims, bind principals, issue Rights or prove
    a root/approval/assignment is still active. It has no authorization/witness API.
    """

    approval_id: str
    assignment_id: str
    assignment_revision: int
    payload_digest: str
    checked_at: datetime
    expires_at: datetime
