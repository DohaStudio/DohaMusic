"""Public persistence conditions/results, NEVER first-registration capabilities."""

from dataclasses import asdict, dataclass

from backend.bootstrap_authority.contracts import require_digest, require_revision, require_uuid


class IblaDenied(RuntimeError):
    def __init__(self, code="IBLA_UNAVAILABLE"):
        super().__init__(code)


class IblaConflict(IblaDenied):
    def __init__(self):
        super().__init__("IBLA_CONFLICT")


class IblaInconsistent(IblaDenied):
    def __init__(self):
        super().__init__("IBLA_INCONSISTENT")


@dataclass(frozen=True, slots=True)
class Binding:
    domain_id: str
    anchor_id: str
    anchor_digest: str
    ledger_id: str
    checkpoint_id: str
    installation_id: str
    installation_proof_digest: str
    deployment_id: str
    lineage_id: str
    designation_digest: str
    authority_epoch: int

    def validate(self):
        if type(self) is not Binding:
            raise ValueError("BINDING")
        for key, value in asdict(self).items():
            if key == "authority_epoch":
                require_revision(value)
            elif type(value) is not str:
                raise ValueError("BINDING")
            elif key.endswith("_digest"):
                require_digest(value)
            else:
                require_uuid(value)
        if self.ledger_id == self.checkpoint_id:
            raise ValueError("BINDING")


@dataclass(frozen=True, slots=True)
class Head:
    revision: int = 0
    digest: str | None = None

    def validate(self):
        if type(self) is not Head or type(self.revision) is not int:
            raise ValueError("HEAD")
        if self.revision == 0:
            if self.digest is not None:
                raise ValueError("HEAD")
        else:
            require_revision(self.revision)
            if type(self.digest) is not str:
                raise ValueError("HEAD")
            require_digest(self.digest)


@dataclass(frozen=True, slots=True)
class Event:
    revision: int
    event_id: str
    operation_id: str
    fingerprint: str
    previous_digest: str | None
    digest: str
    kind: str
    envelope: bytes


@dataclass(frozen=True, slots=True)
class LedgerView:
    binding: Binding
    head: Head
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class CheckpointView:
    binding: Binding
    head: Head
    state: str
    confirmed: Head
    pending: bytes | None


class UnavailableIblaPersistence:
    """Only production entry point. No path/env/fixture fallback or initialization."""

    def open(self, *args, **kwargs):
        raise IblaDenied()
