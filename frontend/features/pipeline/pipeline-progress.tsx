"use client";
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ErrorAlert, Progress, Unsupported } from "@/components/ui";
import { usePipeline } from "@/hooks/use-pipeline";
import { mapPipelineStatus } from "@/lib/mappers";
import { useStudioStore } from "@/stores/studio-store";
import type { PipelineStatus } from "@/types/api";

const stages: PipelineStatus[] = ["VALIDATING", "GENERATING", "STEM_SEPARATING", "VOICE_CONVERTING", "MIXING", "EXPORTING"];

export function PipelineProgress({ jobId }: { jobId: string }) {
  const router = useRouter();
  const patch = useStudioStore((state) => state.patch);
  const setStep = useStudioStore((state) => state.setStep);
  const query = usePipeline(jobId);
  const job = query.data;

  useEffect(() => { patch({ pipelineJobId: jobId, currentStep: "generation" }); }, [jobId, patch]);
  useEffect(() => {
    if (job?.status === "COMPLETED") {
      setStep("result");
      const timer = setTimeout(() => router.push(`/result/${jobId}`), 700);
      return () => clearTimeout(timer);
    }
  }, [job?.status, jobId, router, setStep]);

  if (query.isPending) return <div className="progress-page"><div className="vinyl-loader" /><h1>Job을 불러오는 중</h1></div>;
  if (query.error) return <div className="progress-page"><ErrorAlert title="Backend 연결 오류" message="동일한 Job을 다시 조회할 수 있습니다." /><button className="button" onClick={() => query.refetch()}>다시 연결</button></div>;
  if (!job) return null;
  const current = mapPipelineStatus(job.status);
  return <section className="progress-page">
    <div className="vinyl-loader" />
    <p className="eyebrow">PIPELINE · {job.id.slice(0, 8)}</p>
    <h1>{current.label}</h1>
    <p aria-live="polite" className="sr-status">현재 단계 {current.label}, {job.progress_percent}% 완료</p>
    <Progress value={job.progress_percent} label={`생성 진행률 ${job.progress_percent}%`} />
    <ol className="pipeline-stages">{stages.map((status, index) => {
      const active = status === job.status;
      const currentIndex = stages.indexOf(job.status);
      const done = job.status === "COMPLETED" || index < currentIndex;
      return <li key={status} className={active ? "active" : done ? "done" : ""}><span>{done ? "✓" : index + 1}</span>{mapPipelineStatus(status).label}</li>;
    })}</ol>
    {job.status === "FAILED" && <ErrorAlert title={`Pipeline 실패 · ${job.failed_step ?? "단계 미상"}`} message={job.error_message ?? job.error_code ?? "안전한 오류 정보가 없습니다."} />}
    <div className="actions">{job.status === "FAILED" && <Link className="button" href="/studio" onClick={() => setStep("review")}>Review로 돌아가 새 Job 생성</Link>}<Unsupported>Job 취소</Unsupported></div>
  </section>;
}
