"""Disposable mechanics fixtures, not actual governance/OS lease/private admission."""

import copy
import pickle
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.journal_repository import JournalHead
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.witness_lifetime import (
    CurrentnessBinding,
    WitnessLifetimeDenied,
    _Handle,
    _ProviderWitnessLifetime,
)

SCOPE = tuple(str(UUID(int=i)) for i in (10, 11, 12))
PUBLIC = b"disposable public verifier bytes".ljust(32, b"!")
HEAD = JournalHead(str(UUID(int=1)), 1, 1, digest(b"event"), "root/test", "root/test")


def binding():
    return CurrentnessBinding(
        HEAD,
        HEAD,
        str(UUID(int=2)),
        digest(b"record"),
        "owner/test",
        (SCOPE,),
        "root/test",
        digest(PUBLIC),
        PUBLIC,
    )


@pytest.fixture
def fixture():
    with Session(create_engine("sqlite://")) as session:
        session.begin()
        provider = _ProviderWitnessLifetime()
        lease = object()  # TEST ONLY. Does not acquire/represent actual OS authority.
        current = binding()
        attempt = provider._begin_after_verified_lease(
            lease=lease, session=session, binding=current
        )
        witness = provider._register_after_independent_currentness(attempt)
        yield provider, lease, session, current, attempt, witness
        provider._close()


def check(fixture, **changes):
    provider, lease, session, current, attempt, witness = fixture
    args = dict(
        attempt=attempt,
        witness=witness,
        lease=lease,
        session=session,
        freshly_verified_binding=current,
        exact_scope=SCOPE,
    )
    args.update(changes)
    provider._require_live_binding(**args)


@pytest.mark.parametrize("operation", ["read", "admit", "revalidate"])
def test_live_mechanics_never_production_authority(fixture, operation):
    check(fixture)
    check(fixture)  # Same live transaction; no invented one-use approval semantics.
    for value in (fixture[3], fixture[4], fixture[5], HEAD, object(), True):
        with pytest.raises(CurrentnessUnavailable):
            ports = UnavailableCurrentnessPorts()
            if operation == "read":
                ports.read_private_provisioning_witness()
            elif operation == "admit":
                ports.admit_with_private_ceremony_witness(value)
            else:
                ports.revalidate_private_currentness_witness(value)


@pytest.mark.parametrize("field", ["attempt", "witness", "lease", "session"])
def test_wrong_identity(fixture, field):
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, **{field: object()})


@pytest.mark.parametrize("value", [None, True, {}, HEAD, "verified", 1])
def test_public_only_or_missing_evidence_denied(fixture, value):
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, witness=value)


@pytest.mark.parametrize("operation", [copy.copy, copy.deepcopy, pickle.dumps])
def test_no_handle_export_or_copy(fixture, operation):
    for handle in fixture[4:]:
        with pytest.raises(TypeError, match="OPAQUE_HANDLE"):
            operation(handle)
    assert repr(fixture[5]) == "<opaque deployment handle>"


def test_forged_type_is_not_registry_identity(fixture):
    with pytest.raises(WitnessLifetimeDenied):
        _Handle()
    forged = object.__new__(_Handle)  # Even privileged constructor bypass is unregistered.
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, attempt=forged)
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, witness=forged)


def test_other_provider_or_attempt(fixture):
    other = _ProviderWitnessLifetime()
    with pytest.raises(WitnessLifetimeDenied):
        other._register_after_independent_currentness(fixture[4])
    provider, _, session, current, _, witness = fixture
    lease = object()
    attempt = provider._begin_after_verified_lease(lease=lease, session=session, binding=current)
    provider._register_after_independent_currentness(attempt)
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, attempt=attempt, lease=lease, witness=witness)


@pytest.mark.parametrize("end", ["commit", "rollback", "close"])
def test_transaction_end_and_replacement(fixture, end):
    session = fixture[2]
    getattr(session, end)()
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture)
    session.begin()
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture)


def test_savepoint_not_unlocked_fallback(fixture):
    with fixture[2].begin_nested(), pytest.raises(WitnessLifetimeDenied):
        check(fixture)


