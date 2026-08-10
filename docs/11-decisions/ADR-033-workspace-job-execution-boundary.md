# ADR-033 — Workspace Job 실행·claim·완료 경계

> 상태: 승인
> 작성일: 2026-08-10
> 최종 수정일: 2026-08-10
> 관련 기능: Workspace Job, cancellation, retry, Worker claim·lease와 Artifact completion
> 관련 문서: [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md), [Provider API 계약](../06-api/provider-api-contract.md), [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [ADR-028](ADR-028-provider-runtime-artifact-contract.md), [ADR-032](ADR-032-artifact-storage-resolver-integrity.md)

## 배경

Workspace Job Entity·Repository·Service 기반과 source revision `20260810_0017`의 role·scope·cancel·claim/lease Column 및 Index가 존재하며 HMAC Cursor와 Owner·Workspace scope Repository keyset page도 구현했다. 공개 API, Service state machine, Worker claim·lease와 Provider 결과를 Workspace 성공으로 확정하는 Unit of Work는 구현되지 않았다. 기존 Pipeline cancel·retry와 ThreadPool Worker는 Legacy·Compatibility Runtime 계약이며 Workspace Job 완료 근거로 사용할 수 없다.

## 문제

정확한 실행 Payload와 output role을 고정하지 않으면 같은 AssetVersion에서 임의 Artifact가 선택될 수 있다. 공개 5-state만으로 실행 중 cancel 요청을 최종 취소와 구분할 수 없고, claim·lease가 없으면 중복 Worker 실행과 crash recovery를 안전하게 처리할 수 없다. Provider `success`를 곧바로 Workspace `succeeded`로 번역하면 검증되지 않은 Payload나 부분 출력이 공개될 수 있다.

## 결정

1. 공개 상태는 `queued`, `running`, `succeeded`, `failed`, `cancelled`만 유지하고 cancel 요청은 내부 marker로 분리한다.
2. byte-level 입력은 role과 명시적 Artifact ID로 고정하며 latest/first Artifact 자동 선택을 금지한다.
3. 물리 출력은 role과 Artifact ID를 canonical JobOutput으로 사용하고 Artifact에서 AssetVersion 계보를 확인한다.
4. Retry는 원본을 초기화하지 않고 새 Job lineage로 만든다.
5. Workspace 전체 목록을 공식 Collection으로 채택하고 Job에 불변 `workspace_id`를 추가한다.
6. Worker는 atomic claim, lease와 heartbeat를 사용하고 running lease 만료 Job을 자동 queued 복귀시키지 않는다.
7. Provider 호출은 DohaMusic만 수행하고 transport idempotency는 HTTP `Idempotency-Key` header 하나만 사용한다.
8. Provider `success`와 Workspace `succeeded`를 분리한다. Workspace 성공은 trusted ingestion, Artifact·Catalog·AssetVersion·JobOutput·ModelUsage와 상태 전이가 완료된 뒤 확정한다.
9. DB·filesystem 경계는 보상 transaction으로 관리하고 부분 출력은 제거 또는 quarantine하여 정상 Artifact로 공개하지 않는다.
10. terminal Job은 History audit append 외에 변경하지 않는다.

## 선택 이유

이 결정은 Common Specification의 불변 Job·Artifact와 Provider 비직접호출 원칙을 유지하면서 로컬 SQLite·파일 Storage에서도 중복 실행, cancel race와 crash orphan을 명시적으로 처리한다. 공개 상태를 늘리지 않아 저장소 간 Job vocabulary도 유지한다.

## 대안

1. 공개 `cancel_requested` 상태 추가: 공통 5-state vocabulary와 Provider 매핑을 확장해야 하므로 제외한다.
2. AssetVersion에서 latest Artifact 자동 선택: 실행 재현성과 감사 가능성을 깨므로 제외한다.
3. 실행 중 Job을 lease 만료 후 같은 row로 자동 재실행: Provider side effect 중복 위험 때문에 제외한다.
4. Provider가 Workspace Artifact와 AssetVersion을 직접 등록: 권한·Selection·상업 이용 책임이 Provider로 누출되어 제외한다.
5. DB commit 후 파일 publish: 성공 row가 Payload 없이 노출될 수 있어 제외한다.

## 장점과 단점

- 장점: exact input·output lineage, Owner scope, cancel race, 중복 Worker와 Provider 결과 검증 경계가 명확해진다.
- 장점: Legacy Runtime을 유지한 채 additive Migration과 단계적 API 구현이 가능하다.
- 단점: 실제 DB Migration 적용과 staging Column 강화, Worker 제어, completion orchestration과 보상 테스트가 필요하다.
- 단점: filesystem과 DB의 완전한 원자성 대신 orphan reconciliation을 운영해야 한다.

## 영향

- Job API는 이 계약의 남은 Service state machine·Worker 기반과 공개 Router가 모두 구현되기 전에는 완료로 표시하지 않는다.
- Resource API는 계속 25/64, Job API는 0/5다.
- source head와 실제 사용자 DB는 `20260810_0017`이며 metadata는 36개 Table로 유지한다.
- Legacy Runtime Table 14개와 기존 Worker·Pipeline은 source of truth를 유지한다.
- Backend Foundation과 Generative AI Track은 아직 완료·OPEN 상태가 아니다.

## 마이그레이션

revision `20260810_0017`에서 Workspace scope, input/output role, cancellation marker, claim·lease·heartbeat·attempt와 공개 keyset Index 4개·Worker Index 2개를 additive하게 구현하고 Inventory·backup·restore·migration rehearsal과 명시적 승인 뒤 실제 사용자 DB에 적용했다. 기존 row 보존을 위해 scope와 role은 nullable staging으로 두며 새 Job 생성은 Workspace scope를 기록한다. 의미 기반 role backfill·`NOT NULL` 강화는 별도 검증과 승인 절차를 다시 거친다.

## 재검토 조건

- 외부 durable Queue가 claim·lease의 authoritative owner가 될 때
- PostgreSQL 전환으로 `SKIP LOCKED` 등 claim primitive가 바뀔 때
- Provider callback·event stream 또는 분산 transaction을 도입할 때
- 하나의 Workspace Job이 여러 Provider invocation을 병렬 소유해야 할 때

## 관련 PR

- Workspace Job Foundation 계약을 추가한 `develop` 대상 문서 PR
- source revision `20260810_0017`과 Job schema·Index를 추가하는 `develop` 대상 구현 PR
