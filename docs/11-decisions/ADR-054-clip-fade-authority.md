# ADR-054 — Clip Fade Authority

> 상태: 승인, Backend foundation 구현
> 작성일: 2026-09-03
> 최종 수정일: 2026-09-03
> 관련 기능: AI-native DAW D3 Clip Fade
> 관련 문서: [ADR-040](ADR-040-canonical-track-clip-working-composition-authority.md), [ADR-047](ADR-047-revision-safe-idempotency-completion-result.md), [ADR-050](ADR-050-working-composition-inverse-mutation-authority.md), [ADR-052](ADR-052-working-composition-preview-render-authority.md), [ADR-053](ADR-053-clip-gain-authority.md), [WorkingComposition Service](../03-architecture/working-composition-service.md), [Product API](../06-api/working-composition-api.md)
> 구현 추적: additive Alembic `20260903_0026`, `CLIP_FADE_UPDATE` mutation, Preview manifest schema 3과 FFmpeg linear-amplitude Fade를 구현했다. 실제 사용자 DB·media와 Frontend production code는 변경하지 않았다.

## 배경

D3 편집기는 canonical Clip geometry, static Clip Gain, revision-safe mutation, immutable Composition commit과 revision-pinned Working Preview를 구현했다. Fade를 추가하려면 저장 단위와 곡선, Clip geometry 변화와 inverse mutation, Preview DSP 순서를 하나의 authority로 고정해야 한다.

## 문제

Fade가 transient Frontend state이거나 renderer 전용 설정이면 Copy·Split·Trim·Restore·Commit·Checkout 결과가 재현되지 않는다. Split이나 Trim에서 값을 묵시적으로 clamp하면 사용자가 저장한 envelope가 조용히 변하며, unsplit/resplit과 idempotency replay도 최초 결과를 보존할 수 없다.

## 결정

### Domain과 수치 계약

- Fade는 canonical Clip별 정적 속성 `fade_in`, `fade_out`이다. API 단위는 decimal seconds, persistence 단위는 integer microseconds다.
- 기본값은 각각 `0`이고 정밀도는 최대 소수점 6자리다. 문자열, boolean, NaN, Infinity, 음수, microsecond보다 정밀한 값은 거부한다.
- 각 값은 0 이상이며 `fade_in + fade_out <= source_out - source_in`이어야 한다. 경계의 등호는 허용하고 위반은 `CLIP_FADE_OUT_OF_RANGE`로 거부한다.
- V1 곡선은 고정 linear amplitude다. curve 종류나 automation point를 API·DB에 추가하지 않는다.
- `composition_clips`, `composition_snapshot_clips`, `working_preview_render_clips`가 각 Fade 값을 저장한다.

### Mutation과 revision

- `PATCH /api/v1/projects/{project_id}/working-composition/clips/{clip_id}/fade`는 absolute `fade_in`, `fade_out`, `working_composition_id`, `expected_revision`을 받는다.
- `Idempotency-Key`가 필수이며 typed completion result `CLIP_FADE_UPDATE`는 최초 `clip_id`와 `completed_revision`을 저장한다.
- same key·same fingerprint replay는 현재 revision과 무관하게 최초 결과를 반환하고 새 mutation은 0건이다. 같은 key·다른 fingerprint는 기존 idempotency conflict다.
- 성공 시 Fade만 변경하고 revision은 정확히 1 증가한다. geometry, source lineage, Snapshot, Preview Job과 Artifact를 자동 변경하거나 생성하지 않는다.

### Geometry와 identity

- Copy는 source Clip의 Fade를 새 canonical Clip에 그대로 복사한다.
- Split은 active Fade 구간 내부를 허용하지 않는다. `split_offset < fade_in` 또는 `split_offset > duration - fade_out`이면 `SPLIT_STRUCTURE_CONFLICT`로 전체 rollback한다.
- 유효한 Split에서 left는 `(original.fade_in, 0)`, right는 `(0, original.fade_out)`을 가진다. Fade 경계에서의 Split은 허용한다.
- Move는 Fade를 보존한다. Trim은 Fade를 보존하며 새 duration이 합계보다 짧으면 clamp하지 않고 `CLIP_FADE_OUT_OF_RANGE`로 전체 rollback한다.
- Delete tombstone과 same-ID Restore는 Fade를 그대로 보존한다.
- Unsplit은 original·left·right의 Fade가 위 canonical projection과 정확히 일치할 때만 복원한다. Resplit도 같은 original/left/right identity와 Fade를 복원한다. divergence는 `SPLIT_STRUCTURE_CONFLICT`다.
- initialize는 history boundary이고 checkout은 history barrier라는 기존 authority를 유지한다.

