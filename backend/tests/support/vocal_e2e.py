"""Isolated Music persistence/rights fixtures for real Provider wire E2E."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.models  # noqa: F401
from backend.contracts.vocal_jobs import VOCAL_JOB_INPUT_SETTINGS_KEY, VOCAL_JOB_OUTPUT_ROLES
from backend.core.payload_locator import PayloadLocatorIssue
from backend.db.base import Base
from backend.db.sqlite import configure_sqlite_foreign_keys
from backend.models.workspace import (
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    Job,
    JobInput,
    JobStatus,
    MusicProject,
    ProcessingChain,
    ProjectAsset,
    ProviderJobBinding,
    Workspace,
)
from backend.providers.vocal import (
    AuthorizedVocalJobContext,
    HttpVocalProviderTransport,
    VocalCapability,
    VocalProviderClient,
    map_authorized_create_job,
)
from backend.providers.vocal.contracts import VocalJobInput
from backend.repositories.workspace import SqlAlchemyPayloadLocatorPersistence
from backend.services.workspace import (
    ArtifactIngestionService,
    DohaVocalArtifactCompletionRequest,
    DohaVocalArtifactCompletionService,
    PayloadLocatorService,
    PayloadStagingAuthority,
    PayloadStagingService,
    ProviderResultIngestionService,
    SqlAlchemyVocalCompletionAuthorityPort,
    VocalCompletionModelFacts,
    VocalPayloadReconciliationService,
)
from backend.storage import ArtifactStorageRoots, LocalFilesystemStagingAdapter


class FakeRights:
    """Test-only rights; the production adapter stays unconfigured."""

    allowed = True

    def require_current(self, session, **context):
        assert session.in_transaction()
        assert context["trusted_principal"] == "e2e-principal"
        if not self.allowed:
            raise PermissionError("fixture rights denied")


def graph(tmp_path, runtime, capability):
    now = datetime.now(UTC)
    engine = configure_sqlite_foreign_keys(
        create_engine(f"sqlite:///{(tmp_path / 'isolated.db').as_posix()}")
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    owner = uuid4()
    claim = uuid4()
    transport = HttpVocalProviderTransport(base_url="http://vocal.fixture", client=runtime)
    client = VocalProviderClient(transport)
    with factory.begin() as session:
        workspace = Workspace(owner_id=owner, name="E2E", lifecycle_status="active")
        session.add(workspace)
        session.flush()
        project = MusicProject(
            workspace_id=workspace.workspace_id,
            title="E2E",
            lifecycle_status="active",
            created_by=owner,
        )
        asset = Asset(
            workspace_id=workspace.workspace_id,
            owner_id=owner,
            asset_type=AssetType.VOCAL,
            lifecycle_status="active",
        )
        session.add_all((project, asset))
        session.flush()
        source = AssetVersion(
            asset_id=asset.asset_id,
            version_number=1,
            version_origin="test_fixture",
            settings_snapshot={},
            created_by=owner,
        )
        chain = ProcessingChain(
            name="E2E", chain_version="1", chain_checksum="1" * 64, created_by=owner
        )
        session.add_all((source, chain))
        session.flush()
        asset.selected_asset_version_id = source.asset_version_id
        # These are synthetic metadata rows, never source audio files.
        artifact = Artifact(
            asset_version_id=source.asset_version_id,
            artifact_kind="audio",
            media_type="audio/wav",
            size_bytes=1,
            checksum_algorithm="sha256",
            artifact_checksum="1" * 64,
            producer_type="user",
            retention_status="active",
        )
        session.add(artifact)
        session.add(
            ProjectAsset(
                project_id=project.project_id,
                asset_id=asset.asset_id,
                role="vocal",
                display_order=0,
            )
        )
        session.flush()
        common = {"job_type": capability, "processing_chain_id": str(chain.processing_chain_id)}
        if capability == "vocal_generation":
            job_input = dict(
                common,
                lyrics_reference=str(artifact.artifact_id),
                melody_reference=str(artifact.artifact_id),
            )
        else:
            job_input = dict(
                common,
                source_asset_version_id=str(source.asset_version_id),
                parent_asset_version_id=str(source.asset_version_id),
            )
            if capability == "voice_conversion":
                job_input.update(
                    voice_reference_artifact_id=str(artifact.artifact_id),
                    source_entity_type="ai_generated_vocal",
                    reference_entity_type="voice_enrollment_sample",
                )
            elif capability == "vocal_correction":
                job_input["correction_types"] = ["pitch_correction"]
            else:
                job_input["analysis_types"] = ["pitch"]
        request = map_authorized_create_job(
            AuthorizedVocalJobContext(
                effective_owner_id=owner,
                workspace_id=workspace.workspace_id,
                project_id=project.project_id,
                capability=VocalCapability(capability),
                idempotency_key=f"fixture-{uuid4()}",
                input_asset_version_ids=(source.asset_version_id,),
                input_artifact_ids=(artifact.artifact_id,),
                model_manifest_id="dohavocal.fake-model@0.2.0",
                settings_snapshot={},
                job_input=TypeAdapter(VocalJobInput).validate_python(job_input),
                api_contract_version="0.2.0",
            )
        )
        job = Job(
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            job_type=capability,
            status=JobStatus.RUNNING,
            provider_id="dohavocal",
            api_contract_version="0.2.0",
            model_manifest_id=request.model_manifest_id,
            settings_snapshot={VOCAL_JOB_INPUT_SETTINGS_KEY: job_input},
            requested_by=owner,
            attempt=1,
            claimed_by="e2e",
            claim_token=claim,
            lease_expires_at=now + timedelta(hours=1),
        )
        session.add(job)
        session.flush()
        roles = {
            "vocal_generation": ("lyrics_reference", "melody_reference"),
            "voice_conversion": ("source_vocal", "voice_reference"),
            "vocal_correction": ("source_vocal",),
            "vocal_analysis": ("source_vocal",),
        }[capability]
        for ordinal, role in enumerate(roles):
            session.add(
                JobInput(
                    job_id=job.job_id,
                    artifact_id=artifact.artifact_id,
                    input_role=role,
                    input_order=ordinal,
                )
            )
    # Provider I/O occurs only after the caller-owned setup transaction closes.
    provider_job = client.create_job(request)
    with factory.begin() as session:
        binding = ProviderJobBinding(
            workspace_job_id=job.job_id,
            provider_id="dohavocal",
            provider_job_id=provider_job.job_id,
        )
        session.add(binding)
        session.flush()
    wire = client.get_result(provider_job.job_id, api_contract_version="0.2.0")
    trust = ProviderResultIngestionService()
    with factory.begin() as session:
        candidate = trust.validate_candidate_for_owner(
            session,
            effective_owner_id=owner,
            workspace_job_id=job.job_id,
            provider_job_binding_id=binding.provider_job_binding_id,
            output_role=VOCAL_JOB_OUTPUT_ROLES[capability],
            wire_candidate=wire,
        ).candidate
    payload = candidate.payloads[0]
    locators = PayloadLocatorService(SqlAlchemyPayloadLocatorPersistence(factory))
    issue = PayloadLocatorIssue(
        workspace_job_id=job.job_id,
        provider_job_binding_id=binding.provider_job_binding_id,
        payload_ordinal=0,
        provider_artifact_id=payload.provider_artifact_id,
        role=payload.role,
        source_kind=payload.source_kind,
        source_id=payload.source_id,
        artifact_kind=candidate.artifact_kind,
        expected_checksum_algorithm="sha256",
        expected_payload_checksum=payload.payload_checksum,
        expected_size_bytes=payload.expected_size_bytes,
        expected_media_type=payload.expected_media_type,
        source_available_until=payload.available_until,
        locator_expires_at=now + timedelta(hours=1),
    )
    record = locators.issue(issue)
    staging_root = tmp_path / "staging"
    staging_root.mkdir()
    staging = LocalFilesystemStagingAdapter(staging_root)
    rights = FakeRights()
    state = {"cancelled": False}

    def authority():
        return PayloadStagingAuthority(job.job_id, rights.allowed, True, state["cancelled"])

    reconciliation = VocalPayloadReconciliationService(
        transport,
        locators,
        PayloadStagingService(locators, staging),
        staging,
        max_payload_size_bytes=1024 * 1024,
    )
    artifact_root = tmp_path / "artifacts"
    for domain in ("audio", "music", "vocal", "lm"):
        (artifact_root / domain).mkdir(parents=True)
    publisher_root = tmp_path / "publisher"
    publisher_root.mkdir()
    ingestion = ArtifactIngestionService(
        factory,
        artifact_roots=ArtifactStorageRoots.from_base_root(artifact_root),
        staging_root=publisher_root,
    )
    completion = DohaVocalArtifactCompletionService(
        factory,
        staging=staging,
        ingestion=ingestion,
        authority=SqlAlchemyVocalCompletionAuthorityPort(rights),
    )
    manifest = client.get_model_manifest(request.model_manifest_id)
    completion_request = DohaVocalArtifactCompletionRequest(
        candidate=candidate,
        payload_locator_id=record.locator_id,
        claimed_by="e2e",
        execution_claim_token=claim,
        trusted_principal="e2e-principal",
        model=VocalCompletionModelFacts(
            model_id=manifest.model_id,
            model_version=manifest.model_version,
            checkpoint_version=manifest.checkpoint_version,
            license_status=manifest.license_status,
            commercial_usage_status=manifest.commercial_usage_status,
        ),
    )
    return SimpleNamespace(**locals())
