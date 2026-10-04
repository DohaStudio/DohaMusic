"""Independent disposable R/Q/delegation provisioning; never production setup."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import rfc8785

from backend.bootstrap_authority.ibla.registration_codec import (
    CONFIRMATION_DOMAIN,
    INTENT_DOMAIN,
    PURPOSE,
    SCOPE_DOMAIN,
)
from backend.bootstrap_authority.ibla.registration_source import (
    READERS,
    ROLES,
    _RegistrationOriginals,
)
from backend.bootstrap_authority.ibla.registration_writer import _RegistrationCommitWriter
from backend.bootstrap_authority.ibla.source_codec import CONFIRMATION_DOMAIN as C_DOMAIN
from backend.bootstrap_authority.ibla.source_codec import comparison
from backend.bootstrap_authority.ibla.source_reader import _Role
from backend.bootstrap_authority.ibla.source_verifier import _IblaSourceVerifier
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.source_custody import SourceCustodyPolicy
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.tests.ibla_source_support import native_fixture, sign
from backend.tests.ibla_support import keeper, uid


def registration_fixture(tmp_path, *, transform=None, version=2):
    _, proof, paths, _, setup, a, c, root, initializer, binding = native_fixture(
        tmp_path, version=version
    )
    with keeper(*paths[-2:], binding=binding, version=version) as repo:
        hv = repo.read()
    now = datetime.now(UTC).replace(microsecond=0)
    start, end = now - timedelta(seconds=30), now + timedelta(minutes=30)

    def fmt(t):
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    r = dict(
        schema="dohamusic/ibla-registration-intent/v1",
        purpose=PURPOSE,
        registration_id=uid(4000),
        operation_id=uid(4001),
        binding=asdict(binding),
        inventory_digest=a["inventory_digest"],
        registration_scope_digest=comparison(SCOPE_DOMAIN, a["inventory"]["scopes"]),
        intended_journal_id=a["journal_id"],
        expected_l_head=asdict(hv.confirmed),
        expected_h_head=asdict(hv.head),
        expected_h_confirmed=asdict(hv.confirmed),
        writer_ref=a["ledger_custodian_ref"],
        initializer_ref=a["initializer_ref"],
        root_key_id=a["root_key_id"],
        initializer_key_id=a["initializer_key_id"],
        positive_origin_digest=a["positive_origin_digest"],
        commissioning_confirmation_digest=comparison(C_DOMAIN, c),
        issued_at=fmt(start),
        expires_at=fmt(end),
        recorded_at=fmt(start),
    )
    original = b"Independent disposable initializer registration acceptance, not commissioning."
    delegation = (
        b"Independent accepted current exact root/initializer/registry custodian delegation."
    )
    q = dict(
        schema="dohamusic/ibla-registration-confirmation/v1",
        purpose="IBLA_REGISTRATION_CONFIRMATION_ONLY",
        intent_digest=comparison(INTENT_DOMAIN, r),
        initializer_ref=a["initializer_ref"],
        initializer_key_id=a["initializer_key_id"],
        original_confirmation_ref="fixture-registration-original",
        original_confirmation_digest=digest(original),
        issued_at=fmt(start),
        expires_at=fmt(end),
    )
    if transform:
        original_intent_digest = q["intent_digest"]
        transform(r, q)
        if q["intent_digest"] == original_intent_digest:
            q["intent_digest"] = comparison(INTENT_DOMAIN, r)
    from backend.tests.test_designation_source_custody import (
        SYSTEM,
        acl,
        process_account,
        provision_fixture_acl,
    )

    account = process_account()
    roles, extras = [], []
    for name, reader, raw in zip(
        ROLES,
        READERS,
        (
            sign(root, INTENT_DOMAIN, r),
            sign(initializer, CONFIRMATION_DOMAIN, q),
            original,
            delegation,
        ),
        strict=True,
    ):
        directory = tmp_path / name
        directory.mkdir()
        path = directory / reader._fixed_name
        path.write_bytes(raw)
        for target in (directory, path):
            provision_fixture_acl(target, account)
        files, identities = _WindowsFactFiles(str(directory)), []
        for target, is_directory in ((directory, True), (path, False)):
            handle = files._open(str(target), directory=is_directory)
            try:
                identities.append(files._check(handle, str(target), directory=is_directory)[:2])
            finally:
                files._close([handle])
        policy = SourceCustodyPolicy(
            *identities, account[0], tuple(sorted((account[0], SYSTEM))), acl(account[0], SYSTEM)
        )
        roles.append(_Role(name, str(directory), uid(5000 + len(roles)), policy))
        extras.append(path)
    originals = _RegistrationOriginals(
        rfc8785.dumps(r),
        rfc8785.dumps(q),
        "fixture-registration-original",
        digest(original),
        digest(delegation),
        start,
        end,
        a["ledger_custodian_ref"],
        a["initializer_ref"],
        a["root_key_id"],
        a["initializer_key_id"],
        tuple(roles),
    )
    writer = _RegistrationCommitWriter(originals)
    verifier = _IblaSourceVerifier(setup, consumer=writer)
    return verifier, proof, paths, extras, setup, originals, writer, r, q, binding
