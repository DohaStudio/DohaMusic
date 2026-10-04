"""Original-custody fact reconciliation. No mint, L append, repair or reset."""

from contextlib import contextmanager
from datetime import UTC, datetime

from backend.bootstrap_authority.approval_verifier import _timestamp
from backend.bootstrap_authority.contracts import require_digest, require_uuid
from backend.bootstrap_authority.ibla.contracts import IblaDenied, IblaInconsistent
from backend.bootstrap_authority.ibla.registration_owners import _Owners
from backend.bootstrap_authority.ibla.registration_writer import _result
from backend.bootstrap_authority.ibla.source_native import _DomainLease
from backend.bootstrap_authority.ibla.source_reader import _CommissionedSource, _HeldSource
from backend.bootstrap_authority.lifecycle_verifier import _read


class _OriginalReconciliationReader:
    def __init__(self, commissioned):
        if type(commissioned) is not _CommissionedSource:
            raise IblaDenied()
        self._setup = commissioned

    def __repr__(self):
        return "<IBLA original reconciliation reader>"

    @contextmanager
    def _held(self):
        a = _read(self._setup.accepted_anchor, 1048576, 8)
        c = _read(self._setup.accepted_confirmation, 16384, 8)
        source = _HeldSource(self._setup)
        try:
            with _DomainLease(a["domain_id"]).hold():
                try:
                    source.open(originals_only=True)
                    # Verify retained historical A/C signatures, not fresh PRE eligibility.
                    checked = max(_timestamp(a["not_before"]), _timestamp(c["not_before"]))
                    _, _, binding, _, _ = source._correlate(checked)
                    owner = _Owners(
                        source, binding, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                    )
                    yield owner
                finally:
                    source.close()
        except IblaDenied:
            raise
        except Exception:
            raise IblaDenied() from None

    def read(self, operation_id, fingerprint):
        self._arguments(operation_id, fingerprint)
        with self._held() as owner:
            lv, hv = owner.read()
            return _result(lv, hv, operation_id, fingerprint)

    def confirm_existing(self, operation_id, fingerprint):
        self._arguments(operation_id, fingerprint)
        with self._held() as owner:
            lv, hv = owner.read()
            result = _result(lv, hv, operation_id, fingerprint)
            if not result.post:
                raise IblaDenied()
            owner.checkpoint("confirm", operation_id, fingerprint)
            lv, hv = owner.read()
            return _result(lv, hv, operation_id, fingerprint)

    @staticmethod
    def _arguments(operation_id, fingerprint):
        try:
            if type(operation_id) is not str or type(fingerprint) is not str:
                raise ValueError()
            require_uuid(operation_id)
            require_digest(fingerprint)
        except (ValueError, TypeError):
            raise IblaInconsistent() from None
