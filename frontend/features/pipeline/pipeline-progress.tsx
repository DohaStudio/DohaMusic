"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Button, ErrorAlert, Progress } from "@/components/ui";
import { usePipeline } from "@/hooks/use-pipeline";
import { mapPipelineStatus } from "@/lib/mappers";
import { useStudioStore } from "@/stores/studio-store";
import { userErrorMessage } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import type { PipelineStatus } from "@/types/api";
import { CancelDialog } from "./cancel-dialog";

const stages: PipelineStatus[] = ["VALIDATING", "GENERATING", "STEM_SEPARATING", "VOICE_CONVERTING", "MIXING", "EXPORTING"];
export function PipelineProgress({ jobId }: { jobId: string }) {
  const router = useRouter(); const queryClient = useQueryClient(); const [confirmCancel, setConfirmCancel] = useState(false);
  const patch = useStudioStore((state) => state.patch); const setStep = useStudioStore((state) => state.setStep); const query = usePipeline(jobId); const job = query.data;
  const refreshRelated = async () => { await Promise.all([query.refetch(), queryClient.invalidateQueries({ queryKey: ["history"] }), queryClient.invalidateQueries({ queryKey: ["projects"] })]); };
  const cancel = useMutation({ mutationFn: () => dohaApi.cancelPipelineJob(jobId), onSuccess: async () => { setConfirmCancel(false); await refreshRelated(); } });
  const retry = useMutation({ mutationFn: () => dohaApi.retryPipelineJob(jobId), onSuccess: async ({ job: next }) => { queryClient.setQueryData(["pipeline", next.id], next); await queryClient.invalidateQueries({ queryKey: ["history"] }); router.push(`/generation/${next.id}`); } });
  useEffect(() => { patch({ pipelineJobId: jobId, currentStep: "generation" }); }, [jobId, patch]);
  useEffect(() => { if (job?.status === "COMPLETED") { setStep("result"); const timer = setTimeout(() => router.push(`/result/${jobId}`), 700); return () => clearTimeout(timer); } }, [job?.status, jobId, router, setStep]);
  useEffect(() => { if (["FAILED", "CANCELLED"].includes(job?.status ?? "")) document.querySelector<HTMLElement>(".progress-page h1")?.focus(); }, [job?.status]);
  if (query.isPending) return <div className="progress-page"><div className="vinyl-loader" /><h1>음악을 준비하는 중입니다</h1></div>;
  if (query.error && !job) return <div className="progress-page"><ErrorAlert title="진행 상태를 불러오지 못했습니다" message={userErrorMessage(query.error)} /><button className="button" onClick={() => query.refetch()}>다시 확인</button></div>;
  if (!job) return null;
  const current = mapPipelineStatus(job.status); const terminal = ["FAILED", "CANCELLED"].includes(job.status);
  return <section className="progress-page" aria-busy={cancel.isPending || retry.isPending}><div className="vinyl-loader" /><p className="eyebrow">{terminal ? "만든 음악" : "음악 만드는 중"}</p><h1 tabIndex={-1}>{current.label}</h1><p aria-live="polite" className="sr-status">현재 {current.label}, {job.progress_percent}% 완료</p><Progress value={job.progress_percent} label={`음악 만들기 ${job.progress_percent}%`} />
    {job.status === "CANCEL_REQUESTED" && <div className="notice" aria-live="polite"><strong>취소 요청을 처리하고 있습니다.</strong><p>현재 단계가 안전하게 정리될 때까지 잠시 기다려 주세요.</p></div>}
    {query.error && <ErrorAlert title="진행 상태 확인이 늦어지고 있습니다" message="음악 만들기는 계속 진행될 수 있습니다. 잠시 후 다시 확인해 주세요." />}
    {!terminal && job.status !== "CANCEL_REQUESTED" && <ol className="pipeline-stages">{stages.map((status, index) => { const active = status === job.status; const currentIndex = stages.indexOf(job.status); const done = index < currentIndex; return <li key={status} className={active ? "active" : done ? "done" : ""}><span>{done ? "✓" : index + 1}</span>{mapPipelineStatus(status).label}</li>; })}</ol>}
    {job.status === "FAILED" && <ErrorAlert title="음악을 완성하지 못했습니다" message={job.error_message || "설정을 확인한 뒤 같은 설정으로 다시 만들 수 있습니다."} />}
    {(cancel.error || retry.error) && <ErrorAlert message={userErrorMessage(cancel.error || retry.error)} />}
    <div className="actions">
      {job.can_cancel && job.status !== "CANCEL_REQUESTED" && <Button className="danger" disabled={cancel.isPending} onClick={() => setConfirmCancel(true)}>음악 만들기 취소</Button>}
      {job.can_retry && <Button disabled={retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? "새 작업을 준비하고 있습니다" : "같은 설정으로 다시 만들기"}</Button>}
      {job.status === "CANCELLED" && <Link className="button secondary" href="/history">만든 음악으로 이동</Link>}
      {terminal && <Link className="button secondary" href="/studio">음악 만들기로 돌아가기</Link>}
    </div>
    {job.can_retry && <p className="muted">같은 설정과 Seed로 새 작업을 만듭니다. 생성 환경에 따라 결과는 조금 달라질 수 있습니다.</p>}
    <CancelDialog open={confirmCancel} pending={cancel.isPending} onClose={() => setConfirmCancel(false)} onConfirm={() => cancel.mutate()} />
  </section>;
}
