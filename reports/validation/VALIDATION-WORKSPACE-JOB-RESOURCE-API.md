# Workspace Job Resource API 검증 보고서

> 문서 상태: [완료: 구현 브랜치 검증] / [진행 중: develop 병합 대기]
> 검증일: 2026-08-11
> 기준 브랜치: `feature/job-resource-api`
> 기준 Alembic: `20260810_0017`
> 관련 문서: [Workspace Job Foundation](../../docs/03-architecture/workspace-job-foundation.md), [Job API](../../docs/06-api/job-api.md), [Workspace REST API 계약](../../docs/06-api/workspace-rest-api-contract.md)

## 1. 검증 범위

공식 Workspace Job Endpoint 다섯 개를 기존 `JobService`에 연결했다.

| Method | Path | 결과 |
|---|---|---|
| `GET` | `/api/v1/jobs` | PASS |
| `POST` | `/api/v1/jobs` | PASS |
| `GET` | `/api/v1/jobs/{job_id}` | PASS |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | PASS |
| `POST` | `/api/v1/jobs/{job_id}/retry` | PASS |

Router는 HTTP parsing, Pydantic v2 DTO, effective Workspace·Owner 파생, Service 호출, 오류 매핑과 응답 변환만 담당한다. Repository·Session·`CursorCodec`, Worker·Completion UoW·Provider·Artifact filesystem을 직접 호출하지 않는다.

## 2. 공개 계약

- 목록은 `project_id`, `status`, `job_type`만 filter로 허용하고 `(created_at DESC, job_id DESC)` version 1 HMAC Cursor를 사용한다.
- 생성은 `Idempotency-Key`가 필수이며 신규 요청과 동일 replay 모두 기존 Service의 `201`을 반환한다.
- retry는 failed·cancelled 원본의 frozen request·ordered input을 새 Job으로 복제하고 신규·replay 모두 기존 Service의 `202`를 반환한다.
- queued cancel은 즉시 `cancelled`와 `200`, running cancel은 내부 marker를 기록하고 실제 `running` 상태와 `202`를 반환한다.
- 상세는 정렬된 `inputs`, `outputs`, `model_usages`와 안전한 오류만 반환한다.
- `workspace_id`, `requested_by`, `claim_token`, `claimed_by`, `lease_expires_at`, `heartbeat_at`, `attempt`, `cancel_requested_at`, 설정 원문과 storage path는 공개하지 않는다.
- HTTP 요청은 queued Job을 기록할 뿐 Worker dispatch와 Provider 호출을 시작하지 않는다.

## 3. 테스트 결과

각 묶음은 실제 사용자 DB가 아닌 격리된 임시 SQLite와 임시 Artifact root에서 실행했다.

| 검증 묶음 | 결과 |
|---|---:|
| Workspace Job API transport | 8 passed |
| Job Service·transaction·멱등성 | 11 passed |
| Completion Unit of Work | 14 passed |
| Worker execution foundation | 35 passed |
| Job Cursor·Repository Query Plan | 7 passed |
| Job schema·Migration 계약 | 2 passed |
| Workspace·Project·ProjectAsset API 회귀 | 39 passed |
| Asset·AssetVersion API 회귀 | 18 passed |
| Artifact API 회귀 | 46 passed |
| CompositionSnapshot API 회귀 | 27 passed |
| 합계 | 207 passed |

생성·재시도 validation 및 idempotency conflict에서 partial Job·JobInput·idempotency row가 남지 않는지, cancel·retry 상태 경계, Completion 다중 출력 rollback과 filesystem 보상도 기존 회귀에서 확인했다.

## 4. Query Plan과 API surface

- 10,000건 임시 fixture의 Workspace·Project·status·job type 첫·다음 page는 revision `20260810_0017`의 keyset Index를 사용했다.
- `TEMP B-TREE`: 0
- `SCAN jobs`: 0
- 전체 Route: 75
- `APIRoute`: 71
- OpenAPI Path: 53
- OpenAPI Operation: 73
- Workspace Resource API: 30/64
- Job API: 5/5
- Metadata: 36 Tables
- Alembic source head: `20260810_0017`

신규 Job operation ID 중복은 0이다. 기존 Pipeline file content·download의 GET/HEAD operation ID 중복 두 건은 이번 범위 밖의 WARNING으로 유지한다.

## 5. 상태 판정

BLOCKER는 0건이다. 다만 이 보고서는 Draft PR 브랜치 검증 결과다. develop 병합 전에는 Workspace Backend Foundation을 Complete로, Generative AI Track을 OPEN으로 표시하지 않는다. 병합 뒤 Actions와 문서 Gate가 유지되는지 별도로 확인해야 한다.

실제 DohaLM·DohaAudio·DohaVocal transport, background Worker daemon·scheduler, Runtime read switch, backfill·dual write와 Frontend는 미구현이다. 실제 사용자 DB, 실제 `DohaArtifacts`, 실제 Provider에는 접근하지 않았다.

## 6. WARNING

- 기존 Pipeline file content·download OpenAPI operation ID 중복 두 건
- Starlette TestClient의 `httpx` 호환 계층 폐기 예정 경고
- 실제 Provider transport와 production background daemon·scheduler 미구현
- Runtime Table 14개가 계속 source of truth이며 Workspace Runtime 전환 미수행
