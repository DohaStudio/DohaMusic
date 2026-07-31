"use client";

import Link from "next/link";
import { Button, ErrorAlert, Field, Input } from "@/components/ui";
import { isDevVoicePathEnabled, useVoiceProfiles } from "@/features/voice/voice-profile";
import { userErrorMessage } from "@/services/api-client";
import { useStudioStore } from "@/stores/studio-store";

export function VoiceStep() {
  const store = useStudioStore();
  const profiles = useVoiceProfiles();
  const selected = profiles.data?.find((profile) => profile.id === store.voiceProfileId);
  const valid = Boolean(selected) || (isDevVoicePathEnabled() && /^[0-9a-fA-F-]{36}$/.test(store.voiceProfileId));
  return <div className="studio-form">
    <div className="notice"><strong>내 목소리로 노래하기</strong><p>본인 목소리 또는 사용 허락을 받은 목소리만 선택해 주세요.</p></div>
    {profiles.isPending ? <p role="status">등록한 목소리를 불러오는 중입니다.</p> : profiles.error ? <ErrorAlert message={userErrorMessage(profiles.error)} /> : profiles.data?.length ? <div className="voice-choice-list" role="radiogroup" aria-label="등록한 목소리">{profiles.data.map((profile) => <button className={`voice-choice${profile.id === store.voiceProfileId ? " selected" : ""}`} key={profile.id} type="button" role="radio" aria-checked={profile.id === store.voiceProfileId} onClick={() => store.patch({ voiceProfileId: profile.id, voiceProfileName: profile.name })}><strong>{profile.name}</strong><span>{profile.duration_seconds?.toFixed(1) ?? "-"}초 · 사용 가능</span></button>)}</div> : <div className="empty"><p>아직 등록한 목소리가 없습니다.</p><Link className="button" href="/voice">내 목소리 등록하기</Link></div>}
    {selected && <p className="success-copy">선택한 목소리: {selected.name}</p>}
    {isDevVoicePathEnabled() && <details className="dev-only"><summary>개발자 정보: 목소리 식별자 입력</summary><Field label="목소리 식별자" htmlFor="voice-id"><Input id="voice-id" value={store.voiceProfileId} onChange={(event) => store.patch({ voiceProfileId: event.target.value, voiceProfileName: undefined })} /></Field></details>}
    <div className="actions"><Button className="secondary" onClick={() => store.setStep("lyrics")}>이전</Button><Button disabled={!valid} aria-describedby={!valid ? "voice-next-reason" : undefined} onClick={() => store.setStep("review")}>최종 확인</Button></div>
    {!valid && <p id="voice-next-reason" className="disabled-reason">사용할 목소리를 선택하면 다음 단계로 이동할 수 있습니다.</p>}
  </div>;
}
