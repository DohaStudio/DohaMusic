"use client";

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
        <p className="eyebrow">음악 만들기</p>
        <h1>{copy.title}</h1>
        <span>{copy.subtitle}</span>
      </div>
      {step === "settings" && <MusicSettingsStep />}
      {step === "lyrics" && <LyricsStep />}
      {step === "voice" && <VoiceStep />}
      {step === "review" && <ReviewStep />}
    </section>
  );
}
