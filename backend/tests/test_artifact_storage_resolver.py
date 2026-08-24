"""Artifact Storage Resolver의 격리된 경로·파일 무결성 계약 검증."""

from __future__ import annotations

import inspect as python_inspect
import os
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

import backend.storage.artifact_resolver as resolver_module
from backend.core.config import Settings
from backend.models.workspace.storage import ArtifactStorageLocation
from backend.repositories.workspace import ArtifactStorageRepository
from backend.storage import (
    ArtifactStorageError,
    ArtifactStorageErrorCode,
    ArtifactStorageResolver,
    ArtifactStorageRoots,
)


class FakeArtifactStorageRepository:
    def __init__(self, location: ArtifactStorageLocation | None) -> None:
        self.location = location
        self.requested_ids: list[UUID] = []

    def get_storage_location(self, artifact_id: UUID) -> ArtifactStorageLocation | None:
        self.requested_ids.append(artifact_id)
        return self.location


def _roots(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    for domain in ("lm", "audio", "vocal", "music"):
        (root / domain).mkdir(parents=True)
    return root


def _location(
    artifact_id: UUID,
    *,
    backend: str = "local",
    domain: str = "music",
    key: str = "mixes/project/mix.wav",
    version: int = 1,
) -> ArtifactStorageLocation:
    return ArtifactStorageLocation(
        artifact_id=artifact_id,
        storage_backend=backend,
        storage_domain=domain,
        storage_key=key,
        locator_version=version,
    )


def _resolver(
    tmp_path: Path,
    *,
    backend: str = "local",
    domain: str = "music",
    key: str = "mixes/project/mix.wav",
    version: int = 1,
) -> tuple[UUID, Path, FakeArtifactStorageRepository, ArtifactStorageResolver]:
    artifact_id = uuid4()
    root = _roots(tmp_path)
    repository = FakeArtifactStorageRepository(
        _location(
            artifact_id,
            backend=backend,
            domain=domain,
            key=key,
            version=version,
        )
    )
    return (
        artifact_id,
        root,
        repository,
        ArtifactStorageResolver.from_base_root(repository, root),
    )


@pytest.mark.parametrize("domain", ["lm", "audio", "vocal", "music"])
def test_resolver_maps_each_approved_domain_inside_injected_root(
    tmp_path: Path, domain: str
) -> None:
    artifact_id, root, repository, resolver = _resolver(
        tmp_path, domain=domain, key="runs/2026/payload.bin"
    )
    payload = root / domain / "runs" / "2026" / "payload.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"doha")

    resolved = resolver.resolve(artifact_id)

    assert resolved.artifact_id == artifact_id
    assert resolved.path == payload.resolve(strict=True)
    assert resolved.size_bytes == 4
    assert resolved.storage_backend == "local"
    assert resolved.storage_domain == domain
    assert repository.requested_ids == [artifact_id]


def test_open_payload_reads_the_verified_descriptor(tmp_path: Path) -> None:
    artifact_id, root, _, resolver = _resolver(tmp_path)
    payload = root / "music" / "mixes" / "project" / "mix.wav"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"verified payload")

    with resolver.open_payload(artifact_id) as (resolved, stream):
        assert stream.read() == b"verified payload"
        assert resolved.size_bytes == len(b"verified payload")
        assert not stream.closed
    assert stream.closed


@pytest.mark.parametrize(
    ("backend", "domain", "version", "expected"),
    [
        ("s3", "music", 1, ArtifactStorageErrorCode.UNSUPPORTED_BACKEND),
        ("local", "private", 1, ArtifactStorageErrorCode.INVALID_DOMAIN),
        (
            "local",
            "music",
            2,
            ArtifactStorageErrorCode.UNSUPPORTED_LOCATOR_VERSION,
        ),
    ],
)
def test_resolver_rejects_unsupported_catalog_values(
    tmp_path: Path,
    backend: str,
    domain: str,
    version: int,
    expected: ArtifactStorageErrorCode,
) -> None:
    artifact_id, _, _, resolver = _resolver(
        tmp_path, backend=backend, domain=domain, version=version
    )

    with pytest.raises(ArtifactStorageError) as caught:
        resolver.resolve(artifact_id)
    assert caught.value.code is expected


def test_resolver_rejects_missing_catalog_row(tmp_path: Path) -> None:
    root = _roots(tmp_path)
    repository = FakeArtifactStorageRepository(None)
    resolver = ArtifactStorageResolver.from_base_root(repository, root)

    with pytest.raises(ArtifactStorageError) as caught:
        resolver.resolve(uuid4())
    assert caught.value.code is ArtifactStorageErrorCode.LOCATION_NOT_FOUND


@pytest.mark.parametrize(
    "key",
    [
        "",
        ".",
        "..",
        "../escape.wav",
        "runs/../escape.wav",
        "/absolute.wav",
        "\\absolute.wav",
        "C:/absolute.wav",
        "C:\\absolute.wav",
        "//server/share.wav",
        "file://payload.wav",
        "runs\\payload.wav",
        "runs//payload.wav",
        "runs/./payload.wav",
        "runs/payload.wav/",
        "%2e%2e/escape.wav",
        "runs/null\x00.wav",
        "runs/control\x1f.wav",
        "CON/payload.wav",
        "runs/payload.wav.",
        "runs/payload.wav ",
        "unapproved/payload.wav",
    ],
)
def test_resolver_rejects_noncanonical_or_unsafe_storage_keys(tmp_path: Path, key: str) -> None:
    artifact_id, _, _, resolver = _resolver(tmp_path, key=key)

    with pytest.raises(ArtifactStorageError) as caught:
        resolver.resolve(artifact_id)
    assert caught.value.code is ArtifactStorageErrorCode.INVALID_KEY


