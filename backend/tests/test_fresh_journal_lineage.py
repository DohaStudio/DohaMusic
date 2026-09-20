"""Fresh journal/lineage correlation fixtures; never currentness authority."""

import copy
import pickle
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock

import pytest
import rfc8785
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.fresh_journal_lineage import (
    FreshJournalLineageDenied,
    _FreshJournalLineageObservations,
    _JournalSnapshot,
)
from backend.bootstrap_authority.journal_repository import JournalRepository, PublicKeyHistory
from backend.bootstrap_authority.journal_schema_v1 import migrate_empty_journal
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.private_pin_reader import _PrivatePinFactsReader
from backend.bootstrap_authority.windows_fact_files import PIN_FACTS_FILE
from backend.bootstrap_authority.windows_serialization import _WindowsCeremonySerialization
from backend.bootstrap_authority.witness_lifetime import (
    CurrentnessBinding,
    _ProviderWitnessLifetime,
)
from backend.tests.test_bootstrap_lifecycle_journal import (
    JOURNAL,
    MANIFEST,
    SCOPES,
    append,
    event,
    keys,
)
from backend.tests.test_bootstrap_pin_facts import INSTALLATION_FP
from backend.tests.test_bootstrap_pin_facts import value as pin_value
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_confirmation_payload import _bind_canonical
from backend.tests.test_confirmation_snapshot import live, setup
from backend.tests.test_live_lineage_reader import raw, setup_reader


@pytest.fixture
def journal_engine(tmp_path):
    value = create_engine(f"sqlite:///{tmp_path / 'independent-journal.sqlite'}")
    with value.begin() as connection:
        migrate_empty_journal(connection)
    with Session(value) as session, session.begin():
        JournalRepository(session).initialize_public_identity(JOURNAL)
    yield value
    value.dispose()


@contextmanager
def source_fixture(tmp_path, journal_engine, *, register_currentness=True):
    payload, expected = event()
    payload["designation_record_digest"] = digest(b"record")
    expected = replace(expected, designation_record_digest=payload["designation_record_digest"])
    with Session(journal_engine) as journal_session, journal_session.begin():
        append(journal_session, payload, expected)
    with Session(journal_engine) as read_session:
        head = JournalRepository(read_session).read_public_head()
    public_key = keys()["root/test-1"].public_key().public_bytes_raw()
    binding = CurrentnessBinding(
        head,
        head,
        payload["designation_id"],
        payload["designation_record_digest"],
        payload["deployment_owner_ref"],
        SCOPES,
        payload["new_key_id"],
        digest(public_key),
        public_key,
    )
    pin_data = pin_value(binding)
    pin_data["installation_id"] = SCOPES[0][0]
    pin_path = tmp_path / PIN_FACTS_FILE
    pin_path.write_bytes(rfc8785.dumps(pin_data))
    lifetime = _ProviderWitnessLifetime()
    serialization = _WindowsCeremonySerialization(lifetime)
    pin_reader = _PrivatePinFactsReader(trusted_root=str(tmp_path), serialization=serialization)
    with Session() as source_session:
        source_session.begin()
        lease = serialization._acquire(scopes=SCOPES, session=source_session)
        attempt = lifetime._begin_after_verified_lease(
            lease=lease, session=source_session, binding=binding
        )
        witness = (
            lifetime._register_after_independent_currentness(attempt)
            if register_currentness
            else None
        )
        args = {
            "lease": lease,
            "session": source_session,
            "expected": binding,
            "installation_id": SCOPES[0][0],
            "installation_proof_key_fingerprint": INSTALLATION_FP,
        }
        fx = (pin_reader, args, pin_path, lifetime, attempt, witness, serialization)
        try:
            yield fx
        finally:
            source_session.rollback()
            serialization._release(lease)
            pin_reader._files._cleanup_failed_snapshots()


@contextmanager
def held(tmp_path, journal_engine):
    with source_fixture(tmp_path, journal_engine) as fx:
        confirmation, designation, confirmation_path, _, policy = setup(fx, tmp_path)
        lineage_reader, lineage_path = setup_reader(tmp_path, confirmation)
        with live(fx, confirmation, designation, policy) as inputs:
            payload = _bind_canonical(inputs, confirmation_path)
            lineage_path.write_bytes(raw(inputs["action"], inputs["lineage"], inputs["pin_facts"]))
            with (
                confirmation._open_snapshot(**inputs) as confirmation_handle,
                lineage_reader._open_current(
                    confirmation_handle=confirmation_handle,
                    expected_payload=payload,
                    action=inputs["action"],
                    lineage=inputs["lineage"],
                ) as lineage_handle,
                Session(journal_engine) as journal_session,
            ):
                journal_session.begin()
                observer = _FreshJournalLineageObservations(
                    lineage_snapshots=lineage_reader,
                    journal_repository=JournalRepository(journal_session),
                )
                yield observer, lineage_reader, confirmation_handle, lineage_handle, payload, inputs
                journal_session.rollback()


def observation_args(context):
    _, _, confirmation_handle, lineage_handle, payload, inputs = context
    return {
        "lineage_handle": lineage_handle,
        "confirmation_handle": confirmation_handle,
        "expected_payload": payload,
        "action": inputs["action"],
        "lineage": inputs["lineage"],
    }


