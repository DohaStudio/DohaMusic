"use client";

import { useState } from "react";
import { Button, Field, Input, Textarea } from "@/components/ui";
import { isDeveloperInfoEnabled } from "@/lib/developer-info";
import { useStudioStore } from "@/stores/studio-store";

const genres = ["댄스 팝", "발라드", "R&B", "힙합", "신스 팝", "록", "어쿠스틱", "직접 입력"];
const moods = ["신나는", "당당한", "몽환적인", "강렬한", "감성적인", "밝은", "어두운", "세련된"];

export function MusicSettingsStep() {
  const store = useStudioStore();
  const [error, setError] = useState("");
  const custom = store.genre === "직접 입력";
  const toggleMood = (mood: string) => {
    if (store.selectedMoods.includes(mood)) store.patch({ selectedMoods: store.selectedMoods.filter((item) => item !== mood) });
    else if (store.selectedMoods.length < 3) store.patch({ selectedMoods: [...store.selectedMoods, mood] });
  };
  const next = () => {
    const genre = custom ? store.customGenre.trim() : store.genre;
    if (!genre) return setError("장르를 선택하거나 직접 입력해 주세요.");
    if (!store.prompt.trim()) return setError("어떤 노래를 만들고 싶은지 설명해 주세요.");
    store.patch({ genre });
    store.setStep("lyrics");
  };
  return <div className="studio-form">
    <fieldset className="choice-group"><legend>장르</legend><p>DohaMusic의 대표 추천은 댄스 팝입니다.</p><div className="choice-chips">{genres.map((genre) => <button key={genre} type="button" aria-pressed={store.genre === genre} className={store.genre === genre ? "selected" : ""} onClick={() => store.patch({ genre })}>{genre === "댄스 팝" ? "추천 · 댄스 팝" : genre}</button>)}</div></fieldset>
    {custom && <Field label="직접 입력할 장르" htmlFor="custom-genre"><Input id="custom-genre" value={store.customGenre} onChange={(event) => store.patch({ customGenre: event.target.value })} /></Field>}
    <fieldset className="choice-group"><legend>분위기</legend><p>최대 3개까지 선택하면 곡의 방향이 더 선명해집니다.</p><div className="choice-chips">{moods.map((mood) => <button key={mood} type="button" aria-pressed={store.selectedMoods.includes(mood)} className={store.selectedMoods.includes(mood) ? "selected" : ""} onClick={() => toggleMood(mood)}>{mood}</button>)}</div></fieldset>
    <Field label="노래 설명" htmlFor="prompt" error={error || undefined}><Textarea id="prompt" rows={4} placeholder="예: 밤 무대에서 자신감 있게 춤추는 여성 솔로 댄스곡" value={store.prompt} onChange={(event) => { store.patch({ prompt: event.target.value }); setError(""); }} /></Field>
    <fieldset className="choice-group"><legend>곡 길이</legend><div className="preset-grid"><button type="button" aria-pressed={store.durationPreset === "preview"} className={store.durationPreset === "preview" ? "selected" : ""} onClick={() => store.patch({ durationPreset: "preview", durationSeconds: 30 })}><strong>30초 미리보기</strong><span>아이디어를 빠르게 확인</span></button><button type="button" aria-pressed={store.durationPreset === "verse"} className={store.durationPreset === "verse" ? "selected" : ""} onClick={() => store.patch({ durationPreset: "verse", durationSeconds: 60 })}><strong>1절 중심 · 약 1분</strong><span>가사와 후렴 흐름 확인</span></button><button type="button" disabled aria-describedby="full-song-reason"><strong>완성곡 · 약 2~3분</strong><span id="full-song-reason">안정적인 긴 곡 생성은 준비 중입니다.</span></button></div></fieldset>
    <details className="advanced-settings" open={store.advancedSettingsOpen} onToggle={(event) => store.patch({ advancedSettingsOpen: event.currentTarget.open })}><summary>고급 설정</summary><Field label="재현 번호" htmlFor="seed" hint="같은 번호를 사용하면 비슷한 조건으로 다시 만들 수 있습니다. 비워두면 자동입니다."><Input id="seed" type="number" value={store.seed ?? ""} onChange={(event) => store.patch({ seed: event.target.value ? Number(event.target.value) : undefined })} /></Field><div className="notice"><strong>세부 템포 설정은 준비 중입니다.</strong><p>댄스 팝은 빠르게 · 약 120~128 BPM을 권장하지만 현재 요청에는 가짜 BPM 값을 전송하지 않습니다.</p></div>{isDeveloperInfoEnabled() && <div className="dev-only"><strong>음악 생성 방식</strong><p>서버 설정을 사용합니다.</p></div>}</details>
    <Button onClick={next}>가사 준비하기</Button>
  </div>;
}
