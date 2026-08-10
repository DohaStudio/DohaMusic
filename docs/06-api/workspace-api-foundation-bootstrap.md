# Workspace API 공통 기반과 Bootstrap

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-10
> 관련 기능: Workspace REST API 선행 기반과 단일 사용자 기본 Workspace 준비
> 구현 상태: 공통 기반·명시적 도구·HMAC Cursor와 Workspace·MusicProject·ProjectAsset·Asset·AssetVersion·Artifact·CompositionSnapshot Resource Endpoint 25개 구현, 실제 Bootstrap 미수행
> 관련 문서: [공통 계약](workspace-rest-api-contract.md), [Endpoint 목록](workspace-rest-api-endpoints.md), [API 전환 전략](api-contract-migration-strategy.md), [DB 전환 전략](../07-database/database-redesign-migration-strategy.md)

## 1. 범위

이 문서는 Workspace Resource API 구현 전에 마련한 transport 계약과 기본 Workspace 생성 경계를 설명하고 현재 연결 상태를 함께 기록합니다.

- `/api/v1` Router namespace와 Workspace·MusicProject Router
- 성공·Collection·오류 Pydantic v2 Schema
- request ID 생성·전달
- 기존 `AppError`·validation·내부 오류의 v1 payload 분기
- 단일 사용자 기본 Workspace의 명시적 Bootstrap CLI

Workspace·MusicProject·ProjectAsset·Asset·AssetVersion·Artifact·CompositionSnapshot 25개 Resource Endpoint는 `[완료]`이며 나머지 39개는 `[미구현]`입니다. 임시 상태 Route는 추가하지 않습니다.

## 2. Router와 응답 계약

최상위 Router는 기존 Runtime Route를 `/api`에 그대로 유지하고 `backend.api.v1.router`를 `/api/v1`에 연결합니다. CompositionSnapshot을 포함한 25개 Resource Operation 추가 후 등록 Route는 70개, `APIRoute`는 66개이며 기존 Runtime 경로 수는 유지됩니다.

단일 성공 응답은 `data`, `request_id`를 사용합니다. Collection 응답은 `data`, `pagination`, `links`, `request_id`를 사용하며 `pagination`은 `limit`, `next_cursor`, `has_more`를 가집니다. 오류는 다음 구조입니다.

```json
{
  "error": {
    "error_code": "RESOURCE_NOT_FOUND",
    "message": "Workspace를 찾을 수 없습니다.",
    "details": [],
    "request_id": "opaque-request-id"
  }
}
```

SQLAlchemy Entity를 직접 JSON으로 반환하지 않습니다. v1 공통 Schema와 별도로 Workspace·MusicProject allowlist DTO를 정의했고 내부 소유권·삭제·ORM 관계 필드는 노출하지 않습니다.

## 3. request ID

- Header 이름은 `X-Request-ID`입니다.
- 첫 문자가 영숫자이고 전체가 ASCII 영숫자·점·밑줄·콜론·하이픈으로 구성된 8~128자 값만 재사용합니다.
- 누락되거나 유효하지 않으면 UUID4를 생성합니다.
- `request.state.request_id`와 응답 Header에 저장하고 v1 성공·오류 payload에 포함합니다.
- 기존 Runtime payload는 변경하지 않습니다.
- process ID, DB ID, 경로와 사용자 식별정보를 포함하지 않습니다.

Middleware는 전체 앱의 correlation ID를 준비하지만 payload 분기는 `/api/v1`에만 적용합니다. Runtime API에는 Header만 추가되는 비파괴 변경입니다.

## 4. 오류 호환성

기존 `/api`는 `{error: {code, message}}` 구조를 유지합니다. `/api/v1`만 `error_code`, `message`, `details`, `request_id`를 사용합니다.

- `AppError`: 기존 status code와 안전한 code·message 유지
- `RequestValidationError`: field 위치와 오류 유형만 allowlist detail로 변환
- 내부 오류: 고정 메시지만 반환하고 exception, SQL, credential과 경로는 숨김

기존 Pipeline file Route의 OpenAPI operation ID 중복 2건은 이 단계에서 추가되거나 수정되지 않은 WARNING입니다.

## 5. Bootstrap 실행 계약

기본 동작은 계획 출력이며 DB를 열지 않습니다.

```powershell
python -m backend.cli.workspace_bootstrap `
  --database-url "<explicit-sqlite-url>" `
  --owner-id "<stable-owner-uuid>" `
  --name "기본 Workspace"
