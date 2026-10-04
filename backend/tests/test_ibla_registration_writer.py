"""Actual held originals/native custody/SQLite one-shot registration."""

import pytest

from backend.bootstrap_authority.ibla.contracts import IblaConflict, IblaDenied
from backend.bootstrap_authority.ibla.registration_reconciliation import (
    _OriginalReconciliationReader,
)
from backend.tests.ibla_registration_support import registration_fixture
from backend.tests.ibla_source_support import verified
from backend.tests.ibla_support import ledger


@pytest.mark.parametrize(
    "field",
    [
        "writer_ref",
        "initializer_ref",
        "root_key_id",
        "initializer_key_id",
        "inventory_digest",
        "registration_scope_digest",
        "positive_origin_digest",
        "commissioning_confirmation_digest",
        "intended_journal_id",
    ],
)
def test_independently_signed_wrong_authority_denied(tmp_path, field):
    from backend.bootstrap_authority.lifecycle_verifier import digest
    from backend.tests.ibla_support import uid

    def wrong(r, q):
        r[field] = (
            digest(b"wrong")
            if field.endswith("digest")
            else (uid(9999) if field == "intended_journal_id" else "different-delegate")
        )

    v, proof, paths, *_ = registration_fixture(tmp_path, transform=wrong)
    before = tuple(p.read_bytes() for p in paths)
    with pytest.raises(IblaDenied), v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    assert before == tuple(p.read_bytes() for p in paths)


def test_generic_append_has_no_registration_authority(tmp_path):
    v, proof, paths, _, _, _, _, _, _, binding = registration_fixture(tmp_path)
    with v.observe() as context:
        result = v.handoff(v.mint(verified(v, proof, context)))
    with ledger(paths[-2], binding=binding, version=2) as repo:
        from backend.bootstrap_authority.ibla.contracts import Head
        from backend.bootstrap_authority.ibla.registration_codec import parse_event

        e = parse_event(result.envelope, binding)
        with pytest.raises(IblaDenied):
            repo.append(e.envelope, expected=Head(1, e.previous_digest))
    with pytest.raises(IblaDenied), ledger(paths[-2], readonly=True, binding=binding) as repo:
        repo.read()


@pytest.mark.parametrize("field", ["expected_l_head", "expected_h_head", "expected_h_confirmed"])
def test_exact_expected_head_cannot_be_replaced(tmp_path, field):
    from backend.bootstrap_authority.lifecycle_verifier import digest

    def wrong(r, q):
        r[field] = {"revision": 1, "digest": digest(b"unexpected head")}

    v, proof, paths, *_ = registration_fixture(tmp_path, transform=wrong)
    before = tuple(p.read_bytes() for p in paths)
    with pytest.raises(IblaDenied), v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    assert before == tuple(p.read_bytes() for p in paths)


@pytest.mark.parametrize(
    "field",
    [
        "intent_digest",
        "initializer_ref",
        "initializer_key_id",
        "original_confirmation_ref",
        "original_confirmation_digest",
        "issued_at",
        "expires_at",
    ],
)
def test_q_independent_registration_acceptance(tmp_path, field):
    from backend.bootstrap_authority.lifecycle_verifier import digest

    def wrong(r, q):
        q[field] = (
            "2099-01-01T00:00:00Z"
            if field.endswith("_at")
            else digest(b"wrong")
            if field.endswith("digest")
            else "wrong-independent-original"
        )

    v, proof, paths, *_ = registration_fixture(tmp_path, transform=wrong)
    before = tuple(p.read_bytes() for p in paths)
    with pytest.raises(IblaDenied), v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    assert before == tuple(p.read_bytes() for p in paths)


def test_registration_durable_post_and_independent_confirm(tmp_path):
    v, proof, paths, _, setup, _, writer, _, _, binding = registration_fixture(tmp_path)
    with v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        result = v.handoff(cap)
        assert result.post and result.current_h_state == "CONFIRMED"
        with pytest.raises(IblaConflict):
            v.handoff(cap)
        with pytest.raises(IblaDenied):
            writer(cap)
    reader = _OriginalReconciliationReader(setup)
    assert reader.read(result.operation_id, result.fingerprint) == result
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("POST became PRE")
    with ledger(paths[-2], readonly=True, binding=binding, version=2) as repo:
        assert len(repo.read().events) == 2
    assert not any(p.name.endswith(("-wal", "-shm", "-journal")) for p in tmp_path.rglob("*"))
