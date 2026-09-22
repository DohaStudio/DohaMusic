"""AdmissionAttempt Provider regression; preparation is never durable admission."""

from __future__ import annotations

import copy
import json
import pickle
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from threading import Barrier
from unittest.mock import Mock

import pytest
import rfc8785

from backend.bootstrap_authority.admission_attempt import (
    AdmissionAttemptDenied,
    _AdmissionAttemptProvider,
)
from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.tests.test_bootstrap_lifecycle_journal import event, keys, wire
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_currentness_witness_handoff import (
    issue_args,
    live_handoff,
)
from backend.tests.test_provisioning_authority_source import uid

pytest_plugins = ("backend.tests.test_currentness_witness_handoff",)


def candidate(context, *, kind="NORMAL_ROTATION"):
    binding = context[4]["pin_facts"].binding
    new = None if kind == "REVOKE" else "root/test-2"
    payload, expected = event(
        binding.journal.revision + 1,
        binding.journal.head_digest,
        kind,
        binding.root_key_id,
        new,
    )
    payload["designation_record_digest"] = digest(b"candidate designation record")
    if kind == "EXTERNAL_REDESIGNATION":
        payload["designation_id"] = uid(999)
    manifest = rfc8785.dumps(
        [
            dict(
                zip(
                    ("installation_id", "workspace_id", "existing_owner_id"),
                    scope,
                    strict=True,
                )
            )
            for scope in binding.affected_scopes
        ]
    )
    payload["affected_scope_manifest_digest"] = digest(manifest)
    names = (binding.root_key_id,) if new is None else (binding.root_key_id, new)
    material = keys()
    expected = replace(
        expected,
        designation_id=payload["designation_id"],
        designation_record_digest=payload["designation_record_digest"],
        authoritative_scopes=binding.affected_scopes,
        public_keys=tuple((name, material[name].public_key().public_bytes_raw()) for name in names),
    )
    return wire(payload), manifest, expected


@contextmanager
def live_attempt(tmp_path, engine, *, kind="NORMAL_ROTATION"):
    with live_handoff(tmp_path, engine) as context:
        handoff, currentness_arguments = issue_args(context)
        provider = _AdmissionAttemptProvider(currentness_handoff=handoff)
        artifact, manifest, expected = candidate(context, kind=kind)
        with handoff._open_witness(**currentness_arguments) as witness:
            call = {
                "currentness_witness": witness,
                "artifact": artifact,
                "manifest": manifest,
                "expected": expected,
                **currentness_arguments,
            }
            with provider._open_attempt(**call) as attempt:
                yield provider, attempt, witness, currentness_arguments, context, call


@pytest.mark.parametrize("kind", ["NORMAL_ROTATION", "REVOKE", "EXTERNAL_REDESIGNATION"])
def test_attempt_is_opaque_exact_candidate_and_not_admission(
    tmp_path, currentness_journal_engine, kind
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine, kind=kind) as value:
        provider, attempt, witness, currentness_arguments, _, _ = value
        record = provider._require_prepared(
            attempt,
            currentness_witness=witness,
            **currentness_arguments,
        )
        assert record.candidate.event_kind == kind
        assert record.candidate.event_revision == 2
        assert record.candidate.semantic_revision == 2
        assert record.candidate.expected_head_revision == 1
        assert record.candidate.expected_semantic_revision == 1
        assert record.candidate.event_digest == digest(record.candidate.canonical_event)
        assert (
            record.candidate.designation_record_digest
            != record.currentness_record.binding.designation_record_digest
        )
        assert record.candidate.affected_scopes == (record.currentness_record.exact_scope,)
        assert record.lease is record.currentness_record.lease
        assert record.caller_transaction is record.currentness_record.transaction
        assert record.correlation_digest.startswith("sha256:")
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError, match="OPAQUE_ADMISSION_ATTEMPT"):
                operation(attempt)
        for name in ("commit", "admit", "authorize", "rights", "receipt"):
            assert not hasattr(attempt, name)
    with pytest.raises(AdmissionAttemptDenied):
        provider._require_prepared(
            attempt,
            currentness_witness=witness,
            **currentness_arguments,
        )


