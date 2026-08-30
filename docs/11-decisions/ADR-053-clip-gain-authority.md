# ADR-053 — Clip Gain Authority

> 상태: 승인, Backend foundation 구현
> 작성일: 2026-08-30
> 최종 수정일: 2026-08-31
> 관련 기능: AI-native DAW D3 Clip Gain
> 관련 문서: [ADR-040](ADR-040-canonical-track-clip-working-composition-authority.md), [ADR-047](ADR-047-revision-safe-idempotency-completion-result.md), [ADR-050](ADR-050-working-composition-inverse-mutation-authority.md), [ADR-052](ADR-052-working-composition-preview-render-authority.md), [WorkingComposition Service](../03-architecture/working-composition-service.md), [Product API](../06-api/working-composition-api.md)
> 구현 추적: additive Alembic `20260830_0025`, `CLIP_GAIN_UPDATE` mutation, Preview manifest schema 2와 FFmpeg static gain을 구현했다. 2026-08-31에는 selected Clip Gain slider·exact input·0 dB reset, absolute memory Undo/Redo, revision reconcile과 Preview stale Frontend consumer를 구현했다. 실제 사용자 DB는 변경하지 않았다.

## 배경

D3 편집기는 canonical Clip geometry, revision-safe mutation, immutable Composition commit과 revision-pinned Working Preview를 구현했다. Clip Gain을 추가하려면 영속 위치, 수치 범위, split inverse semantics, Preview DSP 순서와 D4 Mixer 경계를 먼저 하나의 authority로 고정해야 한다.

## 문제

Gain을 Track/Master mix setting이나 transient Frontend state에 두면 Clip copy·split·restore·commit·Preview가 서로 다른 값을 사용할 수 있다. 특히 split child를 개별 편집한 뒤 unsplit하면 어느 값을 original에 적용할지 임의 선택하게 되어 사용자 편집을 조용히 잃을 수 있다.

## 결정

### Domain과 수치 계약

- D3 Gain은 canonical Clip별 정적 속성 `gain_db`다. Track Gain, Master Gain, Pan, Mute, Solo와 automation은 D4다.
- 저장 형식은 exact decimal `NUMERIC(5,2)`이고 기본값은 `0.00 dB`다.
- 허용 범위는 양 끝을 포함한 `-24.00..+24.00 dB`, 해상도는 `0.01 dB`다. 기존 audio 설정의 검증된 bounded dB 관례를 Clip에 명시적으로 적용한다.
- 숫자는 finite여야 한다. `-Infinity`, 별도 sentinel 또는 최소값을 mute로 해석하지 않는다. Mute는 후속 독립 authority다.
- `gain_db`는 `composition_clips`, `composition_snapshot_clips`, `working_preview_render_clips`에 각각 저장한다.

### Mutation과 revision

- `PATCH /api/v1/projects/{project_id}/working-composition/clips/{clip_id}/gain`은 absolute `gain_db`, `working_composition_id`, `expected_revision`을 받는다.
- mutation은 `Idempotency-Key`가 필수이고 typed completion result `CLIP_GAIN_UPDATE`에 최초 `clip_id`와 `completed_revision`을 저장한다.
- same key·same fingerprint replay는 현재 revision과 무관하게 최초 결과를 반환하고 새 mutation은 0건이다. 같은 key·다른 fingerprint는 기존 idempotency conflict다.
- 성공은 Clip Gain만 변경하고 revision을 정확히 1 증가시킨다. geometry, source lineage, Snapshot, Preview Job 또는 Artifact를 자동 변경·생성하지 않는다.

### Identity와 inverse mutation

- Copy는 source Clip의 Gain을 새 canonical Clip에 복사한다.
- Split은 original Gain을 left와 right child 모두에 복사한다.
- Delete tombstone과 same-ID restore는 Gain을 그대로 보존한다. Move와 Trim은 Gain을 변경하지 않는다.
- Unsplit은 original·left·right의 Gain이 정확히 같을 때만 기존 구조 복원 조건을 만족한다. child Gain이 하나라도 다르면 `SPLIT_STRUCTURE_CONFLICT`로 전체 rollback한다.
- 성공한 unsplit 뒤 original Gain이 child와 달라지면 resplit도 같은 오류로 rollback한다. Backend는 평균, left/right 우선 또는 last-write-wins로 편집을 소실하지 않는다.
- 이 규칙은 create → delete → restore redo identity와 delete → restore undo identity를 바꾸지 않는다. initialize와 checkout/commit history barrier도 유지한다.

