"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, ErrorAlert, Input } from "@/components/ui";
import { useProjectStore } from "@/stores/project-store";

export function ProjectList() {
  const store = useProjectStore();
  const [title, setTitle] = useState("");
  useEffect(() => void store.load(), []); // eslint-disable-line react-hooks/exhaustive-deps
  return <section className="collection-page">
    <header className="collection-header"><div><p className="eyebrow">ORGANIZE</p><h1>Projects</h1><p>곡을 Project 단위로 관리합니다.</p></div><Link className="button secondary" href="/history">History</Link></header>
    <form className="collection-filters" onSubmit={(event) => { event.preventDefault(); if (!title.trim()) return; void store.createProject(title.trim()).then(() => setTitle("")); }}><Input aria-label="새 Project 이름" placeholder="새 Project 이름" value={title} onChange={(event) => setTitle(event.target.value)} /><Button type="submit">Project 만들기</Button></form>
    {store.error && <ErrorAlert message={store.error} />}
    {store.loading ? <div className="history-skeleton"><span /><span /></div> : <div className="project-grid">{store.items.map((project) => <article className="surface-card" key={project.id}><p className="eyebrow">{project.job_count} JOBS</p><h2>{project.title}</h2><p>{project.description ?? "설명 없음"}</p><small>생성 {new Date(project.created_at).toLocaleDateString("ko-KR")} · 수정 {new Date(project.updated_at).toLocaleDateString("ko-KR")}</small><div className="actions"><Link className="button" href={`/projects/${project.id}`}>열기</Link><Button className="secondary" onClick={() => { if (confirm("Project만 삭제하고 Job과 결과 파일은 유지할까요?")) void store.deleteProject(project.id); }}>삭제</Button></div></article>)}</div>}
  </section>;
}
