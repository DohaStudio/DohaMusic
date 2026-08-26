# WorkingComposition Product API

> 문서 상태: [완료]
> 최종 수정일: 2026-08-26
> 관련 기능: AI-native DAW D3 Clip Editing Backend API와 Frontend consumer
> 관련 문서: [Service Architecture](../03-architecture/working-composition-service.md), [ADR-050](../11-decisions/ADR-050-working-composition-inverse-mutation-authority.md), [Workspace REST API](workspace-rest-api-contract.md), [Composition Read](composition-read-workspace.md)

## Endpoint

기본 namespace는 `/api/v1/projects/{project_id}/working-composition`이다.

| Method | suffix | 성공 | Idempotency-Key | 목적 |
|---|---|---:|---|---|
| `GET` | `` | 200 | 없음 | ordered active working aggregate 조회 |
| `POST` | `/initialize` | 201 | 필수 | 빈 WorkingComposition 최초 생성 |
| `POST` | `/checkout` | 200 | 필수 | immutable Snapshot arrangement 복원 |
| `POST` | `/tracks` | 201 | 필수 | audio Track 생성 |
| `PATCH` | `/tracks/reorder` | 200 | 없음 | 전체 active Track 절대 순서 적용 |
| `PATCH` | `/tracks/{track_id}` | 200 | 없음 | Track 이름 절대값 적용 |
| `DELETE` | `/tracks/{track_id}` | 200 | 필수 | 빈 Track tombstone |
| `POST` | `/tracks/{track_id}/restore` | 200 | 필수 | canonical Track을 지정 order로 복원 |
| `POST` | `/clips` | 201 | 필수 | exact AssetVersion Clip 생성 |
| `PATCH` | `/clips/{clip_id}/move` | 200 | 없음 | Timeline 시작 절대값 적용 |
| `PATCH` | `/clips/{clip_id}/trim-start` | 200 | 없음 | source/timeline 시작 절대값 적용 |
| `PATCH` | `/clips/{clip_id}/trim-end` | 200 | 없음 | source 끝 절대값 적용 |
| `POST` | `/clips/{clip_id}/split` | 200 | 필수 | original tombstone과 두 child 생성 |
| `DELETE` | `/clips/{clip_id}` | 200 | 필수 | Clip tombstone |
| `POST` | `/clips/{clip_id}/restore` | 200 | 필수 | current eligibility 검증 후 canonical Clip 복원 |
| `POST` | `/clips/{original_clip_id}/unsplit` | 200 | 필수 | exact split child를 tombstone하고 original 복원 |
| `POST` | `/clips/{original_clip_id}/resplit` | 200 | 필수 | 같은 canonical split child를 복원 |

모든 mutation body는 `working_composition_id`와 `expected_revision`을 요구한다. Clip 시간 입력은 decimal seconds이고, source duration·Artifact ID·owner·path·locator는 받지 않는다. replay 응답의 `completed_revision`과 identity는 stored completion result가 authority다.

## Initialize duplicate

- same key + same fingerprint: 최초 `working_composition_id`, `completed_revision`, `replayed=true`
- 다른/new key + existing WorkingComposition: `409 WORKING_COMPOSITION_ALREADY_EXISTS`
- duplicate conflict는 기존 WorkingComposition·Track·Clip·revision을 변경하지 않고 성공 completion result를 만들지 않는다.

## Frontend history boundary

initialize 성공은 빈 Frontend Undo/Redo history의 시작점이다. checkout 성공은 working arrangement 전체를 교체하는 history barrier이며 checkout 자체는 inverse operation이 아니다. Backend API는 command stack을 저장하거나 checkout 이전 command의 재적용을 허가하지 않는다.

Frontend consumer는 17개 operation을 중앙 API client로 호출한다. Backend 응답의 `completed_revision`을 local increment 없이 반영하고 GET으로 canonical Track·Clip aggregate를 reconcile한다. create/delete는 same-ID restore, split은 stored original·left·right identity의 unsplit/resplit을 사용하며 네트워크 응답 유실 재시도에는 동일 `Idempotency-Key`를 유지한다.

## Error

| HTTP | code | 의미 |
|---:|---|---|
| 404 | `PROJECT_NOT_FOUND` | scope-hidden Project 없음·비활성·다른 Owner |
| 404 | `WORKING_COMPOSITION_NOT_FOUND` | 명시 ID/Project의 active working 없음 |
| 404 | `TRACK_NOT_FOUND`, `CLIP_NOT_FOUND` | 대상이 없거나 다른 working scope |
| 404 | `COMPOSITION_SNAPSHOT_NOT_FOUND` | Snapshot 없음 또는 다른 Project |
| 409 | `WORKING_COMPOSITION_ALREADY_EXISTS` | 다른 key의 duplicate initialize |
| 409 | `WORKING_COMPOSITION_REVISION_CONFLICT` | expected revision CAS 실패 |
| 409 | `TRACK_NOT_EMPTY`, `TRACK_ALREADY_ACTIVE`, `TRACK_RESTORE_ORDER_INVALID`, `CLIP_ALREADY_ACTIVE`, `CLIP_OVERLAP` | Product invariant 충돌 |
| 409 | `SPLIT_STRUCTURE_CONFLICT` | split lineage·source·exact geometry 또는 상태가 최초 split 구조와 다름 |
| 409 | `IDEMPOTENCY_KEY_REUSED`, `IDEMPOTENCY_IN_PROGRESS` | key fingerprint 충돌 또는 처리 중 |
| 409 | `SOURCE_ASSET_UNAVAILABLE`, `SOURCE_ARTIFACT_AMBIGUOUS`, `SOURCE_DURATION_UNAVAILABLE` | source eligibility fail-closed |
| 409 | `SNAPSHOT_ARRANGEMENT_NOT_AVAILABLE` | immutable arrangement 없음 |
| 422 | `INVALID_CLIP_RANGE`, `INVALID_INPUT` | 정규화 이후 입력 범위 오류 |

오류는 path, storage root, locator, signed URL, credential, DB path, raw exception과 SQL constraint 이름을 반환하지 않는다.

## Surface 실측

이 Router는 APIRoute 17개, OpenAPI Path 16개, Operation 17개이며 operation ID 중복은 0개다. 전체 application은 Route 94개, APIRoute 90개, `/api/v1` APIRoute 49개, OpenAPI Path 71개, Operation 92개다. 기존 Legacy Pipeline의 GET/HEAD 병합 route 두 곳에서 발생하던 global duplicate operation ID warning 2종은 이 작업 범위에서 변경하지 않았으며, 새 WorkingComposition operation ID와의 충돌은 0개다.

이 17개는 Product API이므로 Workspace Resource Endpoint 30/64 분모에는 포함하지 않는다.
