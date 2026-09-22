"""Durable Admission production composition and fail-closed activation tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.bootstrap_authority.durable_admission import (
    _DurableAdmissionOrchestrator,
    _DurableAdmissionOutcome,
)
from backend.bootstrap_authority.production_composition import (
    ProductionAdmissionCompositionDenied,
    ProductionAdmissionReadiness,
    ProductionAdmissionUnavailable,
    UnavailableProductionAdmissionComposition,
    _ProductionAdmissionCompositionRoot,
)
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_durable_admission import live_orchestration

pytest_plugins = ("backend.tests.test_currentness_witness_handoff",)


def caller(value):
    session = value[5][4]["session"]
    return session, session.get_transaction()


def test_complete_exact_graph_activates_and_delegates_once(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        root = _ProductionAdmissionCompositionRoot()
        session, transaction = caller(value)
        with root.open_scope(
            orchestrator=value[0],
            caller_session=session,
            caller_transaction=transaction,
        ) as scope:
            assert root.readiness is ProductionAdmissionReadiness.COMPOSITION_ROOT_READY
            result = scope.admit(**value[4])
            assert result.outcome is _DurableAdmissionOutcome.COMMITTED_EXACT
        with pytest.raises(ProductionAdmissionCompositionDenied):
            scope.admit(**value[4])
        assert not value[5][5]._attempts


def test_production_default_is_unconditionally_unavailable():
    composition = UnavailableProductionAdmissionComposition()
    assert composition.readiness is ProductionAdmissionReadiness.PRODUCTION_ACTIVATION_UNAVAILABLE
    with pytest.raises(ProductionAdmissionUnavailable):
        composition.activate(provider="fake", fallback=True)


@pytest.mark.parametrize(
    ("component", "attribute"),
    [
        ("orchestrator", "_owner"),
        ("owner", "_attempts"),
        ("reconciler", "_owner"),
        ("attempts", "_currentness"),
        ("handoff", "_correlations"),
        ("correlations", "_observations"),
        ("observations", "_lineage"),
        ("authenticity", "_material"),
        ("material", "_authority"),
        ("authority", "_designation"),
        ("designation", "_pin"),
        ("pin", "_serialization"),
    ],
)
def test_missing_or_partial_graph_dependency_is_denied(
    tmp_path, currentness_journal_engine, monkeypatch, component, attribute
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, attempts, owner, reconciler, _, context = value
        objects = {
            "orchestrator": orchestrator,
            "attempts": attempts,
            "owner": owner,
            "reconciler": reconciler,
            "handoff": attempts._currentness,
            "correlations": context[6],
            "observations": context[7],
            "authenticity": context[8],
            "material": context[8]._material,
            "authority": context[8]._material._authority,
            "designation": context[8]._confirmation._designation,
            "pin": context[8]._confirmation._designation._pin,
        }
        session, transaction = caller(value)
        with monkeypatch.context() as changes:
            changes.setattr(objects[component], attribute, None)
            with (
                pytest.raises(ProductionAdmissionCompositionDenied),
                _ProductionAdmissionCompositionRoot().open_scope(
                    orchestrator=orchestrator,
                    caller_session=session,
                    caller_transaction=transaction,
                ),
            ):
                pytest.fail("partial production graph activated")


def test_subclass_test_double_is_not_a_production_orchestrator(
    tmp_path, currentness_journal_engine
):
    if not native():
        return

    class FakeOrchestrator(_DurableAdmissionOrchestrator):
        pass

    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        fake = object.__new__(FakeOrchestrator)
        fake.__dict__.update(value[0].__dict__)
        session, transaction = caller(value)
        with (
            pytest.raises(ProductionAdmissionCompositionDenied),
            _ProductionAdmissionCompositionRoot().open_scope(
                orchestrator=fake,
                caller_session=session,
                caller_transaction=transaction,
            ),
        ):
            pytest.fail("test subclass activated")


def test_wrong_caller_session_and_application_db_journal_alias_are_denied(
    tmp_path, currentness_journal_engine
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        root = _ProductionAdmissionCompositionRoot()
        with (  # noqa: SIM117
            Session(currentness_journal_engine) as wrong_session,
            wrong_session.begin(),
        ):
            with (
                pytest.raises(ProductionAdmissionCompositionDenied),
                root.open_scope(
                    orchestrator=value[0],
                    caller_session=wrong_session,
                    caller_transaction=wrong_session.get_transaction(),
                ),
            ):
                pytest.fail("application/journal alias activated")


def test_duplicate_scope_does_not_replace_or_destroy_winner(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        root = _ProductionAdmissionCompositionRoot()
        session, transaction = caller(value)
        arguments = dict(
            orchestrator=value[0],
            caller_session=session,
            caller_transaction=transaction,
        )
        with root.open_scope(**arguments) as winner:  # noqa: SIM117
            with (
                pytest.raises(ProductionAdmissionCompositionDenied),
                root.open_scope(**arguments),
            ):
                pytest.fail("duplicate composition activated")
            root._require_active(winner)


def test_cleanup_or_root_shutdown_invalidates_scope_and_lifetime(
    tmp_path, currentness_journal_engine
):
    if not native():
        return
    lifetime = None
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        root = _ProductionAdmissionCompositionRoot()
        lifetime = value[5][5]
        session, transaction = caller(value)
        with root.open_scope(
            orchestrator=value[0],
            caller_session=session,
            caller_transaction=transaction,
        ) as scope:
            root.close()
            with pytest.raises(ProductionAdmissionCompositionDenied):
                root._require_active(scope)
        assert lifetime._attempts
    assert lifetime is not None and not lifetime._attempts


def test_composition_does_not_finish_either_caller_owned_transaction(
    tmp_path, currentness_journal_engine
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        session, transaction = caller(value)
        journal_session = value[3]._engine
        root = _ProductionAdmissionCompositionRoot()
        with root.open_scope(
            orchestrator=value[0],
            caller_session=session,
            caller_transaction=transaction,
        ) as scope:
            assert scope._caller_transaction.is_active
            assert scope._journal_transaction.is_active
            assert scope._journal_session.get_bind() is journal_session
        assert transaction.is_active
        assert value[5][7]._journal.session.get_transaction().is_active
