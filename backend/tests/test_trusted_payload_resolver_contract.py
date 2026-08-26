"""Trusted Payload locator/issuer/resolver Foundation contract tests."""

from __future__ import annotations

import hashlib
import os
from dataclasses import MISSING, FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from backend.services.workspace.job_completion_service import ProviderOutput
from backend.storage import trusted_payload as trusted_payload_module
from backend.storage.artifact_resolver import (
    ArtifactStorageError,
    ArtifactStorageErrorCode,
)
from backend.storage.trusted_payload import (
    InMemoryTrustedPayloadRegistry,
    TrustedPayloadError,
    TrustedPayloadErrorCode,
    TrustedPayloadReference,
)

_FIXED_ID = UUID("12345678-1234-5678-1234-567812345678")
_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self) -> None:
        self.value = _NOW

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def staging_root(tmp_path: Path) -> Path:
    root = tmp_path / "trusted-staging"
    root.mkdir()
    return root


def _registry(
    staging_root: Path, *, clock: MutableClock | None = None
) -> InMemoryTrustedPayloadRegistry:
    return InMemoryTrustedPayloadRegistry(
        staging_root,
        clock=clock or MutableClock(),
        id_factory=lambda: _FIXED_ID,
    )


def _write_payload(root: Path, name: str = "result.txt") -> tuple[Path, bytes]:
    payload = "테스트 보컬 결과\n".encode()
    path = root / name
    path.write_bytes(payload)
    return path, payload


def _assert_code(
    error: pytest.ExceptionInfo[TrustedPayloadError], code: TrustedPayloadErrorCode
) -> None:
    assert error.value.code is code
    assert "trusted-staging" not in str(error.value)


def test_register_and_resolve_derives_stable_byte_metadata(staging_root: Path) -> None:
    path, payload = _write_payload(staging_root)
    registry = _registry(staging_root)

    reference = registry.register_trusted_payload(path, artifact_kind="lyrics_text")
    first = registry.resolve(reference)
    second = registry.resolve(reference)

    assert reference.locator_id == "payloadref:v1:12345678123456781234567812345678"
    assert reference.namespace == "payloadref"
    assert reference.version == 1
    assert reference.opaque_id == _FIXED_ID.hex
    assert str(staging_root) not in reference.locator_id
    assert path.name not in reference.locator_id
    assert reference.payload_checksum == hashlib.sha256(payload).hexdigest()
    assert first == second
    assert first.temporary_path == path.resolve()
    assert first.artifact_kind == "lyrics_text"
    assert first.media_type == "text/plain"
    assert first.size_bytes == len(payload)
    assert first.created_at == _NOW
    assert first.expires_at is None
    with pytest.raises(FrozenInstanceError):
        first.size_bytes = 0  # type: ignore[misc]


@pytest.mark.parametrize(
    "locator",
    [
        "",
        "../payload",
        r"..\payload",
        "%2e%2e/payload",
        "file:///tmp/payload",
        "https://example.test/payload",
        "s3://bucket/key",
        "data:text/plain,payload",
        r"C:\staging\payload.wav",
        "/tmp/payload.wav",
        "payloadref:v2:12345678123456781234567812345678",
        "payloadref:v1:token=12345678123456781234567812345678",
        "payloadref:v1:1234",
    ],
)
def test_reference_rejects_paths_uris_traversal_and_credentials(locator: str) -> None:
    with pytest.raises(TrustedPayloadError) as caught:
        TrustedPayloadReference(locator, "sha256", "0" * 64)
    _assert_code(caught, TrustedPayloadErrorCode.MALFORMED_REFERENCE)


