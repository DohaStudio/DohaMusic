# Revision-safe Idempotency Completion Result

> 문서 상태: [완료]
> 최종 수정일: 2026-08-25
> 관련 기능: WorkingComposition mutation replay 선행 기반
> 관련 문서: [ADR-047](../11-decisions/ADR-047-revision-safe-idempotency-completion-result.md), [ADR-040](../11-decisions/ADR-040-canonical-track-clip-working-composition-authority.md), [Table Definition](../07-database/table-definition.md)

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

Repository는 record를 Session에 반영할 뿐 `commit()`이나 `rollback()`을 호출하지 않는다. 후속 WorkingComposition Service는 domain row, revision, completion result를 하나의 `session.begin()` 경계에 둔다. 강제 실패 시 세 상태가 모두 rollback되어야 한다.

## 현재 상태

- Revision-safe Idempotency Foundation: [완료]
- Alembic source revision: `20260825_0022`
- 실제 사용자 DB migration: [미실행], 현재 `20260810_0017`
- WorkingComposition Service/Product API: [미구현], 다음 작업
