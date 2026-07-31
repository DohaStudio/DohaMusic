"use client";
import { useMutation } from "@tanstack/react-query";
import { Button, Field, Textarea } from "@/components/ui";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
export function LyricsStep() {
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
          onChange={(event) => store.patch({ lyricsText: event.target.value })}
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
          가사 검증
        </Button>
        <Button onClick={() => store.setStep("voice")}>목소리 선택</Button>
      </div>
    </div>
  );
}
