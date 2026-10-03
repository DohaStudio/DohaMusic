"""Actual held Windows custody + query-only L/H + opaque PRE capability."""

import copy
import pickle
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest
from sqlalchemy import text

from backend.bootstrap_authority.ibla.contracts import IblaConflict, IblaDenied
from backend.bootstrap_authority.ibla.source_codec import ANCHOR_DOMAIN, ARRAY_FIELDS
from backend.bootstrap_authority.ibla.source_verifier import _IblaSourceVerifier
from backend.tests.ibla_source_support import b64, native_fixture, sign, verified
from backend.tests.ibla_support import session, uid


def test_authentic_source_capability_handoff_and_persistent_mutation_zero(tmp_path):
    v, proof, paths, received, *_ = native_fixture(tmp_path)
    before = tuple(path.read_bytes() for path in paths)
    with v.observe() as context:
        source = verified(v, proof, context)
        cap = v.mint(source)
        assert repr(cap) == "<opaque IBLA handle>"
        for copier in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError, match="OPAQUE_IBLA_HANDLE"):
                copier(cap)
        with pytest.raises(IblaConflict):
            v.mint(source)
        with pytest.raises(IblaDenied):
            v.require_handoff(cap)
        v.handoff(cap)
        assert received == [cap]
        with pytest.raises(IblaConflict):
            v.handoff(cap)
    with pytest.raises(IblaDenied):
        v.handoff(cap)
    assert before == tuple(path.read_bytes() for path in paths)


@pytest.mark.parametrize("stage", ["empty", "prepared", "appended", "uncertain"])
def test_nonconfirmed_checkpoint_cannot_observe_or_mint(tmp_path, stage):
    v, *_ = native_fixture(tmp_path, stage=stage)
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("unconfirmed observation exposed")


@pytest.mark.parametrize(
    "role", range(7), ids=["A", "C", "designation", "ceremony", "mapping", "L", "H"]
)
def test_each_independently_retained_native_identity_mismatch(tmp_path, role):
    _, _, _, _, setup, *_ = native_fixture(tmp_path)
    roles = list(setup.roles)
    roles[role] = replace(
        roles[role], policy=replace(roles[role].policy, record_identity=(1, b"x" * 16))
    )
    v = _IblaSourceVerifier(replace(setup, roles=tuple(roles)), consumer=lambda cap: None)
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("discovered native identity adopted")


@pytest.mark.parametrize(
    "field",
    [
        "domain_id",
        "deployment_id",
        "installation_id",
        "lineage_id",
        "journal_id",
        "ledger_id",
        "checkpoint_id",
        "designation_id",
        "commissioning_action_id",
        "authority_epoch",
        "installation_proof_digest",
        "root_key_id",
        "initializer_ref",
        "initializer_key_id",
        "ledger_custodian_ref",
        "checkpoint_keeper_ref",
        "positive_origin_digest",
        "governance_provenance_digest",
    ],
)
def test_signed_self_created_action_cannot_replace_independent_original_action(tmp_path, field):
    v, _, paths, _, _, a, _, root, *_ = native_fixture(tmp_path)
    a[field] = (
        2
        if field == "authority_epoch"
        else (uid(9000) if field.endswith("_id") and not field.endswith("_key_id") else "foreign")
    )
    paths[0].write_bytes(sign(root, ANCHOR_DOMAIN, a))
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("new signed action became trusted accepted ceremony")


@pytest.mark.parametrize(
    "kind",
    [
        "REGISTRATION_COMMITTED",
        "INITIAL_AUTHORIZATION_ISSUED",
        "INITIAL_AUTHORIZATION_CONSUMED",
        "INITIAL_AUTHORIZATION_CANCELLED",
        "GENESIS",
        "HISTORY_BLOCK",
        "RETIRE",
        "UNKNOWN",
    ],
)
def test_complete_retained_external_history_cannot_be_erased_into_absence(tmp_path, kind):
    def transform(a, c):
        a["inventory"]["external_history"] = [
            {
                "record_ref": "fixture-prior",
                "record_digest": a["designation_digest"],
                "fact_kind": kind,
                "affected_scopes": a["inventory"]["scopes"],
            }
        ]

    v, *_ = native_fixture(tmp_path, transform=transform)
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("prior/unknown authoritative fact skipped")


