"use client";

import Link from "next/link";
import { StepIndicator } from "@/components/step-indicator";
import { useStudioStore } from "@/stores/studio-store";
import { LyricsStep } from "./lyrics-step";
import { MusicSettingsStep } from "./music-settings-step";
import { ReviewStep } from "./review-step";
import { studioStepCopy } from "./studio-step-copy";
import { VoiceStep } from "./voice-step";

export function StudioWorkspace() {
  const step = useStudioStore((state) => state.currentStep);
  const copy = studioStepCopy[step];
  return (
    <section className="workspace-card">
      <StepIndicator current={step} />
      <div className="workspace-title">
        <p className="eyebrow">새 음악 생성</p>
        <h1>{copy.title}</h1>
        <span>{copy.subtitle}</span>
      </div>
      <aside className="studio-daw-entry" aria-label="DAW 편집 안내">
        <div>
          <strong>이미 만든 곡을 편집하고 싶나요?</strong>
          <span>프로젝트의 DAW에서 트랙과 클립, 미리듣기와 버전을 관리할 수 있습니다.</span>
        </div>
        <Link className="button secondary" href="/projects">프로젝트에서 편집하기</Link>
      </aside>
      {step === "settings" && <MusicSettingsStep />}
      {step === "lyrics" && <LyricsStep />}
      {step === "voice" && <VoiceStep />}
      {step === "review" && <ReviewStep />}
    </section>
  );
}