@pytest.mark.parametrize(
    "attack",
    [
        "artifact",
        "mutable-artifact",
        "manifest",
        "mutable-manifest",
        "noncanonical-manifest",
        "expected-head",
        "expected-revision",
        "expected-scope",
        "extra-key",
        "wrong-current-key",
        "reused-designation",
        "wrong-designation-id",
        "genesis",
    ],
)
def test_invalid_candidate_consumes_witness_one_way(tmp_path, currentness_journal_engine, attack):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, currentness_arguments = issue_args(context)
        provider = _AdmissionAttemptProvider(currentness_handoff=handoff)
        artifact, manifest, expected = candidate(context)
        with handoff._open_witness(**currentness_arguments) as witness:
            if attack == "artifact":
                artifact = artifact[:-1]
            elif attack == "mutable-artifact":
                artifact = bytearray(artifact)
            elif attack == "manifest":
                manifest = b"[]"
            elif attack == "mutable-manifest":
                manifest = bytearray(manifest)
            elif attack == "noncanonical-manifest":
                manifest = json.dumps(json.loads(manifest), indent=2).encode()
            elif attack == "expected-head":
                expected = replace(expected, previous_event_digest=digest(b"stale"))
            elif attack == "expected-revision":
                expected = replace(expected, previous_trust_revision=True)
            elif attack == "expected-scope":
                expected = replace(expected, authoritative_scopes=((uid(1), uid(2), uid(3)),))
            elif attack == "extra-key":
                material = keys()
                expected = replace(
                    expected,
                    public_keys=expected.public_keys
                    + (("root/test-3", material["root/test-3"].public_key().public_bytes_raw()),),
                )
            elif attack == "wrong-current-key":
                expected = replace(
                    expected,
                    public_keys=((expected.public_keys[0][0], bytes(32)), expected.public_keys[1]),
                )
            elif attack in {"reused-designation", "wrong-designation-id"}:
                payload = json.loads(artifact)["payload"]
                if attack == "reused-designation":
                    value = context[4]["pin_facts"].binding.designation_record_digest
                    payload["designation_record_digest"] = value
                    expected = replace(expected, designation_record_digest=value)
                else:
                    value = uid(998)
                    payload["designation_id"] = value
                    expected = replace(expected, designation_id=value)
                artifact = wire(payload)
            elif attack == "genesis":
                payload, expected = event()
                artifact = wire(payload)
            with (
                pytest.raises(AdmissionAttemptDenied),
                provider._open_attempt(
                    currentness_witness=witness,
                    artifact=artifact,
                    manifest=manifest,
                    expected=expected,
                    **currentness_arguments,
                ),
            ):
                pytest.fail("invalid candidate created an attempt")
            valid_artifact, valid_manifest, valid_expected = candidate(context)
            with (
                pytest.raises(AdmissionAttemptDenied),
                provider._open_attempt(
                    currentness_witness=witness,
                    artifact=valid_artifact,
                    manifest=valid_manifest,
                    expected=valid_expected,
                    **currentness_arguments,
                ),
            ):
                pytest.fail("consumed witness was reactivated")


