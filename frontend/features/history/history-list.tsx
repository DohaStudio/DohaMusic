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

  return (
    <section className="collection-page">
      <header className="collection-header">
        <div><p className="eyebrow">YOUR MUSIC</p><h1>History</h1><p>생성 Job은 Pipeline 요청과 함께 자동 저장됩니다.</p></div>
        <Link className="button secondary" href="/projects">Projects</Link>
      </header>
      <form className="collection-filters" onSubmit={(event) => { event.preventDefault(); void store.load(); }}>
        <Input aria-label="제목 검색" placeholder="제목 검색" value={store.query} onChange={(event) => store.setQuery(event.target.value)} />
        <select aria-label="상태 필터" className="input" value={store.status} onChange={(event) => store.setStatus(event.target.value)}>
          <option value="">모든 상태</option><option value="PENDING">Queued</option><option value="GENERATING">Running</option><option value="COMPLETED">Completed</option><option value="FAILED">Failed</option>
        </select>
        <Button type="submit">검색</Button>
      </form>
      {store.error && <ErrorAlert message={store.error} />}
      {store.loading ? <div className="history-skeleton" aria-label="History 로딩 중"><span /><span /><span /></div> : store.items.length === 0 ? <div className="empty-state"><h2>생성한 음악이 없습니다.</h2><Link className="button" href="/studio">첫 음악 만들기</Link></div> : (
        <div className="history-list">{store.items.map((item) => (
          <article key={item.job_id} className="history-row">
            <div><h2>{item.title}</h2><p>{new Date(item.created_at).toLocaleString("ko-KR")} · {item.voice_profile_name} · {item.duration}초</p></div>
            <Badge tone={tones[item.status] ?? "neutral"}>{statusLabel(item.status)}</Badge>
            <span>{item.has_audio ? "Audio ready" : "Audio 없음"}</span>
            <div className="actions"><Button disabled={!item.has_audio} onClick={() => void playJob(item.job_id)}>Play</Button><Button className="secondary" disabled={!item.has_audio} onClick={() => void downloadJob(item.job_id)}>Download</Button><Link className="button secondary" href={`/result/${item.job_id}`}>Open</Link></div>
          </article>
        ))}</div>
      )}
    </section>
  );
}

function statusLabel(status: string) {
  if (status === "COMPLETED") return "Completed";
  if (status === "FAILED") return "Failed";
  if (status === "PENDING" || status === "QUEUED") return "Queued";
  return "Running";
}
