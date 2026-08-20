# 작업 API

> 문서 상태: [완료: 계약·Workspace Job API 5/5] / [진행 중: develop 병합 Gate]
> 최종 수정일: 2026-08-11
> 문서 목적: Legacy Runtime Job과 Workspace Job의 공개 API 범위를 분리한다.
> 관련 문서: [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md), [작업 상태 모델](../07-database/job-state-model.md), [Workspace Endpoint 목록](workspace-rest-api-endpoints.md)

## Legacy Runtime Job — [구현 완료 범위]

`GET /api/generations/{id}`와 생성·Stem·Voice·Pipeline API는 기능별 Legacy Job Table, 기존 Worker와 file row를 사용한다. Pipeline cancel·retry도 Legacy `pipeline_jobs` 계약이다. 이 완료 상태는 Workspace `jobs` Aggregate 또는 `/api/v1/jobs` 구현 완료를 의미하지 않는다.

## Workspace Job — [구현·검증 완료]

공식 API는 다음 5개다.

| Method | Path | 성공 | 상태 |
|---|---|---:|---|
| `GET` | `/api/v1/jobs` | 200 | [완료] |
| `POST` | `/api/v1/jobs` | 201 | [완료] |
| `GET` | `/api/v1/jobs/{job_id}` | 200 | [완료] |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | 200/202 | [완료] |
| `POST` | `/api/v1/jobs/{job_id}/retry` | 202 | [완료] |

JobInput·JobOutput 독립 Endpoint는 제공하지 않는다. 목록은 effective Workspace 전체를 scope로 하고 `project_id`, `status`, `job_type`만 선택 filter로 허용하며 `(created_at DESC, job_id DESC)` HMAC Cursor를 사용한다.

생성과 retry는 `Idempotency-Key`가 필수다. cancel은 반복 호출에 같은 결과를 반환하는 idempotent action이며 terminal `succeeded`·`failed`는 `409 JOB_NOT_CANCELLABLE`이다. 상세 상태·입출력·오류·진행률은 [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md)의 role·Owner·Provider·Artifact 계약을 따른다.

Job Router는 effective Workspace와 Owner를 신뢰된 context에서 파생하고 Repository·Session·CursorCodec·Worker·Provider를 직접 사용하지 않는다. 생성은 필수 `Idempotency-Key`와 Service의 원래 `201`을 재생하며 retry는 `202`를 재생한다. 상세는 정렬된 Input·Output·ModelUsage와 안전한 오류만 반환하고 claim·lease·경로·credential은 공개하지 않는다.

현재 Resource API는 30/64, Workspace Job API는 5/5다. 실제 Provider transport와 background daemon·scheduler는 미구현이며 HTTP 생성은 queued Job만 기록한다. 운영 Generative AI Track 승격은 실제 Provider·background runtime Gate를 별도로 통과해야 한다.
