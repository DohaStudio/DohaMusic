"""ADR-078 private-witness ports: production composition intentionally unavailable."""

from typing import Protocol


class CurrentnessUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("DEPLOYMENT_CURRENTNESS_UNAVAILABLE")


class ProvisionedVerifierReader(Protocol):
    def read_private_provisioning_witness(self) -> object: ...


class VerifierLifecycleAdmissionPort(Protocol):
    def admit_with_private_ceremony_witness(self, witness: object) -> None: ...


class CurrentVerifierRevalidationPort(Protocol):
    def revalidate_private_currentness_witness(self, witness: object) -> None: ...


class UnavailableCurrentnessPorts:
    """Never converts public metadata/receipts, test fakes or absent stores to permission."""

    def read_private_provisioning_witness(self) -> object:
        raise CurrentnessUnavailable()

    def admit_with_private_ceremony_witness(self, witness: object) -> None:
        raise CurrentnessUnavailable()

    def revalidate_private_currentness_witness(self, witness: object) -> None:
        raise CurrentnessUnavailable()
