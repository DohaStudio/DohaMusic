"""Database model exports used by Alembic metadata discovery."""

from backend.models.generated_file import GeneratedFile
from backend.models.generation_job import GenerationJob
from backend.models.idempotency_record import IdempotencyRecord
from backend.models.lyrics_document import LyricsDocument
from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.models.project import Project
from backend.models.stem_file import StemFile
from backend.models.stem_job import StemJob
from backend.models.voice_conversion_file import VoiceConversionFile
from backend.models.voice_conversion_job import VoiceConversionJob
from backend.models.voice_enrollment import VoiceEnrollment
from backend.models.voice_profile import VoiceProfile
from backend.models.voice_sample import VoiceSample
from backend.models.workspace import (
    ARTIFACT_STORAGE_ENTITY_CLASSES,
    Approval,
    Artifact,
    ArtifactStorageLocation,
    Asset,
    AssetRelation,
    AssetVersion,
    Comment,
    CompositionSnapshot,
    Favorite,
    History,
    Job,
    JobInput,
    JobOutput,
    ModelUsage,
    MusicProject,
    ProcessingChain,
    ProcessingStep,
    ProjectAsset,
    RecordingEnrollment,
    SnapshotItem,
    Tag,
    WORKSPACE_ENTITY_CLASSES,
    Workspace,
)

__all__ = [
    "GeneratedFile",
    "GenerationJob",
    "IdempotencyRecord",
    "LyricsDocument",
    "PipelineFile",
    "PipelineJob",
    "Project",
    "StemFile",
    "StemJob",
    "VoiceConversionFile",
    "VoiceConversionJob",
    "VoiceEnrollment",
    "VoiceProfile",
    "VoiceSample",
    "Approval",
    "ARTIFACT_STORAGE_ENTITY_CLASSES",
    "Artifact",
    "ArtifactStorageLocation",
    "Asset",
    "AssetRelation",
    "AssetVersion",
    "Comment",
    "CompositionSnapshot",
    "Favorite",
    "History",
    "Job",
    "JobInput",
    "JobOutput",
    "ModelUsage",
    "MusicProject",
    "ProcessingChain",
    "ProcessingStep",
    "ProjectAsset",
    "RecordingEnrollment",
    "SnapshotItem",
    "Tag",
    "WORKSPACE_ENTITY_CLASSES",
    "Workspace",
]
