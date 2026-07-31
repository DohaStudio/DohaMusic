"use client";
import { useQuery } from "@tanstack/react-query";
import { dohaApi } from "@/services/doha-api";
import type { PipelineJobDto } from "@/types/api";

export function pollingInterval(query: { state: { data?: PipelineJobDto; dataUpdateCount: number } }): number | false { const job = query.state.data; if (job && (job.status === "COMPLETED" || job.status === "FAILED")) return false; if (typeof document !== "undefined" && document.hidden) return 5_000; return query.state.dataUpdateCount < 5 ? 1_000 : 2_000; }
export function usePipeline(jobId: string) { return useQuery({ queryKey: ["pipeline", jobId], queryFn: () => dohaApi.getPipeline(jobId), refetchInterval: pollingInterval, refetchIntervalInBackground: true, enabled: Boolean(jobId) }); }