def test_unknown_and_tampered_references_fail_closed(staging_root: Path) -> None:
    path, _ = _write_payload(staging_root)
    registry = _registry(staging_root)
    reference = registry.register_trusted_payload(path, artifact_kind="lyrics_text")
    unknown = TrustedPayloadReference(
        "payloadref:v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "sha256", "0" * 64
    )
    tampered = TrustedPayloadReference(reference.locator_id, "sha256", "f" * 64)

    with pytest.raises(TrustedPayloadError) as unknown_error:
        registry.resolve(unknown)
    _assert_code(unknown_error, TrustedPayloadErrorCode.UNKNOWN_REFERENCE)
    with pytest.raises(TrustedPayloadError) as tampered_error:
        registry.resolve(tampered)
    _assert_code(tampered_error, TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)


def test_outside_directory_and_missing_payloads_are_rejected(
    staging_root: Path, tmp_path: Path
) -> None:
    registry = _registry(staging_root)
    outside, _ = _write_payload(tmp_path, "outside.txt")

    with pytest.raises(TrustedPayloadError) as outside_error:
        registry.register_trusted_payload(outside, artifact_kind="lyrics_text")
    _assert_code(outside_error, TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT)
    with pytest.raises(TrustedPayloadError) as directory_error:
        registry.register_trusted_payload(staging_root, artifact_kind="lyrics_text")
    _assert_code(directory_error, TrustedPayloadErrorCode.PAYLOAD_NOT_REGULAR_FILE)
    with pytest.raises(TrustedPayloadError) as missing_error:
        registry.register_trusted_payload(staging_root / "missing.txt", artifact_kind="lyrics_text")
    _assert_code(missing_error, TrustedPayloadErrorCode.PAYLOAD_MISSING)


def test_symlink_escape_is_rejected(staging_root: Path, tmp_path: Path) -> None:
    outside, _ = _write_payload(tmp_path, "outside.txt")
    link = staging_root / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(TrustedPayloadError) as caught:
        _registry(staging_root).register_trusted_payload(link, artifact_kind="lyrics_text")
    _assert_code(caught, TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT)


