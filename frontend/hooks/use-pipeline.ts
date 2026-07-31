"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import type { PipelineJobDto } from "@/types/api";

interface PollingState {
  job?: PipelineJobDto;
  successCount: number;
  consecutiveErrors: number;
  error?: unknown;
  hidden: boolean;
}

export function getPollingInterval(state: PollingState): number | false {
  if (state.job?.status === "COMPLETED" || state.job?.status === "FAILED") {
    return false;
  }
  if (state.error instanceof ApiError && state.error.status === 404)
    return false;
  if (state.consecutiveErrors >= 3) return 10_000;
  if (state.consecutiveErrors >= 1) return 5_000;
  if (state.hidden) return 5_000;
  return state.successCount < 5 ? 1_000 : 2_000;
}

export function usePipeline(jobId: string) {
  return useQuery({
    queryKey: ["pipeline", jobId],
    queryFn: ({ signal }) => dohaApi.getPipeline(jobId, signal),
    retry: false,
    refetchInterval: (query) =>
      getPollingInterval({
        job: query.state.data,
        successCount: query.state.dataUpdateCount,
        consecutiveErrors: query.state.fetchFailureCount,
        error: query.state.error,
        hidden: typeof document !== "undefined" && document.hidden,
      }),
    refetchIntervalInBackground: true,
    enabled: Boolean(jobId),
  });
}
