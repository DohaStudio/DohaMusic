import { describe, expect, it } from "vitest";
import {
  getWorkingPreviewPollingInterval,
  isWorkingPreviewStale,
  selectWorkingPreviewOutput,
} from "@/features/composition/working-preview";
import type { WorkspaceJobDetailDto } from "@/types/api";

describe("Working Preview state authority", () => {
  it("rendered revision identity로 stale을 판정한다", () => {
    expect(isWorkingPreviewStale(4, 4)).toBe(false);
    expect(isWorkingPreviewStale(4, 5)).toBe(true);
    expect(isWorkingPreviewStale(4, 4)).toBe(false);
  });

  it("terminal status에서 polling을 중단하고 기존 adaptive interval을 따른다", () => {
    expect(getWorkingPreviewPollingInterval({ successCount: 0, consecutiveErrors: 0, hidden: false })).toBe(1_000);
    expect(getWorkingPreviewPollingInterval({ successCount: 5, consecutiveErrors: 0, hidden: false })).toBe(2_000);
    expect(getWorkingPreviewPollingInterval({ successCount: 1, consecutiveErrors: 1, hidden: false })).toBe(5_000);
    expect(getWorkingPreviewPollingInterval({ successCount: 1, consecutiveErrors: 3, hidden: false })).toBe(10_000);
    expect(getWorkingPreviewPollingInterval({ job: job("cancelled"), successCount: 1, consecutiveErrors: 0, hidden: false })).toBe(false);
  });

  it("working_preview exactly-one Artifact output만 선택한다", () => {
    const value = job("succeeded");
    value.outputs = [
      { output_role: "analysis", output_order: 0, asset_version_id: null, artifact_id: "other" },
      { output_role: "working_preview", output_order: 1, asset_version_id: null, artifact_id: "preview" },
    ];
    expect(selectWorkingPreviewOutput(value).artifact_id).toBe("preview");
    value.outputs = [];
    expect(() => selectWorkingPreviewOutput(value)).toThrow("WORKING_PREVIEW_OUTPUT_INVALID");
    value.outputs = [
      { output_role: "working_preview", output_order: 0, asset_version_id: null, artifact_id: "a" },
      { output_role: "working_preview", output_order: 1, asset_version_id: null, artifact_id: "b" },
    ];
    expect(() => selectWorkingPreviewOutput(value)).toThrow("WORKING_PREVIEW_OUTPUT_INVALID");
  });
});

function job(status: WorkspaceJobDetailDto["status"]): WorkspaceJobDetailDto {
  return {
    job_id: "job-1", project_id: "project-1", composition_snapshot_id: null,
    job_type: "working_preview", status, provider_id: null, model_manifest_id: null,
    progress_percent: null, stage: null, retry_of_job_id: null,
    created_at: "2026-08-29T00:00:00Z", started_at: null, completed_at: null,
    inputs: [], outputs: [], model_usages: [], error_code: null, error_message: null, error_retryable: null,
    error_details_id: null,
  };
}
