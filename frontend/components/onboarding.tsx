"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button } from "./ui";
import { useSettingsStore } from "@/stores/settings-store";

export function Onboarding() {
  const completed = useSettingsStore((state) => state.onboardingCompleted);
  const open = useSettingsStore((state) => state.onboardingOpen);
  const complete = useSettingsStore((state) => state.completeOnboarding);
  const [hydrated, setHydrated] = useState(false);
  const dialog = useRef<HTMLElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const wasOpen = useRef(false);
  const visible = hydrated && !completed && open;

  useEffect(() => {
    let active = true;
    const finishHydration = () => setHydrated(true);
    void Promise.resolve(useSettingsStore.persist.rehydrate()).then(
      () => { if (active) finishHydration(); },
      () => { if (active) finishHydration(); },
    );
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (visible) {
      if (!wasOpen.current) {
        previousFocus.current = document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      }
      wasOpen.current = true;
      dialog.current?.querySelector<HTMLElement>("button, a[href]")?.focus();
      return;
    }
    if (wasOpen.current) previousFocus.current?.focus();
    wasOpen.current = false;
  }, [visible]);

  if (!visible) return null;
  function keepFocus(event: React.KeyboardEvent) {
    if (event.key === "Escape") { complete(); return; }
    if (event.key !== "Tab") return;
    const focusable = dialog.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'); if (!focusable?.length) return;
    const firstItem = focusable[0]; const lastItem = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === firstItem) { event.preventDefault(); lastItem.focus(); }
    else if (!event.shiftKey && document.activeElement === lastItem) { event.preventDefault(); firstItem.focus(); }
  }
  return <div className="modal-backdrop" role="presentation"><section ref={dialog} className="onboarding-dialog" role="dialog" aria-modal="true" aria-labelledby="onboarding-title" aria-describedby="onboarding-description" onKeyDown={keepFocus}><p className="eyebrow">처음 오셨나요?</p><h1 id="onboarding-title">DohaMusic 시작하기</h1><p id="onboarding-description">네 단계만 따라가면 나만의 음악을 만들 수 있습니다.</p><ol><li>음악 스타일 선택</li><li>가사 준비</li><li>내 목소리 등록</li><li>음악 완성</li></ol><div className="actions"><Button className="secondary" onClick={complete}>닫기</Button><Link className="button" href="/studio" onClick={complete}>첫 음악 만들기</Link></div></section></div>;
}