### Preview와 Commit

- Preview 요청 시 current Clip Gain을 immutable manifest에 pin한다. 이후 WorkingComposition Gain mutation은 기존 Preview manifest와 결과를 바꾸지 않는다.
- renderer 순서는 source decode/trim → static Clip Gain → timeline delay/placement → Track mix다. 선형 배율은 `10^(gain_db/20)`이며 FFmpeg의 dB volume filter로 적용한다.
- 향후 Fade envelope는 static Clip Gain 뒤, Track mix 전에 적용한다. Track/Master DSP는 D4 authority 뒤에 추가한다.
- Gain은 waveform source-shape cache key가 아니며 Waveform peak를 재계산하거나 시각 진폭으로 자동 scaling하지 않는다.
- Composition Commit은 active Clip의 Gain을 immutable SnapshotClip에 그대로 고정한다. Commit은 render가 아니며 Preview/Export를 자동 생성하지 않는다.

### Persistence와 경계

- Alembic `20260830_0025`는 세 기존 table에 non-null `gain_db`, server default `0.00`과 범위 CHECK만 additive하게 추가한다. 기존 row는 0 dB가 된다.
- 실제 사용자 DB migration, data backfill 실행, media 접근, Common Contract, Provider, Dataset, Training, GPU와 Frontend production code는 이 gate에서 변경하지 않는다.
- source Alembic head는 `0025`지만 실제 사용자 DB는 승인된 `0017`에 그대로 남는다.

## 선택 이유

Clip에 exact 값을 보존하면 working, replay, Preview, commit과 inverse mutation이 같은 authority를 사용한다. bounded decimal은 JSON/DB/FFmpeg 경계에서 결정적이며, split divergence를 conflict로 처리하면 암묵적인 음량 편집 손실이 없다.

## 검토한 대안

- Track 또는 Master Gain으로 시작: D3 Clip identity와 Copy/Split 요구를 충족하지 못해 제외했다.
- linear amplitude 저장: 사용자 API와 기존 dB 설정 관례가 달라지고 exact replay가 불명확해 제외했다.
- `-Infinity`를 mute로 저장: decimal schema와 별도 Mute 의미를 결합하므로 제외했다.
- unsplit 때 child 평균/한쪽 우선: 사용자 편집을 조용히 잃으므로 제외했다.
- Preview 때 current Clip을 다시 조회: immutable manifest와 revision pin을 깨므로 제외했다.

## 장점과 단점

장점은 canonical identity 전 구간의 결정성, revision-safe replay, Preview 재현성과 편집 손실 방지다. 단점은 child Gain이 diverge한 split을 바로 unsplit할 수 없고 사용자가 먼저 값을 정합화해야 한다는 점이다.

## 영향

WorkingComposition Product operation은 21개가 된다. Preview manifest schema는 2가 되고 source head는 `20260830_0025`가 된다. Frontend는 기존 응답의 `gain_db`를 읽을 수 있지만 이 gate에는 Gain control이나 Undo/Redo command를 추가하지 않는다.

## 마이그레이션

격리 DB에서 `0024 → 0025 → 0024`와 기존 row 0 dB default, 범위 CHECK, FK/integrity를 검증한다. 실제 사용자 DB 적용은 별도 승인 작업에서만 수행한다.

## 재검토 조건

Track/Master Mixer, Mute/Solo, Gain/Fade automation, 범위를 넘는 전문 mastering workflow 또는 Clip Gain UI를 설계할 때 재검토한다. 기존 Snapshot/Preview 재현성을 깨는 재해석은 허용하지 않는다.

## 관련 PR

- Draft PR: 생성 후 연결
