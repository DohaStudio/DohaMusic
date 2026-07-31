"use client";

import Link from "next/link";
import { Button, ErrorAlert, Field, Input } from "@/components/ui";
import {
  isDevVoicePathEnabled,
  useVoiceProfiles,
} from "@/features/voice/voice-profile";
import { ApiError } from "@/services/api-client";
import { useStudioStore } from "@/stores/studio-store";

export function VoiceStep() {
  const store = useStudioStore();
  const profiles = useVoiceProfiles();
  const selected = profiles.data?.find(
    (profile) => profile.id === store.voiceProfileId,
  );
  const valid = Boolean(selected) || (
    isDevVoicePathEnabled() && /^[0-9a-fA-F-]{36}$/.test(store.voiceProfileId)
  );

  return (
    <div className="studio-form">
      <div className="notice">
        <strong>동의된 Voice Profile 선택</strong>
        <p>본인 음성 또는 명시적으로 사용 허가를 받은 음성만 선택하세요.</p>
      </div>
      {profiles.isPending ? (
        <p role="status">Voice Profile을 불러오는 중입니다…</p>
      ) : profiles.error ? (
        <ErrorAlert
          message={
            profiles.error instanceof ApiError
              ? profiles.error.message
              : "Voice Profile 목록을 불러오지 못했습니다."
          }
        />
      ) : profiles.data?.length ? (
        <div className="voice-choice-list" role="radiogroup" aria-label="Voice Profile">
          {profiles.data.map((profile) => (
            <button
              className={`voice-choice${profile.id === store.voiceProfileId ? " selected" : ""}`}
              key={profile.id}
              type="button"
              role="radio"
              aria-checked={profile.id === store.voiceProfileId}
              onClick={() =>
                store.patch({
                  voiceProfileId: profile.id,
                  voiceProfileName: profile.name,
                })
              }
            >
              <strong>{profile.name}</strong>
              <span>
                {profile.duration_seconds?.toFixed(1) ?? "—"}초 · {profile.status}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className="empty">
          <p>등록된 목소리가 없습니다.</p>
          <Link className="button" href="/voice">새 Voice Profile 업로드</Link>
        </div>
      )}
      {selected && <p className="success-copy">선택됨: {selected.name}</p>}
      {isDevVoicePathEnabled() && (
        <details className="dev-only">
          <summary>Development: Profile UUID 직접 입력</summary>
          <Field label="Voice Profile UUID" htmlFor="voice-id">
            <Input
              id="voice-id"
              value={store.voiceProfileId}
              onChange={(event) =>
                store.patch({ voiceProfileId: event.target.value, voiceProfileName: undefined })
              }
            />
          </Field>
        </details>
      )}
      <div className="actions">
        <Button className="secondary" onClick={() => store.setStep("lyrics")}>이전</Button>
        <Button disabled={!valid} onClick={() => store.setStep("review")}>생성 확인</Button>
      </div>
    </div>
  );
}
