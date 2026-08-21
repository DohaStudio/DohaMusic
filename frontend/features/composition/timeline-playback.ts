import { toBackendPublicUrl } from "@/services/doha-api";
import type { CompositionWorkspaceDto } from "@/types/api";
import type { SafePipelineFile } from "@/types/domain";

export type CompositionPlaybackResolution =
  | { status: "available"; source: SafePipelineFile }
  | {
      status: "unavailable";
      code: "NO_CANONICAL_PLAYBACK_SOURCE";
      reason: string;
    };

export function resolveCompositionPlayback(
  data: CompositionWorkspaceDto,
): CompositionPlaybackResolution {
  const mixItems = data.items.filter((item) => item.item_role === "mix");
  if (mixItems.length !== 1) {
    return unavailable("선택된 Snapshot에 단일 Mix 항목이 없습니다.");
  }

  const playableArtifacts = mixItems[0].artifacts.flatMap((artifact) => {
    const contentUrl = toBackendPublicUrl(artifact.content_url);
    if (!artifact.media_type.startsWith("audio/") || !contentUrl) return [];
    return [{ artifact, contentUrl }];
  });
  if (playableArtifacts.length !== 1) {
    return unavailable("Mix 항목의 안전한 Audio Artifact가 단일 소스로 확정되지 않았습니다.");
  }

  const { artifact, contentUrl } = playableArtifacts[0];
  const snapshotId = data.snapshot?.composition_snapshot_id ?? data.project.project_id;
  return {
    status: "available",
    source: {
      id: artifact.artifact_id,
      jobId: snapshotId,
      fileType: `Composition Mix · ${artifact.artifact_kind}`,
      mimeType: artifact.media_type,
      createdAt: artifact.created_at,
      contentAvailable: true,
      downloadAvailable: Boolean(toBackendPublicUrl(artifact.download_url)),
      contentUrl,
      downloadUrl: toBackendPublicUrl(artifact.download_url),
    },
  };
}

export function timelineTimeFromPointer(input: {
  clientX: number;
  viewportLeft: number;
  scrollLeft: number;
  pixelsPerSecond: number;
  duration: number;
}): number {
  if (input.duration <= 0 || input.pixelsPerSecond <= 0) return 0;
  const timelineX = input.clientX - input.viewportLeft + input.scrollLeft;
  return clamp(timelineX / input.pixelsPerSecond, 0, input.duration);
}

export function clampTimelineTime(time: number, duration: number): number {
  if (!Number.isFinite(time) || duration <= 0) return 0;
  return clamp(time, 0, duration);
}

export function formatTimelineTime(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "0:00";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function unavailable(reason: string): CompositionPlaybackResolution {
  return { status: "unavailable", code: "NO_CANONICAL_PLAYBACK_SOURCE", reason };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}
