# ADR-073: AI Music Director Candidate APPLY 권위

> 상태: 승인
> 작성일: 2026-09-17
> 최종 수정일: 2026-09-17
> 구현 상태: Implemented
> 관련 기능: AI-native DAW D5 Candidate APPLY, WorkingComposition atomic mutation
> 관련 문서: [ADR-069](ADR-069-ai-music-director-candidate-workflow.md), [ADR-056](ADR-056-persistent-working-composition-history.md), [ADR-057](ADR-057-working-composition-multi-user-conflict-recovery-authority.md), [ADR-059](ADR-059-typed-persistent-history-target-authority.md), [Workspace API](../06-api/workspace-rest-api-endpoints.md)

## 배경

Music Director Candidate 생성, trusted proposal Artifact materialization, Project-scoped read와
CAS SELECT는 구현됐다. Candidate의 bounded proposal을 mutable WorkingComposition에 적용하는
명령은 composition state, persistent history, Run/Candidate lifecycle과 idempotency completion을
부분 상태 없이 함께 확정해야 한다. SELECT는 선택 pointer만 바꾸며 APPLY를 대신하지 않는다.

## 결정

### Preconditions와 input authority

APPLY는 effective Owner가 접근 가능한 Project의 Run과 Candidate만 허용한다. Candidate는 Run에
속하고 현재 `selected_candidate_id`와 같아야 하며, Run의 Job은 `SUCCEEDED`, Candidate는
`generated`, 모든 materialization은 `COMPLETED`여야 한다. proposal Artifact는 기존 authorized
Artifact resolver로 열고 checksum, size, media type, canonical proposal digest와 source Snapshot을
다시 검증한다. partial Candidate set, rejected Candidate, cross-Run/Project identity는 거부한다.

현재 WorkingComposition은 같은 Project에 속하고 `base_snapshot_id`가 proposal의
`source_snapshot_id`와 같아야 한다. request는 `expected_run_version`과
`expected_working_composition_revision`을 모두 요구한다. 어느 하나라도 달라지면 silent merge,
automatic rebase 또는 per-field merge 없이 conflict로 종료한다.

### Mutation target

proposal schema v1의 다음 absolute operation만 허용한다.

- `set_clip_gain`: Snapshot과 WorkingComposition에 존재하는 canonical Clip의 Gain
- `set_track_gain`: canonical Track의 Gain
- `set_track_pan`: canonical Track의 Pan
- `set_master_gain`: WorkingComposition의 Master Gain

Clip/Track 생성·삭제·이동, arrangement, Fade, Loop, Mute, Solo, Section과 arbitrary payload는
허용하지 않는다. 모든 target과 값, 중복 same-target/property, operation count를 mutation 전에
검증하고 Track Gain/Pan은 기존 Mute/Solo와 변경하지 않는 mixer field를 보존한다.

### Atomicity와 transaction owner

새 transaction framework를 만들지 않는다. `MusicDirectorApplyService`가 기존 Service-owned
`session.begin()` 경계와 commit-free Repository primitive를 조합하는 application UoW owner다.
Repository의 `commit()`과 `rollback()` 호출은 0이다.

검증된 mutation plan에 대해 다음을 한 transaction으로 확정한다.

1. Owner/Project/Run/Candidate/materialization과 selected pointer 재검증
2. Run version과 WorkingComposition revision CAS
3. 모든 Clip/Track/Master absolute mutation
4. 하나의 aggregate persistent history entry와 cursor 갱신
5. WorkingComposition revision 1회 증가
6. Candidate `generated -> applied`, Run applied pointer/result revision과 Run version 갱신
7. idempotency completion result 기록

어느 단계든 실패하면 composition, history, cursor, revision, Candidate와 Run 변경은 모두 0이다.
Artifact와 Snapshot은 이 transaction에서 수정하지 않는다.

### CAS와 idempotency

API는 `Idempotency-Key`를 필수로 받는다. fingerprint는 contract version, effective Owner,
Project, Run, Candidate, expected Run version, WorkingComposition identity와 expected revision,
proposal schema와 digest를 포함한다. 같은 key와 fingerprint는 저장된 동일 completion을 replay하고,
같은 key의 다른 fingerprint는 conflict다. replay 검사는 scope 확인 뒤 현재 revision CAS보다 먼저
수행해 response loss 후에도 최초 completed revision을 반환한다. 새 key로 이미 적용된 Run을 다시
APPLY하는 것은 `ALREADY_APPLIED`로 거부한다.

Run CAS는 SELECT A 뒤 SELECT B가 완료된 A의 stale APPLY를 막는다. WorkingComposition CAS는
동시 사용자 mutation을 막는다. 서로 다른 Candidate의 동시 APPLY와 서로 다른 Run의 같은
WorkingComposition APPLY 모두 최대 하나만 성공한다.

### Persistent history와 Undo/Redo

