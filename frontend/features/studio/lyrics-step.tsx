"use client";

import { useMutation } from "@tanstack/react-query";
import { Button, ErrorAlert, Field, Textarea } from "@/components/ui";
import { userErrorMessage } from "@/services/api-client";
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
      <div className="segmented" aria-label="가사 준비 방법">
        <button type="button" aria-pressed={store.lyricsMode === "generate"} className={store.lyricsMode === "generate" ? "active" : ""} onClick={() => store.patch({ lyricsMode: "generate" })}>AI가 만들어주기</button>
        <button type="button" aria-pressed={store.lyricsMode === "write"} className={store.lyricsMode === "write" ? "active" : ""} onClick={() => store.patch({ lyricsMode: "write" })}>직접 쓰기</button>
      </div>
      {store.lyricsMode === "generate" && <p className="notice">노래 설명을 바탕으로 가사를 함께 준비합니다. 원하는 문장이 있다면 아래에 적어 주세요.</p>}
      <Field label="가사" htmlFor="studio-lyrics" hint="비워 두면 노래 설명을 바탕으로 가사를 준비합니다.">
        <Textarea id="studio-lyrics" rows={13} placeholder="[Verse]\n오늘 밤 우리는..." value={store.lyricsText} onChange={(event) => store.patch({ lyricsText: event.target.value, lyricsValidation: undefined })} />
      </Field>
      {store.lyricsValidation && <p className={store.lyricsValidation.valid ? "validation-good" : "validation-bad"} role="status">{store.lyricsValidation.valid ? "가사 구성을 확인했습니다." : `다듬어야 할 부분이 ${store.lyricsValidation.errors.length}개 있습니다.`}</p>}
      {validate.error && <ErrorAlert message={userErrorMessage(validate.error)} />}
      <div className="actions">
        <Button className="secondary" onClick={() => store.setStep("settings")}>이전</Button>
        <Button className="secondary" disabled={!store.lyricsText || validate.isPending} aria-describedby={!store.lyricsText ? "lyrics-check-reason" : undefined} onClick={() => validate.mutate()}>{validate.isPending ? "확인 중" : "작성 내용 확인"}</Button>
        <Button onClick={() => store.setStep("voice")}>내 목소리 선택</Button>
      </div>
      {!store.lyricsText && <p id="lyrics-check-reason" className="disabled-reason">가사를 입력하면 작성 내용을 확인할 수 있습니다.</p>}
    </div>
  );
}
