"""Lease-bound private FILE facts transport only; NOT a provisioning witness issuer."""

from contextlib import contextmanager

from sqlalchemy.orm import Session

from backend.bootstrap_authority.pin_facts import PrivateFactsDenied, decode_pin_facts
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.bootstrap_authority.windows_serialization import (
    CeremonySerializationDenied,
    _WindowsCeremonySerialization,
)
from backend.bootstrap_authority.witness_lifetime import CurrentnessBinding, WitnessLifetimeDenied


class _PrivatePinFactsReader:
    """No production port/factory/automatic pinning/public repository fallback.

    Root comes from reviewed composition, NEVER request/config/env selection.
    File facts cannot prove private custody/designation/fresh possession/current
    authoritative journal. Those independent checks are still mandatory/unavailable.
    """

    def __init__(self, *, trusted_root: str, serialization: _WindowsCeremonySerialization):
        if type(serialization) is not _WindowsCeremonySerialization:
            raise PrivateFactsDenied()
        self._serialization = serialization
        self._files = _WindowsFactFiles(trusted_root)
        self._active_facts: dict[int, tuple] = {}

    def _require_open_facts(self, facts: object, *, lease: object, session: Session) -> None:
        """Original live FILE snapshot identity only, NOT private provenance proof."""
        active = self._active_facts.get(id(facts))
        if (
            active is None
            or active[0] is not facts
            or active[1] is not lease
            or active[2] is not session
        ):
            raise PrivateFactsDenied()
        self._serialization._require_live(lease, session=session, scopes=active[3].affected_scopes)

    @contextmanager
    def _open_facts(
        self,
        *,
        lease: object,
        session: Session,
        expected: CurrentnessBinding,
        installation_id: str,
        installation_proof_key_fingerprint: str,
    ):
        try:
            # Bind the original lease before caller comparison validation so ALL
            # subsequent denials abandon its witness, even malformed expectations.
            record = self._serialization._lookup(lease)
            try:
                if type(expected) is not CurrentnessBinding:
                    raise PrivateFactsDenied()
                expected.__post_init__()
                self._serialization._require_live(lease, session=session, scopes=record.scopes)
                with self._files._snapshot() as raw:
                    facts = decode_pin_facts(
                        raw,
                        expected=expected,
                        installation_id=installation_id,
                        installation_proof_key_fingerprint=installation_proof_key_fingerprint,
                    )
                    self._serialization._require_live(
                        lease, session=session, scopes=expected.affected_scopes
                    )
                    self._active_facts[id(facts)] = (facts, lease, session, facts.binding)
                    try:
                        yield facts
                    finally:
                        self._active_facts.pop(id(facts), None)
            finally:
                # Context exit (success/denial/exception) ends this snapshot's
                # witness usability. Keep native OS locks until caller Tx ends.
                self._serialization._lifetime._release_lease(lease)
        except (WitnessLifetimeDenied, CeremonySerializationDenied, OSError):
            raise PrivateFactsDenied() from None
