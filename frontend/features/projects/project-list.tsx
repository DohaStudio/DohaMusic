"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, ErrorAlert, Input } from "@/components/ui";
import { useProjectStore } from "@/stores/project-store";

export function ProjectList({ mode = "projects" }: { mode?: "projects" | "daw" }) {
  const store = useProjectStore();
  const [title, setTitle] = useState("");
  const dawMode = mode === "daw";
  useEffect(() => void store.load(), []); // eslint-disable-line react-hooks/exhaustive-deps
  return <section className="collection-page">
    <header className="collection-header"><div><p className="eyebrow">{dawMode ? "DAW 편집" : "프로젝트"}</p><h1>{dawMode ? "DAW에서 편집할 프로젝트 선택" : "프로젝트"}</h1><p>{dawMode ? "편집할 프로젝트를 선택하면 타임라인과 클립 편집 화면으로 이동합니다." : "음악을 주제별로 정리하고 프로젝트 정보와 결과를 관리합니다."}</p></div><Link className="button secondary" href="/history">만든 음악 보기</Link></header>
    <form className="collection-filters" onSubmit={(event) => { event.preventDefault(); if (!title.trim()) return; void store.createProject(title.trim()).then(() => setTitle("")); }}><Input aria-label="새 프로젝트 이름" placeholder="예: 여름 댄스 앨범" value={title} onChange={(event) => setTitle(event.target.value)} /><Button type="submit">프로젝트 만들기</Button></form>
    {store.error && <ErrorAlert message={store.error} />}
    {store.loading ? <div className="history-skeleton" aria-label="프로젝트를 불러오는 중"><span /><span /></div> : store.items.length === 0 ? <div className="empty-state"><h2>아직 프로젝트가 없습니다.</h2><p>위에 이름을 입력해 첫 프로젝트를 만들어 보세요.</p></div> : <div className="project-grid">{store.items.map((project) => <article className="surface-card" key={project.id}><p className="eyebrow">음악 {project.job_count}개</p><h2>{project.title}</h2><p>{project.description ?? "설명 없음"}</p><small>생성 {new Date(project.created_at).toLocaleDateString("ko-KR")} · 수정 {new Date(project.updated_at).toLocaleDateString("ko-KR")}</small><div className="actions"><Link className="button" href={`/projects/${project.id}`}>{dawMode ? "DAW 열기" : "프로젝트 열기"}</Link><Button className="secondary" onClick={() => { if (confirm("프로젝트만 삭제하고 음악과 결과 파일은 유지할까요?")) void store.deleteProject(project.id); }}>삭제</Button></div></article>)}</div>}
  </section>;
}
