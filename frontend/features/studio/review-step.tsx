"use client";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Button, ErrorAlert } from "@/components/ui";
import { ApiError } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import { toPipelineCreate } from "./studio-submit";
export function ReviewStep() {
  const router = useRouter();
  const store = useStudioStore();
  const create = useMutation({
    mutationFn: () => dohaApi.createPipeline(toPipelineCreate(store)),
    onSuccess: (job) => {
      store.patch({ pipelineJobId: job.id, currentStep: "generation" });
      router.push(`/generation/${job.id}`);
    },
  });
  return (
    <div className="studio-form">
      <div className="review-grid">
        <Review label="음악 설명" value={store.prompt} />
        <Review label="장르" value={store.genre || "미지정"} />
        <Review label="길이" value={`${store.durationSeconds}초`} />
        <Review label="Seed" value={store.seed?.toString() ?? "자동"} />
        <Review
          label="가사"
          value={
            store.lyricsText ? `${store.lyricsText.length}자` : "가사 없음"
          }
        />
        <Review label="Voice Profile" value={store.voiceProfileId} />
      </div>
      <div className="notice">
        <strong>생성 전에 확인해 주세요</strong>
        <p>취소 API는 아직 지원되지 않습니다.</p>
      </div>
      {create.error && (
        <ErrorAlert
          message={
            create.error instanceof ApiError
              ? create.error.message
              : "생성 요청에 실패했습니다."
          }
        />
      )}
      <div className="actions">
        <Button className="secondary" onClick={() => store.setStep("voice")}>
          이전
        </Button>
        <Button disabled={create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? "요청 중…" : "음악 생성 시작"}
        </Button>
      </div>
    </div>
  );
}
function Review({ label, value }: { label: string; value: string }) {
  return (
    <div className="review-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