APPLY 전체는 `MUSIC_DIRECTOR_APPLY -> WORKING_COMPOSITION` 한 entry다. bounded before/after
payload는 영향을 받은 canonical Clip Gain, Track Gain/Pan과 Master Gain만 deterministic order로
보존하고 Run/Candidate/proposal digest provenance를 identity로 기록한다. 여러 독립 entry로 나눠
partial Undo를 허용하지 않는다.

Undo 1회는 APPLY가 바꾼 모든 field를 pre-APPLY 값으로 exact 복원하고 revision을 1 증가시킨다.
Redo 1회는 동일 field를 post-APPLY 값으로 exact 복원하고 revision을 다시 1 증가시킨다. 기존
strict LIFO, redo-tail 삭제, target compatibility와 expected revision CAS를 그대로 적용한다.
Undo/Redo는 Run의 applied pointer나 Candidate status를 되돌리지 않는다. 이들은 적용 lineage이며,
현재 composition state는 history cursor와 revision이 나타낸다.

### Snapshot, Preview, Export와 lineage

APPLY는 Snapshot을 자동 생성하거나 기존 Snapshot을 변경하지 않는다. pre-APPLY Snapshot은 계속
불변이며 Checkout은 기존 history barrier와 revision authority를 따른다. APPLY의 revision 증가로
기존 Working Preview는 stale이 되고 다음 explicit Preview가 새 canonical state를 사용한다. 기존
Export와 그 Snapshot은 변경하지 않으며, 이후 명시적으로 생성한 Snapshot/Export만 적용 결과를
포함한다.

proposal Artifact, AssetVersion과 storage publication은 수정·덮어쓰기·삭제하지 않는다. 기존
Run/Candidate/Artifact lineage와 Run의 `applied_candidate_id`, `applied_working_revision`이 provenance
authority다. history payload에는 identity만 기록하고 storage locator나 raw Provider payload를 넣지
않는다.

### SELECT와 APPLY

SELECT는 selected pointer와 Run version만 변경하고 WorkingComposition/history는 변경하지 않는다.
APPLY는 현재 selected Candidate만 적용하며 selected pointer를 자동 변경하지 않는다. 성공 시
applied pointer, applied revision, Candidate status와 Run version만 composition transaction 안에서
함께 갱신한다.

### Proposed API

```text
POST /api/v1/projects/{project_id}/music-director/runs/{run_id}/candidates/{candidate_id}/apply
Idempotency-Key: <required>
```

Request body:

```json
{
  "expected_run_version": 3,
  "expected_working_composition_revision": 12
}
```

Response는 `run_id`, `candidate_id`, `working_composition_id`, `working_composition_revision`,
`run_version`, `history_entry_id`, `replayed`만 반환한다. storage path, claim/client execution key와
Provider payload는 반환하지 않는다.

Internal idempotency completion은 `completed_revision`을 저장하며 replay 시 이를 Public result의
`working_composition_revision`으로 변환한다. 두 field는 같은 최초 APPLY 완료 revision을 나타낸다.

Project/Run/Candidate 비존재와 scope mismatch는 canonical not-found, materialization/selection/Job
state와 already-applied는 typed conflict, stale Run/WorkingComposition은 기존 conflict, proposal
무결성·schema·target 불일치는 fail-closed typed conflict, idempotency mismatch는 기존 idempotency
conflict로 매핑한다. transaction failure는 rollback 후 sanitized internal error로 처리한다.

## Database와 API 영향

`MIGRATION_REQUIRED: NO`. `MusicDirectorRun.applied_candidate_id`,
`applied_working_revision`, Candidate status, WorkingComposition revision과 범용 typed history
JSON이 필요한 authority를 이미 표현한다. 구현 시 code-level history command와 idempotency result
type은 추가하지만 새 column/table은 필요하지 않다.

현재 Runtime API는 90 paths / 111 operations, POST 43이며 fingerprint는
`5805c976c4f950abce8da1db2241437f5d901d55a0363fd54d9f485d902c4dd4`다.

## 보안

effective Owner/Project scope를 Service에서 재검증하고 Router는 Repository, Session, filesystem,
Provider를 직접 사용하지 않는다. response, error, history와 log에 absolute/storage/DB path,
credential, raw Provider response, local model path, stack trace, command와 PID를 노출하지 않는다.

## 대안

- SELECT가 즉시 APPLY: 비교와 mutation 경계를 섞고 취소 가능한 선택을 파괴하므로 거부한다.
- operation별 transaction/history entry: 부분 state와 partial Undo를 허용하므로 거부한다.
- 새 Snapshot 자동 생성: 현재 explicit commit authority를 우회하므로 거부한다.
- automatic rebase/per-field merge: frozen proposal과 aggregate revision CAS를 약화하므로 거부한다.
- 새 APPLY ledger/schema: 기존 Run applied fields, idempotency completion과 transaction UoW로 충분해
  과도하므로 거부한다.

## 결과와 후속 작업

Production endpoint, Service-owned UoW, aggregate history command와 focused tests를 구현했다.
Migration은 필요하지 않으며 Frontend Candidate 비교 UX와 실제 Provider 연결은 후속 작업이다.