@pytest.mark.parametrize("target_kind", ["missing", "directory"])
def test_resolver_rejects_unavailable_or_non_file_payload(tmp_path: Path, target_kind: str) -> None:
    artifact_id, root, _, resolver = _resolver(tmp_path)
    target = root / "music" / "mixes" / "project" / "mix.wav"
    if target_kind == "directory":
        target.mkdir(parents=True)

    with pytest.raises(ArtifactStorageError) as caught:
        resolver.resolve(artifact_id)
    assert caught.value.code is ArtifactStorageErrorCode.CONTENT_UNAVAILABLE


def test_resolver_rejects_symlink_even_when_target_is_inside_root(
    tmp_path: Path,
) -> None:
    artifact_id, root, _, resolver = _resolver(tmp_path, key="mixes/link/payload.wav")
    real = root / "music" / "real"
    real.mkdir()
    (real / "payload.wav").write_bytes(b"inside")
    link = root / "music" / "mixes" / "link"
    link.parent.mkdir()
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"현재 환경에서 symlink 생성 권한이 없습니다: {error}")

    with pytest.raises(ArtifactStorageError) as caught:
        resolver.resolve(artifact_id)
    assert caught.value.code is ArtifactStorageErrorCode.STORAGE_ESCAPE


def test_resolver_rejects_symlink_escape_without_disclosing_path(
    tmp_path: Path,
) -> None:
    artifact_id, root, _, resolver = _resolver(tmp_path, key="mixes/outside/secret.wav")
    outside = tmp_path / "private"
    outside.mkdir()
    (outside / "secret.wav").write_bytes(b"secret")
    link = root / "music" / "mixes" / "outside"
    link.parent.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"현재 환경에서 symlink 생성 권한이 없습니다: {error}")

    with pytest.raises(ArtifactStorageError) as caught:
        resolver.resolve(artifact_id)
    assert caught.value.code is ArtifactStorageErrorCode.STORAGE_ESCAPE
    assert str(tmp_path) not in str(caught.value)
    assert "secret.wav" not in str(caught.value)


def test_resolver_fails_closed_when_a_component_is_reported_as_reparse_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_id, root, _, resolver = _resolver(tmp_path)
    payload = root / "music" / "mixes" / "project" / "mix.wav"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"payload")
    original = resolver_module._is_link_or_reparse

    def report_project_as_reparse(path: Path) -> bool:
        return path == payload.parent or original(path)

    monkeypatch.setattr(resolver_module, "_is_link_or_reparse", report_project_as_reparse)

    with pytest.raises(ArtifactStorageError) as caught:
        resolver.resolve(artifact_id)
    assert caught.value.code is ArtifactStorageErrorCode.STORAGE_ESCAPE


def test_open_payload_rejects_file_replaced_after_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_id, root, _, resolver = _resolver(tmp_path)
    payload = root / "music" / "mixes" / "project" / "mix.wav"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"first")
    stale = resolver.resolve(artifact_id)
    payload.unlink()
    payload.write_bytes(b"replacement")
    monkeypatch.setattr(resolver, "resolve", lambda _: stale)

    with (
        pytest.raises(ArtifactStorageError) as caught,
        resolver.open_payload(artifact_id),
    ):
        pass
    assert caught.value.code is ArtifactStorageErrorCode.CONTENT_UNAVAILABLE


def test_roots_fail_closed_when_configuration_is_missing_or_incomplete(
    tmp_path: Path,
) -> None:
    with pytest.raises(ArtifactStorageError) as missing:
        ArtifactStorageRoots.from_base_root(None)
    assert missing.value.code is ArtifactStorageErrorCode.CONFIGURATION_ERROR

    root = tmp_path / "incomplete"
    root.mkdir()
    with pytest.raises(ArtifactStorageError) as incomplete:
        ArtifactStorageRoots.from_base_root(root)
    assert incomplete.value.code is ArtifactStorageErrorCode.CONFIGURATION_ERROR


def test_artifact_root_configuration_treats_blank_as_unconfigured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert Settings(artifact_root="").artifact_root is None

    monkeypatch.setenv("DOHA_ARTIFACT_ROOT", str(tmp_path))
    assert Settings.from_environment().artifact_root == tmp_path


def test_resolved_payload_is_not_a_public_serialization_model(tmp_path: Path) -> None:
    artifact_id, root, _, resolver = _resolver(tmp_path)
    payload = root / "music" / "mixes" / "project" / "mix.wav"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"private path")

    resolved = resolver.resolve(artifact_id)

    assert not hasattr(resolved, "model_dump")
    assert replace(resolved).path == payload.resolve(strict=True)
    assert os.fspath(payload) not in str(ArtifactStorageErrorCode.INVALID_KEY)


def test_catalog_repository_is_read_only_and_returns_scalar_result() -> None:
    artifact_id = uuid4()
    location = _location(artifact_id)

    class ScalarOnlySession:
        def __init__(self) -> None:
            self.statement = None

        def scalar(self, statement):
            self.statement = statement
            return location

    session = ScalarOnlySession()
    repository = ArtifactStorageRepository(session)  # type: ignore[arg-type]

    assert repository.get_storage_location(artifact_id) is location
    assert session.statement is not None
    source = python_inspect.getsource(ArtifactStorageRepository)
    assert ".commit(" not in source
    assert ".rollback(" not in source
    assert "Path(" not in source
