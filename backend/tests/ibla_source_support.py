"""Disposable independent ceremony/pins/custody only, never a production provider."""

import base64
import sys
from datetime import UTC, datetime, timedelta

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.bootstrap_authority.ibla.codec import encode_event
from backend.bootstrap_authority.ibla.contracts import Binding, Head
from backend.bootstrap_authority.ibla.source_codec import (
    ANCHOR_DOMAIN,
    ANCHOR_FIELDS,
    ARRAY_FIELDS,
    CONFIRMATION_DOMAIN,
    CONFIRMATION_FIELDS,
    INVENTORY_DOMAIN,
    MAPPING_DOMAIN,
    MAPPING_FIELDS,
    comparison,
)
from backend.bootstrap_authority.ibla.source_reader import (
    READERS,
    _CommissionedSource,
    _Role,
    custody_digest,
    custody_identities,
)
from backend.bootstrap_authority.ibla.source_verifier import _IblaSourceVerifier
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.source_custody import SourceCustodyPolicy
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.tests.ibla_support import keeper, ledger, uid


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def sign(private, domain, payload):
    return rfc8785.dumps(
        {"payload": payload, "signature": b64(private.sign(domain + rfc8785.dumps(payload)))}
    )


def payloads():
    root, initializer, proof = (Ed25519PrivateKey.generate() for _ in range(3))
    designation = b"Disposable accepted governance designation and initializer delegation only."
    ceremony = (
        b"Disposable independent complete scope/history/origin and custody action comparison."
    )
    a = {}
    for n, key in enumerate(sorted(ANCHOR_FIELDS), 1):
        if key.endswith(("_digest", "_fingerprint")):
            a[key] = digest(key.encode())
        elif key.endswith("_key_id") or key.endswith("_ref"):
            a[key] = "fixture-" + key.replace("_", "-")
        elif key.endswith("_id"):
            a[key] = uid(n)
    now = datetime.now(UTC).replace(microsecond=0)
    a.update(
        schema="dohamusic/ibla-commissioning-anchor/v1",
        algorithm="Ed25519",
        purpose="IBLA_COMMISSIONING_ONLY",
        authority_epoch=1,
        designation_digest=digest(designation),
        root_fingerprint=digest(root.public_key().public_bytes_raw()),
        initializer_fingerprint=digest(initializer.public_key().public_bytes_raw()),
        installation_proof_digest=digest(proof.public_key().public_bytes_raw()),
        issued_at=(now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        not_before=(now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=(now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    i = {
        key: a[key]
        for key in (
            "domain_id",
            "deployment_id",
            "lineage_id",
            "installation_id",
            "installation_proof_digest",
            "journal_id",
            "positive_origin_ref",
            "positive_origin_digest",
        )
    }
    i.update(
        schema="dohamusic/ibla-scope-inventory/v1",
        coverage_start_ref="fixture-coverage-start",
        coverage_start_digest=digest(designation),
        scopes=[
            {
                "installation_id": a["installation_id"],
                "workspace_id": uid(1000),
                "existing_owner_id": uid(1001),
            }
        ],
    )
    i.update({key: [] for key in ARRAY_FIELDS})
    a["inventory"] = i
    a["inventory_digest"] = comparison(INVENTORY_DOMAIN, i)
    a["commissioning_mapping_digest"] = comparison(
        MAPPING_DOMAIN, {key: a[key] for key in MAPPING_FIELDS}
    )
    c = {key: a[key] for key in CONFIRMATION_FIELDS if key in a}
    c.update(
        schema="dohamusic/ibla-initializer-confirmation/v1",
        purpose="IBLA_COMMISSIONING_CONFIRMATION_ONLY",
        confirmation_id=uid(2000),
        original_confirmation_ref="fixture-independent-original-confirmation",
        original_confirmation_digest=digest(ceremony),
        anchor_digest=comparison(ANCHOR_DOMAIN, a),
    )
    return a, c, root, initializer, proof, designation, ceremony


def native_fixture(tmp_path, *, stage="confirmed", transform=None, consumer=None, version=1):
    if sys.platform != "win32":
        pytest.skip("IBLA native held custody requires Windows; codec tests run independently")
    from backend.tests.test_designation_source_custody import (
        SYSTEM,
        acl,
        process_account,
        provision_fixture_acl,
    )

    a, c, root, initializer, proof, designation, ceremony = payloads()
    account = process_account()
    logical = (
        a["anchor_id"],
        c["confirmation_id"],
        a["designation_id"],
        a["commissioning_action_id"],
        a["domain_id"],
        a["ledger_id"],
        a["checkpoint_id"],
    )
    roles, paths = [], []
    for name, reader, logical_id in zip(
        ("anchor", "confirmation", "designation", "ceremony", "mapping", "ledger", "checkpoint"),
        READERS,
        logical,
        strict=True,
    ):
        directory = tmp_path / name
        directory.mkdir()
        path = directory / reader._fixed_name
        path.write_bytes(b"" if name in {"ledger", "checkpoint"} else b"fixture placeholder")
        provision_fixture_acl(directory, account)
        provision_fixture_acl(path, account)
        files, ids = _WindowsFactFiles(str(directory)), []
        for target, is_directory in ((directory, True), (path, False)):
            handle = files._open(str(target), directory=is_directory)
            try:
                ids.append(files._check(handle, str(target), directory=is_directory)[:2])
            finally:
                files._close([handle])
        policy = SourceCustodyPolicy(
            *ids, account[0], tuple(sorted((account[0], SYSTEM))), acl(account[0], SYSTEM)
        )
        roles.append(_Role(name, str(directory), logical_id, policy))
        paths.append(path)
    roles = tuple(roles)
    a["custody_provisioning_digest"] = custody_digest(roles, custody_identities(a))
    c["custody_provisioning_digest"] = a["custody_provisioning_digest"]
    c["anchor_digest"] = comparison(ANCHOR_DOMAIN, a)
    if transform:
        transform(a, c)
        a["inventory_digest"] = comparison(INVENTORY_DOMAIN, a["inventory"])
        a["commissioning_mapping_digest"] = comparison(
            MAPPING_DOMAIN, {key: a[key] for key in MAPPING_FIELDS}
        )
        for key in ("inventory_digest", "commissioning_mapping_digest"):
            c[key] = a[key]
        c["anchor_digest"] = comparison(ANCHOR_DOMAIN, a)
    paths[0].write_bytes(sign(root, ANCHOR_DOMAIN, a))
    paths[1].write_bytes(sign(initializer, CONFIRMATION_DOMAIN, c))
    paths[2].write_bytes(designation)
    paths[3].write_bytes(ceremony)
    b = Binding(
        **{
            key: c["anchor_digest"] if key == "anchor_digest" else a[key]
            for key in Binding.__dataclass_fields__
        }
    )
    for path, role in zip(paths[-2:], ("L", "H"), strict=True):
        # Preserve the independently recorded native identity, fixture-only initialize empty file.
        from backend.bootstrap_authority.ibla.schema import install_empty_store
        from backend.tests.ibla_support import engine

        e = engine(path)
        with e.begin() as connection:
            install_empty_store(connection, role=role, binding=b, version=version)
        e.dispose()
    wire = encode_event(
        b,
        event_id=uid(3000),
        operation_id=uid(3001),
        expected=Head(),
        kind="COMMISSION",
        evidence_digest=b.anchor_digest,
        recorded_at=a["issued_at"],
    )
    if stage != "empty":
        with keeper(*paths[-2:], binding=b, version=version) as h:
            h.prepare(wire, expected=h.read().head)
    if stage == "uncertain":
        from backend.bootstrap_authority.ibla.codec import parse_event

        event = parse_event(wire, b)
        with keeper(*paths[-2:], binding=b, version=version) as h:
            h.mark_uncertain(event.operation_id, event.fingerprint)
    if stage in {"appended", "confirmed"}:
        with ledger(paths[-2], binding=b, version=version) as ledger_writer:
            event = ledger_writer.append(wire, expected=Head())
    if stage == "confirmed":
        with keeper(*paths[-2:], binding=b, version=version) as h:
            h.confirm(event.operation_id, event.fingerprint)
    paths[4].write_bytes(
        rfc8785.dumps(
            {"payload": {key: a[key] for key in MAPPING_FIELDS}, "anchor_digest": b.anchor_digest}
        )
    )
    setup = _CommissionedSource(
        rfc8785.dumps(a),
        rfc8785.dumps(c),
        root.public_key().public_bytes_raw(),
        initializer.public_key().public_bytes_raw(),
        proof.public_key().public_bytes_raw(),
        digest(designation),
        digest(ceremony),
        rfc8785.dumps(
            {"payload": {key: a[key] for key in MAPPING_FIELDS}, "anchor_digest": b.anchor_digest}
        ),
        roles,
    )
    received = []
    verifier = _IblaSourceVerifier(
        setup,
        consumer=consumer or (lambda cap: (verifier.require_handoff(cap), received.append(cap))),
    )
    return verifier, proof, paths, received, setup, a, c, root, initializer, b


def verified(verifier, proof, context):
    return verifier.verify_source(context, b64(proof.sign(verifier.challenge(context))))
