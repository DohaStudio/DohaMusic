"""Authentic confirmation/live-lineage/fresh-journal exact-correlation regression."""

from __future__ import annotations

import copy
import pickle
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.bootstrap_authority.confirmation_authenticity import (
    SIGNATURE_DOMAIN,
    _OriginalConfirmationAuthenticity,
)
from backend.bootstrap_authority.confirmation_lineage_correlation import (
    ConfirmationLineageCorrelationDenied,
    _ConfirmationLineageCorrelations,
)
from backend.bootstrap_authority.confirmation_payload import ExpectedConfirmationPayload
from backend.bootstrap_authority.fresh_journal_lineage import _FreshJournalLineageObservations
from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.bootstrap_authority.journal_schema_v1 import migrate_empty_journal
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.provisioning_binding import (
    InitializerConfirmationFacts,
    PolicyLineageFacts,
    PolicySnapshotFacts,
    ProvisioningActionFacts,
    policy_snapshot_digest,
)
from backend.tests.test_bootstrap_lifecycle_journal import keys
from backend.tests.test_bootstrap_pin_facts import INSTALLATION_FP
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_confirmation_authenticity import (
    confirmation_raw,
    setup_confirmation,
    signature_text,
)
from backend.tests.test_fresh_journal_lineage import source_fixture
from backend.tests.test_live_lineage_reader import raw as lineage_raw
from backend.tests.test_live_lineage_reader import setup_reader
from backend.tests.test_provisioning_authority_source import (
    authority,
    setup_source,
    source_raw,
    uid,
)
from backend.tests.test_provisioning_verifier_material import (
    active_history,
    material_raw,
    setup_material,
)


@pytest.fixture
def correlation_journal_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'correlation-journal.sqlite'}")
    with engine.begin() as connection:
        migrate_empty_journal(connection)
    from backend.tests.test_bootstrap_lifecycle_journal import JOURNAL

    with Session(engine) as session, session.begin():
        JournalRepository(session).initialize_public_identity(JOURNAL)
    yield engine
    engine.dispose()


@contextmanager
def correlated(tmp_path, engine):
    with source_fixture(tmp_path, engine) as fx:
        args = fx[1]
        binding = args["expected"]
        root_key = keys()[binding.root_key_id]
        verifier_key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
        public = verifier_key.public_key().public_bytes_raw()
        auth_scope = authority(root_key, binding)
        events = active_history(auth_scope, public)
        source_bytes, expected_source = source_raw(auth_scope, events=events)
        authority_reader, designation, _, _, source_policy = setup_source(
            tmp_path, fx, source_bytes
        )
        material_bytes, expected_material, _, _ = material_raw(auth_scope, expected_source, public)
        material_reader, _, _ = setup_material(
            tmp_path, authority_reader, source_policy, material_bytes
        )
        with fx[0]._open_facts(**args) as facts:
            policy = PolicySnapshotFacts(
                uid(50),
                1,
                auth_scope[2].installation_id,
                INSTALLATION_FP,
                uid(51),
                designation._files._policy,
            )
            expected_payload = ExpectedConfirmationPayload(
                uid(100),
                "original/test",
                auth_scope[2].producer_ref,
                auth_scope[2].installation_id,
                INSTALLATION_FP,
                uid(200),
                policy_snapshot_digest(policy),
                facts.binding.designation_record_digest,
                "provisioner/material-v1",
                digest(public),
                uid(300),
            )
            confirmation_bytes = confirmation_raw(expected_payload)
            confirmation_fact = InitializerConfirmationFacts(
                expected_payload.confirmation_id,
                expected_payload.original_confirmation_ref,
                digest(confirmation_bytes),
                expected_payload.initializer_ref,
                expected_payload.action_id,
                expected_payload.policy_digest,
                facts,
            )
            action = ProvisioningActionFacts(
                expected_payload.action_id, policy, confirmation_fact, None
            )
            lineage = PolicyLineageFacts(
                uid(52), auth_scope[2].installation_id, uid(51), (action,), ("ACTIVE",)
            )
            confirmation_reader, _ = setup_confirmation(
                tmp_path, fx, designation, confirmation_bytes
            )
            lineage_reader, lineage_path = setup_reader(tmp_path, confirmation_reader)
            lineage_path.write_bytes(lineage_raw(action, lineage, facts))
            authenticity = _OriginalConfirmationAuthenticity(
                confirmation_snapshots=confirmation_reader,
                material_snapshots=material_reader,
            )
            signature = signature_text(verifier_key, SIGNATURE_DOMAIN + confirmation_bytes)
            with (
                designation._open_record(
                    lease=args["lease"], session=args["session"], pin_facts=facts
                ) as designation_handle,
                confirmation_reader._open_snapshot(
                    lease=args["lease"],
                    session=args["session"],
                    pin_facts=facts,
                    designation=designation_handle,
                    action=action,
                    lineage=lineage,
                ) as confirmation_handle,
                authority_reader._open_source(
                    designation_handle=designation_handle,
                    lease=args["lease"],
                    session=args["session"],
                    pin_facts=facts,
                    expected_source=expected_source,
                    expected_scope=auth_scope[2],
                ) as authority_handle,
                material_reader._open_material(
                    authority_handle=authority_handle,
                    designation_handle=designation_handle,
                    lease=args["lease"],
                    session=args["session"],
                    pin_facts=facts,
                    expected_source=expected_source,
                    expected_scope=auth_scope[2],
                    expected_material=expected_material,
                ) as material_handle,
                lineage_reader._open_current(
                    confirmation_handle=confirmation_handle,
                    expected_payload=expected_payload,
                    action=action,
                    lineage=lineage,
                ) as lineage_handle,
                Session(engine) as journal_session,
            ):
                journal_session.begin()
                observations = _FreshJournalLineageObservations(
                    lineage_snapshots=lineage_reader,
                    journal_repository=JournalRepository(journal_session),
                )
                correlations = _ConfirmationLineageCorrelations(
                    authenticity=authenticity, observations=observations
                )
                auth_args = {
                    "confirmation_handle": confirmation_handle,
                    "material_handle": material_handle,
                    "authority_handle": authority_handle,
                    "designation_handle": designation_handle,
                    "lease": args["lease"],
                    "session": args["session"],
                    "pin_facts": facts,
                    "fresh_action": action,
                    "fresh_lineage": lineage,
                    "expected_payload": expected_payload,
                    "expected_material": expected_material,
                    "expected_source": expected_source,
                    "expected_scope": auth_scope[2],
                    "signature_text": signature,
                }
                observation_args = {
                    "lineage_handle": lineage_handle,
                    "confirmation_handle": confirmation_handle,
                    "expected_payload": expected_payload,
                    "action": action,
                    "lineage": lineage,
                }
                with (
                    authenticity._open_authenticity(**auth_args) as authenticity_handle,
                    observations._open_observation(**observation_args) as observation_handle,
                ):
                    call = dict(
                        authenticity_handle=authenticity_handle,
                        observation_handle=observation_handle,
                        lineage_handle=lineage_handle,
                        **auth_args,
                    )
                    yield correlations, call, observations, authenticity
                journal_session.rollback()