def test_release_restart_and_lease_reuse(fixture):
    provider, lease, session, current, _, _ = fixture
    provider._release_lease(lease)
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture)
    with pytest.raises(WitnessLifetimeDenied):
        provider._begin_after_verified_lease(lease=lease, session=session, binding=current)
    provider._close()
    with pytest.raises(WitnessLifetimeDenied):
        provider._begin_after_verified_lease(lease=object(), session=session, binding=current)
    with pytest.raises(WitnessLifetimeDenied):
        _ProviderWitnessLifetime()._register_after_independent_currentness(fixture[4])


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "REVOKED"),
        ("status", "RETIRED"),
        ("status", "COMPROMISED"),
        ("domain", "dohamusic/deployment-bootstrap-approval/v1"),
        ("root_fingerprint", digest(b"wrong")),
        ("root_public_key", b"wrong"),
        ("root_public_key", bytearray(PUBLIC)),
        ("designation_id", "invalid"),
        ("designation_record_digest", "invalid"),
        ("deployment_owner_ref", ""),
        ("affected_scopes", ()),
        ("affected_scopes", [SCOPE]),
        ("affected_scopes", (SCOPE, SCOPE)),
        ("affected_scopes", (("wrong", *SCOPE[1:]),)),
        ("affected_scopes", (SCOPE,) * 4097),
        ("installed_pin", None),
    ],
)
def test_binding_invalid(field, value):
    with pytest.raises(WitnessLifetimeDenied):
        replace(binding(), **{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("revision", True),
        ("revision", 1.0),
        ("revision", 0),
        ("revision", 9007199254740992),
        ("trust_revision", True),
        ("trust_revision", 2),
        ("head_digest", None),
        ("head_digest", "bad"),
        ("current_key_id", None),
        ("current_key_id", "root/wrong"),
        ("last_key_id", "root/wrong"),
        ("journal_id", "invalid"),
    ],
)
def test_malformed_or_terminal_head(field, value):
    invalid = replace(HEAD, **{field: value})
    with pytest.raises(WitnessLifetimeDenied):
        replace(binding(), journal=invalid, installed_pin=invalid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("revision", 2),
        ("trust_revision", 2),
        ("head_digest", digest(b"fork")),
        ("journal_id", str(UUID(int=3))),
        ("current_key_id", "root/other"),
    ],
)
def test_pin_journal_mismatch(field, value):
    with pytest.raises(WitnessLifetimeDenied):
        replace(binding(), installed_pin=replace(HEAD, **{field: value}))


@pytest.mark.parametrize("field", ["revision", "trust_revision"])
@pytest.mark.parametrize("value", [True, 1.0])
def test_pin_counters_cannot_use_bool_float_equality(field, value):
    with pytest.raises(WitnessLifetimeDenied):
        replace(binding(), installed_pin=replace(HEAD, **{field: value}))


@pytest.mark.parametrize(
    "change", ["installation", "workspace", "owner", "designation", "record", "revision", "key"]
)
def test_fresh_binding_drift(fixture, change):
    current = binding()
    if change in ("installation", "workspace", "owner"):
        scope = list(SCOPE)
        scope[{"installation": 0, "workspace": 1, "owner": 2}[change]] = str(UUID(int=20))
        current = replace(current, affected_scopes=(tuple(scope),))
    elif change == "designation":
        current = replace(current, designation_id=str(UUID(int=20)))
    elif change == "record":
        current = replace(current, designation_record_digest=digest(b"other"))
    elif change == "revision":
        head = replace(HEAD, revision=2, trust_revision=2, head_digest=digest(b"next"))
        current = replace(current, journal=head, installed_pin=head)
    else:
        head = replace(HEAD, current_key_id="root/new", last_key_id="root/new")
        current = replace(current, journal=head, installed_pin=head, root_key_id="root/new")
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, freshly_verified_binding=current)


def test_scope_exact_and_frozen(fixture):
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, exact_scope=(*SCOPE[:2], str(UUID(int=99))))
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, exact_scope=list(SCOPE))
    with pytest.raises(FrozenInstanceError):
        fixture[3].status = "REVOKED"