@pytest.mark.parametrize(
    "name", ["installation_aliases", "lineage_aliases", "journal_aliases", "imported_scope_refs"]
)
def test_valid_retained_alias_import_is_unsupported_not_silent_negative_proof(tmp_path, name):
    def transform(a, c):
        row = {
            key: (
                a[key]
                if key in a
                else ("fixture-import" if key == "ref" else a["designation_digest"])
            )
            for key in ARRAY_FIELDS[name]
        }
        a["inventory"][name] = [row]

    v, *_ = native_fixture(tmp_path, transform=transform)
    with pytest.raises(IblaDenied, match="^IBLA_UNAVAILABLE$"), v.observe():
        pytest.fail("unsupported coverage approved")


def test_missing_original_mapping_and_wrong_independent_pin_cannot_enroll(tmp_path):
    _, _, _, _, setup, *_ = native_fixture(tmp_path)
    for change in (
        {"root_public": b"x" * 32},
        {"initializer_public": b"x" * 32},
        {"proof_public": b"x" * 32},
        {"retained_mapping": b"{}"},
        {"designation_digest": "sha256:" + "0" * 64},
        {"ceremony_digest": "sha256:" + "0" * 64},
    ):
        v = _IblaSourceVerifier(replace(setup, **change), consumer=lambda cap: None)
        with pytest.raises(IblaDenied), v.observe():
            pytest.fail("source self-pinned")


def test_possession_is_fresh_once_and_different_observation_replay_denied(tmp_path):
    v, proof, *_ = native_fixture(tmp_path)
    with v.observe() as context:
        response = b64(proof.sign(v.challenge(context)))
        source = v.verify_source(context, response)
        with pytest.raises(IblaConflict):
            v.verify_source(context, response)
        assert v.mint(source)
    with pytest.raises(IblaDenied), v.observe() as context:
        v.verify_source(context, response)


def test_expiry_release_and_foreign_provider_never_revive(tmp_path, monkeypatch):
    import backend.bootstrap_authority.ibla.source_verifier as module

    v, proof, _, _, setup, *_ = native_fixture(tmp_path)
    foreign = _IblaSourceVerifier(setup, consumer=lambda cap: None)
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        with pytest.raises(IblaDenied):
            foreign.handoff(cap)
        record = v._records[id(cap)]
        actual = module.time.monotonic
        with monkeypatch.context() as m:
            m.setattr(module.time, "monotonic", lambda: record.deadline + 1)
            with pytest.raises(IblaDenied):
                v.handoff(cap)
        assert actual() < record.deadline
        with pytest.raises(IblaDenied):
            v.handoff(cap)


def test_deterministic_concurrent_mint_handoff_original_thread_single_winner(tmp_path):
    v, proof, _, received, *_ = native_fixture(tmp_path)
    barrier = Barrier(2)

    def foreign_call(function, handle):
        barrier.wait(timeout=10)
        with pytest.raises(IblaDenied):
            function(handle)

    with v.observe() as context, ThreadPoolExecutor(max_workers=1) as executor:
        source = verified(v, proof, context)
        worker = executor.submit(foreign_call, v.mint, source)
        barrier.wait(timeout=10)
        cap = v.mint(source)
        worker.result(timeout=10)
        worker = executor.submit(foreign_call, v.handoff, cap)
        barrier.wait(timeout=10)
        v.handoff(cap)
        worker.result(timeout=10)
        assert received == [cap]


def test_changed_acl_permanent_stale_even_after_restoration(tmp_path):
    from backend.tests.test_designation_source_custody import native_acl, process_account

    v, proof, paths, *_ = native_fixture(tmp_path)
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        sid = process_account()[1]
        native_acl(paths[0], sid, suffix="(A;;FR;;;WD)")
        with pytest.raises(IblaDenied):
            v.handoff(cap)
        native_acl(paths[0], sid)
        v.handoff(cap)


