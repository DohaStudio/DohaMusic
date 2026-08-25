# WorkingComposition Atomic Mutation Service

> 문서 상태: [완료]
> 최종 수정일: 2026-08-25
> 관련 기능: AI-native DAW D3 Clip Editing Backend
> 관련 문서: [ADR-040](../11-decisions/ADR-040-canonical-track-clip-working-composition-authority.md), [ADR-045](../11-decisions/ADR-045-clip-service-deletion-media-duration-authority.md), [ADR-047](../11-decisions/ADR-047-revision-safe-idempotency-completion-result.md), [Product API](../06-api/working-composition-api.md)

## 책임과 계층

`WorkingCompositionService`가 effective Owner·Workspace·Project scope, transaction, revision, mutation validation과 idempotency completion을 소유한다. Router는 Service만 호출하고 Repository·Session·ORM·filesystem·Resolver·Provider에 접근하지 않는다. Repository는 deterministic read와 persistence primitive만 제공하며 `commit()`·`rollback()`을 호출하지 않는다.

```text
Router → WorkingCompositionService → Repository / trusted metadata Service
                   └─ 하나의 session.begin()
                      claim → validate → mutate → revision CAS → complete
```

GET은 WorkingComposition을 자동 생성하지 않는다. active Track은 `(track_order, track_id)`, active Clip은 Track order 뒤 `(timeline_start, clip_id)` 순서로 반환하고 working duration은 active Clip의 최대 `timeline_end`에서 계산한다.

## Initialize 계약

initialize는 GET-or-create가 아닌 explicit create다.

| 조건 | 결과 |
|---|---|
| Project에 WorkingComposition 없음 | 새 opaque ID, revision 0, completion result 저장 |
| 같은 key·같은 fingerprint | 최초 ID와 revision 0 replay, mutation 0 |
| 기존 WorkingComposition + 다른/새 key | `409 WORKING_COMPOSITION_ALREADY_EXISTS`, mutation·revision·성공 completion 0 |
| concurrent duplicate loser | DB unique race를 같은 Product conflict로 정규화, partial row 0 |

기존 WorkingComposition이나 현재 revision을 새 initialize 성공 응답으로 반환하지 않는다.

## Revision과 replay

모든 상태 mutation은 `expected_revision`을 받고 마지막에 `UPDATE ... WHERE revision=:expected_revision RETURNING revision` compare-and-swap을 수행한다. affected row가 없으면 transaction 전체가 rollback되고 `WORKING_COMPOSITION_REVISION_CONFLICT`다. 성공한 operation은 정확히 `+1`이다.

checkout·Track create/delete·Clip create/split/delete는 `Idempotency-Key`를 요구한다. fingerprint는 effective Owner, Project, WorkingComposition, operation, expected revision, target ID와 microseconds로 정규화한 body를 포함한다. completed replay는 현재 revision과 domain validation보다 먼저 stored typed result를 반환한다. move·trim·rename·reorder는 ADR-040의 absolute mutation 계약을 유지하며 이전 revision 재시도는 conflict 후 GET/reconcile한다.

## Track·Clip mutation

- Track create는 V1 `audio`와 연속 order를 사용한다.
- reorder는 임시 offset 뒤 최종 `0..N-1`로 배치해 active-order unique 충돌을 피한다.
- active Clip이 있는 Track delete는 `TRACK_NOT_EMPTY`; cascade하지 않는다.
- Clip create는 exact AssetVersion, active audio Asset, effective scope, active ProjectAsset와 exactly-one eligible Artifact의 persisted positive `duration_us`를 요구한다.
- public decimal seconds는 half-up integer microseconds로 변환한 뒤 range를 다시 검증한다.
- create·move·trim·split·checkout은 같은 Track의 `[start,end)` overlap을 거부하고 adjacency와 cross-Track overlap을 허용한다.
- split은 original을 tombstone하고 두 새 canonical ID에 `split_from_clip_id=original`을 기록한다.
- delete는 tombstone만 만들고 AssetVersion·Artifact·payload를 변경하지 않는다.

checkout은 같은 Project의 immutable SnapshotTrack/SnapshotClip만 authority로 사용한다. canonical Track/Clip ID, exact AssetVersion과 frozen duration을 한 transaction에서 복원하고 legacy arrangement가 없으면 fail-closed한다. `SnapshotItem`은 사용하지 않는다.

## 검증과 범위 밖 항목

격리 SQLite fixture에서 revision race exactly-one success, initialize unique race, replay fidelity, overlap, scope/source eligibility, query-plan index 사용과 forced rollback을 검증했다. source Alembic head는 `20260825_0022`이며 새 migration은 없다. 실제 사용자 DB·Artifact payload·media·Provider·GPU에는 접근하지 않았다.

Composition commit, Frontend Undo/Redo, Waveform, working preview/render와 Mixer는 후속 범위다.
