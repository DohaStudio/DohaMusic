# Provider Job Persistence Contract

> 문서 상태: [구현]
> 최종 수정일: 2026-08-20
> 관련 문서: [Workspace Job Foundation](workspace-job-foundation.md), [DohaVocal Consumer Contract](dohavocal-consumer-contract.md), [ADR-036](../11-decisions/ADR-036-provider-job-persistence.md)

## 1. 목적과 권위

DohaMusic은 `provider_job_bindings`에 Workspace Job과 Provider 실행 identity의 관계만 영속화한다. Provider 상태와 결과의 권위는 계속 Provider Runtime에 있다. 따라서 binding에는 `queued`·`running`·terminal 상태나 마지막 polling 시각을 복제하지 않는다.

```text
Workspace Job 1
  └─ N ProviderJobBinding
       ├─ provider_id
       ├─ provider_job_id
       └─ retry_of_provider_job_id (optional)
```

기존 Job은 binding이 없어도 정상이다. 아직 dispatch되지 않았거나 이 revision 이전에 생성된 Job을 자동 실패로 바꾸거나 backfill하지 않는다.

## 2. 저장 계약

| 항목 | 계약 |
|---|---|
| PK | `provider_job_binding_id` UUID |
| Workspace 연결 | `workspace_job_id → jobs.job_id`, `ON DELETE RESTRICT` |
| Provider identity | `(provider_id, provider_job_id)` UNIQUE |
| Retry lineage | 같은 Provider의 기존 identity를 가리키는 composite self FK |
| History order | `(workspace_job_id, created_at, provider_job_binding_id)` |
| Mutation | create/read만 제공하며 identity update·delete API 없음 |
| 상태 | 저장하지 않음. Provider Runtime이 authority |

`provider_job_id` 단독 global uniqueness는 가정하지 않는다. 같은 opaque job ID는 서로 다른 Provider namespace에서 존재할 수 있다. `UNIQUE(workspace_job_id)`도 두지 않아 한 Workspace Job의 여러 Provider retry 실행을 보존한다.

attempt/sequence는 넣지 않았다. 동시 retry 발급에서 race-safe sequence allocation과 단일 active execution 정책은 Worker orchestration과 함께 결정해야 하기 때문이다. `latest`는 가장 최근에 기록된 identity를 재조회하기 위한 deterministic convenience이며 active/terminal 판정이 아니다.

## 3. Service와 transaction

`ProviderJobPersistenceService`가 transaction을 소유하고 Repository는 `flush()`만 한다. 생성 transaction 안에서 다음을 검증한다.

1. Workspace Job이 effective Owner의 활성 Workspace에 속한다.
2. binding의 `provider_id`가 Job의 `provider_id`와 일치한다.
3. logical identifier만 허용하고 URL·절대 경로·raw payload 형태는 거부한다.
4. retry parent가 존재하며 같은 Provider와 같은 Workspace Job에 속한다.
5. insert를 flush하고 DB UNIQUE/FK/CHECK 충돌을 fail-closed 처리한다.

Owner가 다른 Job은 존재 여부를 노출하지 않고 `Workspace Job not found`로 취급한다. Project scope는 immutable Job의 `project_id`·`workspace_id` 관계를 통해 유지된다. caller가 `provider_job_id`만으로 임의 Owner의 binding을 읽는 Service API는 없다.

Repository는 identity 조회, binding ID 조회, Job별 전체 history와 latest 조회를 제공한다. 새 Service/Session 인스턴스도 DB에서 같은 identity를 복구하므로 in-memory cache는 authority가 아니다.

## 4. Retry와 race

retry는 기존 row를 갱신하지 않고 새 binding을 append한다.

```text
W1 → P1
W1 → P2 (retry_of=P1)
```

self retry, unknown parent, cross-Workspace Job retry, cross-Provider retry는 서로 구분 가능한 application reason으로 거부한다. 동일 `(provider_id, provider_job_id)` 동시 등록은 사전 조회와 무관하게 DB UNIQUE constraint가 차단한다.

같은 Workspace Job에 서로 다른 retry가 동시에 생성되는 것은 이 persistence 계층에서 금지하지 않는다. 어떤 실행을 발급하고 poll할지는 후속 Worker/ProviderDispatcher의 claim·idempotency·serialization 정책이 책임진다.

## 5. Crash window와 후속 작업

```text
Provider CreateJob success
  → Worker crash
  → binding insert 미수행
```

외부 HTTP side effect와 DohaMusic DB commit은 하나의 transaction이 아니므로 이 window는 이번 PR만으로 제거할 수 없다. 후속 Worker wiring은 Workspace Job 기반 stable Provider idempotency key로 CreateJob을 재조회/재생하고, 응답 identity를 즉시 `create_binding_for_owner()`에 저장해야 한다. 새 Provider Job을 무조건 다시 생성해서는 안 된다.

이번 구현에는 공개 API, Worker wiring, Provider 호출·polling·cancel/retry 호출, Artifact ingestion, Completion UoW 변경이 없다.

## 6. Migration과 운영

Alembic `20260821_0019`는 `provider_job_bindings` 한 개를 additive하게 생성한다. 기존 Job row backfill은 없다. downgrade는 self-FK history를 제거한 뒤 table을 삭제하며 기존 Job row는 보존한다.
