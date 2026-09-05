# Revision-safe Idempotency Completion Result

> 문서 상태: [완료]
> 최종 수정일: 2026-08-30
> 관련 기능: WorkingComposition mutation replay 선행 기반
> 관련 문서: [ADR-047](../11-decisions/ADR-047-revision-safe-idempotency-completion-result.md), [ADR-050](../11-decisions/ADR-050-working-composition-inverse-mutation-authority.md), [ADR-040](../11-decisions/ADR-040-canonical-track-clip-working-composition-authority.md), [Table Definition](../07-database/table-definition.md)

## 계약

새 mutation의 완료 경계는 다음과 같다.

```text
Idempotency claim
→ domain mutation
→ WorkingComposition revision +1
→ typed IdempotencyCompletionResult
→ 같은 transaction에서 COMPLETED 저장
```

`IdempotencyCompletionResult`는 `result_version`, `completed_revision`, allowlist `result_type`, operation별 UUID `result_payload`를 가진 immutable value object다. Repository의 `claim_with_result()`는 같은 key·fingerprint의 replay에서 저장된 결과만 반환한다. 현재 WorkingComposition이나 대상 Resource를 다시 읽어 최초 revision을 덮어쓰지 않는다.

## 저장 및 검증 경계

- version: V1은 정확히 `1`; unknown version은 fail-closed
- revision: 0 이상 정수
- payload: JSON object, 정확한 operation별 key와 canonical UUID 문자열만 허용
- 크기: canonical UTF-8 JSON 8,192 bytes 이하
- 보안: owner secret, token, path, storage locator, signed URL, Artifact/Provider raw response 금지
- lifecycle: `IN_PROGRESS`, `COMPLETED` 유지; 실패 응답 cache는 구현하지 않음

기존 `complete()`와 resource replay는 Voice Enrollment, CompositionSnapshot, Workspace Job 호환성을 위해 유지한다. 새 revision-safe operation은 `claim_with_result()`와 `complete_with_result()`만 사용하며 completion 필드가 없거나 일부만 존재하면 성공으로 처리하지 않는다.

## Transaction 책임

Repository는 record를 Session에 반영할 뿐 `commit()`이나 `rollback()`을 호출하지 않는다. WorkingComposition Service는 domain row, revision, completion result를 하나의 `session.begin()` 경계에 둔다. split·checkout·create·delete 강제 실패 테스트에서 세 상태가 함께 rollback됨을 검증했다.

V1 allowlist는 Track restore, Clip restore, Clip unsplit/resplit과 `CLIP_COPY`를 포함한다. restore result는 복원한 canonical ID, unsplit/resplit result는 original·left·right canonical ID를 모두 보존하고 Copy result는 최초 서버 발급 `clip_id` 하나만 보존한다. 같은 key·fingerprint replay는 현재 tombstone·active 상태나 revision을 재검증하지 않고 최초 `completed_revision`과 identity를 반환한다.

initialize는 GET-or-create가 아니다. 최초 요청만 revision 0 aggregate를 만들며, 같은 key·같은 fingerprint는 최초 identity/revision을 replay한다. 다른 key 또는 새 key로 이미 존재하는 Project를 initialize하면 `WORKING_COMPOSITION_ALREADY_EXISTS`이고 성공 completion result를 남기지 않는다. DB unique race의 loser도 같은 Product conflict다.

## 현재 상태

- Revision-safe Idempotency Foundation: [완료]
- Alembic source revision: `20260825_0022`
- 실제 사용자 DB migration: [미실행], 현재 `20260810_0017`
- WorkingComposition Service/Product API: [완료], 20개 operation
- Frontend WorkingComposition consumer·Backend persistent Undo/Redo: [완료]
- Working preview/render: [완료] 같은 key replay는 최초 Job을 반환하고 새 action·retry는 새 Job identity를 사용한다.
- Composition commit: [완료] `COMPOSITION_COMMIT` payload의 최초 `composition_snapshot_id`와 `completed_revision`을 aggregate 재조회 없이 replay한다.
