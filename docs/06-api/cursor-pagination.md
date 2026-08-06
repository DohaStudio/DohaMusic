# HMAC Cursor Pagination 설계

> 문서 상태: [완료]
> 최종 수정일: 2026-08-06
> 관련 기능: Workspace v1 목록의 opaque cursor와 keyset 조회 기반
> 구현 상태: codec·설정·Workspace와 Project Repository·Service page 완료, Resource Endpoint 미구현
> 관련 문서: [Workspace REST API 계약](workspace-rest-api-contract.md), [API 전환 전략](api-contract-migration-strategy.md), [Backend 아키텍처](../03-architecture/backend-architecture.md)

## 1. 목적과 범위

Workspace v1 목록은 외부에 offset을 노출하지 않고 안정적인 keyset pagination을 사용합니다. 이 단계는 공통 cursor와 Workspace·Project 조회 기반만 구현하며 `/api/v1` Resource Router, 인증, Idempotency, 실제 사용자 DB 작업은 포함하지 않습니다.

## 2. 서명 키

`DOHAMUSIC_CURSOR_SIGNING_KEY`는 Cursor 전용 비밀값이며 UTF-8 기준 32바이트 이상이어야 합니다. 자동 생성값이나 Production 기본값을 제공하지 않고 Pydantic `SecretStr`로 보관합니다. 기존 Runtime과 Bootstrap은 cursor가 필요하지 않으므로 앱 시작을 막지 않으며 `CursorCodec` 구성 또는 page 기능 사용 시점에 검증합니다.

실제 비밀값은 Git·문서·오류·로그에 기록하지 않습니다. `backend/.env.example`에는 설정 위치를 설명하는 placeholder만 둡니다. JWT 등 다른 목적의 비밀키와 공유하지 않습니다.

## 3. 토큰 계약

토큰 형식은 다음과 같습니다.

```text
base64url(canonical-json-payload).base64url(hmac-sha256-signature)
```

Payload 필드는 다음으로 고정합니다.

| 필드 | 값 |
|---|---|
| `v` | `1` |
| `resource` | `workspace` 또는 `project` |
| `direction` | `next` |
| `sort` | `created_at_desc` |
| `last_created_at` | 직전 page 마지막 row의 UTC ISO 8601 시각 |
| `last_id` | 직전 page 마지막 row의 UUID |
| `filter_hash` | canonical filter JSON의 SHA-256 |
| `limit` | 1~100의 page 크기 |

Payload에 owner·Workspace 이름·Project 제목·DB 경로·Table명·SQL·credential을 넣지 않습니다. Base64url은 암호화가 아니므로 민감한 filter 원문도 넣지 않고 hash만 저장합니다.

## 4. 검증과 오류

Decode는 token 구조와 base64url, `compare_digest` 기반 서명, 정확한 payload field 집합, version, Resource, 방향, 정렬, UUID, timezone이 있는 datetime, filter fingerprint와 limit을 검증합니다. 실패 원인은 내부 `reason`으로만 구분하며 외부에는 `422 INVALID_CURSOR`와 고정 메시지만 제공합니다.

서명 키가 없거나 짧으면 `500 CURSOR_CONFIGURATION_ERROR`, 요청 limit이 범위를 벗어나면 `422 INVALID_LIMIT`입니다. 서명값과 payload 원문을 오류에 포함하지 않습니다.

## 5. Filter fingerprint

Workspace fingerprint는 `include_deleted=false`, 정렬과 내부 owner filter를 사용합니다. Project fingerprint는 `workspace_id`, `include_deleted=false`와 정렬을 사용합니다. JSON key 정렬과 공백 없는 canonical 직렬화 뒤 SHA-256을 계산하므로 다른 Workspace·owner·정렬 조건에 cursor를 재사용할 수 없습니다.

## 6. Keyset 조회

정렬은 공통 계약에 따라 `(created_at DESC, UUID DESC)`입니다. 다음 page 조건은 아래와 같습니다.

```text
created_at < last_created_at
OR (created_at = last_created_at AND resource_id < last_id)
```

Repository는 SQLAlchemy 2.0 `select()`만 사용하고 Soft Delete row를 제외합니다. 기존 내부 `limit`·`offset` 메서드는 호환성을 위해 유지하지만 API용 page Service는 `list_*_after()`만 사용합니다.

Service는 `limit + 1`개를 조회해 `has_more`를 계산하고 응답 항목은 `limit`개로 자릅니다. 다음 row가 있으면 마지막 반환 row로 서명된 `next_cursor`를 만들고, 마지막 page와 빈 page에서는 `has_more=false`, `next_cursor=null`을 반환합니다.

## 7. 후속 작업

1. App composition에서 환경 설정으로 `CursorCodec`을 구성합니다.
2. Workspace·Project Resource 목록 Route에 `limit`과 `cursor`를 연결합니다.
3. 공통 Collection Envelope의 `has_more`와 `next_cursor` 불변 조건을 API 테스트로 검증합니다.
4. 운영 전 서명 키 교체와 cursor 만료 정책을 확정합니다.

Resource Endpoint, Idempotency replay, 인증·권한, Frontend, backfill·dual write는 별도 PR 범위입니다.