def test_reported_reparse_point_is_rejected_without_path_disclosure(
    staging_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = _write_payload(staging_root)
    registry = _registry(staging_root)

    def reject_reparse(_root: Path, _candidate: Path) -> None:
        raise ArtifactStorageError(ArtifactStorageErrorCode.STORAGE_ESCAPE)

    monkeypatch.setattr(trusted_payload_module, "assert_safe_local_path", reject_reparse)
    with pytest.raises(TrustedPayloadError) as caught:
        registry.register_trusted_payload(path, artifact_kind="lyrics_text")
    _assert_code(caught, TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT)


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics regression")
@pytest.mark.parametrize(
    "candidate",
    [Path(r"Z:\outside\payload.txt"), Path(r"\\server\share\payload.txt")],
)
def test_windows_drive_and_unc_paths_outside_root_are_rejected(
    staging_root: Path, candidate: Path
) -> None:
    with pytest.raises(TrustedPayloadError) as caught:
        _registry(staging_root).register_trusted_payload(candidate, artifact_kind="lyrics_text")
    _assert_code(caught, TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT)


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics regression")
def test_windows_root_containment_is_case_insensitive(staging_root: Path) -> None:
    path, payload = _write_payload(staging_root)
    registry = _registry(staging_root)

    reference = registry.register_trusted_payload(
        Path(str(path).swapcase()), artifact_kind="lyrics_text"
    )

    assert registry.resolve(reference).payload_checksum == hashlib.sha256(payload).hexdigest()


def test_expiry_is_explicit_timezone_aware_and_fail_closed(staging_root: Path) -> None:
    path, _ = _write_payload(staging_root)
    clock = MutableClock()
    registry = _registry(staging_root, clock=clock)
    expires_at = _NOW + timedelta(minutes=5)
    reference = registry.register_trusted_payload(
        path, artifact_kind="lyrics_text", expires_at=expires_at
    )
    assert registry.resolve(reference).expires_at == expires_at

    clock.value = expires_at
    with pytest.raises(TrustedPayloadError) as expired_error:
        registry.resolve(reference)
    _assert_code(expired_error, TrustedPayloadErrorCode.EXPIRED_REFERENCE)

    with pytest.raises(TrustedPayloadError) as naive_error:
        _registry(staging_root).register_trusted_payload(
            path,
            artifact_kind="lyrics_text",
            expires_at=datetime(2026, 8, 21, 13, 0),
        )
    _assert_code(naive_error, TrustedPayloadErrorCode.INVALID_EXPIRY)


def test_mutation_replacement_and_cleanup_invalidate_reference(
    staging_root: Path,
) -> None:
    path, _ = _write_payload(staging_root)
    registry = _registry(staging_root)
    reference = registry.register_trusted_payload(path, artifact_kind="lyrics_text")

    path.write_text("changed", encoding="utf-8")
    with pytest.raises(TrustedPayloadError) as changed_error:
        registry.resolve(reference)
    _assert_code(changed_error, TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)

    path.unlink()
    path.write_text("테스트 보컬 결과\n", encoding="utf-8")
    with pytest.raises(TrustedPayloadError) as replacement_error:
        registry.resolve(reference)
    _assert_code(replacement_error, TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)

    path.unlink()
    with pytest.raises(TrustedPayloadError) as missing_error:
        registry.resolve(reference)
    _assert_code(missing_error, TrustedPayloadErrorCode.PAYLOAD_MISSING)


def test_each_registration_is_unique_and_collision_is_rejected(
    staging_root: Path,
) -> None:
    first, _ = _write_payload(staging_root, "first.txt")
    second, _ = _write_payload(staging_root, "second.txt")
    registry = _registry(staging_root)
    registry.register_trusted_payload(first, artifact_kind="lyrics_text")

    with pytest.raises(TrustedPayloadError) as caught:
        registry.register_trusted_payload(second, artifact_kind="lyrics_text")
    _assert_code(caught, TrustedPayloadErrorCode.DUPLICATE_REFERENCE)


def test_invalid_kind_and_credential_like_internal_path_are_rejected(
    staging_root: Path,
) -> None:
    path, _ = _write_payload(staging_root)
    credential_path, _ = _write_payload(staging_root, "token=do-not-store.txt")
    registry = _registry(staging_root)

    with pytest.raises(TrustedPayloadError) as kind_error:
        registry.register_trusted_payload(path, artifact_kind="provider_binary")
    _assert_code(kind_error, TrustedPayloadErrorCode.INVALID_ARTIFACT_KIND)
    with pytest.raises(TrustedPayloadError) as credential_error:
        registry.register_trusted_payload(credential_path, artifact_kind="lyrics_text")
    _assert_code(credential_error, TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT)

    user_info_path, _ = _write_payload(staging_root, "user:pass@host.txt")
    with pytest.raises(TrustedPayloadError) as user_info_error:
        registry.register_trusted_payload(user_info_path, artifact_kind="lyrics_text")
    _assert_code(user_info_error, TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT)


def test_configuration_and_non_regular_special_file_fail_closed(
    staging_root: Path,
) -> None:
    with pytest.raises(TrustedPayloadError) as config_error:
        InMemoryTrustedPayloadRegistry(None)
    _assert_code(config_error, TrustedPayloadErrorCode.CONFIGURATION_ERROR)

    if os.name == "nt":
        return
    fifo = staging_root / "payload.fifo"
    os.mkfifo(fifo)
    with pytest.raises(TrustedPayloadError) as fifo_error:
        _registry(staging_root).register_trusted_payload(fifo, artifact_kind="lyrics_text")
    _assert_code(fifo_error, TrustedPayloadErrorCode.PAYLOAD_NOT_REGULAR_FILE)


def test_completion_provider_output_keeps_required_temporary_path() -> None:
    temporary_path = next(
        field for field in fields(ProviderOutput) if field.name == "temporary_path"
    )
    assert temporary_path.default is MISSING
    assert temporary_path.default_factory is MISSING
