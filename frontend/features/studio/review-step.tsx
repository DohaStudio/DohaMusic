"use client";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Button, ErrorAlert } from "@/components/ui";
import { userErrorMessage } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import { toPipelineCreate } from "./studio-submit";
import { getKPopPreset } from "./kpop-presets";

export function ReviewStep() {
  const router = useRouter();
  const store = useStudioStore();
  const preset = getKPopPreset(store.kpopPresetId);
  const create = useMutation({ mutationFn: () => dohaApi.createPipeline(toPipelineCreate(store)), onSuccess: (job) => { store.patch({ pipelineJobId: job.id, currentStep: "generation" }); router.push(`/generation/${job.id}`); } });
  return <div className="studio-form">
    <div className="review-grid">
      <Review label="노래 설명" value={store.prompt} />
      <Review label="K-POP 스타일" value={preset.displayName} />
      <Review label="추가 장르 방향" value={store.genre || "선택하지 않음"} />
      <Review label="분위기" value={store.selectedMoods.join(", ") || "선택하지 않음"} />
      <Review label="목표 BPM" value={`${store.generationOptions.requestedBpm} BPM (Prompt 목표)`} />
      <Review label="가사 언어 목표" value={`한국어 ${store.generationOptions.languageRatio.ko}% · 영어 ${store.generationOptions.languageRatio.en}%`} />
      <Review label="후렴 Hook" value={store.generationOptions.hook?.phrase || "별도 지정 없음"} />
      <Review label="보컬 에너지" value={store.generationOptions.vocalEnergy} />
      <Review label="콘셉트" value={store.generationOptions.concept || "Preset 기본값"} />
      <Review label="곡 구조" value={[store.generationOptions.includePostChorus && "Post-Chorus", store.generationOptions.includeDanceBreak && "Dance Break"].filter(Boolean).join(", ") || "추가 구조 없음"} />
      <Review label="길이" value={`${store.durationSeconds}초`} />
      <Review label="가사" value={store.lyricsText ? `${store.lyricsText.length}자` : "AI가 준비"} />
      <Review label="내 목소리" value={store.voiceProfileName || "선택 완료"} />
    </div>
    <div className="notice"><strong>마지막으로 확인해 주세요</strong><p>생성을 시작하면 완료될 때까지 이 화면을 닫아도 만든 음악에서 진행 상태를 확인할 수 있습니다.</p></div>
    {create.error && <ErrorAlert message={userErrorMessage(create.error)} />}
    <div className="actions"><Button className="secondary" onClick={() => store.setStep("voice")}>이전</Button><Button disabled={create.isPending} onClick={() => create.mutate()}>{create.isPending ? "준비 중" : "음악 만들기"}</Button></div>
  </div>;
}
function Review({ label, value }: { label: string; value: string }) { return <div className="review-item"><span>{label}</span><strong>{value}</strong></div>; }