def test_foreign_witness_cannot_destroy_live_witness(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, currentness_arguments = issue_args(context)
        provider = _AdmissionAttemptProvider(currentness_handoff=handoff)
        artifact, manifest, expected = candidate(context)
        with handoff._open_witness(**currentness_arguments) as witness:
            with (
                pytest.raises(AdmissionAttemptDenied),
                provider._open_attempt(
                    currentness_witness=object(),
                    artifact=artifact,
                    manifest=manifest,
                    expected=expected,
                    **currentness_arguments,
                ),
            ):
                pytest.fail("foreign witness created an attempt")
            with provider._open_attempt(
                currentness_witness=witness,
                artifact=artifact,
                manifest=manifest,
                expected=expected,
                **currentness_arguments,
            ) as attempt:
                provider._require_prepared(
                    attempt,
                    currentness_witness=witness,
                    **currentness_arguments,
                )


def test_forged_attempt_bool_int_and_hostile_hash_are_denied(tmp_path, currentness_journal_engine):
    if not native():
        return

    class Hostile:
        def __hash__(self):
            raise AssertionError("hostile hash reached")

        def __eq__(self, other):
            raise AssertionError("hostile equality reached")

    with live_attempt(tmp_path, currentness_journal_engine) as value:
        provider, attempt, witness, currentness_arguments, _, _ = value
        for forged in (True, 1, Hostile(), object()):
            with pytest.raises(AdmissionAttemptDenied):
                provider._require_prepared(
                    forged,
                    currentness_witness=witness,
                    **currentness_arguments,
                )
        provider._require_prepared(
            attempt,
            currentness_witness=witness,
            **currentness_arguments,
        )


def test_duplicate_prepare_is_denied_without_destroying_winner(
    tmp_path, currentness_journal_engine
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        provider, attempt, witness, currentness_arguments, _, call = value
        with pytest.raises(AdmissionAttemptDenied), provider._open_attempt(**call):
            pytest.fail("one witness prepared a second attempt")
        provider._require_prepared(
            attempt,
            currentness_witness=witness,
            **currentness_arguments,
        )


@pytest.mark.parametrize(
    "attack",
    ["witness", "lease", "transaction", "journal-head", "lineage", "correlation"],
)
def test_revalidation_failure_invalidates_attempt_and_witness(
    tmp_path, currentness_journal_engine, attack
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        provider, attempt, witness, currentness_arguments, context, _ = value
        original = dict(currentness_arguments)
        if attack == "witness":
            witness = object()
        elif attack == "lease":
            currentness_arguments["lease"] = object()
        elif attack == "transaction":
            currentness_arguments["session"].rollback()
            currentness_arguments["session"].begin()
        elif attack == "journal-head":
            observations = context[7]
            head = observations._journal.read_public_head()
            observations._journal.read_public_head = Mock(
                return_value=replace(head, revision=head.revision + 1)
            )
        elif attack == "lineage":
            currentness_arguments["fresh_lineage"] = object()
        else:
            context[6]._records.pop(original["correlation_handle"])
        with pytest.raises(AdmissionAttemptDenied):
            provider._require_prepared(
                attempt,
                currentness_witness=witness,
                **currentness_arguments,
            )
        with pytest.raises(AdmissionAttemptDenied):
            provider._require_prepared(
                attempt,
                currentness_witness=value[2],
                **original,
            )
        assert not provider._records


def test_concurrent_prepare_has_one_winner(tmp_path, currentness_journal_engine, monkeypatch):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, currentness_arguments = issue_args(context)
        provider = _AdmissionAttemptProvider(currentness_handoff=handoff)
        artifact, manifest, expected = candidate(context)
        with handoff._open_witness(**currentness_arguments) as witness:
            witness_record = handoff._records[witness]
            monkeypatch.setattr(provider, "_require_witness", lambda *a, **kw: witness_record)
            monkeypatch.setattr(handoff, "_require_current", lambda *a, **kw: None)
            barrier = Barrier(2)

            def prepare(_):
                manager = provider._open_attempt(
                    currentness_witness=witness,
                    artifact=artifact,
                    manifest=manifest,
                    expected=expected,
                    **currentness_arguments,
                )
                try:
                    attempt = manager.__enter__()
                except AdmissionAttemptDenied:
                    barrier.wait()
                    return "denied", None, None
                barrier.wait()
                return "winner", manager, attempt

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(prepare, range(2)))
            assert sorted(item[0] for item in results) == ["denied", "winner"]
            winner = next(item for item in results if item[0] == "winner")
            provider._require_prepared(
                winner[2],
                currentness_witness=witness,
                **currentness_arguments,
            )
            winner[1].__exit__(None, None, None)


def test_consumer_exception_and_unavailable_production_port(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, currentness_arguments = issue_args(context)
        provider = _AdmissionAttemptProvider(currentness_handoff=handoff)
        artifact, manifest, expected = candidate(context)
        with handoff._open_witness(**currentness_arguments) as witness:
            with (
                pytest.raises(AdmissionAttemptDenied),
                provider._open_attempt(
                    currentness_witness=witness,
                    artifact=artifact,
                    manifest=manifest,
                    expected=expected,
                    **currentness_arguments,
                ),
            ):
                raise OSError("injected consumer failure")
            assert not provider._records
    with pytest.raises(CurrentnessUnavailable):
        UnavailableCurrentnessPorts().prepare(object(), object(), b"event", b"manifest")
