"""ADR-075 fact mappings; these entities do not authorize any caller."""

from backend.db.base import Base
from backend.db.vocal_rights_schema_v1 import define_tables, register_integrity
from backend.db.vocal_rights_scope_guard_integrity_v2 import register_scope_guard_integrity

_tables = define_tables(Base.metadata)
register_integrity(Base.metadata)
register_scope_guard_integrity(Base.metadata)


class VocalRightsScopeGuard(Base):
    __tablename__ = "vocal_rights_scope_guards"
    __table__ = _tables["vocal_rights_scope_guards"]


class VocalRightsSubject(Base):
    __tablename__ = "vocal_rights_subjects"
    __table__ = _tables["vocal_rights_subjects"]


class VocalRightsCurrentAuthority(Base):
    __tablename__ = "vocal_rights_current_authorities"
    __table__ = _tables["vocal_rights_current_authorities"]


class VocalRightsEvidence(Base):
    __tablename__ = "vocal_rights_evidence"
    __table__ = _tables["vocal_rights_evidence"]


class VocalRightsEvidenceScope(Base):
    __tablename__ = "vocal_rights_evidence_scopes"
    __table__ = _tables["vocal_rights_evidence_scopes"]


class VocalRightsEvidenceGuard(Base):
    __tablename__ = "vocal_rights_evidence_guards"
    __table__ = _tables["vocal_rights_evidence_guards"]


class VocalRightsEvidenceWithdrawal(Base):
    __tablename__ = "vocal_rights_evidence_withdrawals"
    __table__ = _tables["vocal_rights_evidence_withdrawals"]


class VocalRightsGrant(Base):
    __tablename__ = "vocal_rights_grants"
    __table__ = _tables["vocal_rights_grants"]


class VocalRightsEvent(Base):
    __tablename__ = "vocal_rights_events"
    __table__ = _tables["vocal_rights_events"]


class VocalCompletionRightsReceipt(Base):
    __tablename__ = "vocal_completion_rights_receipts"
    __table__ = _tables["vocal_completion_rights_receipts"]


class VocalCompletionRightsReceiptItem(Base):
    __tablename__ = "vocal_completion_rights_receipt_items"
    __table__ = _tables["vocal_completion_rights_receipt_items"]


VOCAL_RIGHTS_ENTITY_CLASSES = (
    VocalRightsScopeGuard,
    VocalRightsSubject,
    VocalRightsCurrentAuthority,
    VocalRightsEvidence,
    VocalRightsEvidenceScope,
    VocalRightsEvidenceGuard,
    VocalRightsEvidenceWithdrawal,
    VocalRightsGrant,
    VocalRightsEvent,
    VocalCompletionRightsReceipt,
    VocalCompletionRightsReceiptItem,
)
