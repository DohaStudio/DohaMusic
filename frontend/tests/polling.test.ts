import { describe, expect, it } from "vitest";
import { getPollingInterval } from "@/hooks/use-pipeline";
import { ApiError } from "@/services/api-client";
import type { PipelineJobDto } from "@/types/api";
const job = (status: PipelineJobDto["status"]): PipelineJobDto => ({
  id: "j",
  project_id: null,
  voice_profile_id: "v",
  status,
  current_step: "step",
  progress_percent: 0,
  prompt: "p",
  lyrics: null,
  genre: null,
  duration_seconds: 30,
  seed: null,
  pipeline_version: "1",
  result_metadata: {},
  failed_step: null,
  error_code: null,
  error_message: null,
  created_at: "",
  updated_at: "",
  completed_at: null,
});
const state = (overrides = {}) => ({
  job: job("GENERATING"),
  successCount: 1,
  consecutiveErrors: 0,
  hidden: false,
  ...overrides,
});
describe("adaptive polling", () => {
  it("정상 초기 5회는 1초, 이후 2초다", () => {
    expect(getPollingInterval(state())).toBe(1000);
    expect(getPollingInterval(state({ successCount: 5 }))).toBe(2000);
  });
  it("background는 최소 5초다", () =>
    expect(getPollingInterval(state({ hidden: true }))).toBe(5000));
  it("연속 오류에 5초·10초 backoff를 적용한다", () => {
    expect(getPollingInterval(state({ consecutiveErrors: 1 }))).toBe(5000);
    expect(getPollingInterval(state({ consecutiveErrors: 2 }))).toBe(5000);
    expect(getPollingInterval(state({ consecutiveErrors: 3 }))).toBe(10000);
  });
  it("성공 후 오류 count가 0이면 정상 간격으로 복귀한다", () =>
    expect(
      getPollingInterval(state({ successCount: 6, consecutiveErrors: 0 })),
    ).toBe(2000));
  it("terminal과 404에서 중단한다", () => {
    expect(getPollingInterval(state({ job: job("COMPLETED") }))).toBe(false);
    expect(getPollingInterval(state({ job: job("FAILED") }))).toBe(false);
    expect(
      getPollingInterval(
        state({ error: new ApiError(404, "RESOURCE_NOT_FOUND", "없음") }),
      ),
    ).toBe(false);
  });
});
