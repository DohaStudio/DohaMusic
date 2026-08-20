# ADR-036: Provider Job identity를 별도 불변 binding history로 저장

- 상태: 승인
- 날짜: 2026-08-20

## Context

Workspace Job은 Provider 요청 snapshot과 lifecycle을 보존하지만 실제 Provider `job_id`를 영속화하지 않았다. DohaVocal retry는 새 Provider Job identity를 만들므로 Workspace Job의 단일 column은 실행 이력을 잃는다. Worker 재시작 후 in-memory 값에 의존하지 않고 기존 Provider Job을 다시 찾아야 한다.

## Decision

DohaMusic에 generic `ProviderJobBinding` 1:N table을 추가한다.

- identity는 `(provider_id, provider_job_id)`이며 pair만 unique다.
- 각 binding은 `workspace_job_id`를 `RESTRICT` FK로 참조한다.
- retry는 새 binding이며 `retry_of_provider_job_id`가 같은 Provider identity를 참조한다.
- binding history는 create/read-only application surface로 취급한다.
- Provider status를 복제하지 않으며 Provider Runtime을 상태 authority로 유지한다.
- Owner·Project scope는 Workspace Job을 먼저 확인하여 검증한다.
- attempt 번호와 active flag는 저장하지 않는다.

## Consequences

Worker crash/restart 시 Workspace Job ID로 전체 history 또는 latest identity를 복구할 수 있고 retry lineage를 감사할 수 있다. DB UNIQUE·FK·CHECK가 duplicate, unknown/cross-provider parent와 self retry를 fail-closed한다. 기존 Job은 binding 없이 유효하며 backfill이 필요 없다.

반면 Provider CreateJob 성공과 binding commit 사이 crash window는 남는다. 후속 Worker orchestration은 stable idempotency/recovery 계약을 사용해야 한다. 동시 retry 중 어느 실행이 active인지, polling과 terminal observation, Artifact ingestion은 이 ADR의 범위가 아니다.

## Rejected alternatives

- `jobs.provider_job_id` 단일 column: retry 1:N history를 표현하지 못한다.
- Provider 상태 snapshot 저장: stale cache가 DohaMusic을 잘못된 상태 authority로 만든다.
- application 사전 조회만으로 duplicate 방지: concurrent insert race를 막지 못한다.
- binding attempt 번호: Worker serialization 정책 없이 race-safe 의미를 확정할 수 없다.
