"""Storage containment remains stable while publication creates parent directories."""

from __future__ import annotations

import ntpath
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import Barrier, Event, get_ident
from uuid import uuid4

import pytest

from backend.storage.artifact_publisher import (
    ArtifactPublishError,
    ArtifactPublishErrorCode,
    PublicationOutcome,
    TrustedPublicationIdentity,
)
from backend.storage.artifact_resolver import (
    ArtifactStorageError,
    ArtifactStorageErrorCode,
    ArtifactStorageRoots,
    _storage_relative_path,
)
from backend.tests.test_artifact_publish_or_adopt import _publish, _publisher, _stage, _wav


@pytest.mark.skipif(os.name != "nt", reason="native Windows realpath interleaving")
def test_parent_creation_during_native_resolution_keeps_candidate_identity(tmp_path, monkeypatch):
    for domain in ("lm", "audio", "vocal", "music"):
        (tmp_path / domain).mkdir()
    roots = ArtifactStorageRoots.from_base_root(tmp_path)
    target = roots.roots["music"] / "runs" / "new-parent" / "payload.json"
    missing_parent = Event()
    parent_created = Event()
    original = ntpath._getfinalpathname
    errors = []

    def observe_native_lookup(value):
        try:
            return original(value)
        except OSError as error:
            if Path(value) == target:
                errors.append(error.winerror)
                if not missing_parent.is_set():
                    missing_parent.set()
                    assert parent_created.wait(10), "parent creation not released"
            raise

    monkeypatch.setattr(ntpath, "_getfinalpathname", observe_native_lookup)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(roots.candidate_path, "music", "runs/new-parent/payload.json")
        try:
            assert missing_parent.wait(10), "native lookup did not reach missing parent"
            target.parent.mkdir(parents=True)
        finally:
            parent_created.set()
        actual = future.result(timeout=10)
    assert actual == target
    assert errors[0] == 3  # ERROR_PATH_NOT_FOUND before the other publisher creates parents.
    assert 2 in errors[1:]  # ERROR_FILE_NOT_FOUND after parents exist; no fake OS error.
    assert not target.exists()


@pytest.mark.parametrize(
    ("candidate", "root"),
    [
        (r"C:\store\runs\item", r"C:\store"),
        (r"\\?\C:\store\runs\item", r"C:\store"),
        (r"C:\store\runs\item", r"\\?\C:\store"),
        (r"\\?\c:\STORE\runs\item", "C:/store/"),
        (r"\\?\UNC\host\share\store\runs\item", r"\\host\share\store"),
        (r"\\host\share\store\runs\item", r"\\?\UNC\host\share\store"),
    ],
)
def test_equivalent_native_anchors_have_one_relative_identity(candidate, root):
    assert _storage_relative_path(PureWindowsPath(candidate), PureWindowsPath(root)) == (
        PureWindowsPath("runs/item")
    )


@pytest.mark.parametrize(
    "candidate",
    [
        r"\\?\D:\store\runs\item",
        r"\\?\C:\store-other\runs\item",
        r"\\?\UNC\host\share\store\runs\item",
        r"\\.\C:\store\runs\item",
        r"\\?\Volume{other}\store\runs\item",
        r"C:store\runs\item",
        r"store\runs\item",
    ],
)
def test_other_drive_root_device_and_relative_paths_do_not_alias(candidate):
    with pytest.raises(ValueError):
        _storage_relative_path(PureWindowsPath(candidate), PureWindowsPath(r"C:\store"))


def test_posix_identity_keeps_case_and_root_boundaries():
    root = PurePosixPath("/store")
    assert _storage_relative_path(root / "runs/item", root) == PurePosixPath("runs/item")
    for other in ("/STORE/runs/item", "/store-other/runs/item", "store/runs/item"):
        with pytest.raises(ValueError):
            _storage_relative_path(PurePosixPath(other), root)