```

실제 row 생성은 운영자가 명시적으로 `--apply`를 추가해야 합니다.

```powershell
python -m backend.cli.workspace_bootstrap `
  --database-url "<explicit-sqlite-url>" `
  --owner-id "<stable-owner-uuid>" `
  --name "기본 Workspace" `
  --apply
```

`--database-url`을 생략하면 명시적으로 설정된 `DATABASE_URL`만 사용합니다. 애플리케이션의 상대 기본값을 사용하거나 DB를 자동 탐색하지 않습니다. 실제 운영 URL과 개인 경로는 문서·로그에 기록하지 않습니다.

## 6. owner와 멱등성

인증·로컬 Owner 자동 식별 계약이 아직 없으므로 `--owner-id`는 필수 UUID입니다. 이메일·사용자명에서 UUID를 만들거나 실행마다 임의 값을 생성하지 않습니다.

Bootstrap은 `WorkspaceService.bootstrap_default_workspace()`의 단일 transaction을 사용합니다.

1. 삭제되지 않은 Workspace를 최대 2개 조회합니다.
2. 하나이고 명시한 owner와 일치하면 이름과 무관하게 기존 Workspace를 반환합니다.
3. 하나지만 owner가 다르면 잘못된 기본 Workspace를 반환하지 않고 중단합니다.
4. 없으면 trim한 이름으로 활성 Workspace 하나를 생성합니다.
5. 둘 이상이면 임의 선택하지 않고 중단합니다.
6. Soft Delete된 Workspace는 자동 복구하지 않습니다.

Project·Asset·AssetVersion과 Runtime Table row는 생성하거나 변경하지 않습니다. Workspace Table에는 owner 단위 Unique Constraint가 없으므로 동시 CLI 실행의 최종 DB 방어와 재시도 정책은 후속 검토가 필요합니다.

## 7. 적용 사전 조건

`--apply`는 다음 조건을 모두 확인합니다.

- 명시적 SQLite URL
- 기존 SQLite 파일 또는 명시적 in-memory 테스트 DB
- `alembic_version` Table 존재
- revision이 정확히 `20260807_0013`
- `workspaces` Table 존재

Schema 생성, Alembic upgrade, Runtime Table 조회·수정과 앱 startup 자동 생성을 수행하지 않습니다. 이번 작업에서는 실제 사용자 DB에 Bootstrap을 실행하지 않습니다.

## 8. Idempotency-Key 후속 판단

현행 `idempotency_records`는 Guided Voice Enrollment와 CompositionSnapshot 생성에서 사용합니다. CompositionSnapshot은 effective Owner·Project scope, canonical body fingerprint, Resource 재조회 replay와 24시간 보존을 구현했지만 다음 일반 Workspace API 계약은 아직 전체 Resource에 확정되지 않았습니다.

- Workspace·actor·HTTP Method·정규화 Path scope
- canonical request fingerprint
- 응답 body 또는 Resource 재조회 기반 replay
- Workspace Job과 Legacy Job의 namespace 분리
- 보존·정리·충돌 정책

따라서 Bootstrap은 owner 기반 조회로 자체 멱등성을 보장합니다. CompositionSnapshot POST는 필수 `Idempotency-Key`를 연결했으며 다른 Resource POST의 공통 연결은 별도 PR이 필요합니다.

## 9. Cursor pagination 후속 판단

기존 내부 Workspace Repository는 호환성을 위해 `limit`·`offset`을 유지하지만 이를 API cursor로 노출하지 않습니다. HMAC-SHA256 기반 Cursor codec과 Workspace·Project의 `(created_at DESC, UUID DESC)` keyset Repository·Service 기반은 구현했으며, versioned opaque base64url payload는 다음 값을 포함합니다.

- Resource type
- sort와 방향
- filter fingerprint
- 마지막 `created_at`
- 마지막 Resource UUID

Client 변조를 막기 위해 환경별 전용 비밀키로 HMAC 서명을 검증하며 비밀키가 없는 unsigned cursor는 허용하지 않습니다. `CursorCodec`의 App Composition 등록, keyset 복합 Index 실제 적용과 Workspace·Project 목록 API 연결은 완료했습니다.

## 10. 후속 순서

1. Idempotency scope·fingerprint·replay 계약
2. HMAC 서명 cursor codec과 Repository·Service keyset 기반 — [완료]
3. 기본 Workspace 실제 실행의 별도 운영 승인
4. 읽기 전용 Workspace Resource Route — [완료]
5. Project mutation Route — [부분 완료: Project 5개 완료, Asset·History·Idempotency 미구현]
6. Artifact Resolver와 Job dispatch 이후 관련 Endpoint