def test_native_exact_correlation_is_opaque_and_non_authorizing(
    tmp_path, correlation_journal_engine
):
    if not native():
        return
    with correlated(tmp_path, correlation_journal_engine) as (correlations, call, _, _):
        with correlations._open_correlation(**call) as handle:
            correlations._require_open(handle, **call)
            record = correlations._records[handle]
            assert record.facts.confirmation_id == call["expected_payload"].confirmation_id
            assert record.facts.lineage_anchor_id == call["fresh_lineage"].anchor_id
            assert record.facts.journal_head_digest == call["pin_facts"].binding.journal.head_digest
            assert (
                record.facts.verifier_fingerprint == call["expected_payload"].verifier_fingerprint
            )
            assert record.caller_transaction is not record.journal_transaction
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with pytest.raises(TypeError, match="OPAQUE_HANDLE"):
                    operation(handle)
            for name in ("currentness_witness", "admit", "authorize", "receipt"):
                assert not hasattr(handle, name)
        with pytest.raises(ConfirmationLineageCorrelationDenied):
            correlations._require_open(handle, **call)


@pytest.mark.parametrize(
    "attack",
    [
        "confirmation",
        "action",
        "lineage",
        "source",
        "material",
        "signature",
        "lease",
        "caller-transaction",
        "journal-transaction",
        "journal-head",
    ],
)
def test_native_substitution_or_staleness_abandons_correlation(
    tmp_path, correlation_journal_engine, attack
):
    if not native():
        return
    with correlated(tmp_path, correlation_journal_engine) as (
        correlations,
        call,
        observations,
        authenticity,
    ):
        original = dict(call)
        with correlations._open_correlation(**call) as handle:
            if attack == "confirmation":
                call["expected_payload"] = replace(call["expected_payload"], replay_id=uid(999))
            elif attack == "action":
                changed_confirmation = replace(
                    call["fresh_action"].confirmation, action_id=uid(998)
                )
                call["fresh_action"] = replace(
                    call["fresh_action"],
                    action_id=uid(998),
                    confirmation=changed_confirmation,
                )
            elif attack == "lineage":
                call["fresh_lineage"] = replace(call["fresh_lineage"], anchor_id=uid(997))
            elif attack == "source":
                call["expected_source"] = replace(call["expected_source"], source_revision=2)
            elif attack == "material":
                call["expected_material"] = replace(call["expected_material"], material_revision=2)
            elif attack == "signature":
                call["signature_text"] = "A" * 86
            elif attack == "lease":
                call["lease"] = object()
            elif attack == "caller-transaction":
                call["session"].rollback()
                call["session"].begin()
            elif attack == "journal-transaction":
                observations._journal.session.rollback()
                observations._journal.session.begin()
            else:
                current = observations._journal.read_public_head()
                observations._journal.read_public_head = Mock(
                    return_value=replace(current, revision=current.revision + 1)
                )
            with pytest.raises(ConfirmationLineageCorrelationDenied):
                correlations._require_open(handle, **call)
            with pytest.raises(ConfirmationLineageCorrelationDenied):
                correlations._require_open(handle, **original)
            assert not correlations._records
            assert not authenticity._records


def test_foreign_handle_does_not_destroy_live_correlation(tmp_path, correlation_journal_engine):
    if not native():
        return
    with (
        correlated(tmp_path, correlation_journal_engine) as (correlations, call, _, _),
        correlations._open_correlation(**call) as handle,
    ):
        with pytest.raises(ConfirmationLineageCorrelationDenied):
            correlations._require_open(object(), **call)
        correlations._require_open(handle, **call)


def test_consumer_failure_abandons_whole_chain(tmp_path, correlation_journal_engine):
    if not native():
        return
    with correlated(tmp_path, correlation_journal_engine) as (
        correlations,
        call,
        observations,
        authenticity,
    ):
        with (
            pytest.raises(ConfirmationLineageCorrelationDenied),
            correlations._open_correlation(**call),
        ):
            raise OSError("injected consumer failure")
        assert not correlations._records
        assert not observations._observations
        assert not authenticity._records


def test_constructor_requires_one_shared_confirmation_chain():
    for authenticity, observations in ((object(), object()), (None, None), (True, {})):
        with pytest.raises(ConfirmationLineageCorrelationDenied):
            _ConfirmationLineageCorrelations(authenticity=authenticity, observations=observations)
