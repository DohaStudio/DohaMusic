"use client";
import { Button, Field, Input, Unsupported } from "@/components/ui";
import { useStudioStore } from "@/stores/studio-store";
export function VoiceStep() {
  const store = useStudioStore();
  const valid = /^[0-9a-fA-F-]{36}$/.test(store.voiceProfileId);
  return (
    <div className="studio-form">
      <div className="notice">
        <strong>현재 Voice API 범위</strong>
        <p>
          목록 조회와 파일 업로드 API는 아직 없습니다. 기존 UUID를 입력하세요.
        </p>
      </div>
      <Field label="Voice Profile UUID" htmlFor="voice-id">
        <Input
          id="voice-id"
          value={store.voiceProfileId}
          onChange={(event) =>
            store.patch({ voiceProfileId: event.target.value })
          }
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
