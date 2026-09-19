"""Authenticated held authority source regression; never witness/admission tests."""

from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, replace
from uuid import UUID, uuid4

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy.orm import Session

from backend.bootstrap_authority.contracts import PinnedRootVerifier
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PIN_FACTS_SCHEMA, SCOPE_FIELDS
from backend.bootstrap_authority.private_pin_reader import _PrivatePinFactsReader
from backend.bootstrap_authority.provisioning_authority import (
    ExpectedProvisioningAuthorityScope,
)
from backend.bootstrap_authority.provisioning_authority_source import (
    SOURCE_FILE,
    SOURCE_SCHEMA,
    ExpectedProvisioningAuthoritySource,
    ProvisioningAuthoritySourceDenied,
    _decode_source,
    _ProvisioningAuthoritySourceSnapshots,
)
from backend.bootstrap_authority.windows_fact_files import PIN_FACTS_FILE, _WindowsFactFiles
from backend.bootstrap_authority.windows_serialization import _WindowsCeremonySerialization
from backend.bootstrap_authority.witness_lifetime import (
    CurrentnessBinding,
    _ProviderWitnessLifetime,
)
from backend.tests.test_bootstrap_pin_facts import INSTALLATION_FP
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_bootstrap_witness_lifetime import HEAD
from backend.tests.test_designation_source_custody import (
    process_account,
    provision_fixture_acl,
)
from backend.tests.test_designation_source_custody import (
    setup as custody_setup,
)
from backend.tests.test_provisioning_authority import _artifact, _payload


def uid(value):
    return str(UUID(int=value))


def authority(key, binding):
    expected = ExpectedProvisioningAuthorityScope(
        uid(10), binding.affected_scopes[0][0], "initializer/disposable-producer", digest(b"gov")
    )
    root = PinnedRootVerifier(
        binding.root_key_id,
        binding.designation_id,
        binding.deployment_owner_ref,
        binding.designation_record_digest,
        binding.root_fingerprint,
        binding.root_public_key,
    )
    return key, root, expected


def source_raw(authority_value, *, events=None, **changes):
    if events is None:
        events = (_artifact(authority_value, _payload(authority_value)),)
    value = {
        "schema": SOURCE_SCHEMA,
        "source_id": uid(20),
        "source_revision": len(events),
        "authorization_id": authority_value[2].authorization_id,
        "root_key_id": authority_value[1].root_key_id,
        "head_event_digest": digest(events[-1]),
        "events": [base64.urlsafe_b64encode(item).rstrip(b"=").decode() for item in events],
    }
    value.update(changes)
    return rfc8785.dumps(value), ExpectedProvisioningAuthoritySource(
        uid(20), len(events), digest(events[-1])
    )


@contextmanager
def root_fixture(tmp_path):
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public = key.public_key().public_bytes_raw()
    scopes = (tuple(str(uuid4()) for _ in range(3)),)
    binding = CurrentnessBinding(
        HEAD,
        HEAD,
        uid(2),
        digest(b"record"),
        "owner/test",
        scopes,
        HEAD.current_key_id,
        digest(public),
        public,
    )
    data = {
        "schema": PIN_FACTS_SCHEMA,
        "installation_id": scopes[0][0],
        "installation_proof_key_fingerprint": INSTALLATION_FP,
        "pin": asdict(binding.installed_pin),
        "designation_id": binding.designation_id,
        "designation_record_digest": binding.designation_record_digest,
        "deployment_owner_ref": binding.deployment_owner_ref,
        "affected_scopes": [dict(zip(SCOPE_FIELDS, scope, strict=True)) for scope in scopes],
        "root_key_id": binding.root_key_id,
        "root_fingerprint": binding.root_fingerprint,
        "root_public_key": base64.urlsafe_b64encode(public).rstrip(b"=").decode(),
        "status": binding.status,
        "domain": binding.domain,
    }
    (tmp_path / PIN_FACTS_FILE).write_bytes(rfc8785.dumps(data))
    lifetime = _ProviderWitnessLifetime()
    serialization = _WindowsCeremonySerialization(lifetime)
    reader = _PrivatePinFactsReader(trusted_root=str(tmp_path), serialization=serialization)
    with Session() as session:
        session.begin()
        lease = serialization._acquire(scopes=scopes, session=session)
        args = dict(
            lease=lease,
            session=session,
            expected=binding,
            installation_id=scopes[0][0],
            installation_proof_key_fingerprint=INSTALLATION_FP,
        )
        try:
            yield (reader, args), key, binding
        finally:
            session.rollback()
            serialization._release(lease)
            reader._files._cleanup_failed_snapshots()


def setup_source(tmp_path, fx, raw):
    designation, _, owner_text, policy = custody_setup(fx, tmp_path)
    path = tmp_path / SOURCE_FILE
    path.write_bytes(raw)
    account = process_account()
    provision_fixture_acl(path, account)
    files = _WindowsFactFiles(str(tmp_path))
    handle = files._open(str(path), directory=False)
    try:
        identity = files._check(handle, str(path), directory=False)[:2]
    finally:
        files._close([handle])
    source_policy = replace(policy, record_identity=identity)
    reader = _ProvisioningAuthoritySourceSnapshots(
        trusted_root=str(tmp_path),
        designation_snapshots=designation,
        source_policy=source_policy,
    )
    return reader, designation, path, owner_text, source_policy