@pytest.mark.parametrize(
    "key",
    [r"\\?\C:\store\file", r"\\?\UNC\host\share\file", r"C:relative", "file:///store/file"],
)
def test_comparison_projection_does_not_admit_native_paths_as_storage_keys(tmp_path, key):
    publisher, _ = _publisher(tmp_path)
    with pytest.raises(ArtifactStorageError) as caught:
        publisher.artifact_roots.candidate_path("music", key)
    assert caught.value.code is ArtifactStorageErrorCode.INVALID_KEY
    assert key not in str(caught.value)


@pytest.mark.skipif(os.name != "nt", reason="native Windows publication interleaving")
def test_two_publishers_converge_across_parent_creation(tmp_path, monkeypatch):
    publisher, staging = _publisher(tmp_path)
    content = _wav()
    identity = TrustedPublicationIdentity.for_wav_export(uuid4())
    target = publisher.artifact_roots.roots["music"].joinpath(*identity.storage_key.split("/"))
    first_source = _stage(staging, "first.wav", content)
    second_source = _stage(staging, "second.wav", content)
    missing_parent, parent_created, release_second = Event(), Event(), Event()
    first_thread = []
    original_lookup, original_link = ntpath._getfinalpathname, os.link
    errors = []

    def observe_native_lookup(value):
        try:
            return original_lookup(value)
        except OSError as error:
            if first_thread and get_ident() == first_thread[0] and Path(value) == target:
                errors.append(error.winerror)
                if not missing_parent.is_set():
                    missing_parent.set()
                    assert parent_created.wait(10), "second publisher did not create parents"
            raise

    def pause_second_link(source, destination, **kwargs):
        if get_ident() != first_thread[0] and Path(destination) == target:
            parent_created.set()
            assert release_second.wait(10), "second publisher not released"
        return original_link(source, destination, **kwargs)

    def first_publish():
        first_thread.append(get_ident())
        return _publish(publisher, first_source, identity, content)

    monkeypatch.setattr(ntpath, "_getfinalpathname", observe_native_lookup)
    monkeypatch.setattr(os, "link", pause_second_link)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_publish)
        try:
            assert missing_parent.wait(10), "first publisher did not reach native lookup"
            second = pool.submit(_publish, publisher, second_source, identity, content)
            created = first.result(timeout=10)
        finally:
            release_second.set()
            parent_created.set()
        adopted = second.result(timeout=10)
    assert errors[0] == 3 and 2 in errors[1:]
    assert created.outcome is PublicationOutcome.PUBLISHED_NEW
    assert adopted.outcome is PublicationOutcome.ADOPTED_EXISTING
    assert created.path == adopted.path == target
    assert created.file_identity == adopted.file_identity
    assert target.read_bytes() == content


@pytest.mark.parametrize("same_target", [True, False])
def test_real_competing_bytes_conflict_but_independent_targets_succeed(tmp_path, same_target):
    publisher, staging = _publisher(tmp_path)
    contents = (_wav(), _wav()[:-4] + b"\x01\x00\x01\x00")
    first = TrustedPublicationIdentity.for_wav_export(uuid4())
    identities = (
        first,
        first if same_target else TrustedPublicationIdentity.for_wav_export(uuid4()),
    )
    sources = tuple(
        _stage(staging, f"input-{i}.wav", content) for i, content in enumerate(contents)
    )
    start = Barrier(2)

    def publish(index):
        start.wait(timeout=10)
        try:
            return _publish(publisher, sources[index], identities[index], contents[index])
        except ArtifactPublishError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(publish, range(2)))
    failures = [item for item in results if isinstance(item, ArtifactPublishError)]
    successes = [item for item in results if not isinstance(item, ArtifactPublishError)]
    if same_target:
        assert len(successes) == len(failures) == 1
        assert failures[0].code is ArtifactPublishErrorCode.PUBLICATION_INTEGRITY_MISMATCH
        assert successes[0].path.read_bytes() in contents
    else:
        assert not failures and len(successes) == 2
        assert successes[0].path != successes[1].path
        assert tuple(item.path.read_bytes() for item in successes) == contents
