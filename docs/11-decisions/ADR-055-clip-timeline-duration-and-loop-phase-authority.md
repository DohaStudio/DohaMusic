# ADR-055: Clip Timeline Duration and Loop Phase Authority

> 상태: 승인
> 작성일: 2026-09-05
> 최종 수정일: 2026-09-05
> 관련 기능: AI-native DAW D3 Clip Loop geometry foundation
> 관련 문서: [ADR-040](ADR-040-canonical-track-clip-working-composition-authority.md), [ADR-050](ADR-050-working-composition-inverse-mutation-authority.md), [ADR-052](ADR-052-working-composition-preview-render-authority.md), [ADR-053](ADR-053-clip-gain-authority.md), [ADR-054](ADR-054-clip-fade-authority.md)

## Context

현재 Clip은 `timeline_start`, `source_in`, `source_out`, `source_duration`을 저장하며 `source_out - source_in`을 timeline duration으로도 사용한다. 이 결합으로 2초 source window를 7초 timeline에 반복하는 상태와 split/trim 뒤의 source phase를 표현할 수 없다.

## Problem

Loop는 source window와 timeline extent를 분리해야 한다. 또한 loop cycle 내부 split과 trim-start는 right/result Clip의 첫 sample이 기존 timeline과 연속되도록 phase를 이동해야 한다. `source_in`을 이동하면 반복 window 자체가 바뀌므로 기존 geometry만으로 phase를 표현할 수 없다.

## Decision

Decision B를 채택한다. Working Clip, immutable Snapshot Clip과 Preview manifest Clip에 다음 canonical state를 둔다.

- `timeline_duration`: positive integer microseconds
- `loop_enabled`: boolean, 기본값 `false`
- `loop_phase`: non-negative integer microseconds, 기본값 `0`

`source_in`, `source_out`은 반복할 immutable source window를 계속 정의한다. `loop_phase`는 그 window 안에서 Clip timeline offset 0이 시작할 상대 offset이다. API는 기존 timing contract와 같이 decimal seconds를 받고 최대 소수점 6자리를 exact integer microseconds로 정규화한다.

## Alternatives

- Option A, `timeline_duration`만 추가: split/trim-start 뒤 source continuity를 표현하지 못한다.
- Option B, `timeline_duration + loop_phase`: 최소 독립 field로 extent와 phase를 모두 표현하므로 채택한다.
- Option C, `timeline_end`: 시작과 길이의 이중 authority 또는 duration 재계산을 만들며 phase 문제를 해결하지 못한다.
- Option D, `repeat_count + partial_duration`: 동일 duration을 둘로 표현하고 split/trim projection이 복잡해진다.
- 별도 loop region aggregate: 현재 고정 source window 하나를 반복하는 요구보다 크며 premature하다.

## Invariants

`W = source_out - source_in`, `D = timeline_duration`, `P = loop_phase`로 둔다.

- `source_duration > 0`, `0 <= source_in < source_out <= source_duration`
- `D > 0`
- `loop_enabled = false`이면 `D = W`이고 `P = 0`
- `loop_enabled = true`이면 `0 <= P < W`
- loop-enabled split/trim fragment는 `D < W`일 수 있다. 이를 금지하면 cycle 내부 split을 표현할 수 없다.
- boolean string, non-finite seconds, 6자리 초과 precision, zero/negative duration은 거부한다.
- implicit clamp, source window 변경과 phase 추측은 금지한다.

## Renderer equation

Loop가 켜진 Clip의 timeline offset `0 <= t < D`에서 source position은 다음이다.

```text
source_position(t) = source_in + ((P + t) mod W)
```

최종 cycle은 `D`에서 정확히 truncate한다. exact boundary `P + t = nW`는 `source_in`으로 wrap한다. Loop off는 기존 `[source_in, source_out)` slice이며 `D = W`다.

## Split

`0 < s < D`에서 split한다.

```text
left.timeline_start    = old.timeline_start
left.timeline_duration = s
left.loop_phase        = P

right.timeline_start    = old.timeline_start + s
right.timeline_duration = D - s
right.loop_phase        = (P + s) mod W
```

두 child는 source identity/window, `loop_enabled`, Gain을 상속한다. ADR-054에 따라 left는 Fade-in, right는 Fade-out projection만 보존한다. Projection을 exact 표현하거나 검증할 수 없으면 `SPLIT_STRUCTURE_CONFLICT`로 전체 rollback한다.

## Trim

Trim-start offset `x`는 `0 < x < D`다.

```text
timeline_start'    = timeline_start + x
timeline_duration' = D - x
loop_phase'        = (P + x) mod W
```

Trim-end offset `y`는 `0 < y < D`다.

```text
timeline_start'    = timeline_start
timeline_duration' = D - y
loop_phase'        = P
```

Loop source window는 두 연산 모두 바꾸지 않는다. Loop-off Clip은 기존 source range trim 계약을 유지한다. Loop-on과 Loop-off 경로를 암묵적으로 전환하지 않는다.

## Fade and DSP