def test_strict_source_codec_binds_expected_head_scope_and_active_lifecycle():
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public = key.public_key().public_bytes_raw()
    binding = CurrentnessBinding(
        HEAD,
        HEAD,
        uid(2),
        digest(b"record"),
        "owner/test",
        ((uid(1), uid(2), uid(3)),),
        HEAD.current_key_id,
        digest(public),
        public,
    )
    auth = authority(key, binding)
    raw, expected = source_raw(auth)
    receipt = _decode_source(raw, expected_source=expected, expected_scope=auth[2], root=auth[1])
    assert receipt.lifecycle_state == "ACTIVE"
    for changed in (
        {"source_revision": True},
        {"authorization_id": uid(999)},
        {"root_key_id": "root/other"},
        {"head_event_digest": digest(b"fork")},
    ):
        bad, _ = source_raw(auth, **changed)
        with pytest.raises((ValueError, ProvisioningAuthoritySourceDenied)):
            _decode_source(bad, expected_source=expected, expected_scope=auth[2], root=auth[1])
    empty = json.loads(raw)
    empty["events"] = []
    with pytest.raises(ValueError):
        _decode_source(
            rfc8785.dumps(empty),
            expected_source=expected,
            expected_scope=auth[2],
            root=auth[1],
        )


def test_strict_codec_rejects_noncanonical_duplicate_malformed_and_is_parallel_deterministic():
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public = key.public_key().public_bytes_raw()
    binding = CurrentnessBinding(
        HEAD,
        HEAD,
        uid(2),
        digest(b"record"),
        "owner/test",
        ((uid(1), uid(2), uid(3)),),
        HEAD.current_key_id,
        digest(public),
        public,
    )
    auth = authority(key, binding)
    raw, expected = source_raw(auth)

    def verify():
        return _decode_source(raw, expected_source=expected, expected_scope=auth[2], root=auth[1])

    with ThreadPoolExecutor(8) as pool:
        assert (
            len({item.head_event_digest for item in pool.map(lambda _: verify(), range(32))}) == 1
        )
    for malformed in (
        b"",
        b"\xff",
        b"{}",
        b'{"schema":"a","schema":"b"}',
        json.dumps(json.loads(raw), indent=2).encode(),
        b"x" * 1_048_577,
    ):
        with pytest.raises((ValueError, UnicodeError)):
            _decode_source(
                malformed,
                expected_source=expected,
                expected_scope=auth[2],
                root=auth[1],
            )


@pytest.mark.parametrize("attack", ["replacement", "scope", "transaction", "revoked"])
def test_native_source_read_verify_reread_and_stale_reuse_denial(tmp_path, attack):
    if not native():
        return
    with root_fixture(tmp_path) as (fx, key, binding):
        auth = authority(key, binding)
        events = (_artifact(auth, _payload(auth)),)
        if attack == "revoked":
            revoke = _payload(
                auth,
                revision=2,
                previous=digest(events[0]),
                kind="REVOKE",
                old_id="provisioner/key-v1",
                old_fingerprint=digest(b"verifier v1"),
                new_id=None,
                new_fingerprint=None,
            )
            events += (_artifact(auth, revoke),)
        raw, expected = source_raw(auth, events=events)
        reader, designation, path, _, _ = setup_source(tmp_path, fx, raw)
        args = fx[1]
        with (
            fx[0]._open_facts(**args) as facts,
            designation._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as designation_handle,
        ):
            open_args = dict(
                designation_handle=designation_handle,
                lease=args["lease"],
                session=args["session"],
                pin_facts=facts,
                expected_source=expected,
                expected_scope=auth[2],
            )
            if attack == "revoked":
                with (
                    pytest.raises(ProvisioningAuthoritySourceDenied),
                    reader._open_source(**open_args),
                ):
                    pytest.fail("revoked authority became a usable source")
                return
            with reader._open_source(**open_args) as handle:
                reader._require_open(handle, **open_args)
                if attack == "replacement":
                    with pytest.raises(OSError):
                        path.write_bytes(raw)
                    bad = replace(expected, head_event_digest=digest(b"other"))
                    open_args["expected_source"] = bad
                elif attack == "scope":
                    open_args["expected_scope"] = replace(auth[2], producer_ref="producer/other")
                else:
                    args["session"].rollback()
                    args["session"].begin()
                with pytest.raises(ProvisioningAuthoritySourceDenied):
                    reader._require_open(handle, **open_args)
                with pytest.raises(ProvisioningAuthoritySourceDenied):
                    reader._require_open(handle, **open_args)
        assert not reader._records


def test_source_result_is_opaque_and_not_authority():
    for target in (ExpectedProvisioningAuthoritySource, ProvisioningAuthoritySourceDenied):
        for attribute in ("admit", "authorize", "currentness_witness", "verify_confirmation"):
            assert not hasattr(target, attribute)
