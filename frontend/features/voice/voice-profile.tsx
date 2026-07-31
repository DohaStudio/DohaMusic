"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorAlert, Field, Input } from "@/components/ui";
import { userErrorMessage } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import type { VoiceProfileDto } from "@/types/api";

export const MAX_VOICE_FILE_BYTES = 25 * 1024 * 1024;
const VOICE_PROFILES_KEY = ["voice-profiles"] as const;

export function isDevVoicePathEnabled(
  value = process.env.NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH,
) {
  return value === "true";
}

export function validateVoiceFile(file?: File): string | undefined {
  if (!file) return "WAV 파일을 선택해 주세요.";
  if (!file.name.toLowerCase().endsWith(".wav")) return "WAV 파일만 등록할 수 있습니다.";
  if (file.size === 0) return "빈 파일은 등록할 수 없습니다.";
  if (file.size > MAX_VOICE_FILE_BYTES) return "파일은 25MB 이하여야 합니다.";
  return undefined;
}

export function useVoiceProfiles() {
  return useQuery({
    queryKey: VOICE_PROFILES_KEY,
    queryFn: dohaApi.listVoiceProfiles,
  });
}

export function VoiceProfilePanel() {
  const queryClient = useQueryClient();
  const profiles = useVoiceProfiles();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File>();
  const [consent, setConsent] = useState(false);
  const [clientError, setClientError] = useState<string>();
  const selectedId = useStudioStore((state) => state.voiceProfileId);
  const patch = useStudioStore((state) => state.patch);

  const upload = useMutation({
    mutationFn: () =>
      dohaApi.uploadVoiceProfile({
        file: file!,
        name,
        consentTextVersion: "v1",
      }),
    onSuccess: async (profile) => {
      patch({ voiceProfileId: profile.id, voiceProfileName: profile.name });
      setName("");
      setFile(undefined);
      setConsent(false);
      await queryClient.invalidateQueries({ queryKey: VOICE_PROFILES_KEY });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => dohaApi.deleteVoiceProfile(id),
    onSuccess: async (_, id) => {
      if (selectedId === id) patch({ voiceProfileId: "", voiceProfileName: undefined });
      await queryClient.invalidateQueries({ queryKey: VOICE_PROFILES_KEY });
    },
  });
  const error = upload.error || remove.error || profiles.error;

  return (
    <section className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">내 목소리</p>
        <h1>내 목소리로 노래할 준비</h1>
        <p>깨끗하게 녹음한 목소리를 등록하고 음악 만들기에 사용하세요.</p>
      </header>
      <div className="two-panel">
        <form
          className="surface-card studio-form"
          onSubmit={(event) => {
            event.preventDefault();
            const validation = validateVoiceFile(file);
            if (validation) return setClientError(validation);
            setClientError(undefined);
            upload.mutate();
          }}
        >
          <h2>새 목소리 등록</h2>
          <Field label="목소리 이름" htmlFor="voice-upload-name">
            <Input
              id="voice-upload-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </Field>
          <Field
            label="목소리 파일"
            htmlFor="voice-upload-file"
            hint="주변 소음과 음악이 없는 10~30초 WAV 녹음을 권장합니다. 최대 25MB입니다."
          >
            <input
              id="voice-upload-file"
              type="file"
              accept=".wav,audio/wav,audio/x-wav"
              onChange={(event) => {
                const next = event.target.files?.[0];
                setFile(next);
                setClientError(validateVoiceFile(next));
              }}
            />
          </Field>
          <label className="check">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            본인 음성 또는 명시적 동의를 받은 음성만 등록하며, 타인의 음성을 무단으로 사용하지 않습니다.
          </label>
          <p className="muted">
            동의 확인은 자동 신원 확인이나 본인 음성 판정을 의미하지 않습니다.
          </p>
          {clientError && <ErrorAlert message={clientError} />}
          {upload.isPending && <p role="status">파일 업로드와 음성 검증을 진행 중입니다…</p>}
          <Button disabled={!name || !file || !consent || upload.isPending}>
            {upload.isPending ? "등록 중…" : "내 목소리 등록"}
          </Button>
        </form>
        <article className="surface-card">
          <h2>등록한 목소리</h2>
          {profiles.isPending ? (
            <p role="status">목록을 불러오는 중입니다…</p>
          ) : profiles.data?.length ? (
            <div className="profile-list">
              {profiles.data.map((profile) => (
                <ProfileCard
                  key={profile.id}
                  profile={profile}
                  selected={profile.id === selectedId}
                  deleting={remove.isPending && remove.variables === profile.id}
                  onSelect={() =>
                    patch({ voiceProfileId: profile.id, voiceProfileName: profile.name })
                  }
                  onDelete={() => remove.mutate(profile.id)}
                />
              ))}
            </div>
          ) : (
            <div className="empty">
              <span>◉</span>
              <p>아직 등록한 목소리가 없습니다. 왼쪽에서 첫 목소리를 등록해 보세요.</p>
            </div>
          )}
        </article>
      </div>
      {error && (
        <ErrorAlert
          message={userErrorMessage(error)}
        />
      )}
      {isDevVoicePathEnabled() && <DevelopmentVoiceProfileForm />}
    </section>
  );
}

export function ProfileCard({
  profile,
  selected,
  deleting,
  onSelect,
  onDelete,
}: {
  profile: VoiceProfileDto;
  selected: boolean;
  deleting: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <article className={`profile-card${selected ? " selected" : ""}`}>
      <div className="avatar-wave">∿</div>
      <div>
        <strong>{profile.name}</strong>
        <p>
          {profile.duration_seconds?.toFixed(1) ?? "—"}초 · {profile.sample_rate ? `${profile.sample_rate / 1000}kHz` : "—"} · {profile.channels ? `${profile.channels}ch` : "—"}
        </p>
        <small>{profile.status}{selected ? " · 음악 만들기에 선택됨" : ""}</small>
        {profile.quality_warnings.map((warning) => (
          <small className="warning-copy" key={warning}>{warning}</small>
        ))}
      </div>
      <div className="profile-actions">
        <Button className="secondary" onClick={onSelect} disabled={selected}>선택</Button>
        <Button className="danger" onClick={onDelete} disabled={deleting}>삭제</Button>
      </div>
    </article>
  );
}

function DevelopmentVoiceProfileForm() {
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [consent, setConsent] = useState(false);
  const patch = useStudioStore((state) => state.patch);
  const create = useMutation({
    mutationFn: () => dohaApi.createVoiceProfile({ name, reference_file_path: path, consent_confirmed: true }),
    onSuccess: (profile) => patch({ voiceProfileId: profile.id, voiceProfileName: profile.name }),
  });
  return (
    <details className="surface-card dev-only">
      <summary>Development: 서버 경로로 Profile 생성</summary>
      <form className="studio-form" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
        <p className="muted">Production에서는 활성화하지 마세요.</p>
        <Field label="개발 Profile 이름" htmlFor="dev-voice-name"><Input id="dev-voice-name" value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label="서버 참조 파일 경로" htmlFor="voice-path"><Input id="voice-path" value={path} onChange={(event) => setPath(event.target.value)} /></Field>
        <label className="check"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />동의된 음성임을 확인합니다.</label>
        <Button disabled={!name || !path || !consent || create.isPending}>개발용 Profile 생성</Button>
      </form>
    </details>
  );
}