### Preview와 Commit

- Composition Commit은 active Clip의 Fade를 immutable SnapshotClip에 그대로 고정한다. 이전 Snapshot은 변경하지 않는다.
- Checkout은 선택한 Snapshot의 Fade를 새 WorkingComposition state에 정확히 복원한다.
- Preview 요청은 current Clip Fade를 immutable manifest에 pin한다. 이후 WorkingComposition mutation은 기존 manifest와 결과를 바꾸지 않는다.
- renderer 순서는 source decode/trim → static Clip Gain → linear-amplitude Fade → timeline delay/placement → Track mix다. Fade는 waveform source-shape cache를 변경하지 않는다.
- persisted schema 1·2 manifest의 Fade 누락은 0으로 해석해 기존 Preview retry/read 호환성을 유지한다.

### Persistence와 경계

- Alembic `20260903_0026`은 세 기존 table에 non-null integer Fade column, server default 0과 범위 CHECK만 additive하게 추가한다. table 수는 48개로 유지된다.
- 실제 사용자 DB migration·data backfill, media 접근, Common Contract, Provider, Dataset, Training, GPU와 Frontend production code는 이 gate에서 변경하지 않는다.
- source Alembic head는 `0026`이지만 실제 사용자 DB는 승인된 `0017`에 남는다.

## 선택 이유

Clip-relative duration과 integer microseconds는 기존 canonical geometry와 같은 정밀도를 사용한다. 고정 linear amplitude와 fail-closed geometry 정책은 DB, Service, Snapshot, Preview 사이의 의미를 결정적으로 유지하며 묵시적 envelope 손실을 막는다.

## 검토한 대안

- timeline absolute Fade point: Move·Trim에서 의미가 불안정해 제외했다.
- percentage Fade: Trim에 따라 실제 시간이 자동 변해 Snapshot 재현성을 해치므로 제외했다.
- 여러 curve 종류: V1 범위를 넓히고 renderer별 차이를 만들므로 제외했다.
- Split 시 두 child에 양쪽 Fade 복사: split 경계에 의도하지 않은 Fade out/in을 만들어 제외했다.
- Trim 시 자동 clamp: 저장된 편집 의도를 조용히 변경하므로 제외했다.
- Preview render 때 current Clip 재조회: immutable manifest와 revision pin을 깨므로 제외했다.

## 장점과 단점

장점은 Working, Snapshot, Preview와 inverse mutation이 동일한 exact Fade를 사용하고 replay와 renderer 결과가 결정적이라는 점이다. 단점은 active Fade 내부 Split과 지나치게 짧은 Trim 전에 사용자가 Fade를 먼저 줄여야 하며, V1에서 곡선 선택을 제공하지 않는다는 점이다.

## 영향

WorkingComposition Product operation은 22개, OpenAPI Path는 21개가 된다. Preview manifest schema는 3, source head는 `20260903_0026`이 된다. Frontend는 응답의 `fade_in`, `fade_out`을 읽을 수 있지만 이 gate에는 Fade control이나 Undo/Redo command를 추가하지 않는다.

## 마이그레이션

격리 DB에서 `0025 → 0026 → 0025`, 기존 row의 0 Fade default, 경계·범위 CHECK와 FK/integrity를 검증한다. 실제 사용자 DB 적용은 별도 승인 작업에서만 수행한다.

## 재검토 조건

Fade curve 선택, automation, crossfade/layering, Track/Master DSP 또는 Frontend Fade UI를 설계할 때 재검토한다. 기존 Snapshot/Preview 재현성을 깨는 재해석은 허용하지 않는다.

## 관련 PR

- Draft PR: 생성 후 연결
