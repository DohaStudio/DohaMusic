"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { ProjectList } from "@/features/projects/project-list";

export default function ProjectsPage() {
  return <AppShell><Suspense fallback={<div className="history-skeleton" aria-label="프로젝트를 불러오는 중"><span /><span /></div>}><ProjectsRoute /></Suspense></AppShell>;
}

function ProjectsRoute() {
  const searchParams = useSearchParams();
  return <ProjectList mode={searchParams.get("mode") === "daw" ? "daw" : "projects"} />;
}
