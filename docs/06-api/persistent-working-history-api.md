# Persistent WorkingComposition History API

> 문서 상태: [완료]
> 최종 수정일: 2026-09-05
> 관련 결정: [ADR-056](../11-decisions/ADR-056-persistent-working-composition-history.md)

## 조회

`GET /api/v1/projects/{project_id}/working-composition/history?working_composition_id={id}`는
현재 revision, cursor, command count, `can_undo`, `can_redo`를 반환한다. command payload는
Backend authority이며 공개하지 않는다.

## Intent mutation

- `POST /api/v1/projects/{project_id}/working-composition/history/undo`
- `POST /api/v1/projects/{project_id}/working-composition/history/redo`

요청 body는 `working_composition_id`, `expected_revision`만 허용하고 `Idempotency-Key` header가
필수다. 성공 시 target `clip_id`, `completed_revision`, `replayed`를 반환한다. 빈 stack은
`409 WORKING_HISTORY_EMPTY`, 구조 불일치는 `409 WORKING_HISTORY_STRUCTURE_CONFLICT`, revision
불일치는 기존 `409 WORKING_COMPOSITION_REVISION_CONFLICT`를 사용한다.

동일 key와 동일 intent는 최초 completion을 replay하며 cursor와 revision을 다시 변경하지 않는다.
클라이언트는 before/after state, command type, loop phase를 제출할 수 없다.
