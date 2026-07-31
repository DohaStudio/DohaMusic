# K-POP Generation Options 계약

> 문서 상태: [완료]
> 최종 수정일: 2026-08-01
> 관련 기능: K-POP Preset·Generation Options
> 관련 문서: [제품 정의](../02-product/kpop-creation-product-definition.md), [Prompt Compiler](kpop-prompt-compiler.md), [Capability Matrix](../04-models/kpop-provider-capability-matrix.md)

## 현재 계약과 확장 경계

현재 `PipelineCreate`는 기존 필드에 optional `generation_options`를 추가해 하위 호환을 유지한다. 중첩 `KPopGenerationOptions`, `LanguageRatio`, `HookOptions`는 알 수 없는 필드를 거부하고 Backend가 최종 검증·컴파일 권위가 된다.

`generation_options`가 없으면 기존 요청과 동일하게 동작한다. 값이 있으면 `preset_id`의 canonical genre와 기존 `genre`가 일치해야 하며 불일치는 `PRESET_GENRE_MISMATCH`로 거부한다. Preset이 genre를 조용히 덮어쓰지 않는다.

```json
{
  "prompt": "bright summer night",
  "lyrics": "[Verse 1]...",
  "genre": "kpop_dance",
  "duration_seconds": 60,
  "seed": 1042,
  "generation_options": {
    "preset_id": "kpop_dance",
    "requested_bpm": 124,
    "language_ratio": { "ko": 70, "en": 30 },
    "hook": {
      "phrase": "Play My Heart",
      "style": "title_repeat",
      "repeat_count": 3
    },
    "include_post_chorus": true,
    "include_dance_break": false,
    "vocal_energy": "medium",
    "concept": "confident_bright"
  }
}
```

## 지원 상태

- `DIRECT_PROVIDER_PARAMETER`: Provider의 검증된 직접 파라미터
- `PROMPT_COMPILED`: Compiler가 자연어 Prompt로 변환
- `METADATA_ONLY`: 추적·평가용으로만 저장하며 생성 제어를 주장하지 않음
- `NOT_SUPPORTED`: 받거나 활성화하지 않음

## Preset

| ID | 표시 이름 | 목표 경험 | 기본 장르·분위기 | BPM 목표 | 에너지 | 보컬·Hook | Post-Chorus / Dance Break | 현재 상태 |
|---|---|---|---|---:|---|---|---|---|
| `kpop_dance` | K-POP Dance | 밝고 춤추기 쉬운 상업 Pop | dance pop, bright·confident | 120~128 | medium~high | 선명한 여성 보컬, 짧은 제목 반복 | 권장 / 선택 | [완료], Prompt Compiler |
| `kpop_easy_listening` | K-POP Easy Listening | 편안하고 반복 청취 가능한 Pop | soft pop, warm·fresh | 100~120 | low~medium | 자연스러운 여성 보컬, 부드러운 Hook | 선택 / 미지원 | [완료], Prompt Compiler |
| `kpop_performance` | K-POP Performance | 무대 대비와 강한 퍼포먼스 | performance pop, bold·intense | 120~140 | high | chant Hook, 강한 Chorus | 선택 / 선택 | [완료], Prompt Compiler |

향후 후보는 K-POP R&B, K-POP Pop Rock, Custom이다. Provider에 Preset을 직접 전달하지 않고 Compiler가 반영한다.

## 필드 계약

| 필드 | 필수 | 기본값 | 허용값·검증 | 현재 상태 | Compiler 반영 | Public DTO | Snapshot |
|---|---|---|---|---|---|---|---|
| `preset_id` | 예 | 없음 | 위 3개 allowlist | PROMPT_COMPILED | Preset 문장 | 예 | 예 |
| `requested_bpm` | 아니오 | Preset 범위 중앙값 | 정수 70~180 | PROMPT_COMPILED | `Target tempo around N BPM` | 예 | 예 |
| `language_ratio` | 아니오 | Preset별 목표값 | `ko+en=100`, 각 0~100 | PROMPT_COMPILED | Lyrics 지시 | 예 | 예 |
| `hook.phrase` | 아니오 | 없음 | trim 후 1~40자 | PROMPT_COMPILED | Lyrics·Music Hook 지시 | 예 | 예 |
| `hook.style` | 아니오 | `title_repeat` | 초기 `title_repeat`, `chant` | PROMPT_COMPILED | Hook 문장 | 예 | 예 |
| `hook.repeat_count` | 아니오 | 2 | 정수 1~6 | PROMPT_COMPILED | 반복 목표 | 예 | 예 |
| `include_post_chorus` | 아니오 | Preset값 | boolean | PROMPT_COMPILED | 구조 문장 | 예 | 예 |
| `include_dance_break` | 아니오 | Preset값 | boolean | PROMPT_COMPILED | 구조 문장 | 예 | 예 |
| `vocal_energy` | 아니오 | Preset값 | `low`, `medium`, `high` | PROMPT_COMPILED | 보컬 에너지 문장 | 예 | 예 |
| `concept` | 아니오 | Preset값 | trim 후 최대 40자, 제어문자 금지, 빈 문자열은 `null` | PROMPT_COMPILED | Mood·Concept 문장 | 예 | 예 |

`language_ratio`는 Lyrics Prompt의 목표 비율이며 정확한 문자·음절 비율을 보장하지 않는다. 생성 후 검증은 후속 단계다.

## 우선순위와 Snapshot

충돌 시 `사용자 명시 Prompt > 사용자 Custom 옵션 > Preset 기본값 > 시스템 기본값` 순서다. 충돌을 삭제하지 않고 최종 Prompt Preview와 compile warning에 남긴다.

기존 JSON `input_snapshot`에 원본 `prompt`·`generation_options`, `compiled_prompt`, `normalized_generation_options`, `compiler_version`, `compiler_warnings`를 저장한다. 별도 DB 컬럼이나 Migration은 없다. Retry는 원본 Prompt와 옵션을 다시 검증·컴파일해 새 Job을 만들며 구형 Snapshot은 기존 경로로 처리한다.

공개 Job·History·Project·Result metadata는 검증된 `generation_options`와 `kpop_prompt_compiler_version`만 allowlist로 반환한다. 내부 Snapshot 전체, compiled prompt, PID·절대 경로·API Key·Provider secret은 공개하지 않는다. `detected_bpm`은 K2 Generation Options가 아니라 별도 K3.2 `audio_analysis.tempo` 공개 DTO로 제공하며 Hook timestamp는 아직 없다.

K3.0은 `requested_bpm` 같은 Prompt 목표와 최종 WAV 측정·추정을 별도 계약으로 분리했다. K3.1 Quality Metrics와 K3.2 Tempo는 완료됐으며 Hook/Chorus·Preview는 K3.3~K3.4 계획이다. 세부 의미와 신뢰도는 [K3 Audio Analysis 제품 정의](../02-product/k3-audio-analysis-product-definition.md)를 따른다.
