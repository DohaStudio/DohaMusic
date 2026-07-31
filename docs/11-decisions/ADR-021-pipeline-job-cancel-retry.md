# ADR-021 — Pipeline Job Cancel·Retry

> 상태: 승인
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Pipeline Job Cancel·Retry
> 관련 문서: [Pipeline API](../06-api/pipeline-api.md), [Pipeline Orchestrator](../03-architecture/pipeline-orchestrator.md), [ADR-020](ADR-020-project-history-retention.md)

## Context

로컬 단일 사용자 Studio에서 대기·실행 중 작업을 안전하게 취소하고 실패·취소 작업을 같은 입력으로 다시 만들 수 있어야 한다. 기존 in-process ThreadPool과 Provider subprocess는 Job별 안전한 process ownership handle을 제공하지 않는다.

## 결정

1. 대기 Job은 즉시 `CANCELLED`, 실행 Job은 `CANCEL_REQUESTED` 후 `CANCELLED`로 전이한다.
2. Worker는 Job 시작, 각 단계 전후, 결과 저장 전에 DB 취소 상태를 확인한다.
3. Provider 실행을 무조건 kill하지 않고 현재 단계 반환 뒤 정리하는 cooperative cancellation을 사용한다.
4. 취소된 부분 출력은 삭제하고 최종 Result와 다운로드 capability를 공개하지 않는다.
5. Retry는 원본 상태를 되돌리지 않고 `PipelineCreate` 검증을 재사용해 새 Job을 만든다.
6. 공개 입력을 `input_snapshot`에 보존하고 동일 Seed, Voice Profile, Project를 재검증한다.
7. `retry_of_job_id` self FK로 원본 관계를 기록하며 원본 제거 시 `SET NULL`이다.
8. 같은 원본의 중복 Retry 요청은 기존 재시도 Job을 반환한다.

## Result commit race

Worker는 최종 metadata·파일 저장 직전까지 취소를 재확인한다. 취소 commit이 먼저 관찰되면 Result를 공개하지 않는다. 완료 commit이 먼저 확정되면 `COMPLETED`를 유지하고 이후 Cancel은 `409`다. 로컬 SQLite·단일 Worker 범위를 넘는 분산 원자성은 보장하지 않는다.

## Project·History 정책

취소 Job은 기록에서 삭제하지 않는다. Retry Job은 원본 Project를 유지하고 Project가 없어졌다면 Default Project 정책을 사용한다. History에는 원본과 새 Job을 각각 표시한다.

## 장점과 단점

- 장점: 기존 상태·Service·검증 경계를 유지하고 손상 결과 공개를 막는다.
- 단점: 실행 중인 긴 단일 Provider 호출을 즉시 중단하지 못하며 분산 Worker 간 취소 일관성을 제공하지 않는다.

## Storage cleanup

취소 확인 시 `PipelineContext.generated_paths()`의 부분 파일을 제거한다. 완료된 중간 진단 metadata는 DB 정책에 따라 남을 수 있지만 공개 audio capability는 `COMPLETED`에만 제공한다.

## Production conditions

인증·소유권·인가, 감사 로그, rate limit, 분산 lock·Queue, Worker lease, process ownership, 보존·삭제 재시도 정책이 필요하다. 이 결정은 공개 운영 승인이 아니다.

## Rollback

Frontend action과 신규 endpoint를 비활성화하고 migration 0009를 downgrade한다. 기존 원본 Job과 결과 파일은 삭제하지 않는다.

## 재검토 조건

다중 Worker·외부 Queue 도입, Provider 공식 cancel 지원, 안전한 subprocess handle registry 도입, Job 삭제·보존 정책 변경 시 재검토한다.
