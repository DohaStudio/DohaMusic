from __future__ import annotations

import os
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import dohastudio_common_ai
import pytest

from backend.contracts import common_ai


def _rights_metadata() -> dict[str, object]:
    return {
        "schema_name": "rights_metadata",
        "schema_version": "1.0.0",
        "object_id": "rights_1",
        "created_at": "2026-08-11T12:00:00Z",
        "created_by": "actor_test",
        "producer": {"name": "dohamusic-test", "version": "1.0.0"},
        "rights_metadata_id": "rights_1",
        "source_type": "user_created",
        "rights_status": "approved",
        "user_created": True,
        "generated": False,
        "reference": False,
        "uploaded": True,
        "external": False,
        "analysis_allowed": True,
        "training_allowed": False,
        "redistribution_allowed": False,
        "retention_allowed": True,
        "derivative_generation_allowed": True,
        "consent_evidence_refs": ["consent_1"],
        "jurisdiction": "KR",
        "reviewed_at": "2026-08-11T12:00:00Z",
        "reviewed_by": "reviewer_1",
    }


def test_status_verifies_pinned_package_and_registry() -> None:
    status = common_ai.common_ai_contract_status()

    assert status.package_version == "0.1.0"
    assert status.policy_version == "1.0.0"
    assert len(status.schema_names) == 12
    assert len(status.resource_names) == 13


def test_schema_is_loaded_from_package_public_api() -> None:
    schema = common_ai.load_common_ai_schema("rights_metadata")

    assert schema["$id"].endswith("/rights-metadata.schema.json")
    assert schema["properties"]["schema_name"] == {"const": "rights_metadata"}


def test_schema_is_loaded_by_official_id() -> None:
    schema_id = (
        "https://schemas.dohastudio.org/common-ai/v1/rights-metadata.schema.json"
    )

    assert common_ai.load_common_ai_schema(schema_id)["$id"] == schema_id


def test_valid_rights_metadata_returns_no_issues() -> None:
    assert common_ai.validate_rights_metadata(_rights_metadata()) == ()


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda payload: payload.pop("jurisdiction"), "MISSING_REQUIRED_FIELD"),
        (
            lambda payload: payload.update(rights_status="not-a-status"),
            "INVALID_ENUM_VALUE",
        ),
        (
            lambda payload: payload.update(analysis_allowed="yes"),
            "SCHEMA_VALIDATION_ERROR",
        ),
        (
            lambda payload: payload.update(schema_version="2.0.0"),
            "UNSUPPORTED_SCHEMA_VERSION",
        ),
        (
            lambda payload: payload.update(schema_version="version-one"),
            "INVALID_SCHEMA_VERSION",
        ),
        (
            lambda payload: payload.update(unexpected=True),
            "UNKNOWN_FIELD",
        ),
    ],
)
def test_invalid_rights_metadata_keeps_canonical_issue(
    mutation: Callable[[dict[str, object]], object], expected_code: str
) -> None:
    payload = _rights_metadata()
    mutation(payload)

    issues = common_ai.validate_rights_metadata(payload)

    assert expected_code in {issue.code for issue in issues}
    assert all(
        isinstance(issue, dohastudio_common_ai.ValidationIssue) for issue in issues
    )


def test_rights_adapter_does_not_synthesize_missing_fields() -> None:
    payload = _rights_metadata()
    payload.pop("consent_evidence_refs")

    adapter_issues = common_ai.validate_rights_metadata(payload)
    package_issues = dohastudio_common_ai.validate_contract(
        payload, expected_kind="rights_metadata"
    )

    assert adapter_issues == package_issues
    assert "consent_evidence_refs" not in payload


def test_kind_mismatch_fails_closed() -> None:
    payload = _rights_metadata()
    payload["schema_name"] = "music_intent"

    issues = common_ai.validate_rights_metadata(payload)

    assert "OBJECT_SCHEMA_KIND_MISMATCH" in {issue.code for issue in issues}


def test_canonical_issues_are_deterministic_and_do_not_expose_payload() -> None:
    payload = _rights_metadata()
    payload["private_note"] = "SENSITIVE-PAYLOAD-VALUE"

    first = common_ai.validate_rights_metadata(payload)
    second = common_ai.validate_rights_metadata(payload)
    rendered = str([issue.to_dict() for issue in first])

    assert first == second
    assert "SENSITIVE-PAYLOAD-VALUE" not in rendered
    assert all(issue.path.startswith("$") for issue in first)


def test_unknown_schema_name_has_sanitized_error() -> None:
    with pytest.raises(common_ai.CommonAIContractError) as captured:
        common_ai.load_common_ai_schema("unknown_contract")

    assert str(captured.value) == (
        "The requested Common AI Contract schema is unavailable."
    )


def test_missing_package_has_sanitized_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(_: str) -> object:
        raise ModuleNotFoundError("missing", name="dohastudio_common_ai")

    monkeypatch.setattr(common_ai, "import_module", unavailable)

    with pytest.raises(common_ai.CommonAIContractUnavailableError) as captured:
        common_ai.common_ai_contract_status()

    assert str(captured.value) == (
        "The pinned Common AI Contract package is unavailable."
    )


def test_incompatible_package_has_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incompatible = SimpleNamespace(
        ContractResourceError=LookupError,
        __version__="9.9.9",
        contract_policy_version=lambda: "1.0.0",
        get_schema=lambda _: {},
        resource_names=lambda: (),
        schema_names=lambda: (),
        validate_contract=lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(common_ai, "import_module", lambda _: incompatible)

    with pytest.raises(common_ai.CommonAIContractCompatibilityError) as captured:
        common_ai.common_ai_contract_status()

    assert str(captured.value) == (
        "The Common AI Contract package does not match the supported v1 contract."
    )


def test_validation_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def network_forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", network_forbidden)

    schema = common_ai.load_common_ai_schema("rights_metadata")
    assert schema["allOf"] == [{"$ref": "common-envelope.schema.json"}]
    assert common_ai.validate_rights_metadata(_rights_metadata()) == ()


def test_import_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository_root)
    script = (
        "import os, threading; "
        "environment = dict(os.environ); "
        "thread_count = len(threading.enumerate()); "
        "import dohastudio_common_ai; "
        "import backend.contracts.common_ai; "
        "assert dict(os.environ) == environment; "
        "assert len(threading.enumerate()) == thread_count"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_repository_does_not_copy_common_schemas() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    assert list((repository_root / "backend").rglob("*.schema.json")) == []


def test_dependency_uses_exact_vcs_commit() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    project_metadata = (repository_root / "pyproject.toml").read_text(encoding="utf-8")

    assert (
        "dohastudio-common-ai-contracts @ "
        "git+https://github.com/DohaStudio/.github.git@"
        "dd75fc88c16e9ae9a04acfafb72756a905f6365b"
    ) in project_metadata
    assert ".github.git@develop" not in project_metadata