def test_callback_response_loss_is_abandoned_no_retry(tmp_path):
    def consumer(cap):
        raise RuntimeError("private callback material")

    v, proof, *_ = native_fixture(tmp_path, consumer=consumer)
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        with pytest.raises(IblaDenied, match="^IBLA_UNAVAILABLE$"):
            v.handoff(cap)
        v.handoff(cap)


def test_complete_ordered_history_query_plan_preserves_indexes(tmp_path):
    _, _, paths, *_ = native_fixture(tmp_path)
    for path in paths[-2:]:
        with session(path, readonly=True) as s:
            plan = s.execute(
                text(
                    "EXPLAIN QUERY PLAN SELECT revision,envelope FROM ibla_events ORDER BY revision"
                )
            ).all()
            assert not any("TEMP B-TREE" in row[3] for row in plan)
            plan = s.execute(
                text(
                    "EXPLAIN QUERY PLAN SELECT envelope FROM ibla_events "
                    "WHERE operation_id=:operation"
                ),
                {"operation": uid(3001)},
            ).all()
            assert any("INDEX" in row[3] for row in plan)


@pytest.mark.parametrize(
    "change", ["gap", "projection", "hidden-suffix", "unknown-kind", "bad-evidence", "H-head"]
)
def test_actual_whole_history_and_projection_fail_closed(tmp_path, change):
    v, _, paths, *_ = native_fixture(tmp_path)
    import sqlite3

    path = paths[-1] if change == "H-head" else paths[-2]
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA ignore_check_constraints=ON")
        # Deliberately corrupt ONLY disposable stores; never modify production schema.
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall():
            conn.execute(f'DROP TRIGGER "{name}"')
        if change == "gap":
            conn.execute("DELETE FROM ibla_events WHERE revision=1")
        elif change in {"projection", "H-head"}:
            conn.execute("UPDATE ibla_head SET revision=revision+1")
        elif change == "unknown-kind":
            conn.execute("UPDATE ibla_events SET kind='REGISTRATION_COMMITTED'")
        elif change == "hidden-suffix":
            conn.execute("UPDATE ibla_events SET revision=2")
        else:
            conn.execute("UPDATE ibla_events SET envelope=?", (b"{}",))
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("partial history admitted")


@pytest.mark.parametrize(
    "change", ["empty", "missing-field", "different-scope", "duplicate", "unsorted"]
)
def test_partial_or_malformed_inventory_never_proves_absence(tmp_path, change):
    def transform(a, c):
        i = a["inventory"]
        if change == "empty":
            i["scopes"] = []
        elif change == "missing-field":
            del i["coverage_start_digest"]
        elif change == "different-scope":
            i["scopes"][0]["installation_id"] = uid(9999)
        elif change == "duplicate":
            i["scopes"] *= 2
        else:
            first = dict(i["scopes"][0], workspace_id=uid(9999))
            i["scopes"].insert(0, first)

    v, *_ = native_fixture(tmp_path, transform=transform)
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("incomplete authoritative inventory admitted")


def test_valid_later_block_is_conflict_and_stale_lh_never_revalidates(tmp_path):
    from backend.bootstrap_authority.ibla.codec import encode_event
    from backend.tests.ibla_support import keeper, ledger

    v, proof, paths, _, _, a, _, _, _, binding = native_fixture(tmp_path)
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        with ledger(paths[-2], readonly=True, binding=binding) as reader:
            head = reader.read().head
        wire = encode_event(
            binding,
            event_id=uid(3100),
            operation_id=uid(3101),
            expected=head,
            kind="HISTORY_BLOCK",
            evidence_digest=binding.anchor_digest,
            recorded_at=a["issued_at"],
        )
        with keeper(*paths[-2:], binding=binding) as writer:
            writer.prepare(wire, expected=writer.read().head)
        with ledger(paths[-2], binding=binding) as writer:
            result = writer.append(wire, expected=head)
        with keeper(*paths[-2:], binding=binding) as writer:
            writer.confirm(result.operation_id, result.fingerprint)
        with pytest.raises(IblaConflict):
            v.handoff(cap)
        v.handoff(cap)


