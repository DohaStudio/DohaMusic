"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpenText,
  CircleUserRound,
  Info,
  FolderKanban,
  History,
  Mic2,
  Settings2,
  SlidersHorizontal,
} from "lucide-react";
import type { ReactNode } from "react";
import { Brand } from "./brand";
import { ApiStatus } from "./api-status";
import { GlobalPlayer } from "@/features/player/global-player";

const nav = [
  { href: "/studio", label: "음악 만들기", icon: SlidersHorizontal },
  { href: "/lyrics", label: "가사 만들기", icon: BookOpenText },
  { href: "/voice", label: "내 목소리", icon: Mic2 },
  { href: "/history", label: "만든 음악", icon: History },
  { href: "/projects", label: "프로젝트", icon: FolderKanban },
  { href: "/settings", label: "설정", icon: Settings2 },
  { href: "/about", label: "서비스 소개", icon: Info },
];
export function AppShell({
  children,
  context,
}: {
  children: ReactNode;
  context?: ReactNode;
}) {
  const path = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <nav aria-label="주요 메뉴">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={path.startsWith(href) ? "active" : ""}
            >
              <Icon size={19} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <CircleUserRound />
          <span>
            Local Creator<small>개인 작업 공간</small>
          </span>
        </div>
      </aside>
      <header className="mobile-header">
        <Brand compact />
        <ApiStatus />
        <CircleUserRound />
      </header>
      <main id="main-content" className="main-workspace">
        {children}
      </main>
      <aside className="context-panel">
        <div className="context-head">
          <span>도움말</span>
          <ApiStatus />
        </div>
        {context ?? <ContextDefault />}
      </aside>
      <GlobalPlayer />
      <nav className="mobile-nav" aria-label="모바일 메뉴">
        {nav.slice(0, 4).map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={path.startsWith(href) ? "active" : ""}
          >
            <Icon />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
function ContextDefault() {
  return (
    <div className="context-copy">
      <p className="eyebrow">DOHA MUSIC</p>
      <h2>처음이어도 괜찮아요</h2>
      <p>음악 스타일과 가사, 내 목소리를 차례로 선택하면 완성까지 안내해 드립니다.</p>
    </div>
  );
}
