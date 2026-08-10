# Workspace Job Service Foundation 검증

> 문서 상태: [완료]
> 검증일: 2026-08-10
> 기준 브랜치: `feature/job-service-foundation`
> 기준 revision: `20260810_0017`

## 검증 범위

- 공식 7개 Job type과 type별 Snapshot·input role Matrix
- effective Owner·Workspace·Project·ProjectAsset 범위
- exact `asset_version_id XOR artifact_id`와 Artifact lineage
- queued 초기값, succeeded를 제외한 상태 전이, 단조 progress와 bounded stage
- queued 즉시 취소, running cancel marker와 상태 기반 반복 취소
- 실패·취소 원본의 frozen retry와 `retry_of_job_id` lineage
- Owner 단위 create/retry action scope와 Workspace·Project·원본 Job을 포함한 canonical fingerprint
- 동일 요청 replay, 프로젝트·Workspace·원본 Job 교차 key conflict와 rollback
- ordered JobInput·JobOutput·ModelUsage aggregate read

## 결과

| 항목 | 결과 |
|---|---|
| 신규 Job Service 테스트 | 11 passed |
| Job Cursor·Workspace Service 회귀 | 20 passed |
| Job schema migration·Repository 회귀 | 10 passed |
| CompositionSnapshot 회귀 | 24 passed |
| Artifact 접근·reconciliation 회귀 | 36 passed |
| API Foundation·Workspace/Project 회귀 | 20 passed |
| 합계 | 121 passed |
| Python compile | PASS |
| Ruff lint·format | PASS |
| Metadata | 36개 Table 유지 |
| Alembic | `20260810_0017`, 신규 revision 없음 |
| API surface | 변경 없음, Job API 0/5·Resource API 25/64 |
| 실제 사용자 DB·Artifact 접근 | 미수행 |

## Transaction과 경계

Service가 transaction을 소유하고 Repository는 `commit()`·`rollback()`을 호출하지 않는다. create/retry 멱등성 scope는 endpoint action과 effective Owner namespace로 고정하고, authoritative Workspace·Project·원본 Job과 frozen 요청 값은 fingerprint로 비교한다. Job·ordered JobInput·멱등성 record 중 하나가 실패하거나 동일 key가 다른 요청에 재사용되면 임시 SQLite 검증에서 부분 row가 남지 않았다. 요청 Provider·Manifest는 Job에만 저장하며 실제 `ModelUsage`는 Completion Unit of Work 전에는 만들지 않는다.

## 남은 범위

- Worker atomic claim·lease·heartbeat와 crash recovery
- Artifact trusted ingestion을 포함한 Completion Unit of Work와 `succeeded` 전이
- Provider 호출과 실제 `ModelUsage` 기록
- 공개 Job Router/API 5개
- nullable staging scope·role의 의미 기반 backfill과 강화

따라서 Backend Foundation과 Generative AI Track은 아직 완료 또는 OPEN 상태가 아니다.

기존 OpenAPI file route의 operation ID 중복 경고 2건은 이번 범위 밖의 알려진 WARNING으로 유지한다. 여러 회귀 파일을 한 번에 실행한 최초 묶음은 환경 시간 제한으로 결과를 회수하지 못했으며, 위 표의 파일 단위 재실행 결과만 PASS 근거로 사용했다.