Fade invariant는 `fade_in + fade_out <= timeline_duration`이다. Loop-off migration 값은 기존 source span과 같으므로 동작 변화가 없다. Fade는 각 cycle이 아니라 최종 Clip timeline edge에 한 번 적용한다.

```text
decode -> source window -> loop expansion -> static Gain
       -> full-timeline linear Fade -> placement -> Track mix
```

## Copy, delete, restore and inverse structure

Copy는 source window, `timeline_duration`, `loop_enabled`, `loop_phase`, Gain과 Fade를 exact 상속한다. Tombstone과 same-ID restore는 새 geometry를 reset하지 않는다. Unsplit/resplit은 original과 두 child가 위 split equation 및 기존 Fade projection에 exact 일치할 때만 수행하며 divergence는 `SPLIT_STRUCTURE_CONFLICT`다.

## Snapshot and checkout

Commit은 active state의 세 새 field를 immutable Snapshot Clip에 exact freeze한다. Checkout은 선택 Snapshot 값을 exact 복원하며 이전 draft 값을 누출하지 않는다. 기존 Snapshot은 `D = W`, loop off, phase 0으로 deterministic하게 해석한다.

## Preview manifest

Preview schema 4는 `timeline_duration_us`, `loop_enabled`, `loop_phase_us`를 추가한다. schema 1~3은 `timeline_duration_us = source_out_us - source_in_us`, loop off, phase 0으로 읽는다. 생성 후 manifest rewrite는 금지한다.

## Persistence and migration plan

additive migration `20260905_0027`은 `composition_clips`, `composition_snapshot_clips`, `working_preview_render_clips`에 세 field를 추가한다. 기존 row는 `timeline_duration = source_out - source_in`, `loop_enabled = false`, `loop_phase = 0`으로 deterministic backfill한다. 기존 Snapshot row 의미는 바뀌지 않으며 downgrade는 새 column/check만 제거한다. 실제 사용자 DB에는 적용하지 않았다.

## API impact

일반 Loop mutation은 기존 expected revision CAS, Idempotency-Key, typed completion과 Service-owned transaction을 재사용한다. 최소 request는 absolute `loop_enabled`와 `timeline_duration`을 받는다. 외부 consumer가 일반 mutation에서 phase를 임의 지정하지 않는다. Loop off에서 enable하면 phase는 0이고, Loop on 상태의 duration update는 현재 canonical phase를 보존하며, disable 결과는 phase 0이다. Disable caller는 `timeline_duration = W`를 명시적으로 제출해야 하며 다른 값은 `422 CLIP_LOOP_GEOMETRY_INVALID`로 side effect 없이 거부한다. Backend는 제출된 duration을 무시하거나 clamp하지 않고 request fingerprint에도 포함한다.

Frontend-owned Undo/Redo가 nonzero phase 상태를 exact 복원해야 할 때는 별도 history restore operation을 사용한다. 이 operation만 `loop_enabled`, `timeline_duration`, `loop_phase`의 전체 canonical state를 받고 phase까지 fingerprint에 포함한다. Loop off restore는 `D = W, P = 0`, Loop on restore는 `D > 0, 0 <= P < W`를 요구한다. 일반 Loop mutation의 phase 입력 금지와 Split·Trim phase equation은 유지된다. Restore도 같은 revision CAS, idempotency replay와 transaction authority를 사용하며 Backend command stack은 추가하지 않는다.

필요한 새 오류는 입력/geometry용 `CLIP_LOOP_GEOMETRY_INVALID` 하나로 제한한다. 기존 revision, idempotency, source, overlap 및 `SPLIT_STRUCTURE_CONFLICT`를 재사용한다.

## Compatibility

Loop-off backfill은 기존 duration, Gain, Fade, Copy, Split, Trim, Preview, Commit과 Checkout 결과를 바꾸지 않는다. Waveform은 source window authority를 유지하며 Loop state는 resolver, fetch, decode 또는 peak cache key가 아니다. Frontend repeated visualization은 후속 범위다.

## Implementation test matrix

- loop-off migration과 byte/sample behavior 호환
- duration이 source span보다 큰 반복과 partial final cycle
- duration이 source span보다 짧은 split fragment
- exact cycle boundary와 non-zero phase
- cycle 내부 split 및 right phase
- trim-start phase 이동과 trim-end phase 유지
- full timeline Fade, Gain + Loop, Fade + Loop, Gain + Fade + Loop
- Copy, tombstone/restore, unsplit/resplit conflict
- Snapshot freeze와 Checkout exact restore
- Preview schema 4 freeze와 schema 1~3 compatibility
- revision CAS, replay, fingerprint conflict와 response-loss retry

## Consequences

세 Clip persistence 경계와 renderer는 source span 대신 explicit timeline duration을 사용한다. Loop phase는 structural operation의 canonical 결과가 되어 복잡성이 늘지만 source window를 변형하거나 consumer가 phase를 추측하는 더 큰 위험을 제거한다. Loop Backend foundation은 구현됐고 Frontend integration은 별도 후속 작업이다.
