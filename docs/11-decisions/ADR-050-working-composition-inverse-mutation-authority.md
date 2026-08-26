# ADR-050 — WorkingComposition Inverse Mutation 권위

> 상태: 승인
> 작성일: 2026-08-25
> 최종 수정일: 2026-08-26
> 관련 기능: AI-native DAW D3 Backend inverse mutation과 Frontend Undo/Redo 경계
> 관련 문서: [ADR-040](ADR-040-canonical-track-clip-working-composition-authority.md), [ADR-045](ADR-045-clip-service-deletion-media-duration-authority.md), [ADR-047](ADR-047-revision-safe-idempotency-completion-result.md), [WorkingComposition Service](../03-architecture/working-composition-service.md), [Product API](../06-api/working-composition-api.md)

> 구현 추적: 2026-08-26 Track/Clip restore와 atomic unsplit/resplit Backend에 이어 Frontend strict LIFO memory command history를 구현했다. initialize·checkout·Project 변경·conflict reconcile history boundary, same-ID undo/redo와 response revision authority를 소비한다. Composition commit은 후속이다.

## 1. 배경

ADR-040은 Undo/Redo 명령 이력을 Frontend가 소유하고 Backend는 각 역연산이 반영된 canonical working state만 저장하도록 결정했다. 기존 Backend는 delete와 split을 tombstone으로 보존했지만, 같은 canonical identity를 안전하게 복원하는 Product operation과 split을 원자적으로 되돌리고 다시 적용하는 구조 검증 계약이 없었다.

일반 create로 undo/redo를 흉내 내면 identity가 바뀌고, 현재 source eligibility나 overlap을 무시한 단순 tombstone 해제는 권한·보존 상태·배치 불변식을 우회한다. split child가 편집된 뒤 원본을 복원하면 어느 geometry가 authority인지도 모호해진다.

## 2. 결정

### 2.1 Track restore

- 요청은 `target_track_order`를 명시해야 하며 허용 범위는 현재 active Track 수를 `N`이라 할 때 `0..N`이다.
- 복원하는 row는 delete 전과 같은 `track_id`를 사용한다. 새 Track을 생성하지 않는다.
- 기존 active Track을 원자적으로 shift/reindex하고 결과 order를 `0..N`의 연속 값으로 만든다.
- 이미 active인 Track, 범위 밖 order, 다른 WorkingComposition의 Track은 성공으로 위장하지 않는다.
- state 변경, revision compare-and-swap, completion result는 하나의 Service transaction이다.

### 2.2 Clip restore

- 복원하는 row는 delete 전과 같은 `clip_id`, exact `source_asset_version_id`, frozen `source_duration`과 geometry를 유지한다.
- 요청 시점의 effective Owner, ProjectAsset, AssetVersion, active audio Asset, exactly-one eligible Artifact와 parent Track 활성 상태를 다시 검증한다.
- 현재 trusted Artifact duration을 다시 해석할 수 있어야 하지만 기존 Clip의 frozen `source_duration`과 geometry를 새 값으로 덮어쓰지 않는다.
- same-Track active Clip overlap을 다시 검사한다. 권한·source·parent·overlap 중 하나라도 만족하지 않으면 fail-closed하고 partial restore를 남기지 않는다.
- 이미 active인 Clip은 conflict다.

### 2.3 Unsplit과 resplit

최초 split에서 다음 구조를 authority로 고정한다.

```text
original: [timeline_start, source_in, source_out], tombstone
left:     [timeline_start, source_in, split_point], active
right:    [timeline_start + (split_point - source_in), split_point, source_out], active
left.split_from_clip_id = right.split_from_clip_id = original.clip_id
```

- 비교는 DB에 저장된 integer microseconds의 exact equality를 사용한다.
- 두 child는 같은 WorkingComposition·Track·source AssetVersion·frozen source duration과 정확한 complementary geometry를 가져야 한다.
- unsplit은 두 active child를 함께 tombstone하고 original을 같은 ID로 복원한다.
- resplit은 tombstone original을 유지하고 같은 left/right canonical ID를 함께 복원한다.
- child move·trim·delete, source·Track·lineage 변경, child 누락·추가 상태 차이가 있으면 `SPLIT_STRUCTURE_CONFLICT`로 거부한다. 자동 보정이나 새 child 생성은 하지 않는다.
- overlap 검증, 세 row 상태 변경, revision 증가와 completion 저장은 하나의 transaction이다.

### 2.4 Revision-safe idempotency

`TRACK_RESTORE`, `CLIP_RESTORE`, `CLIP_UNSPLIT`, `CLIP_RESPLIT`을 `IdempotencyCompletionResult` V1 allowlist에 추가한다. Track/Clip restore payload는 복원 canonical ID를, unsplit/resplit payload는 original·left·right ID를 저장한다.

- 같은 key·같은 fingerprint는 최초 identity와 `completed_revision`을 replay하고 새 mutation은 0건이다.
- 같은 key·다른 fingerprint는 `IDEMPOTENCY_KEY_REUSED`다.
- `IN_PROGRESS`와 unknown/malformed result는 기존 fail-closed 계약을 유지한다.
- validation 또는 revision conflict의 실패 completion result는 기록하지 않는다.

## 3. History 경계

- initialize는 새 WorkingComposition과 함께 빈 Frontend history에서 시작한다.
- checkout은 전체 working state를 교체하는 history barrier다. checkout 이전 command를 이후 Undo/Redo 대상으로 유지하지 않는다.
- checkout 자체를 inverse mutation으로 만들지 않는다.
- Backend는 command stack, cursor, redo branch 또는 사용자별 history를 저장하지 않는다.
- Frontend는 성공 응답의 canonical ID와 completed revision으로 command를 구성하고, conflict 시 GET/reconcile한다.

## 4. 선택 이유와 대안

1. **restore를 create로 표현**: canonical identity와 idempotent replay가 깨져 제외한다.
2. **현재 Track 끝에만 복원**: 사용자 의도와 undo fidelity를 잃으므로 explicit target order를 채택한다.
3. **Clip tombstone을 검증 없이 해제**: 현재 권한·보존·Artifact eligibility와 overlap을 우회하므로 제외한다.
4. **변경된 split child를 자동 병합**: 어떤 geometry를 보존할지 모호하고 비파괴 편집을 예측 불가능하게 만들어 제외한다.
5. **Backend command history table 추가**: V1의 revision·idempotency와 Frontend-owned history 경계를 넘어가므로 제외한다.
6. **checkout을 undoable command로 취급**: 서로 다른 immutable base arrangement 사이의 과거 command 재적용이 불명확하므로 history barrier를 채택한다.

## 5. 영향과 호환성

네 Product operation이 추가되어 WorkingComposition surface는 17개 operation, 16개 path가 된다. 기존 요청·응답과 DB table은 변경하지 않으며 `idempotency_records.result_type`은 문자열 allowlist 검증이므로 schema migration이 필요하지 않다. Snapshot·SnapshotItem·media payload·Provider·실제 사용자 DB에는 영향을 주지 않는다.

## 6. 검증과 재검토 조건

격리 DB에서 같은 identity 복원, Track order shift, current source eligibility, overlap, exact split geometry, repeated undo/redo, same-key replay, stale revision, concurrent race와 forced rollback을 검증한다. Frontend multi-user collaborative history, edited-child merge, branching undo graph 또는 checkout을 넘는 history가 필요해지면 별도 ADR로 재검토한다.
