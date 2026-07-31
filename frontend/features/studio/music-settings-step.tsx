"use client";

import { useState } from "react";
import { Button, Field, Input, Textarea } from "@/components/ui";
import { isDeveloperInfoEnabled } from "@/lib/developer-info";
import { useStudioStore } from "@/stores/studio-store";
import {
  compileKPopPrompt,
  KPOP_PRESETS,
  withKPopCustomDirections,
} from "./kpop-presets";

const genres = ["댄스 팝", "R&B", "힙합", "신스 팝", "록", "어쿠스틱", "직접 입력"];
const moods = ["신나는", "당당한", "몽환적인", "강렬한", "감성적인", "밝은", "어두운", "세련된"];

export function MusicSettingsStep() {
  const store = useStudioStore();
  const [error, setError] = useState("");
  const custom = store.genre === "직접 입력";
  const options = store.generationOptions;
  const previewOptions = () => withKPopCustomDirections(options, [
    custom ? store.customGenre : store.genre,
    ...store.selectedMoods,
  ]);
  const toggleMood = (mood: string) => {
    if (store.selectedMoods.includes(mood)) store.patch({ selectedMoods: store.selectedMoods.filter((item) => item !== mood) });
    else if (store.selectedMoods.length < 3) store.patch({ selectedMoods: [...store.selectedMoods, mood] });
  };
  const next = () => {
    const genre = custom ? store.customGenre.trim() : store.genre;
    if (!store.prompt.trim()) return setError("어떤 노래를 만들고 싶은지 설명해 주세요.");
    try {
      compileKPopPrompt({
        presetId: store.kpopPresetId,
        userPrompt: store.prompt,
        options: previewOptions(),
      });
    } catch (compileError) {
      return setError(
        compileError instanceof Error
          ? compileError.message
          : "K-POP Prompt를 만들 수 없습니다.",
      );
    }
    store.patch({ genre });
    store.setStep("lyrics");
  };
  const preview = (() => {
    if (!store.prompt.trim()) return "노래 설명을 입력하면 실제 전송 Prompt를 미리 볼 수 있습니다.";
    try {
      return compileKPopPrompt({
        presetId: store.kpopPresetId,
        userPrompt: store.prompt,
        options: previewOptions(),
      }).prompt;
    } catch (compileError) {
      return compileError instanceof Error ? compileError.message : "Prompt Preview를 만들 수 없습니다.";
    }
  })();
  return <div className="studio-form">
    <fieldset className="choice-group"><legend>K-POP 스타일</legend><p>Preset과 고급 설정은 Provider-neutral Prompt 방향이며 실제 음원 수치를 보장하지 않습니다.</p><div className="kpop-preset-grid">{KPOP_PRESETS.map((preset) => <button key={preset.id} type="button" aria-pressed={store.kpopPresetId === preset.id} className={store.kpopPresetId === preset.id ? "selected" : ""} onClick={() => store.selectKPopPreset(preset.id)}><strong>{preset.displayName}</strong><span>{preset.description}</span></button>)}</div>{store.generationOptionsCustomized && <p className="muted" role="status">직접 바꾼 고급 설정은 스타일을 바꿔도 유지됩니다.</p>}</fieldset>
    <fieldset className="choice-group"><legend>추가 장르 방향 (선택)</legend><p>선택하면 Preset보다 우선하는 사용자 설정으로 Prompt에 반영됩니다.</p><div className="choice-chips">{genres.map((genre) => <button key={genre} type="button" aria-pressed={store.genre === genre} className={store.genre === genre ? "selected" : ""} onClick={() => store.patch({ genre: store.genre === genre ? "" : genre })}>{genre}</button>)}</div></fieldset>
    {custom && <Field label="직접 입력할 장르" htmlFor="custom-genre"><Input id="custom-genre" value={store.customGenre} onChange={(event) => store.patch({ customGenre: event.target.value })} /></Field>}
    <fieldset className="choice-group"><legend>분위기</legend><p>최대 3개까지 선택하면 곡의 방향이 더 선명해집니다.</p><div className="choice-chips">{moods.map((mood) => <button key={mood} type="button" aria-pressed={store.selectedMoods.includes(mood)} className={store.selectedMoods.includes(mood) ? "selected" : ""} onClick={() => toggleMood(mood)}>{mood}</button>)}</div></fieldset>
    <Field label="노래 설명" htmlFor="prompt" error={error || undefined}><Textarea id="prompt" rows={4} placeholder="예: 밤 무대에서 자신감 있게 춤추는 여성 솔로 댄스곡" value={store.prompt} onChange={(event) => { store.patch({ prompt: event.target.value }); setError(""); }} /></Field>
    <div className="prompt-preview" aria-live="polite"><strong>Prompt Preview</strong><pre>{preview}</pre><small>Compiler: kpop-prompt-v1 · 사용자 설명이 Preset보다 우선합니다.</small></div>
    <fieldset className="choice-group"><legend>곡 길이</legend><div className="preset-grid"><button type="button" aria-pressed={store.durationPreset === "preview"} className={store.durationPreset === "preview" ? "selected" : ""} onClick={() => store.patch({ durationPreset: "preview", durationSeconds: 30 })}><strong>30초 미리보기</strong><span>아이디어를 빠르게 확인</span></button><button type="button" aria-pressed={store.durationPreset === "verse"} className={store.durationPreset === "verse" ? "selected" : ""} onClick={() => store.patch({ durationPreset: "verse", durationSeconds: 60 })}><strong>1절 중심 · 약 1분</strong><span>가사와 후렴 흐름 확인</span></button><button type="button" disabled aria-describedby="full-song-reason"><strong>완성곡 · 약 2~3분</strong><span id="full-song-reason">안정적인 긴 곡 생성은 준비 중입니다.</span></button></div></fieldset>
    <details className="advanced-settings" open={store.advancedSettingsOpen} onToggle={(event) => store.patch({ advancedSettingsOpen: event.currentTarget.open })}><summary>K-POP 고급 설정</summary>
      <div className="generation-options-grid">
        <Field label="목표 BPM" htmlFor="requested-bpm" hint="70~180의 Prompt 목표값이며 실제 BPM을 보장하지 않습니다."><Input id="requested-bpm" type="number" min={70} max={180} value={options.requestedBpm} onChange={(event) => store.updateGenerationOptions({ requestedBpm: Number(event.target.value) })} /></Field>
        <Field label="한국어 비율 (%)" htmlFor="language-ko"><Input id="language-ko" type="number" min={0} max={100} value={options.languageRatio.ko} onChange={(event) => store.updateGenerationOptions({ languageRatio: { ko: Number(event.target.value), en: options.languageRatio.en } })} /></Field>
        <Field label="영어 비율 (%)" htmlFor="language-en" hint="두 비율의 합은 100이어야 합니다."><Input id="language-en" type="number" min={0} max={100} value={options.languageRatio.en} onChange={(event) => store.updateGenerationOptions({ languageRatio: { ko: options.languageRatio.ko, en: Number(event.target.value) } })} /></Field>
        <Field label="곡 분위기·콘셉트" htmlFor="kpop-concept" hint="40자 이내의 제작 방향입니다."><Input id="kpop-concept" maxLength={40} value={options.concept ?? ""} onChange={(event) => store.updateGenerationOptions({ concept: event.target.value })} /></Field>
        <Field label="후렴 Hook" htmlFor="hook-phrase" hint="비워 두면 별도 Hook 문구를 지정하지 않습니다."><Input id="hook-phrase" maxLength={40} value={options.hook?.phrase ?? ""} onChange={(event) => store.updateGenerationOptions({ hook: event.target.value ? { phrase: event.target.value, style: options.hook?.style ?? "title_repeat", repeatCount: options.hook?.repeatCount ?? 2 } : undefined })} /></Field>
        <Field label="Hook 방식" htmlFor="hook-style"><select id="hook-style" className="input" disabled={!options.hook} value={options.hook?.style ?? "title_repeat"} onChange={(event) => options.hook && store.updateGenerationOptions({ hook: { ...options.hook, style: event.target.value as "title_repeat" | "chant" } })}><option value="title_repeat">제목 반복</option><option value="chant">챈트</option></select></Field>
        <Field label="Hook 반복 횟수" htmlFor="hook-repeat"><Input id="hook-repeat" type="number" min={1} max={6} disabled={!options.hook} value={options.hook?.repeatCount ?? 2} onChange={(event) => options.hook && store.updateGenerationOptions({ hook: { ...options.hook, repeatCount: Number(event.target.value) } })} /></Field>
        <Field label="보컬 에너지" htmlFor="vocal-energy"><select id="vocal-energy" className="input" value={options.vocalEnergy} onChange={(event) => store.updateGenerationOptions({ vocalEnergy: event.target.value as "low" | "medium" | "high" })}><option value="low">차분하게</option><option value="medium">균형 있게</option><option value="high">강하게</option></select></Field>
      </div>
      <div className="choice-chips" aria-label="곡 구조 설정"><button type="button" aria-pressed={options.includePostChorus} className={options.includePostChorus ? "selected" : ""} onClick={() => store.updateGenerationOptions({ includePostChorus: !options.includePostChorus })}>Post-Chorus</button><button type="button" aria-pressed={options.includeDanceBreak} className={options.includeDanceBreak ? "selected" : ""} onClick={() => store.updateGenerationOptions({ includeDanceBreak: !options.includeDanceBreak })}>Dance Break</button></div>
      <Button type="button" className="secondary" onClick={() => store.resetGenerationOptions()}>현재 스타일 기본값으로 초기화</Button>
      <Field label="재현 번호" htmlFor="seed" hint="같은 번호를 사용하면 같은 입력 설정으로 다시 만들 수 있습니다. 비워두면 자동입니다."><Input id="seed" type="number" value={store.seed ?? ""} onChange={(event) => store.patch({ seed: event.target.value ? Number(event.target.value) : undefined })} /></Field>
      <div className="notice"><strong>정밀 분석 기능이 아닙니다.</strong><p>BPM·언어 비율·Hook·Dance Break는 Prompt 지시이며 실제 오디오 위치나 수치를 검출하지 않습니다.</p></div>{isDeveloperInfoEnabled() && <div className="dev-only"><strong>음악 생성 방식</strong><p>서버의 Provider-neutral Compiler를 최종 기준으로 사용합니다.</p></div>}</details>
    <Button onClick={next}>가사 준비하기</Button>
  </div>;
}
