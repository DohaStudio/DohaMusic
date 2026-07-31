"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenText, CircleUserRound, Info, Mic2, Settings2, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { Brand } from "./brand";
import { ApiStatus } from "./api-status";

const nav = [{ href: "/studio", label: "Studio", icon: SlidersHorizontal }, { href: "/lyrics", label: "Lyrics Lab", icon: BookOpenText }, { href: "/voice", label: "Voice", icon: Mic2 }, { href: "/settings", label: "Settings", icon: Settings2 }, { href: "/about", label: "About", icon: Info }];
export function AppShell({ children, context }: { children: ReactNode; context?: ReactNode }) { const path = usePathname(); return <div className="app-shell"><aside className="sidebar"><Brand /><nav aria-label="주요 메뉴">{nav.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={path.startsWith(href) ? "active" : ""}><Icon size={19} /><span>{label}</span></Link>)}</nav><div className="sidebar-foot"><CircleUserRound /><span>Local Creator<small>개인 작업 공간</small></span></div></aside><header className="mobile-header"><Brand compact /><ApiStatus /><CircleUserRound /></header><main id="main-content" className="main-workspace">{children}</main><aside className="context-panel"><div className="context-head"><span>Studio Context</span><ApiStatus /></div>{context ?? <ContextDefault />}</aside><PlayerShell /><nav className="mobile-nav" aria-label="모바일 메뉴">{nav.slice(0,4).map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={path.startsWith(href) ? "active" : ""}><Icon /><span>{label}</span></Link>)}</nav></div>; }
function ContextDefault() { return <div className="context-copy"><p className="eyebrow">LOCAL FIRST</p><h2>당신의 아이디어를<br />한 곡의 흐름으로</h2><p>Frontend는 모델을 직접 호출하지 않습니다. 모든 생성은 DohaMusic FastAPI의 Provider Adapter 경계를 통과합니다.</p></div>; }
function PlayerShell() { return <footer className="player-shell"><div className="mini-art">D</div><div><strong>미리듣기 준비 전</strong><small>Audio content API가 필요합니다</small></div><div className="wave" aria-hidden="true">{Array.from({ length: 22 }, (_, i) => <i key={i} style={{ height: `${10 + (i * 7) % 24}px` }} />)}</div><button disabled aria-label="재생, Backend API 준비 필요">▶</button></footer>; }
