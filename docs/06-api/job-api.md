# 작업 API

> 문서 상태: [완료: 계약] / [미구현: Workspace Job API]
> 최종 수정일: 2026-08-10
> 문서 목적: Legacy Runtime Job과 Workspace Job의 공개 API 범위를 분리한다.
> 관련 문서: [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md), [작업 상태 모델](../07-database/job-state-model.md), [Workspace Endpoint 목록](workspace-rest-api-endpoints.md)

## Legacy Runtime Job — [구현 완료 범위]

`GET /api/generations/{id}`와 생성·Stem·Voice·Pipeline API는 기능별 Legacy Job Table, 기존 Worker와 file row를 사용한다. Pipeline cancel·retry도 Legacy `pipeline_jobs` 계약이다. 이 완료 상태는 Workspace `jobs` Aggregate 또는 `/api/v1/jobs` 구현 완료를 의미하지 않는다.

## Workspace Job — [계약 완료, API 미구현]

공식 API는 다음 5개다.

| Method | Path | 성공 | 상태 |
|---|---|---:|---|
| `GET` | `/api/v1/jobs` | 200 | [미구현] |
| `POST` | `/api/v1/jobs` | 202 | [미구현] |
| `GET` | `/api/v1/jobs/{job_id}` | 200 | [미구현] |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | 200/202 | [미구현] |
| `POST` | `/api/v1/jobs/{job_id}/retry` | 202 | [미구현] |

JobInput·JobOutput 독립 Endpoint는 제공하지 않는다. 목록은 effective Workspace 전체를 scope로 하고 `project_id`, `status`, `job_type`만 선택 filter로 허용하며 `(created_at DESC, job_id DESC)` HMAC Cursor를 사용한다.

생성과 retry는 `Idempotency-Key`가 필수다. cancel은 반복 호출에 같은 결과를 반환하는 idempotent action이며 terminal `succeeded`·`failed`는 `409 JOB_NOT_CANCELLABLE`이다. 상세 상태·입출력·오류·진행률은 [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md)의 role·Owner·Provider·Artifact 계약을 따른다.

현재 Resource API는 25/64, Workspace Job API는 0/5다. 역할·Workspace scope·cancellation marker·claim/lease Column과 Index는 source revision `20260810_0017`에 구현해 실제 DB에 적용했고 Cursor·Repository keyset과 생성·상태·취소·재시도 Service 기반도 구현했다. Worker와 completion Unit of Work·Router를 구현·검증하기 전에는 이 API를 완료로 표시하지 않는다.
