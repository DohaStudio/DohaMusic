# K-POP Generation Options 계약

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 기능: K-POP Preset·Generation Options
> 관련 문서: [제품 정의](../02-product/kpop-creation-product-definition.md), [Prompt Compiler](kpop-prompt-compiler.md), [Capability Matrix](../04-models/kpop-provider-capability-matrix.md)

## 현재 계약과 확장 경계

현재 `PipelineCreate`는 `prompt`, `lyrics`, `genre`, `duration_seconds`, `seed`, `voice_profile_id`, `project_id`만 검증하며 `input_snapshot`은 이 DTO를 그대로 저장한다. K1 Frontend는 Preset을 컴파일한 `prompt`와 `genre`만 이 계약으로 전송한다. `generation_options`는 아직 API·DB·Frontend에 구현되지 않았다.

향후 확장은 기존 필드를 유지하고 optional `generation_options`를 추가한다. 기존 요청은 동일하게 동작해야 하며 알 수 없는 옵션을 조용히 무시하지 않는다. 구현 전에는 해당 필드를 받지 않고, 구현 후에는 명시적 validation error 또는 capability 비활성화로 처리한다.

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
| `kpop_dance` | K-POP Dance | 밝고 춤추기 쉬운 상업 Pop | dance pop, bright·confident | 120~128 | medium~high | 선명한 여성 보컬, 짧은 제목 반복 | 권장 / 선택 | [진행 중], Prompt Compiler |
| `kpop_easy_listening` | K-POP Easy Listening | 편안하고 반복 청취 가능한 Pop | soft pop, warm·fresh | 100~120 | low~medium | 자연스러운 여성 보컬, 부드러운 Hook | 선택 / 미지원 | [진행 중], Prompt Compiler |
| `kpop_performance` | K-POP Performance | 무대 대비와 강한 퍼포먼스 | performance pop, bold·intense | 120~140 | high | chant Hook, 강한 Chorus | 선택 / 선택 | [진행 중], Prompt Compiler |

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
| `hook.target_seconds` | 아니오 | 없음 | 3~15초, 목표값일 뿐 길이 보장 안 함 | METADATA_ONLY | Preview 설계 목표 | 예 | 예 |
| `hook.language` | 아니오 | `mixed` | `ko`, `en`, `mixed` | PROMPT_COMPILED | Lyrics 지시 | 예 | 예 |
| `hook.section` | 아니오 | `chorus` | `chorus`, `post_chorus` | PROMPT_COMPILED | 구조 지시 | 예 | 예 |
| `include_post_chorus` | 아니오 | Preset값 | boolean | PROMPT_COMPILED | 구조 문장 | 예 | 예 |
| `include_dance_break` | 아니오 | false | boolean | `NOT_SUPPORTED`에서 시작 | Capability 지원 후에만 | 예 | 예 |
| `vocal_energy` | 아니오 | Preset값 | `low`, `medium`, `high` | PROMPT_COMPILED | 보컬 에너지 문장 | 예 | 예 |
| `concept` | 아니오 | Preset값 | allowlist 또는 trim 후 1~40자 | PROMPT_COMPILED | Mood·Concept 문장 | 예 | 예 |

`language_ratio`는 Lyrics Prompt의 목표 비율이며 정확한 문자·음절 비율을 보장하지 않는다. 생성 후 검증은 후속 단계다.

## 우선순위와 Snapshot

충돌 시 `사용자 명시 Prompt > 사용자 Custom 옵션 > Preset 기본값 > 시스템 기본값` 순서다. 충돌을 삭제하지 않고 최종 Prompt Preview와 compile warning에 남긴다.

Snapshot에는 원본 `generation_options`, 정규화된 옵션, `compiler_version`, 최종 Provider-neutral Prompt, warning을 저장한다. 내부 PID·절대 경로·비밀 옵션·Provider secret은 Public DTO나 Snapshot에 넣지 않는다.
