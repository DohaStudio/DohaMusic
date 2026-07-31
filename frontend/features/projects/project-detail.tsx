"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button, ErrorAlert, Input, Textarea } from "@/components/ui";
import { dohaApi } from "@/services/doha-api";
import { GenerationOptionsSummary } from "@/features/kpop/generation-options-summary";
import { AudioQualitySummary } from "@/features/audio/audio-quality-summary";
import { parseAudioAnalysis } from "@/lib/audio-analysis";

export function ProjectDetail({ projectId }: { projectId: string }) {
  const query = useQuery({ queryKey: ["project", projectId], queryFn: () => dohaApi.getProject(projectId) });
  if (query.error) return <ErrorAlert message="Project를 불러오지 못했습니다." />;
  if (!query.data) return <div className="history-skeleton"><span /><span /></div>;
  const project = query.data;
  return <section className="collection-page"><header className="collection-header"><div><p className="eyebrow">프로젝트</p><h1>{project.title}</h1><p>{project.description ?? "설명 없음"}</p></div><Link className="button secondary" href="/projects">목록</Link></header><ProjectEditor key={project.updated_at} projectId={projectId} title={project.title} description={project.description ?? ""} onSaved={() => query.refetch()} /><div className="history-list">{project.jobs.length ? project.jobs.map((job) => <article className="history-row" key={job.job_id}><div><h2>{job.title}</h2><p>{new Date(job.created_at).toLocaleString("ko-KR")} · {job.duration}초</p><GenerationOptionsSummary options={job.generation_options} retryOfJobId={job.retry_of_job_id} /><AudioQualitySummary compact analysis={parseAudioAnalysis(job.audio_analysis)} /></div><Badge tone={job.status === "COMPLETED" ? "success" : job.status === "FAILED" ? "error" : "active"}>{job.status === "COMPLETED" ? "완성" : job.status === "FAILED" ? "완료하지 못함" : job.status === "CANCELLED" ? "취소됨" : job.status === "CANCEL_REQUESTED" ? "취소 중" : "만드는 중"}</Badge><Link className="button" href={job.status === "COMPLETED" ? `/result/${job.job_id}` : `/generation/${job.job_id}`}>자세히 보기</Link></article>) : <div className="empty-state"><h2>아직 담긴 음악이 없습니다.</h2></div>}</div></section>;
}

function ProjectEditor({ projectId, title: initialTitle, description: initialDescription, onSaved }: { projectId: string; title: string; description: string; onSaved: () => Promise<unknown> }) {
  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState(initialDescription);
  return <form className="surface-card collection-editor" onSubmit={(event) => { event.preventDefault(); if (!title.trim()) return; void dohaApi.updateProject(projectId, { title: title.trim(), description: description || null }).then(() => onSaved()); }}><Input aria-label="Project 이름 수정" value={title} onChange={(event) => setTitle(event.target.value)} /><Textarea aria-label="Project 설명 수정" value={description} onChange={(event) => setDescription(event.target.value)} /><Button type="submit">Project 정보 저장</Button></form>;
}
