"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import {
  Button,
  ErrorAlert,
  Field,
  Input,
  Textarea,
  Unsupported,
} from "@/components/ui";
import { StepIndicator } from "@/components/step-indicator";
import { ApiError } from "@/services/api-client";

const settingsSchema = z.object({
  prompt: z.string().min(1, "곡의 설명을 입력해 주세요.").max(4000),
  genre: z.string().max(100),
  durationSeconds: z.number().int().min(1).max(600),
  seed: z
    .union([z.number().int().min(0).max(2147483647), z.literal("")])
    .optional(),
});
type Settings = z.infer<typeof settingsSchema>;

export function StudioWorkspace() {
  const draft = useStudioStore();
  return (
    <section className="workspace-card">
      <StepIndicator current={draft.currentStep} />
      <div className="workspace-title">
        <p className="eyebrow">NEW PROJECT</p>
        <h1>{titleFor(draft.currentStep)}</h1>
        <span>{subtitleFor(draft.currentStep)}</span>
      </div>
      {draft.currentStep === "settings" && <SettingsStep />}
      {draft.currentStep === "lyrics" && <LyricsStep />}
      {draft.currentStep === "voice" && <VoiceStep />}
      {draft.currentStep === "review" && <ReviewStep />}
    </section>
  );
}
function SettingsStep() {
  const store = useStudioStore();
  const form = useForm<Settings>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      prompt: store.prompt,
      genre: store.genre,
      durationSeconds: store.durationSeconds,
      seed: store.seed,
    },
  });
  const submit = (value: Settings) => {
    store.patch({
      prompt: value.prompt,
      genre: value.genre,
      durationSeconds: value.durationSeconds,
      seed: value.seed === "" ? undefined : value.seed,
    });
    store.setStep("lyrics");
  };
  return (
    <form onSubmit={form.handleSubmit(submit)} className="studio-form">
      <Field
        label="음악 설명"
        htmlFor="prompt"
        error={form.formState.errors.prompt?.message}
      >
        <Textarea
          id="prompt"
          rows={5}
          placeholder="새벽 도시를 걷는 따뜻한 R&B 곡"
          {...form.register("prompt")}
        />
      </Field>
      <div className="form-grid">
        <Field label="장르" htmlFor="genre">
          <Input id="genre" {...form.register("genre")} />
        </Field>
        <Field label="길이 (초)" htmlFor="duration">
          <Input
            id="duration"
            type="number"
            {...form.register("durationSeconds", { valueAsNumber: true })}
          />
        </Field>
        <Field label="Seed (선택)" htmlFor="seed">
          <Input
            id="seed"
            type="number"
            {...form.register("seed", {
              setValueAs: (value) => (value === "" ? "" : Number(value)),
            })}
          />
        </Field>
      </div>
      <div className="feature-disabled">
        <Unsupported>BPM</Unsupported>
        <Unsupported>Model 선택</Unsupported>
        <Unsupported>고급 믹싱</Unsupported>
      </div>
      <Button type="submit">가사 단계로</Button>
    </form>
  );
}
function LyricsStep() {
  const store = useStudioStore();
  const validate = useMutation({
    mutationFn: () => dohaApi.validateLyrics(store.lyricsText),
    onSuccess: (lyricsValidation) => store.patch({ lyricsValidation }),
  });
  return (
    <div className="studio-form">
      <div className="segmented">
        <button
          className={store.lyricsMode === "generate" ? "active" : ""}
          onClick={() => store.patch({ lyricsMode: "generate" })}
        >
          AI 가사 사용
        </button>
        <button
          className={store.lyricsMode === "write" ? "active" : ""}
          onClick={() => store.patch({ lyricsMode: "write" })}
        >
          직접 작성
        </button>
      </div>
      <Field
        label="가사"
        htmlFor="studio-lyrics"
        hint="비워두면 Pipeline이 음악 설명만 사용합니다."
      >
        <Textarea
          id="studio-lyrics"
          rows={13}
          value={store.lyricsText}
          onChange={(e) => store.patch({ lyricsText: e.target.value })}
          placeholder="[Verse]\n가사를 입력하거나 Lyrics Lab에서 생성하세요."
        />
      </Field>
      {store.lyricsValidation && (
        <p
          className={
            store.lyricsValidation.valid ? "validation-good" : "validation-bad"
          }
        >
          {store.lyricsValidation.valid
            ? "검증을 통과했습니다."
            : `오류 ${store.lyricsValidation.errors.length}건을 확인해 주세요.`}
        </p>
      )}
      <div className="actions">
        <Button className="secondary" onClick={() => store.setStep("settings")}>
          이전
        </Button>
        <Button
          className="secondary"
          disabled={!store.lyricsText || validate.isPending}
          onClick={() => validate.mutate()}
        >
          {validate.isPending ? "검증 중" : "가사 검증"}
        </Button>
        <Button onClick={() => store.setStep("voice")}>목소리 선택</Button>
      </div>
    </div>
  );
}
function VoiceStep() {
  const store = useStudioStore();
  const valid = /^[0-9a-fA-F-]{36}$/.test(store.voiceProfileId);
  return (
    <div className="studio-form">
      <div className="notice">
        <strong>현재 Voice API 범위</strong>
        <p>
          목록 조회와 파일 업로드 API는 아직 없습니다. 이 세션에서 생성한
          Profile 또는 기존 UUID를 입력하세요.
        </p>
      </div>
      <Field label="Voice Profile UUID" htmlFor="voice-id" hint="36자 UUID">
        <Input
          id="voice-id"
          value={store.voiceProfileId}
          onChange={(e) => store.patch({ voiceProfileId: e.target.value })}
          placeholder="00000000-0000-0000-0000-000000000000"
        />
      </Field>
      <Unsupported>음성 파일 업로드</Unsupported>
      <div className="actions">
        <Button className="secondary" onClick={() => store.setStep("lyrics")}>
          이전
        </Button>
        <Button disabled={!valid} onClick={() => store.setStep("review")}>
          생성 확인
        </Button>
      </div>
    </div>
  );
}
function ReviewStep() {
  const router = useRouter();
  const store = useStudioStore();
  const create = useMutation({
    mutationFn: () =>
      dohaApi.createPipeline({
        prompt: store.prompt,
        lyrics: store.lyricsText || undefined,
        genre: store.genre || undefined,
        duration_seconds: store.durationSeconds,
        seed: store.seed,
        voice_profile_id: store.voiceProfileId,
      }),
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
        <p>
          생성 요청은 비동기 Pipeline Job을 만듭니다. 취소 API는 아직 지원되지
          않습니다.
        </p>
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
function titleFor(step: string) {
  return (
    (
      {
        settings: "어떤 음악을 만들까요?",
        lyrics: "이야기에 가사를 입혀요",
        voice: "노래할 목소리를 연결해요",
        review: "생성 설정을 확인해요",
      } as Record<string, string>
    )[step] ?? "Doha Studio"
  );
}
function subtitleFor(step: string) {
  return (
    (
      {
        settings: "지원되는 Pipeline 필드만으로 첫 곡을 설계합니다.",
        lyrics: "직접 쓰거나 Lyrics Lab 결과를 이어서 사용하세요.",
        voice: "동의된 Voice Profile만 사용할 수 있습니다.",
        review: "확인 후 하나의 추적 가능한 Job으로 생성합니다.",
      } as Record<string, string>
    )[step] ?? ""
  );
}
