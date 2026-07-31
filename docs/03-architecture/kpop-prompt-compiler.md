# KPopPromptCompiler 설계

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 기능: Provider-neutral K-POP Prompt 컴파일
> 관련 문서: [Generation Options](kpop-generation-options.md), [Music Adapter](../04-models/music-generation-adapter.md), [ADR-022](../11-decisions/ADR-022-kpop-generation-control-layer.md)

## 목적과 경계

`KPopPromptCompiler`는 Frontend 선택값과 `KPopGenerationOptions`를 검증된 Provider-neutral Prompt로 변환한다. Frontend나 Provider Adapter가 독자적으로 Prompt를 조립하지 않는다. 현재 구현은 없으며 K1의 대상이다.

```text
Frontend 선택값
→ KPopGenerationOptions validation
→ KPopPromptCompiler
→ Provider-neutral Prompt + warning + compiler_version
→ MusicGenerator
```

## 컴파일 순서

1. Preset 기본값 적용
2. Mood·Concept·Genre 정규화
3. 사용자 Custom 옵션 적용
4. 사용자 명시 Prompt를 최우선으로 병합
5. BPM·Hook·구조·보컬 에너지 문장 생성
6. 금지 요구와 특정 아티스트 모방 지시 차단
7. 중복 문장·상충 표현을 정리하고 길이 제한 적용
8. 최종 Prompt Preview, warning, compiler version 저장

Prompt 최대 길이는 구현 시 현재 Provider 제한을 확인해 확정한다. 초안 정책은 1,500자로 제한하고 잘라내기보다 validation error를 우선한다. Provider별 전용 문구는 Adapter 내부의 검증된 최소 변환으로만 허용한다.

## 충돌 처리

`Preset=bright`인데 사용자 Prompt가 `dark aggressive`라면 사용자 Prompt를 우선한다. Compiler는 `preset_mood_overridden` warning을 반환하고 Preview에 실제 적용된 방향을 보여준다. 위험·권리 침해·금지 콘텐츠는 우선순위와 무관하게 거부한다.

## 출력 예시

### K-POP Dance

```text
Modern Korean female dance pop with punchy electronic drums, deep synth bass and bright polished synth layers. Use a rhythmic verse, rising pre-chorus, short repeated title hook and energetic chorus. Target tempo around 124 BPM. Use clear Korean pronunciation with a short English hook.
```

### K-POP Easy Listening

```text
Soft modern Korean pop with a light UK garage rhythm, warm synths and restrained drums. Use a close, natural female vocal, a comfortable repeated chorus and a smooth structure.
```

### K-POP Performance

```text
High-energy Korean performance pop with hip-hop drums, electronic bass and a low rhythmic verse. Build through a rising pre-chorus into a chant-style hook and powerful chorus, with optional dance-break contrast.
```

어떤 예시도 특정 아티스트·곡·고유 창법을 모방하도록 작성하지 않는다.

## K-POP Lyrics Template

```text
[Intro]
[Verse 1]
[Pre-Chorus]
[Chorus]
[Post-Chorus]
[Verse 2]
[Pre-Chorus]
[Chorus]
[Bridge]
[Final Chorus]
```

- Verse는 한국어 중심의 서사, Pre-Chorus는 상승과 전환을 담당한다.
- Chorus에는 제목 또는 핵심 Hook을 두고 2~4회 반복하되 한 줄을 짧게 유지한다.
- Post-Chorus는 짧은 반복 음절·영어를 허용하되 과도한 무의미 반복을 피한다.
- Bridge는 반복을 줄이고 감정·리듬 대비를 만든다.
- Final Chorus는 기존 Hook을 유지하면서 제한적으로 변주한다.
- 혐오·차별·노골적 성적 표현과 특정 아티스트 문체 모방을 금지한다.
- 영어 비율은 목표값이며 자동 강제나 정확한 비율 보장은 후속 검증 대상이다.