def test_scope_equality_spoofing_denied(fixture):
    class EqualitySpoof:
        def __eq__(self, other):
            return True

    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, exact_scope=tuple(EqualitySpoof() for _ in range(3)))


@pytest.mark.parametrize("field", ["domain", "root_fingerprint"])
def test_comparison_string_subclass_denied(field):
    class StringSpoof(str):
        def __eq__(self, other):
            return True

        __hash__ = str.__hash__

    original = binding()
    with pytest.raises(WitnessLifetimeDenied):
        replace(original, **{field: StringSpoof(getattr(original, field))})


def test_observed_head_drift_cannot_reactivate_old_handle(fixture):
    head = replace(HEAD, revision=2, trust_revision=2, head_digest=digest(b"rotation"))
    changed = replace(binding(), journal=head, installed_pin=head)
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture, freshly_verified_binding=changed)
    # Replaying the old matching public projection must not resurrect the attempt.
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture)


def test_unsupported_nested_attempt_cannot_reactivate(fixture):
    with fixture[2].begin_nested(), pytest.raises(WitnessLifetimeDenied):
        check(fixture)
    with pytest.raises(WitnessLifetimeDenied):
        check(fixture)


def test_registration_transaction_denial_abandons_attempt():
    with Session() as session:
        session.begin()
        provider = _ProviderWitnessLifetime()
        attempt = provider._begin_after_verified_lease(
            lease=object(), session=session, binding=binding()
        )
        with session.begin_nested(), pytest.raises(WitnessLifetimeDenied):
            provider._register_after_independent_currentness(attempt)
        with pytest.raises(WitnessLifetimeDenied):
            provider._register_after_independent_currentness(attempt)


def test_single_assignment_and_concurrent_registration():
    provider = _ProviderWitnessLifetime()
    with Session() as session:
        session.begin()
        attempt = provider._begin_after_verified_lease(
            lease=object(), session=session, binding=binding()
        )

        def register(_):
            try:
                provider._register_after_independent_currentness(attempt)
                return "winner"
            except WitnessLifetimeDenied:
                return "denied"

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(register, range(2))) == ["denied", "winner"]
        with pytest.raises(WitnessLifetimeDenied):
            provider._register_after_independent_currentness(attempt)


def test_no_transaction_side_effects(fixture):
    session = fixture[2]
    session.commit = Mock(side_effect=AssertionError("hidden commit"))
    session.rollback = Mock(side_effect=AssertionError("hidden rollback"))
    session.flush = Mock(side_effect=AssertionError("hidden flush"))
    check(fixture)
    assert session.commit.call_count == session.rollback.call_count == session.flush.call_count == 0
    # Restore so caller-owned fixture cleanup can close normally.
    del session.commit, session.rollback, session.flush


@pytest.mark.parametrize("change", ["no_transaction", "missing_lease", "public_receipt"])
def test_attempt_cannot_start_without_required_mechanics(change):
    with Session() as session:
        if change != "no_transaction":
            session.begin()
        with pytest.raises(WitnessLifetimeDenied):
            _ProviderWitnessLifetime()._begin_after_verified_lease(
                lease=None if change == "missing_lease" else object(),
                session=session,
                binding=HEAD if change == "public_receipt" else binding(),
            )


@pytest.mark.parametrize("point", ["partial_flush", "rollback", "provider_crash"])
def test_partial_flush_or_attempt_abandonment(point):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE isolated_test_fact(id INTEGER PRIMARY KEY)"))
    with Session(engine) as session:
        session.begin()
        provider = _ProviderWitnessLifetime()
        lease = object()
        attempt = provider._begin_after_verified_lease(
            lease=lease, session=session, binding=binding()
        )
        session.execute(text("INSERT INTO isolated_test_fact VALUES(1)"))
        session.flush()
        if point == "provider_crash":
            provider._close()
        else:
            session.rollback()
        with pytest.raises(WitnessLifetimeDenied):
            provider._register_after_independent_currentness(attempt)
        session.rollback()
        assert session.execute(text("SELECT count(*) FROM isolated_test_fact")).scalar_one() == 0
