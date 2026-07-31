"use client";
import Link from "next/link";
import { ApiStatus } from "@/components/api-status";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui";
import { isDeveloperInfoEnabled } from "@/lib/developer-info";
import { useSettingsStore } from "@/stores/settings-store";

export default function SettingsPage() {
  const reducedMotion = useSettingsStore((state) => state.reducedMotion); const setReducedMotion = useSettingsStore((state) => state.setReducedMotion); const reopenOnboarding = useSettingsStore((state) => state.reopenOnboarding);
  return <AppShell><section className="page-stack narrow"><header className="page-heading"><p className="eyebrow">설정</p><h1>나에게 맞게 사용하기</h1><p>화면 움직임과 시작 안내를 관리할 수 있습니다.</p></header>
    <div className="surface-card settings-list">
      <label><span>화면 움직임</span><select aria-label="화면 움직임" value={reducedMotion === null ? "system" : String(reducedMotion)} onChange={(event) => setReducedMotion(event.target.value === "system" ? null : event.target.value === "true")}><option value="system">기기 설정 따르기</option><option value="true">움직임 줄이기</option><option value="false">기본 움직임</option></select></label>
      <div><span>시작 안내</span><Button className="secondary" onClick={reopenOnboarding}>다시 보기</Button></div>
      <div><span>내 목소리 관리</span><Link className="button secondary" href="/voice">등록한 목소리 보기</Link></div>
      <div><span>화면 테마</span><strong>어두운 테마 · 다른 테마는 준비 중</strong></div>
      {isDeveloperInfoEnabled() && <details className="dev-only"><summary>개발자 정보</summary><div className="settings-list"><div><span>API 주소</span><code>{process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend"}</code></div><div><span>연결 상태</span><ApiStatus /></div><div><span>상태 확인 간격</span><strong>정상 1초→2초 · 오류 5초→10초</strong></div></div></details>}
    </div></section></AppShell>;
}
