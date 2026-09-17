"""Disposable SQLite ADR-075 persistence, integrity and caller-Tx proofs.

Test-owned issuance fixtures are not a production issuer/rights adapter.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers

import backend.models  # noqa: F401
from backend.core.vocal_rights import (
    VocalRightsOperation as Operation,
)
from backend.core.vocal_rights import (
    VocalRightsPersistenceError,
)
from backend.core.vocal_rights import (
    VocalRightsSubjectType as Subject,
)
from backend.core.vocal_rights import (
    VocalRightsTransition as Transition,
)
from backend.core.vocal_rights import (
    VocalRightsUsageRole as Role,
)
from backend.db.base import Base
from backend.db.session import create_database_engine, create_session_factory
from backend.db.vocal_rights_schema_v1 import IMMUTABLE_TABLES, MAX_TOKEN, TABLE_NAMES
from backend.models.workspace import (
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    Job,
    JobOutput,
    JobStatus,
    MusicProject,
    Workspace,
)
from backend.models.workspace.vocal_rights import (
    VOCAL_RIGHTS_ENTITY_CLASSES,
    VocalCompletionRightsReceipt,
    VocalCompletionRightsReceiptItem,
    VocalRightsCurrentAuthority,
    VocalRightsEvent,
    VocalRightsEvidence,
    VocalRightsEvidenceGuard,
    VocalRightsEvidenceScope,
    VocalRightsEvidenceWithdrawal,
    VocalRightsGrant,
    VocalRightsScopeGuard,
)
from backend.repositories.workspace.vocal_rights_repository import VocalRightsRepository


def seed_legacy(session):
    owner = uuid4()
    workspace = Workspace(
        owner_id=owner, name="Synthetic rights fixture", lifecycle_status="active"
    )
    session.add(workspace)
    session.flush()
    project = MusicProject(
        workspace_id=workspace.workspace_id,
        title="Synthetic project",
        lifecycle_status="active",
        created_by=owner,
    )
    session.add(project)
    session.flush()
    asset = Asset(
        owner_id=owner,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.VOCAL,
        lifecycle_status="active",
    )
    session.add(asset)
    session.flush()
    versions = []
    for number in (1, 2):
        version = AssetVersion(
            asset_id=asset.asset_id,
            version_number=number,
            version_origin="user_upload",
            settings_snapshot={},
            created_by=owner,
            parent_asset_version_id=versions[0].asset_version_id if versions else None,
        )
        session.add(version)
        session.flush()
        versions.append(version)
    artifact = Artifact(
        asset_version_id=versions[1].asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=10,
        checksum_algorithm="sha256",
        artifact_checksum="a" * 64,
        producer_type="provider",
        producer_id="dohavocal",
        retention_status="active",
    )
    session.add(artifact)
    job = Job(
        project_id=project.project_id,
        workspace_id=workspace.workspace_id,
        job_type="vocal_correction",
        status=JobStatus.RUNNING,
        provider_id="dohavocal",
        api_contract_version="0.2.0",
        model_manifest_id="synthetic@1",
        settings_snapshot={},
        requested_by=owner,
        attempt=1,
    )
    session.add(job)
    session.flush()
    return dict(
        owner=owner,
        workspace=workspace.workspace_id,
        asset=asset.asset_id,
        versions=[version.asset_version_id for version in versions],
        artifact=artifact.artifact_id,
        job=job.job_id,
    )


@pytest.fixture
def rights_graph(tmp_path):
    url = f"sqlite:///{(tmp_path / 'rights.db').as_posix()}"
    engine = create_database_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    factory = create_session_factory(url)
    with factory.begin() as session:
        graph = seed_legacy(session)
        repository = VocalRightsRepository(session)
        guard = repository.ensure_scope_guard(graph["owner"], graph["workspace"])
        repository.conditional_guard_update("scope", guard.scope_guard_id, 0)
        graph["scope"] = guard.scope_guard_id
        graph["authorities"] = [
            repository.ensure_current_authority(
                guard.scope_guard_id, Subject.ASSET_VERSION, version, Operation.VOCAL_CORRECT, role
            ).authority_id
            for version, role in zip(
                graph["versions"], (Role.SOURCE_VOCAL, Role.PARENT_VOCAL), strict=True
            )
        ]
        graph["evidence"] = []
        for ordinal in (1, 2):
            evidence = VocalRightsEvidence(
                opaque_reference=f"synthetic-evidence-{ordinal}",
                digest_sha256=str(ordinal) * 64,
                policy_version="synthetic-v1",
                rights_holder_id=graph["owner"],
                verifier_id=graph["owner"],
            )
            repository.append_evidence(evidence, set(graph["authorities"]))
            graph["evidence"].append(evidence.evidence_id)
    graph.update(engine=engine, factory=factory, url=url)
    yield graph
    engine.dispose()


def lock_graph(session, graph, evidence_ids=None):
    repository = VocalRightsRepository(session)
    for evidence_id in sorted(evidence_ids or graph["evidence"], key=lambda value: value.hex):
        guard = session.get(VocalRightsEvidenceGuard, evidence_id, populate_existing=True)
        repository.conditional_guard_update("evidence", evidence_id, guard.guard_epoch)
    guard = session.get(VocalRightsScopeGuard, graph["scope"], populate_existing=True)
    repository.conditional_guard_update("scope", graph["scope"], guard.guard_epoch)
    return repository


def append_fixture_transition(
    repository, graph, index=0, transition=Transition.GRANTED, evidence_index=0
):
    current = repository.read_current(graph["authorities"][index])
    revision = current.semantic_revision + 1
    event_id, grant_id = uuid4(), uuid4()
    issuance = None
    if transition != Transition.REVOKED:
        issuance = VocalRightsGrant(
            grant_id=grant_id,
            authority_id=current.authority_id,
            evidence_id=graph["evidence"][evidence_index],
            issuer_id=graph["owner"],
            actor_id=graph["owner"],
            issued_revision=revision,
            issuance_event_id=event_id,
            idempotency_digest=f"{revision:064x}",
            reason_code="SYNTHETIC_FIXTURE",
        )
    event = VocalRightsEvent(
        event_id=event_id,
        authority_id=current.authority_id,
        semantic_revision=revision,
        transition=transition,
        old_grant_id=current.current_grant_id if transition != Transition.GRANTED else None,
        new_grant_id=grant_id if issuance else None,
        actor_id=graph["owner"],
        reason_code="SYNTHETIC_FIXTURE",
    )
    result = repository.append_transition(event, expected_revision=revision - 1, issuance=issuance)
    return result, event


def activate(graph):
    with graph["factory"].begin() as session:
        repository = lock_graph(session, graph)
        for index in (0, 1):
            append_fixture_transition(repository, graph, index)


def final_receipt(session, graph, repository):
    job = session.get(Job, graph["job"])
    job.status = JobStatus.SUCCEEDED
    output = JobOutput(
        job_id=job.job_id,
        artifact_id=graph["artifact"],
        output_role="corrected_vocal",
        output_order=0,
    )
    session.add(output)
    session.flush()
    receipt = VocalCompletionRightsReceipt(
        job_id=job.job_id,
        job_output_id=output.job_output_id,
        artifact_id=graph["artifact"],
        operation=Operation.VOCAL_CORRECT,
        actor_id=graph["owner"],
    )
    items = []
    for authority_id in reversed(graph["authorities"]):
        current = repository.read_current(authority_id)
        grant = session.get(VocalRightsGrant, current.current_grant_id)
        evidence = session.get(VocalRightsEvidence, grant.evidence_id)
        items.append(
            VocalCompletionRightsReceiptItem(
                authority_id=authority_id,
                grant_id=grant.grant_id,
                semantic_revision=current.semantic_revision,
                evidence_id=evidence.evidence_id,
                digest_sha256=evidence.digest_sha256,
                policy_version=evidence.policy_version,
            )
        )
    return repository.append_receipt(receipt, items)


def seed_all_audit(graph):
    activate(graph)
    with graph["factory"].begin() as session:
        repository = lock_graph(session, graph)
        final_receipt(session, graph, repository)
        for index in (0, 1):
            append_fixture_transition(repository, graph, index, Transition.REVOKED)
        repository.append_withdrawal_fact(
            VocalRightsEvidenceWithdrawal(
                evidence_id=graph["evidence"][0],
                actor_id=graph["owner"],
                reason_code="SYNTHETIC_WITHDRAWAL",
            )
        )


def test_mapper_metadata_and_fk_enabled(rights_graph):
    configure_mappers()
    assert {entity.__tablename__ for entity in VOCAL_RIGHTS_ENTITY_CLASSES} == set(TABLE_NAMES)
    with rights_graph["engine"].connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert not connection.execute(text("PRAGMA foreign_key_check")).all()
    inspector = inspect(rights_graph["engine"])
    assert set(TABLE_NAMES) <= set(inspector.get_table_names())
    assert all(inspector.get_foreign_keys(table) for table in TABLE_NAMES)


def test_empty_anchor_convergence_and_no_grant(rights_graph):
    graph = rights_graph
    with graph["factory"].begin() as session:
        repository = VocalRightsRepository(session)
        first = repository.ensure_scope_guard(graph["owner"], graph["workspace"])
        second = repository.ensure_scope_guard(graph["owner"], graph["workspace"])
        assert first.scope_guard_id == second.scope_guard_id == graph["scope"]
        current = repository.read_current(graph["authorities"][0])
        assert (current.current_grant_id, current.semantic_revision, current.last_event_id) == (
            None,
            0,
            None,
        )
        assert not session.scalars(select(VocalRightsGrant)).all()


def test_guard_actual_sql_rowcount_and_epoch_not_semantic_revision(rights_graph):
    statements = []
    sa_event.listen(
        rights_graph["engine"],
        "before_cursor_execute",
        lambda conn, cursor, sql, params, context, many: statements.append(sql),
    )
    # Factory has its own engine; attach observation to the actual Session bind.
    with rights_graph["factory"].begin() as session:
        sa_event.listen(
            session.get_bind(),
            "before_cursor_execute",
            lambda conn, cursor, sql, params, context, many: statements.append(sql),
        )
        repository = lock_graph(session, rights_graph)
        assert repository.read_current(rights_graph["authorities"][0]).semantic_revision == 0
    assert any(
        sql.startswith("UPDATE vocal_rights_scope_guards SET guard_epoch=")
        and "guard_epoch = ?" in sql
        for sql in statements
    )


@pytest.mark.parametrize("epoch", [-1, 0, MAX_TOKEN, MAX_TOKEN + 1])
def test_stale_invalid_overflow_epoch(rights_graph, epoch):
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        VocalRightsRepository(session).conditional_guard_update(
            "scope", rights_graph["scope"], epoch
        )


@pytest.mark.parametrize("kind", ["evidence", "scope"])
def test_missing_guard_is_conflict_not_provision(rights_graph, kind):
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        VocalRightsRepository(session).conditional_guard_update(kind, uuid4(), 0)


def test_guard_order_and_transaction_local_proof(rights_graph):
    graph = rights_graph
    with graph["factory"]() as session:
        with session.begin():
            repository = VocalRightsRepository(session)
            guard = session.get(VocalRightsScopeGuard, graph["scope"])
            repository.conditional_guard_update("scope", graph["scope"], guard.guard_epoch)
            with pytest.raises(VocalRightsPersistenceError):
                repository.conditional_guard_update("evidence", graph["evidence"][0], 0)
        with session.begin(), pytest.raises(VocalRightsPersistenceError):
            append_fixture_transition(repository, graph)


def test_evidence_order_rejects_late_lower_id(rights_graph):
    low, high = sorted(rights_graph["evidence"], key=lambda value: value.hex)
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        repository = VocalRightsRepository(session)
        repository.conditional_guard_update("evidence", high, 0)
        repository.conditional_guard_update("evidence", low, 0)


def test_issuance_revoke_regrant_supersede_one_revision_each(rights_graph):
    graph = rights_graph
    ids = []
    for transition, evidence_index in (
        (Transition.GRANTED, 0),
        (Transition.SUPERSEDED, 1),
        (Transition.REVOKED, 1),
        (Transition.GRANTED, 0),
    ):
        with graph["factory"].begin() as session:
            repository = lock_graph(session, graph)
            current, event = append_fixture_transition(
                repository, graph, transition=transition, evidence_index=evidence_index
            )
            ids.append((event.old_grant_id, event.new_grant_id))
            assert current.last_event_id == event.event_id
    with graph["factory"].begin() as session:
        repository = VocalRightsRepository(session)
        events = repository.list_events(graph["authorities"][0])
        assert [event.semantic_revision for event in events] == [1, 2, 3, 4]
        assert [event.transition for event in events] == [
            "GRANTED",
            "SUPERSEDED",
            "REVOKED",
            "GRANTED",
        ]
        assert ids[0][1] == ids[1][0] and ids[1][1] == ids[2][0]
        assert ids[3][1] not in {ids[0][1], ids[1][1]}
        assert len(session.scalars(select(VocalRightsGrant)).all()) == 3


def test_duplicate_active_denied(rights_graph):
    activate(rights_graph)
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        append_fixture_transition(lock_graph(session, rights_graph), rights_graph)


def test_stale_transition_cannot_overwrite_new_current(rights_graph):
    activate(rights_graph)
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        repository = lock_graph(session, rights_graph)
        current = repository.read_current(rights_graph["authorities"][0])
        repository.append_transition(
            VocalRightsEvent(
                authority_id=current.authority_id,
                semantic_revision=1,
                transition=Transition.REVOKED,
                old_grant_id=current.current_grant_id,
                actor_id=rights_graph["owner"],
                reason_code="SYNTHETIC_STALE",
            ),
            expected_revision=0,
        )


@pytest.mark.parametrize(
    "column,value",
    [
        ("semantic_revision", -1),
        ("semantic_revision", 2),
        ("semantic_revision", 0),
        ("current_grant_id", uuid4()),
        ("operation", "VOCAL_ANALYZE"),
        ("usage_role", "WILDCARD"),
        ("scope_guard_id", uuid4()),
    ],
)
def test_projection_direct_update_denied(rights_graph, column, value):
    activate(rights_graph)
    with pytest.raises(IntegrityError), rights_graph["factory"].begin() as session:
        session.execute(
            update(VocalRightsCurrentAuthority)
            .where(VocalRightsCurrentAuthority.authority_id == rights_graph["authorities"][0])
            .values(**{column: value})
        )


def test_cross_authority_pointer_denied(rights_graph):
    activate(rights_graph)
    with pytest.raises(IntegrityError), rights_graph["factory"].begin() as session:
        first = session.get(VocalRightsCurrentAuthority, rights_graph["authorities"][0])
        second = session.get(VocalRightsCurrentAuthority, rights_graph["authorities"][1])
        session.execute(
            update(VocalRightsCurrentAuthority)
            .where(VocalRightsCurrentAuthority.authority_id == first.authority_id)
            .values(
                current_grant_id=second.current_grant_id,
                semantic_revision=first.semantic_revision + 1,
            )
        )


@pytest.mark.parametrize("table", IMMUTABLE_TABLES)
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE"])
def test_immutable_audit_raw_sql(rights_graph, table, verb):
    seed_all_audit(rights_graph)
    with pytest.raises(IntegrityError), rights_graph["factory"].begin() as session:
        column = list(Base.metadata.tables[table].columns)[0].name
        sql = (
            f"DELETE FROM {table}"
            if verb == "DELETE"
            else f"UPDATE {table} SET {column} = {column}"
        )
        session.execute(text(sql))


@pytest.mark.parametrize(
    "table",
    [
        "vocal_rights_scope_guards",
        "vocal_rights_evidence_guards",
        "vocal_rights_current_authorities",
    ],
)
def test_stable_anchors_never_deleted(rights_graph, table):
    with pytest.raises(IntegrityError), rights_graph["factory"].begin() as session:
        session.execute(text(f"DELETE FROM {table}"))


@pytest.mark.parametrize("target", [Workspace, Asset, AssetVersion, Artifact])
def test_audit_parent_delete_restricted(rights_graph, target):
    seed_all_audit(rights_graph)
    with pytest.raises(IntegrityError), rights_graph["factory"].begin() as session:
        session.execute(target.__table__.delete())


def test_wrong_workspace_and_wrong_owner_cannot_provision(rights_graph):
    graph = rights_graph
    with pytest.raises(VocalRightsPersistenceError), graph["factory"].begin() as session:
        VocalRightsRepository(session).ensure_scope_guard(uuid4(), graph["workspace"])
    with pytest.raises(VocalRightsPersistenceError), graph["factory"].begin() as session:
        repository = lock_graph(session, graph)
        repository.ensure_current_authority(
            graph["scope"], Subject.WORKSPACE, uuid4(), Operation.VOCAL_GENERATE, Role.CREATE_OUTPUT
        )


@pytest.mark.parametrize(
    "operation,role",
    [
        ("TRANSFORM", "SOURCE_VOCAL"),
        ("VOCAL_TRANSFORM", "OUTPUT"),
        ("VOCAL_ANALYZE", "VOICE_REFERENCE"),
        ("OUTPUT_READ", "SOURCE_VOCAL"),
        ("VOCAL_CORRECT", "ALL"),
    ],
)
def test_invalid_exact_key_vocabulary_denied(rights_graph, operation, role):
    with pytest.raises(IntegrityError), rights_graph["factory"].begin() as session:
        session.add(
            VocalRightsCurrentAuthority(
                scope_guard_id=rights_graph["scope"],
                subject_type="ASSET_VERSION",
                subject_id=rights_graph["versions"][0],
                operation=operation,
                usage_role=role,
            )
        )
        session.flush()


def test_withdrawal_cannot_skip_connected_current_grants(rights_graph):
    activate(rights_graph)
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        repository = lock_graph(session, rights_graph)
        repository.append_withdrawal_fact(
            VocalRightsEvidenceWithdrawal(
                evidence_id=rights_graph["evidence"][0],
                actor_id=rights_graph["owner"],
                reason_code="SYNTHETIC_WITHDRAWAL",
            )
        )


def test_withdrawn_evidence_cannot_support_new_issuance(rights_graph):
    graph = rights_graph
    with graph["factory"].begin() as session:
        repository = lock_graph(session, graph)
        repository.append_withdrawal_fact(
            VocalRightsEvidenceWithdrawal(
                evidence_id=graph["evidence"][0],
                actor_id=graph["owner"],
                reason_code="SYNTHETIC_WITHDRAWAL",
            )
        )
    with pytest.raises(VocalRightsPersistenceError), graph["factory"].begin() as session:
        append_fixture_transition(lock_graph(session, graph), graph)


def test_receipt_multi_item_snapshot_and_historical_preservation(rights_graph):
    graph = rights_graph
    activate(graph)
    with graph["factory"].begin() as session:
        receipt = final_receipt(session, graph, lock_graph(session, graph))
        receipt_id = receipt.receipt_id
    with graph["factory"].begin() as session:
        append_fixture_transition(
            lock_graph(session, graph), graph, transition=Transition.SUPERSEDED, evidence_index=1
        )
    with graph["factory"].begin() as session:
        items = session.scalars(
            select(VocalCompletionRightsReceiptItem)
            .where(VocalCompletionRightsReceiptItem.receipt_id == receipt_id)
            .order_by(VocalCompletionRightsReceiptItem.ordinal)
        ).all()
        assert len(items) == 2
        assert [item.ordinal for item in items] == [0, 1]
        assert {item.semantic_revision for item in items} == {1}
        assert {item.digest_sha256 for item in items} == {"1" * 64}
        assert {item.policy_version for item in items} == {"synthetic-v1"}
        current = session.get(VocalRightsCurrentAuthority, graph["authorities"][0])
        assert current.semantic_revision == 2


@pytest.mark.parametrize("failure_point", ["header", "first_item", "last_item", "after_receipt"])
def test_receipt_and_output_caller_transaction_roll_back_together(rights_graph, failure_point):
    graph = rights_graph
    activate(graph)
    injected_points = []
    with (
        pytest.raises(RuntimeError, match="synthetic failure"),
        graph["factory"].begin() as session,
    ):
        repository = lock_graph(session, graph)

        def injected(session, flush_context):
            receipts = [
                obj
                for obj in session.identity_map.values()
                if isinstance(obj, VocalCompletionRightsReceipt)
            ]
            items = [
                obj
                for obj in session.identity_map.values()
                if isinstance(obj, VocalCompletionRightsReceiptItem)
            ]
            if (
                (failure_point == "header" and receipts and not items)
                or (failure_point == "first_item" and len(items) == 1)
                or (failure_point == "last_item" and len(items) == 2)
            ):
                injected_points.append(failure_point)
                raise RuntimeError("synthetic failure")

        sa_event.listen(session, "after_flush_postexec", injected)
        final_receipt(session, graph, repository)
        raise RuntimeError("synthetic failure")
    if failure_point != "after_receipt":
        assert injected_points == [failure_point]
    with graph["factory"].begin() as session:
        assert session.get(Job, graph["job"]).status == JobStatus.RUNNING
        assert not session.scalars(select(JobOutput)).all()
        assert not session.scalars(select(VocalCompletionRightsReceipt)).all()
        assert not session.scalars(select(VocalCompletionRightsReceiptItem)).all()


def test_receipt_incomplete_header_cannot_commit(rights_graph):
    activate(rights_graph)
    with pytest.raises(IntegrityError), rights_graph["factory"].begin() as session:
        job = session.get(Job, rights_graph["job"])
        job.status = JobStatus.SUCCEEDED
        output = JobOutput(
            job_id=job.job_id,
            artifact_id=rights_graph["artifact"],
            output_role="corrected_vocal",
            output_order=0,
        )
        session.add(output)
        session.flush()
        session.add(
            VocalCompletionRightsReceipt(
                job_id=job.job_id,
                job_output_id=output.job_output_id,
                artifact_id=rights_graph["artifact"],
                operation=Operation.VOCAL_CORRECT,
                actor_id=rights_graph["owner"],
                item_count=1,
                last_ordinal=0,
                last_item_id=uuid4(),
            )
        )
        session.flush()


def test_duplicate_receipt_is_conflict_not_replay_mutation(rights_graph):
    activate(rights_graph)
    with rights_graph["factory"].begin() as session:
        final_receipt(session, rights_graph, lock_graph(session, rights_graph))
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        original = session.scalar(select(VocalCompletionRightsReceipt))
        duplicate = VocalCompletionRightsReceipt(
            job_id=original.job_id,
            job_output_id=original.job_output_id,
            artifact_id=original.artifact_id,
            operation=original.operation,
            actor_id=original.actor_id,
        )
        original_items = session.scalars(select(VocalCompletionRightsReceiptItem)).all()
        items = [
            VocalCompletionRightsReceiptItem(
                authority_id=item.authority_id,
                grant_id=item.grant_id,
                semantic_revision=item.semantic_revision,
                evidence_id=item.evidence_id,
                digest_sha256=item.digest_sha256,
                policy_version=item.policy_version,
            )
            for item in original_items
        ]
        lock_graph(session, rights_graph).append_receipt(duplicate, items)


def test_flush_only_caller_owned_session(rights_graph, monkeypatch):
    with rights_graph["factory"]() as session:
        with session.begin():

            def forbidden(*args, **kwargs):
                raise AssertionError("repository must not own transaction end")

            monkeypatch.setattr(session, "commit", forbidden)
            monkeypatch.setattr(session, "rollback", forbidden)
            repository = lock_graph(session, rights_graph)
            append_fixture_transition(repository, rights_graph)
        with session.begin():
            assert (
                session.get(
                    VocalRightsCurrentAuthority, rights_graph["authorities"][0]
                ).semantic_revision
                == 1
            )


def test_actual_guard_update_serializes_two_sessions_until_commit(rights_graph):
    graph = rights_graph
    attempted, finished = Event(), Event()
    with graph["factory"]() as first, ThreadPoolExecutor(max_workers=1) as executor:
        with first.begin():
            repository = VocalRightsRepository(first)
            repository.conditional_guard_update("scope", graph["scope"], 1)

            def contender():
                attempted.set()
                try:
                    with graph["factory"].begin() as session:
                        VocalRightsRepository(session).conditional_guard_update(
                            "scope", graph["scope"], 1
                        )
                except VocalRightsPersistenceError as exc:
                    return exc.code
                finally:
                    finished.set()
                return "unexpected success"

            future = executor.submit(contender)
            assert attempted.wait(2)
            assert not finished.wait(0.15)
        assert future.result(timeout=5) == "AUTHORITY_CONFLICT"
    with graph["factory"].begin() as session:
        assert session.get(VocalRightsScopeGuard, graph["scope"]).guard_epoch == 2


def test_guard_rollback_allows_waiting_caller_without_semantic_change(rights_graph):
    graph = rights_graph
    with pytest.raises(RuntimeError), graph["factory"].begin() as session:
        lock_graph(session, graph)
        append_fixture_transition(VocalRightsRepository(session), graph)
        raise RuntimeError("synthetic rollback")
    with graph["factory"].begin() as session:
        repository = lock_graph(session, graph)
        assert repository.read_current(graph["authorities"][0]).semantic_revision == 0
        append_fixture_transition(repository, graph)


def test_missing_caller_transaction_and_unsupported_engine_fail_closed(rights_graph, monkeypatch):
    with rights_graph["factory"]() as session:
        with pytest.raises(VocalRightsPersistenceError):
            VocalRightsRepository(session).ensure_scope_guard(
                rights_graph["owner"], rights_graph["workspace"]
            )
        with session.begin():
            monkeypatch.setattr(session.get_bind().dialect, "name", "unsupported")
            with pytest.raises(VocalRightsPersistenceError, match="AUTHORITY_UNAVAILABLE"):
                VocalRightsRepository(session).conditional_guard_update(
                    "scope", rights_graph["scope"], 1
                )


def test_safe_error_contains_no_sql_evidence_or_path(rights_graph):
    activate(rights_graph)
    with (
        pytest.raises(VocalRightsPersistenceError) as caught,
        rights_graph["factory"].begin() as session,
    ):
        append_fixture_transition(lock_graph(session, rights_graph), rights_graph)
    assert str(caught.value) == "AUTHORITY_CONFLICT"
    assert caught.value.__suppress_context__ or caught.value.__context__ is None


def test_evidence_scope_cannot_extend_after_binding_commit(rights_graph):
    graph = rights_graph
    with graph["factory"].begin() as session:
        repository = lock_graph(session, graph)
        new_authority = repository.ensure_current_authority(
            graph["scope"],
            Subject.WORKSPACE,
            graph["workspace"],
            Operation.VOCAL_GENERATE,
            Role.CREATE_OUTPUT,
        )
        authority_id = new_authority.authority_id
    with pytest.raises(IntegrityError), graph["factory"].begin() as session:
        session.add(
            VocalRightsEvidenceScope(
                evidence_id=graph["evidence"][0], authority_id=authority_id, ordinal=2
            )
        )
        session.flush()


def test_nested_transaction_cannot_claim_root_guard_proof(rights_graph):
    with (
        rights_graph["factory"].begin() as session,
        session.begin_nested(),
        pytest.raises(VocalRightsPersistenceError, match="AUTHORITY_UNAVAILABLE"),
    ):
        VocalRightsRepository(session).conditional_guard_update("scope", rights_graph["scope"], 1)


def test_foreign_keys_disabled_connection_fails_closed(rights_graph):
    with rights_graph["factory"].begin() as session:
        session.execute(text("PRAGMA foreign_keys = OFF"))
        with pytest.raises(VocalRightsPersistenceError, match="AUTHORITY_UNAVAILABLE"):
            VocalRightsRepository(session).conditional_guard_update(
                "scope", rights_graph["scope"], 1
            )
        session.execute(text("PRAGMA foreign_keys = ON"))


@pytest.mark.parametrize(
    "column,value",
    [
        ("opaque_reference", "https://not-an-opaque-reference.invalid"),
        ("opaque_reference", "synthetic/path"),
        ("digest_sha256", "x" * 64),
        ("digest_sha256", "a" * 63),
        ("policy_version", ""),
    ],
)
def test_invalid_evidence_facts_are_safe_conflicts(rights_graph, column, value):
    graph = rights_graph
    with pytest.raises(VocalRightsPersistenceError) as caught, graph["factory"].begin() as session:
        facts = dict(
            opaque_reference="synthetic-new",
            digest_sha256="a" * 64,
            policy_version="synthetic-v1",
            rights_holder_id=graph["owner"],
            verifier_id=graph["owner"],
        )
        facts[column] = value
        lock_graph(session, graph).append_evidence(
            VocalRightsEvidence(**facts), set(graph["authorities"])
        )
    assert str(caught.value) == "AUTHORITY_CONFLICT"


def test_unissued_grant_cannot_commit_without_exact_event(rights_graph):
    graph = rights_graph
    with pytest.raises(IntegrityError), graph["factory"].begin() as session:
        lock_graph(session, graph)
        session.add(
            VocalRightsGrant(
                authority_id=graph["authorities"][0],
                evidence_id=graph["evidence"][0],
                issuer_id=graph["owner"],
                actor_id=graph["owner"],
                issued_revision=1,
                issuance_event_id=uuid4(),
                idempotency_digest="f" * 64,
                reason_code="SYNTHETIC_UNISSUED",
            )
        )
        session.flush()


@pytest.mark.parametrize(
    "model,column,value",
    [
        (VocalCompletionRightsReceipt, "artifact_id", uuid4()),
        (VocalCompletionRightsReceipt, "job_id", uuid4()),
        (VocalCompletionRightsReceipt, "operation", Operation.VOCAL_GENERATE),
        (VocalCompletionRightsReceiptItem, "semantic_revision", 2),
        (VocalCompletionRightsReceiptItem, "digest_sha256", "a" * 64),
        (VocalCompletionRightsReceiptItem, "policy_version", "synthetic-wrong"),
    ],
)
def test_receipt_wrong_binding_or_snapshot_denied(rights_graph, model, column, value):
    activate(rights_graph)
    with pytest.raises(VocalRightsPersistenceError), rights_graph["factory"].begin() as session:
        repository = lock_graph(session, rights_graph)

        def corrupt_fixture(session, flush_context, instances):
            for obj in session.new:
                if isinstance(obj, model):
                    setattr(obj, column, value)

        sa_event.listen(session, "before_flush", corrupt_fixture)
        final_receipt(session, rights_graph, repository)


def test_sqlite_busy_is_safe_unavailable_and_never_unlocked_fallback(rights_graph):
    graph = rights_graph
    with graph["factory"].begin() as holder, ThreadPoolExecutor(max_workers=1) as executor:
        VocalRightsRepository(holder).conditional_guard_update("scope", graph["scope"], 1)

        def busy_caller():
            try:
                with graph["factory"].begin() as session:
                    session.execute(text("PRAGMA busy_timeout = 30"))
                    VocalRightsRepository(session).conditional_guard_update(
                        "scope", graph["scope"], 1
                    )
            except VocalRightsPersistenceError as exc:
                return exc.code
            return "unexpected success"

        assert executor.submit(busy_caller).result(timeout=3) == "AUTHORITY_UNAVAILABLE"


def test_sqlite_wal_snapshot_conflict_requires_whole_caller_restart(rights_graph):
    graph = rights_graph
    with graph["engine"].connect() as connection:
        assert connection.scalar(text("PRAGMA journal_mode = WAL")) == "wal"
    with graph["factory"]() as stale:
        with (
            pytest.raises(VocalRightsPersistenceError, match="AUTHORITY_UNAVAILABLE"),
            stale.begin(),
        ):
            stale.execute(text("BEGIN"))
            assert stale.get(VocalRightsScopeGuard, graph["scope"]).guard_epoch == 1
            with graph["factory"].begin() as winner:
                VocalRightsRepository(winner).conditional_guard_update("scope", graph["scope"], 1)
            VocalRightsRepository(stale).conditional_guard_update("scope", graph["scope"], 1)
        with stale.begin():
            guard = stale.get(VocalRightsScopeGuard, graph["scope"], populate_existing=True)
            assert guard.guard_epoch == 2
            VocalRightsRepository(stale).conditional_guard_update("scope", graph["scope"], 2)


def test_absent_key_two_callers_converge_to_one_guard_after_unique_loser_restart(rights_graph):
    graph = rights_graph
    with graph["factory"].begin() as session:
        workspace = Workspace(
            owner_id=graph["owner"], name="Synthetic absent key", lifecycle_status="active"
        )
        session.add(workspace)
        session.flush()
        workspace_id = workspace.workspace_id
    discovered, release = Event(), Event()
    with ThreadPoolExecutor(max_workers=1) as executor:

        def loser():
            try:
                with graph["factory"].begin() as session:
                    repository = VocalRightsRepository(session)
                    assert repository.get_scope_guard(graph["owner"], workspace_id) is None
                    discovered.set()
                    assert release.wait(3)
                    # Stale absence discovery deliberately attempts unique insert.
                    session.add(
                        VocalRightsScopeGuard(owner_id=graph["owner"], workspace_id=workspace_id)
                    )
                    session.flush()
            except IntegrityError:
                with graph["factory"].begin() as session:
                    return (
                        VocalRightsRepository(session)
                        .ensure_scope_guard(graph["owner"], workspace_id)
                        .scope_guard_id
                    )
            return None

        future = executor.submit(loser)
        assert discovered.wait(3)
        with graph["factory"].begin() as session:
            guard_id = (
                VocalRightsRepository(session)
                .ensure_scope_guard(graph["owner"], workspace_id)
                .scope_guard_id
            )
        release.set()
        assert future.result(timeout=5) == guard_id
    with graph["factory"].begin() as session:
        guards = session.scalars(
            select(VocalRightsScopeGuard).where(VocalRightsScopeGuard.workspace_id == workspace_id)
        ).all()
        assert len(guards) == 1 and guards[0].guard_epoch == 0
