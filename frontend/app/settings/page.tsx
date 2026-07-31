"use client";

import { ApiStatus } from "@/components/api-status";
import { AppShell } from "@/components/app-shell";
import { useSettingsStore } from "@/stores/settings-store";

export default function SettingsPage() {
  const reducedMotion = useSettingsStore((state) => state.reducedMotion);
  const setReducedMotion = useSettingsStore((state) => state.setReducedMotion);
  return (
    <AppShell>
      <section className="page-stack narrow">
        <header className="page-heading">
          <p className="eyebrow">SETTINGS</p>
          <h1>Studio 환경</h1>
          <p>개인 브라우저 표시 설정과 Backend 연결 상태를 확인합니다.</p>
        </header>
        <div className="surface-card settings-list">
          <div>
            <span>API Base URL</span>
            <code>{process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend"}</code>
          </div>
          <div>
            <span>Backend 상태</span>
            <ApiStatus />
          </div>
          <label>
            <span>Theme</span>
            <select aria-label="테마" defaultValue="dark" disabled>
              <option value="dark">Premium Dark</option>
            </select>
          </label>
          <label>
            <span>움직임 줄이기</span>
            <select
              aria-label="움직임 줄이기"
              value={reducedMotion === null ? "system" : String(reducedMotion)}
              onChange={(event) =>
                setReducedMotion(
                  event.target.value === "system"
                    ? null
                    : event.target.value === "true",
                )
              }
            >
              <option value="system">시스템 설정 사용</option>
              <option value="true">사용</option>
              <option value="false">사용 안 함</option>
            </select>
          </label>
          <div>
            <span>Polling</span>
            <strong>정상 1초→2초 · 오류 5초→10초</strong>
          </div>
          <div>
            <span>Frontend 상태</span>
            <strong>Phase 8 MVP · Responsive Web</strong>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
