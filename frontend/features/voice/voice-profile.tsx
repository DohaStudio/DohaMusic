"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorAlert, Field, Input, Unsupported } from "@/components/ui";
import { ApiError } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import type { VoiceProfileDto } from "@/types/api";

export function isDevVoicePathEnabled(
  value = process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH,
) {
  return value === "true";
}

export function VoiceProfilePanel() {
  const devPathEnabled = isDevVoicePathEnabled();
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [consent, setConsent] = useState(false);
  const [profile, setProfile] = useState<VoiceProfileDto>();
  const voiceProfileId = useStudioStore((state) => state.voiceProfileId);
  const patch = useStudioStore((state) => state.patch);
  const create = useMutation({
    mutationFn: () =>
      dohaApi.createVoiceProfile({
        name,
        reference_file_path: path,
        consent_confirmed: true,
      }),
    onSuccess: (value) => {
      setProfile(value);
      patch({ voiceProfileId: value.id });
    },
  });
  const remove = useMutation({
    mutationFn: () => dohaApi.deleteVoiceProfile(profile!.id),
    onSuccess: () => {
      setProfile(undefined);
      patch({ voiceProfileId: "" });
    },
  });
  const error = create.error || remove.error;

  return (
    <section className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">VOICE PROFILE</p>
        <h1>동의된 목소리만, 안전하게</h1>
        <p>
          일반 사용자는 기존 Profile UUID를 연결하며 upload·목록 API는 아직 준비
          중입니다.
        </p>
      </header>
      <div className="two-panel">
        <article className="surface-card">
          <h2>Voice 연결</h2>
          <Field label="기존 Profile UUID" htmlFor="existing-profile">
            <Input
              id="existing-profile"
              value={voiceProfileId}
              onChange={(event) =>
                patch({ voiceProfileId: event.target.value })
              }
            />
          </Field>
          <Unsupported>음성 파일 업로드</Unsupported>
          <p className="muted">
            Voice Profile list/get API가 없어 임의 목록을 표시하지 않습니다.
          </p>
        </article>
        <article className="surface-card">
          <h2>현재 Session Profile</h2>
          {profile ? (
            <div className="profile-card">
              <div className="avatar-wave">∿</div>
              <div>
                <strong>{profile.name}</strong>
                <p>{profile.id}</p>
                <small>동의 확인됨 · 이 세션에서 생성</small>
              </div>
              <Button
                className="danger"
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
              >
                삭제
              </Button>
            </div>
          ) : (
            <div className="empty">
              <span>◉</span>
              <p>현재 session에 생성된 Profile이 없습니다.</p>
            </div>
          )}
        </article>
      </div>
      {devPathEnabled && (
        <form
          className="surface-card dev-only"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <div className="alert alert-error">
            <strong>개발 전용</strong>
            <span>
              Production에서는 활성화하지 마세요. 경로는 Backend Storage의
              voices/references 아래 파일만 허용됩니다.
            </span>
          </div>
          <Field label="Profile 이름" htmlFor="voice-name">
            <Input
              id="voice-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </Field>
          <Field
            label="서버 참조 파일 경로"
            htmlFor="voice-path"
            hint="예: voices/references/my-voice.wav"
          >
            <Input
              id="voice-path"
              value={path}
              onChange={(event) => setPath(event.target.value)}
              required
            />
          </Field>
          <label className="check">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            본인 음성 또는 명시적 동의를 받은 음성임을 확인합니다.
          </label>
          {error && (
            <ErrorAlert
              message={
                error instanceof ApiError
                  ? error.message
                  : "요청에 실패했습니다."
              }
            />
          )}
          <Button disabled={!name || !path || !consent || create.isPending}>
            개발용 Profile 생성
          </Button>
        </form>
      )}
    </section>
  );
}
