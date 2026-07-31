"use client";
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ErrorAlert, Progress } from "@/components/ui";
import { usePipeline } from "@/hooks/use-pipeline";
import { mapPipelineStatus } from "@/lib/mappers";
import { useStudioStore } from "@/stores/studio-store";
import { userErrorMessage } from "@/services/api-client";
import type { PipelineStatus } from "@/types/api";

const stages: PipelineStatus[] = ["VALIDATING", "GENERATING", "STEM_SEPARATING", "VOICE_CONVERTING", "MIXING", "EXPORTING"];
export function PipelineProgress({ jobId }: { jobId: string }) {
  const router = useRouter(); const patch = useStudioStore((state) => state.patch); const setStep = useStudioStore((state) => state.setStep); const query = usePipeline(jobId); const job = query.data;
  useEffect(() => { patch({ pipelineJobId: jobId, currentStep: "generation" }); }, [jobId, patch]);
  useEffect(() => { if (job?.status === "COMPLETED") { setStep("result"); const timer = setTimeout(() => router.push(`/result/${jobId}`), 700); return () => clearTimeout(timer); } }, [job?.status, jobId, router, setStep]);
  if (query.isPending) return <div className="progress-page"><div className="vinyl-loader" /><h1>음악을 준비하는 중입니다</h1></div>;
  if (query.error && !job) return <div className="progress-page"><ErrorAlert title="진행 상태를 불러오지 못했습니다" message={userErrorMessage(query.error)} /><button className="button" onClick={() => query.refetch()}>다시 확인</button></div>;
  if (!job) return null;
  const current = mapPipelineStatus(job.status);
  return <section className="progress-page"><div className="vinyl-loader" /><p className="eyebrow">음악 만드는 중</p><h1>{current.label}</h1><p aria-live="polite" className="sr-status">현재 {current.label}, {job.progress_percent}% 완료</p><Progress value={job.progress_percent} label={`음악 만들기 ${job.progress_percent}%`} />
    {query.error && <ErrorAlert title="진행 상태 확인이 늦어지고 있습니다" message="음악 만들기는 계속 진행될 수 있습니다. 잠시 후 다시 확인해 주세요." />}
    <ol className="pipeline-stages">{stages.map((status, index) => { const active = status === job.status; const currentIndex = stages.indexOf(job.status); const done = job.status === "COMPLETED" || index < currentIndex; return <li key={status} className={active ? "active" : done ? "done" : ""}><span>{done ? "✓" : index + 1}</span>{mapPipelineStatus(status).label}</li>; })}</ol>
    {job.status === "FAILED" && <ErrorAlert title="음악을 완성하지 못했습니다" message={userErrorMessage({ code: job.error_code, message: job.error_message })} />}
    {job.status === "FAILED" && <div className="actions"><Link className="button" href="/studio" onClick={() => setStep("review")}>설정을 확인하고 다시 만들기</Link></div>}
  </section>;
}
