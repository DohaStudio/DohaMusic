"""Workspace Job Vocal capability 공개 schema 계약 검증."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from backend.schemas.workspace import JobCreateRequest


@pytest.mark.parametrize(
    ("job_type", "job_input"),
    [
        (
            "vocal_generation",
            {
                "job_type": "vocal_generation",
                "lyrics_reference": str(uuid4()),
                "melody_reference": str(uuid4()),
            },
        ),
        (
            "voice_conversion",
            {
                "job_type": "voice_conversion",
                "source_asset_version_id": str(uuid4()),
                "voice_reference_artifact_id": str(uuid4()),
                "source_entity_type": "ai_generated_vocal",
                "reference_entity_type": "voice_enrollment_sample",
                "training_dataset_id": None,
            },
        ),
        (
            "vocal_correction",
            {
                "job_type": "vocal_correction",
                "source_asset_version_id": str(uuid4()),
                "correction_types": ["natural_tune"],
            },
        ),
        (
            "vocal_analysis",
            {
                "job_type": "vocal_analysis",
                "source_asset_version_id": str(uuid4()),
                "analysis_types": ["pronunciation"],
            },
        ),
    ],
)
def test_public_schema_accepts_each_vocal_job_input(job_type, job_input) -> None:
    request = JobCreateRequest.model_validate(
        {
            "project_id": str(uuid4()),
            "job_type": job_type,
            "job_input": job_input,
        }
    )
    assert request.job_input is not None
    assert request.job_input.job_type == job_type


def test_public_schema_rejects_cross_type_fields() -> None:
    with pytest.raises(ValidationError):
        JobCreateRequest.model_validate(
            {
                "project_id": str(uuid4()),
                "job_type": "vocal_generation",
                "job_input": {
                    "job_type": "vocal_generation",
                    "lyrics_reference": str(uuid4()),
                    "melody_reference": str(uuid4()),
                    "correction_types": ["pitch_correction"],
                },
            }
        )


def test_openapi_keeps_workspace_job_operation_surface(app: FastAPI) -> None:
    schema = app.openapi()
    job_operations = {
        operation["operationId"]
        for path, path_item in schema["paths"].items()
        if path.startswith("/api/v1/jobs")
        for method, operation in path_item.items()
        if method in {"get", "post"}
    }
    assert job_operations == {
        "list_workspace_jobs",
        "create_workspace_job",
        "get_workspace_job",
        "cancel_workspace_job",
        "retry_workspace_job",
    }
    assert len(
        [
            operation["operationId"]
            for path_item in schema["paths"].values()
            for method, operation in path_item.items()
            if method in {"get", "post", "put", "patch", "delete"}
        ]
    ) == len(
        {
            operation["operationId"]
            for path_item in schema["paths"].values()
            for method, operation in path_item.items()
            if method in {"get", "post", "put", "patch", "delete"}
        }
    )
