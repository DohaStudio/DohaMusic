"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Vinyl } from "@/components/brand";
import { Badge, ErrorAlert, Unsupported } from "@/components/ui";
import { usePipeline } from "@/hooks/use-pipeline";
import { mapSafeFiles } from "@/lib/mappers";
import { publicMetadataRows } from "@/lib/result-metadata";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";

export function ResultPanel({ jobId }: { jobId: string }) {
  const setStep = useStudioStore((state) => state.setStep);
  const jobQuery = usePipeline(jobId);
  const filesQuery = useQuery({
    queryKey: ["pipeline-files", jobId],
    queryFn: () => dohaApi.getPipelineFiles(jobId),
    enabled: jobQuery.data?.status === "COMPLETED",
  });
  const job = jobQuery.data;
  if (jobQuery.error)
    return <ErrorAlert message="결과 Job을 조회할 수 없습니다." />;
  if (!job)
    return (
      <div className="progress-page">
        <div className="vinyl-loader" />
        <h1>결과를 불러오는 중</h1>
      </div>
    );
  if (job.status !== "COMPLETED")
    return (
      <div className="progress-page">
        <h1>아직 결과가 준비되지 않았습니다.</h1>
        <Link className="button" href={`/generation/${jobId}`}>
          진행 화면 보기
        </Link>
      </div>
    );

  const files = mapSafeFiles(filesQuery.data ?? []);
  const metadata = publicMetadataRows(job.result_metadata);
  return (
    <section className="result-layout">
      <div className="result-hero">
        <Vinyl />
        <p className="eyebrow">GENERATION COMPLETE</p>
        <h1>{job.prompt}</h1>
        <p>
          {job.genre ?? "장르 미지정"} · {job.duration_seconds}초
        </p>
        <div className="actions">
          <Unsupported>재생</Unsupported>
          <Unsupported>다운로드</Unsupported>
        </div>
      </div>
      <div className="surface-card">
        <div className="result-head">
          <h2>결과 Metadata</h2>
          <Badge tone="success">COMPLETED</Badge>
        </div>
        <dl className="metadata-list">
          <Meta label="Pipeline" value={job.pipeline_version} />
          <Meta label="Seed" value={job.seed?.toString() ?? "자동"} />
          <Meta
            label="완료 시각"
            value={
              job.completed_at
                ? new Date(job.completed_at).toLocaleString("ko-KR")
                : "-"
            }
          />
          {metadata.map((item) => (
            <Meta key={item.label} label={item.label} value={item.value} />
          ))}
        </dl>
        <h3>생성 파일 Metadata</h3>
        {files.length ? (
          <ul className="file-list">
            {files.map((file) => (
              <li key={file.id}>
                <span>{file.fileType}</span>
                <strong>{file.mimeType}</strong>
                <small>
                  {new Date(file.createdAt).toLocaleString("ko-KR")}
                </small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">파일 metadata가 없습니다.</p>
        )}
        <p className="notice">
          Backend public DTO와 화면 모두 내부 Storage 경로를 포함하지 않습니다.
        </p>
        <Link
          className="button secondary"
          href="/studio"
          onClick={() => setStep("review")}
        >
          같은 설정으로 새 Job 만들기
        </Link>
      </div>
    </section>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
