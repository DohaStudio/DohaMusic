"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Badge, Button, ErrorAlert, Input } from "@/components/ui";
import { mapSafeFiles, selectPreferredAudioFile } from "@/lib/mappers";
import { dohaApi } from "@/services/doha-api";
import { useHistoryStore } from "@/stores/history-store";
import { usePlayerStore } from "@/stores/player-store";

const tones: Record<string, string> = {
  PENDING: "neutral",
  QUEUED: "neutral",
  GENERATING: "active",
  SEPARATING: "active",
  CONVERTING: "active",
  MIXING: "active",
  COMPLETED: "success",
  FAILED: "error",
  CANCEL_REQUESTED: "active",
  CANCELLED: "neutral",
};

export function HistoryList() {
  const store = useHistoryStore();
  const play = usePlayerStore((state) => state.play);
  useEffect(() => void store.load(), []); // eslint-disable-line react-hooks/exhaustive-deps

  async function playJob(jobId: string) {
    const files = mapSafeFiles(await dohaApi.getPipelineFiles(jobId));
    const preferred = selectPreferredAudioFile(files);
    if (preferred) play(preferred);
  }

  async function downloadJob(jobId: string) {
    const files = mapSafeFiles(await dohaApi.getPipelineFiles(jobId));
    const preferred = selectPreferredAudioFile(files);
    if (preferred?.downloadUrl) window.location.assign(preferred.downloadUrl);
  }

  async function cancelJob(jobId: string) {
    await dohaApi.cancelPipelineJob(jobId);
    await store.load();
  }

  async function retryJob(jobId: string) {
    const response = await dohaApi.retryPipelineJob(jobId);
    window.location.assign(`/generation/${response.job.id}`);
  }

  return (
    <section className="collection-page">
      <header className="collection-header">
        <div><p className="eyebrow">만든 음악</p><h1>최근에 만든 음악</h1><p>완성된 곡과 지금 만들고 있는 곡을 한곳에서 확인합니다.</p></div>
        <Link className="button secondary" href="/projects">프로젝트로 정리하기</Link>
      </header>
      <form className="collection-filters" onSubmit={(event) => { event.preventDefault(); void store.load(); }}>
        <Input aria-label="제목 검색" placeholder="제목 검색" value={store.query} onChange={(event) => store.setQuery(event.target.value)} />
        <select aria-label="상태 필터" className="input" value={store.status} onChange={(event) => store.setStatus(event.target.value)}>
          <option value="">모든 상태</option><option value="PENDING">시작 전</option><option value="GENERATING">만드는 중</option><option value="COMPLETED">완성</option><option value="FAILED">완료하지 못함</option>
        </select>
        <Button type="submit">검색</Button>
      </form>
      {store.error && <ErrorAlert message={store.error} />}
      {store.loading ? <div className="history-skeleton" aria-label="만든 음악을 불러오는 중"><span /><span /><span /></div> : store.items.length === 0 ? <div className="empty-state"><h2>아직 만든 음악이 없습니다.</h2><p>스타일과 목소리를 골라 첫 곡을 만들어 보세요.</p><Link className="button" href="/studio">첫 음악 만들기</Link></div> : (
        <div className="history-list">{store.items.map((item) => (
          <article key={item.job_id} className="history-row">
            <div><h2>{item.title}</h2><p>{new Date(item.created_at).toLocaleString("ko-KR")} · {item.voice_profile_name} · {item.duration}초</p></div>
            <Badge tone={tones[item.status] ?? "neutral"}>{statusLabel(item.status)}</Badge>
            <span>{item.has_audio ? "재생 가능" : "아직 재생할 수 없음"}</span>
            <div className="actions">{item.has_audio && <><Button onClick={() => void playJob(item.job_id)}>재생</Button><Button className="secondary" onClick={() => void downloadJob(item.job_id)}>다운로드</Button></>}{item.can_cancel && item.status !== "CANCEL_REQUESTED" && <Button className="danger" onClick={() => void cancelJob(item.job_id)}>취소</Button>}{item.can_retry && <Button onClick={() => void retryJob(item.job_id)}>다시 만들기</Button>}<Link className="button secondary" href={item.status === "COMPLETED" ? `/result/${item.job_id}` : `/generation/${item.job_id}`}>열기</Link></div>
          </article>
        ))}</div>
      )}
    </section>
  );
}

function statusLabel(status: string) {
  if (status === "COMPLETED") return "완성";
  if (status === "FAILED") return "완료하지 못함";
  if (status === "CANCEL_REQUESTED") return "취소 중";
  if (status === "CANCELLED") return "취소됨";
  if (status === "PENDING" || status === "QUEUED") return "시작 전";
  return "만드는 중";
}
