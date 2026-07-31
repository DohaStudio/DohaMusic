"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button, ErrorAlert, Input, Textarea } from "@/components/ui";
import { dohaApi } from "@/services/doha-api";

export function ProjectDetail({ projectId }: { projectId: string }) {
  const query = useQuery({ queryKey: ["project", projectId], queryFn: () => dohaApi.getProject(projectId) });
  if (query.error) return <ErrorAlert message="Project를 불러오지 못했습니다." />;
  if (!query.data) return <div className="history-skeleton"><span /><span /></div>;
  const project = query.data;
  return <section className="collection-page"><header className="collection-header"><div><p className="eyebrow">PROJECT</p><h1>{project.title}</h1><p>{project.description ?? "설명 없음"}</p></div><Link className="button secondary" href="/projects">목록</Link></header><ProjectEditor key={project.updated_at} projectId={projectId} title={project.title} description={project.description ?? ""} onSaved={() => query.refetch()} /><div className="history-list">{project.jobs.length ? project.jobs.map((job) => <article className="history-row" key={job.job_id}><div><h2>{job.title}</h2><p>{new Date(job.created_at).toLocaleString("ko-KR")} · {job.duration}초</p></div><Badge tone={job.status === "COMPLETED" ? "success" : job.status === "FAILED" ? "error" : "active"}>{job.status}</Badge><Link className="button" href={job.status === "COMPLETED" ? `/result/${job.job_id}` : `/generation/${job.job_id}`}>Result 열기</Link></article>) : <div className="empty-state"><h2>포함된 Job이 없습니다.</h2></div>}</div></section>;
}

function ProjectEditor({ projectId, title: initialTitle, description: initialDescription, onSaved }: { projectId: string; title: string; description: string; onSaved: () => Promise<unknown> }) {
  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState(initialDescription);
  return <form className="surface-card collection-editor" onSubmit={(event) => { event.preventDefault(); if (!title.trim()) return; void dohaApi.updateProject(projectId, { title: title.trim(), description: description || null }).then(() => onSaved()); }}><Input aria-label="Project 이름 수정" value={title} onChange={(event) => setTitle(event.target.value)} /><Textarea aria-label="Project 설명 수정" value={description} onChange={(event) => setDescription(event.target.value)} /><Button type="submit">Project 정보 저장</Button></form>;
}
