"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Vinyl } from "@/components/brand";
import { Badge, Button, ErrorAlert } from "@/components/ui";
import { usePipeline } from "@/hooks/use-pipeline";
import { mapSafeFiles, selectPreferredAudioFile } from "@/lib/mappers";
import { publicMetadataRows } from "@/lib/result-metadata";
import { parseAudioAnalysis } from "@/lib/audio-analysis";
import { AudioQualitySummary } from "@/features/audio/audio-quality-summary";
import { TempoSummary } from "@/features/audio/tempo-summary";
import { HookSummary } from "@/features/audio/hook-summary";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import { usePlayerStore } from "@/stores/player-store";

export function ResultPanel({ jobId }: { jobId: string }) {
  const setStep = useStudioStore((state) => state.setStep);
  const playerFile = usePlayerStore((state) => state.currentFile);
  const shouldPlay = usePlayerStore((state) => state.shouldPlay);
  const selectPlayerFile = usePlayerStore((state) => state.select);
  const play = usePlayerStore((state) => state.play);
  const pause = usePlayerStore((state) => state.pause);
  const [selectedId, setSelectedId] = useState("");
  const jobQuery = usePipeline(jobId);
  const filesQuery = useQuery({
    queryKey: ["pipeline-files", jobId],
    queryFn: () => dohaApi.getPipelineFiles(jobId),
    enabled: jobQuery.data?.status === "COMPLETED",
  });
  const job = jobQuery.data;
  const files = mapSafeFiles(filesQuery.data ?? []);
  const preferred = selectPreferredAudioFile(files);
  const selected = files.find((file) => file.id === selectedId) ?? preferred;

  useEffect(() => {
    if (!selectedId && preferred && playerFile?.id !== preferred.id) {
      selectPlayerFile(preferred);
    }
  }, [playerFile?.id, preferred, selectPlayerFile, selectedId]);
  if (jobQuery.error)
    return <ErrorAlert message="완성된 음악을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." />;
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

  const metadata = publicMetadataRows(job.result_metadata);
  const audioAnalysis = parseAudioAnalysis(
    job.audio_analysis ?? job.result_metadata,
  );
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
          <Button
            disabled={!selected?.contentAvailable || !selected.contentUrl}
            onClick={() => {
              if (!selected) return;
              if (playerFile?.id === selected.id && shouldPlay) pause();
              else play(selected);
            }}
          >
            {playerFile?.id === selected?.id && shouldPlay
              ? "일시정지"
              : "재생"}
          </Button>
          {selected?.downloadAvailable && selected.downloadUrl ? (
            <a className="button secondary" href={selected.downloadUrl}>
              WAV 다운로드
            </a>
          ) : (
            <button className="button secondary" disabled>
              다운로드 불가
            </button>
          )}
        </div>
      </div>
      <div className="surface-card">
        <div className="result-head">
          <h2>완성 정보</h2>
          <Badge tone="success">완성</Badge>
        </div>
        <dl className="metadata-list">
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
        <AudioQualitySummary analysis={audioAnalysis} />
        <TempoSummary analysis={audioAnalysis} />
        <HookSummary analysis={audioAnalysis} />
        <h3>재생할 파일</h3>
        {filesQuery.error && (
          <ErrorAlert message="생성 파일 목록을 조회할 수 없습니다." />
        )}
        {files.length ? (
          <ul className="file-list">
            {files.map((file) => (
              <li
                key={file.id}
                className={selected?.id === file.id ? "selected" : ""}
              >
                <button
                  type="button"
                  disabled={!file.contentAvailable}
                  aria-label={`${file.fileType} 재생 파일 선택`}
                  onClick={() => {
                    setSelectedId(file.id);
                    selectPlayerFile(file);
                  }}
                >
                  <span>{file.fileType}</span>
                  <strong>{file.mimeType}</strong>
                  <small>
                    {file.contentAvailable ? "재생 가능" : "재생 불가"} ·{" "}
                    {new Date(file.createdAt).toLocaleString("ko-KR")}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">재생할 파일이 아직 없습니다.</p>
        )}
        <Link
          className="button secondary"
          href="/studio"
          onClick={() => setStep("review")}
        >
          같은 설정으로 새 음악 만들기
        </Link>
        {job.project_id && (
          <Link className="button secondary" href={`/projects/${encodeURIComponent(job.project_id)}`}>
            프로젝트에서 편집
          </Link>
        )}
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
