# ADR-047 — Revision-safe Idempotency Completion Result 권위

> 상태: 승인
> 작성일: 2026-08-25
> 최종 수정일: 2026-08-25
> 관련 기능: AI-native DAW D3 WorkingComposition mutation 선행 기반
> 관련 문서: [ADR-040](ADR-040-canonical-track-clip-working-composition-authority.md), [Idempotency Completion Result](../03-architecture/idempotency-completion-result.md), [Database Table Definition](../07-database/table-definition.md)

## 1. 배경

ADR-040은 성공한 WorkingComposition mutation이 완료 revision을 반환하고 같은 `Idempotency-Key`와 fingerprint가 최초 결과를 재생하도록 요구한다. 기존 `idempotency_records`는 단일 `resource_type`, `resource_id`, `response_status`만 저장하므로 split의 두 자식 Clip, checkout의 base Snapshot, commit의 Snapshot과 당시 완료 revision을 함께 보존할 수 없다. 현재 aggregate를 다시 읽으면 후속 mutation 뒤 최초 revision이 달라지므로 faithful replay가 아니다.

## 2. 결정

`idempotency_records`를 HTTP response cache가 아니라 **mutation completion fact와 versioned replay result**의 저장소로 확장한다. 기존 필드는 유지하고 다음 nullable 필드를 additive하게 추가한다.

| 필드 | 의미 |
|---|---|
| `completed_revision` | 최초 성공 transaction에서 확정된 WorkingComposition revision |
| `result_type` | 내부 allowlist의 mutation 결과 종류 |
| `result_version` | payload 해석 version, 최초 값 `1` |
| `result_payload` | operation별 최소 Product identity만 담는 bounded JSON object |

새 mutation은 `complete_with_result()`로 이 값을 domain mutation·revision 증가와 같은 Service-owned transaction에 기록한다. Repository는 `flush()` 참여만 하며 commit과 rollback을 호출하지 않는다.

## 3. 결과 계약

V1 result type은 다음 여덟 개만 허용한다.

- `WORKING_COMPOSITION_INITIALIZE`
- `WORKING_COMPOSITION_CHECKOUT`
- `TRACK_CREATE`, `TRACK_DELETE`
- `CLIP_CREATE`, `CLIP_SPLIT`, `CLIP_DELETE`
- `COMPOSITION_COMMIT`

각 payload는 계약에 정의된 canonical UUID key만 허용한다. split은 `original_clip_id`, `left_clip_id`, `right_clip_id`를 보존한다. checkout은 `working_composition_id`, `base_composition_snapshot_id`, commit은 `composition_snapshot_id`를 보존한다. payload는 canonical UTF-8 JSON 기준 8,192 bytes 이하이고 arbitrary key, aggregate dump, path, locator, credential, signed URL, Provider response를 허용하지 않는다.

## 4. Replay와 실패

- same key + same fingerprint + 완전한 `COMPLETED`: 저장된 typed result를 반환한다.
- 현재 aggregate revision이나 현재 Resource 상태를 다시 계산하지 않는다.
- same key + different fingerprint: 기존 `IDEMPOTENCY_CONFLICT` 내부 계약을 유지한다. 공개 `IDEMPOTENCY_KEY_REUSED` mapping은 후속 Product Service/API가 담당한다.
- `IN_PROGRESS`: 기존 `IDEMPOTENCY_IN_PROGRESS`를 유지한다.
- unknown version, unknown type, schema 불일치, 일부 필드만 있는 결과: fail-closed한다.
- validation·revision conflict 등 실패 응답은 저장하지 않는다. 현재 권위는 성공 mutation replay만 다룬다.

## 5. Legacy 호환성

기존 `complete()`와 `resource_type/resource_id/response_status` consumer는 변경하지 않는다. 새 Column은 nullable이며 기존 `COMPLETED` row에 결과를 추측해 backfill하지 않는다. 기존 API는 기존 resource replay를 계속 사용할 수 있지만 새 revision-safe operation은 completion result가 없는 legacy row를 성공 replay로 해석하지 않는다.

## 6. 대안

1. **JSON만 저장**: revision 검색·무결성 의미가 불명확해 제외했다.
2. **revision·primary resource + auxiliary JSON**: 채택했다. 기존 Resource replay 호환성과 복수 identity 표현을 함께 보존한다.
3. **operation별 child table**: V1 결과가 작고 종류가 제한적인데 join·migration 수가 과도해 제외했다.
4. **`resource_id`에 JSON·쉼표 연결 저장**: 길이·타입·호환성을 깨고 schema를 숨기므로 금지한다.

## 7. 영향과 재검토

Alembic `20260825_0022`는 네 nullable Column과 revision/version CHECK만 추가하고 실제 사용자 DB, Artifact, media에 접근하지 않는다. WorkingComposition Service/API는 이번 결정의 소비자이지만 이 ADR 구현 범위에는 포함하지 않는다. error replay, 새로운 result version, aggregate 전체 replay가 필요해지면 별도 authority를 승인한 뒤 재검토한다.
