import type {
  WorkspaceJobDetailDto,
  WorkspaceJobOutputDto,
  WorkspaceJobStatusDto,
} from "@/types/api";

export type WorkingPreviewPhase =
  | "idle"
  | "submitting"
  | WorkspaceJobStatusDto
  | "ready"
  | "unavailable";

export interface WorkingPreviewRequestState {
  jobId: string;
  previewRenderId: string;
  renderedRevision: number;
  phase: Exclude<WorkingPreviewPhase, "idle" | "ready" | "unavailable">;
}

export function isWorkingPreviewStale(renderedRevision: number, currentRevision: number): boolean {
  return renderedRevision !== currentRevision;
}

export function selectWorkingPreviewOutput(job: WorkspaceJobDetailDto): WorkspaceJobOutputDto {
  const outputs = job.outputs.filter((output) => output.output_role === "working_preview");
  if (outputs.length !== 1 || !outputs[0].artifact_id) {
    throw new Error("WORKING_PREVIEW_OUTPUT_INVALID");
  }
  return outputs[0];
}

export function getWorkingPreviewPollingInterval(input: {
  job?: WorkspaceJobDetailDto;
  successCount: number;
  consecutiveErrors: number;
  hidden: boolean;
}): number | false {
  if (input.job && isTerminalJobStatus(input.job.status)) return false;
  if (input.consecutiveErrors >= 3) return 10_000;
  if (input.consecutiveErrors >= 1 || input.hidden) return 5_000;
  return input.successCount < 5 ? 1_000 : 2_000;
}

export function isTerminalJobStatus(status: WorkspaceJobStatusDto): boolean {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

export function workingPreviewErrorMessage(code: string | null | undefined): string {
  const messages: Record<string, string> = {
    WORKING_COMPOSITION_REVISION_CONFLICT: "편집 상태가 변경되었습니다. 최신 revision을 확인한 뒤 Preview를 다시 실행해 주세요.",
    WORKING_PREVIEW_EMPTY: "재생할 Clip이 없어 Preview를 만들 수 없습니다.",
    WORKING_PREVIEW_LIMIT_EXCEEDED: "Preview 길이 또는 Track/Clip 제한을 초과했습니다.",
    WORKING_PREVIEW_SOURCE_UNAVAILABLE: "Preview에 필요한 원본 오디오를 사용할 수 없습니다.",
    WORKING_PREVIEW_OUTPUT_INVALID: "Preview 결과를 안전하게 재생할 수 없습니다.",
    WORKING_PREVIEW_MANIFEST_CONFLICT: "Preview 입력 구성이 일치하지 않습니다. 다시 실행해 주세요.",
    WORKING_PREVIEW_JOB_STATE_CONFLICT: "Preview 작업 상태가 변경되어 결과를 확정할 수 없습니다.",
    IDEMPOTENCY_KEY_REUSED: "동일한 요청 키가 다른 Preview 요청에 사용되었습니다.",
    IDEMPOTENCY_IN_PROGRESS: "동일한 Preview 요청이 아직 처리 중입니다.",
  };
  return code && messages[code]
    ? messages[code]
    : "Preview를 완료하지 못했습니다. 다시 실행해 주세요.";
}