@pytest.mark.parametrize(
    "action", ["proof-wrong", "source-release", "lease-release", "provider-close", "clock-rollback"]
)
def test_all_lifetime_intersections_and_proof_failures_permanently_abandon(
    tmp_path, action, monkeypatch
):
    import backend.bootstrap_authority.ibla.source_verifier as module

    v, proof, *_ = native_fixture(tmp_path)
    with pytest.raises(IblaDenied), v.observe() as context:
        if action == "proof-wrong":
            v.verify_source(context, "A" * 86)
        cap = v.mint(verified(v, proof, context))
        record = v._records[id(cap)]
        if action == "source-release":
            record.source.close()
        elif action == "lease-release":
            record.lease._active = False
        elif action == "provider-close":
            v.close()
        else:
            monkeypatch.setattr(module.time, "monotonic", lambda: record.started - 1)
        v.handoff(cap)


def test_missing_replaced_hardlinked_source_not_a_new_first_origin(tmp_path):
    import os

    v, _, paths, *_ = native_fixture(tmp_path)
    os.link(paths[0], paths[0].with_suffix(".link"))
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("hardlinked commissioning source admitted")


def test_live_source_write_rename_delete_blocked(tmp_path):
    v, proof, paths, *_ = native_fixture(tmp_path)
    with v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        for path in paths[:5]:
            with pytest.raises(OSError):
                path.write_bytes(b"replacement")
            with pytest.raises(OSError):
                path.rename(path.with_suffix(".moved"))
            with pytest.raises(OSError):
                path.unlink()
        v.handoff(cap)


def test_source_cleanup_uncertainty_retains_native_ownership(tmp_path, monkeypatch):
    v, proof, *_ = native_fixture(tmp_path)
    files = None
    with pytest.raises(IblaDenied), v.observe() as context:
        v.mint(verified(v, proof, context))
        files = v._records[id(context)].source.files[0]
        close = files._api.CloseHandle
        monkeypatch.setattr(files._api, "CloseHandle", lambda handle: False)
    assert v._retained and files._quarantine
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("uncertain provider reused")
    monkeypatch.setattr(files._api, "CloseHandle", close)
    files._cleanup_failed_snapshots()
    assert not files._quarantine


def test_unexpected_nested_read_transaction_abandons_observation(tmp_path, monkeypatch):
    from backend.bootstrap_authority.ibla.repository import LedgerRepository

    v, proof, *_ = native_fixture(tmp_path)
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        original_read = LedgerRepository.read

        def unexpected_savepoint(repository):
            result = original_read(repository)
            repository.session.begin_nested()
            return result

        monkeypatch.setattr(LedgerRepository, "read", unexpected_savepoint)
        v.handoff(cap)


def test_source_release_during_callback_abandons_delivered_handle(tmp_path):
    def consumer(cap):
        v.require_handoff(cap)
        v._records[id(cap)].source.close()

    v, proof, *_ = native_fixture(tmp_path, consumer=consumer)
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        with pytest.raises(IblaDenied):
            v.handoff(cap)
        v.handoff(cap)


def test_foreign_thread_cannot_cleanup_original_source(tmp_path):
    v, proof, *_ = native_fixture(tmp_path)
    with v.observe() as context, ThreadPoolExecutor(max_workers=1) as executor:
        cap = v.mint(verified(v, proof, context))
        source = v._records[id(cap)].source
        with pytest.raises(IblaDenied):
            executor.submit(source.close).result(timeout=10)
        assert not source.closed
        v.handoff(cap)


@pytest.mark.parametrize("role", ["L", "H"])
def test_wal_profile_rejected_before_sqlite_can_create_sidecar_files(tmp_path, role):
    import sqlite3

    v, _, paths, *_ = native_fixture(tmp_path)
    path = paths[-2] if role == "L" else paths[-1]
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    connection.close()
    before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
    with pytest.raises(IblaDenied), v.observe():
        pytest.fail("WAL profile opened through read-only verifier")
    assert before == {p.name: p.read_bytes() for p in path.parent.iterdir()}
