"""AssetVersion 중심 Workspace 목표 Entity의 명시적 등록 지점."""

from backend.models.workspace.asset import (
    Artifact,
    Asset,
    AssetRelation,
    AssetVersion,
)
from backend.models.workspace.collaboration import (
    Approval,
    Comment,
    Favorite,
    History,
    RecordingEnrollment,
    Tag,
)
from backend.models.workspace.composition import (
    CompositionSnapshot,
    ProcessingChain,
    ProcessingStep,
    ProjectCompositionSelection,
    SnapshotItem,
)
from backend.models.workspace.enums import AssetType, JobStatus
from backend.models.workspace.job import Job, JobInput, JobOutput, ModelUsage
from backend.models.workspace.provider_job import ProviderJobBinding
from backend.models.workspace.storage import (
    ARTIFACT_STORAGE_ENTITY_CLASSES,
    ArtifactStorageLocation,
)
from backend.models.workspace.workspace import MusicProject, ProjectAsset, Workspace

WORKSPACE_ENTITY_CLASSES = (
    Workspace,
    MusicProject,
    ProjectAsset,
    Asset,
    AssetVersion,
    Artifact,
    AssetRelation,
    CompositionSnapshot,
    ProjectCompositionSelection,
    SnapshotItem,
    Job,
    JobInput,
    JobOutput,
    ProcessingChain,
    ProcessingStep,
    ModelUsage,
    ProviderJobBinding,
    RecordingEnrollment,
    Tag,
    Comment,
    Favorite,
    History,
    Approval,
)

__all__ = [
    "ARTIFACT_STORAGE_ENTITY_CLASSES",
    "WORKSPACE_ENTITY_CLASSES",
    "Approval",
    "Artifact",
    "ArtifactStorageLocation",
    "Asset",
    "AssetRelation",
    "AssetType",
    "AssetVersion",
    "Comment",
    "CompositionSnapshot",
    "Favorite",
    "History",
    "Job",
    "JobInput",
    "JobOutput",
    "JobStatus",
    "ModelUsage",
    "MusicProject",
    "ProcessingChain",
    "ProcessingStep",
    "ProviderJobBinding",
    "ProjectAsset",
    "ProjectCompositionSelection",
    "RecordingEnrollment",
    "SnapshotItem",
    "Tag",
    "Workspace",
]