def test_native_fresh_observation_is_opaque_and_not_authority(tmp_path, journal_engine):
    if not native():
        return
    with held(tmp_path, journal_engine) as context:
        observer = context[0]
        args = observation_args(context)
        with observer._open_observation(**args) as handle:
            observer._require_fresh(handle, **args)
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with pytest.raises(TypeError, match="OPAQUE_HANDLE"):
                    operation(handle)
            for operation in ("read", "admit", "revalidate"):
                with pytest.raises(CurrentnessUnavailable):
                    ports = UnavailableCurrentnessPorts()
                    if operation == "read":
                        ports.read_private_provisioning_witness()
                    elif operation == "admit":
                        ports.admit_with_private_ceremony_witness(handle)
                    else:
                        ports.revalidate_private_currentness_witness(handle)
        with pytest.raises(FreshJournalLineageDenied):
            observer._require_fresh(handle, **args)


@pytest.mark.parametrize(
    "change",
    ["transaction", "head", "history", "source", "exception"],
)
def test_native_change_abandons_whole_source_chain(tmp_path, journal_engine, monkeypatch, change):
    if not native():
        return
    with held(tmp_path, journal_engine) as context:
        observer, lineage_reader, confirmation_handle, lineage_handle, _, _ = context
        args = observation_args(context)
        with observer._open_observation(**args) as handle:
            if change == "transaction":
                observer._journal.session.rollback()
                observer._journal.session.begin()
            elif change in {"head", "history", "exception"}:
                method = "read_public_head" if change == "head" else "read_public_history"
                original = getattr(observer._journal, method)
                if change == "exception":
                    monkeypatch.setattr(observer._journal, method, Mock(side_effect=OSError("x")))
                elif change == "head":
                    current = original()
                    monkeypatch.setattr(
                        observer._journal,
                        method,
                        Mock(return_value=replace(current, revision=current.revision + 1)),
                    )
                else:
                    monkeypatch.setattr(observer._journal, method, Mock(return_value=()))
            elif change == "source":
                args["expected_payload"] = replace(
                    args["expected_payload"], replay_id=str(SCOPES[0][1])
                )
            with pytest.raises(FreshJournalLineageDenied):
                observer._require_fresh(handle, **args)
            assert lineage_handle not in lineage_reader._records
            assert confirmation_handle not in lineage_reader._confirmation._records


def test_foreign_observation_cannot_abandon_valid_source(tmp_path, journal_engine):
    if not native():
        return
    with held(tmp_path, journal_engine) as context:
        observer = context[0]
        args = observation_args(context)
        with observer._open_observation(**args) as handle:
            with pytest.raises(FreshJournalLineageDenied):
                observer._require_fresh(object(), **args)
            observer._require_fresh(handle, **args)


def test_consumer_exception_is_safe_denial_and_abandons_source(tmp_path, journal_engine):
    if not native():
        return
    with held(tmp_path, journal_engine) as context:
        observer, lineage_reader, confirmation_handle, lineage_handle, _, _ = context
        with (
            pytest.raises(FreshJournalLineageDenied),
            observer._open_observation(**observation_args(context)),
        ):
            raise OSError("injected consumer failure")
        assert lineage_handle not in lineage_reader._records
        assert confirmation_handle not in lineage_reader._confirmation._records


def test_native_moving_head_during_open_never_yields(tmp_path, journal_engine, monkeypatch):
    if not native():
        return
    with held(tmp_path, journal_engine) as context:
        observer = context[0]
        args = observation_args(context)
        original = observer._journal.read_public_head
        current = original()
        monkeypatch.setattr(
            observer._journal,
            "read_public_head",
            Mock(side_effect=[current, replace(current, revision=2)]),
        )
        with pytest.raises(FreshJournalLineageDenied), observer._open_observation(**args):
            pytest.fail("moving journal head yielded an observation")


def test_same_source_and_journal_session_is_denied_without_fallback(tmp_path, journal_engine):
    if not native():
        return
    with held(tmp_path, journal_engine) as context:
        observer, lineage_reader, confirmation_handle, _, _, _ = context
        parent = lineage_reader._confirmation._records[confirmation_handle]
        observer._journal = JournalRepository(parent.session)
        with (
            pytest.raises(FreshJournalLineageDenied),
            observer._open_observation(**observation_args(context)),
        ):
            pytest.fail("co-mingled source/application session yielded an observation")


@pytest.mark.parametrize(
    "history",
    [
        (),
        (PublicKeyHistory("root/test-1", digest(b"wrong"), "ACTIVE_ISSUANCE", False, None),),
        (PublicKeyHistory("root/test-1", "sha256:" + "0" * 64, "REVOKED", False, 1),),
        (PublicKeyHistory("root/test-1", "sha256:" + "0" * 64, "ACTIVE_ISSUANCE", True, 1),),
        (
            PublicKeyHistory("root/test-1", "sha256:" + "0" * 64, "ACTIVE_ISSUANCE", False, None),
            PublicKeyHistory("root/other", "sha256:" + "1" * 64, "ACTIVE_ISSUANCE", False, None),
        ),
        (object(),),
    ],
)
def test_active_projection_requires_one_exact_untainted_current_key(history):
    from backend.tests.test_bootstrap_witness_lifetime import binding

    current = binding()
    with pytest.raises(FreshJournalLineageDenied):
        _FreshJournalLineageObservations._require_active_projection(
            _JournalSnapshot(current.journal, history), current
        )


def test_constructor_and_snapshot_shape_are_strict():
    from backend.tests.test_bootstrap_witness_lifetime import binding

    for lineage, repository in ((object(), object()), (None, None), (True, {})):
        with pytest.raises(FreshJournalLineageDenied):
            _FreshJournalLineageObservations(
                lineage_snapshots=lineage, journal_repository=repository
            )
    with pytest.raises(FreshJournalLineageDenied):
        _FreshJournalLineageObservations._require_active_projection(object(), binding())


def test_test_manifest_remains_exact_and_separate():
    assert len(MANIFEST) > 0
    assert tuple(sorted(set(SCOPES))) == SCOPES
