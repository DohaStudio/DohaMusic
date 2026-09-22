# ADR-103: Durable Admission Production Composition Foundation

> 상태: [제안 — Foundation 구현, production activation 비활성]
> 작성일: 2026-09-22
> 기준 develop: `a7469a5dd8f5a3106cb258c4848b36ffd0ae3ad0` (#189 squash merge)
> 관련 결정: [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-102](ADR-102-durable-admission-orchestration-foundation.md)
> 검증: [Production Composition 검증](../10-operations/durable-admission-production-composition-validation.md)

## 결정

완성된 Durable Admission chain을 한 ceremony/request 범위에서만 선택하는 내부 `_ProductionAdmissionCompositionRoot`를 둔다. Root는 새 authority를 만들지 않고 이미 열린 exact provider graph와 caller-owned root transaction을 검증한 뒤 `_ProductionAdmissionScope`를 발급한다. Scope만 기존 `_DurableAdmissionOrchestrator` 호출을 전달하며 scope 종료·root shutdown 뒤에는 더 이상 전달하지 않는다.

검증 대상 graph는 다음 exact object identity 전체다.

`authenticated authority source → ACTIVE verifier material → Original Confirmation authenticity → live lineage/fresh journal observation → exact correlation → CurrentnessWitness handoff → AdmissionAttempt provider → external Journal Transaction Owner → Commit Reconciler → Durable Admission Orchestrator`

Graph 내부의 designation/private pin, Windows ceremony serialization, ProviderWitnessLifetime, caller Session/root transaction, 별도 external journal Session/root transaction도 동일 identity로 연결되어야 한다. subclass, duck type, 누락·교체된 component, 같은 application/journal Session 또는 같은 bound engine, nested/inactive transaction, 이미 사용된 graph, 중복 activation은 거부한다. Application DB를 external journal로 사용하는 fallback은 없다.

## Lifetime과 transaction ownership

Composition root는 application-owned이고 active/used graph registry만 소유한다. Scope와 orchestrator graph는 ceremony/request-owned다. caller는 source handle, Windows lease, CurrentnessWitness와 caller Session/root transaction의 정상 teardown을 소유한다. External Journal Transaction Owner만 external journal commit/rollback을 소유한다. Composition은 어느 Session에도 commit, rollback, flush, SQL, retry 또는 repair를 수행하지 않는다.

Scope cleanup은 gate membership을 먼저 제거한다. Provider context manager보다 먼저 lifetime/lease를 강제 종료하지 않는다. 그렇게 하면 부모 source cleanup의 final revalidation 순서를 파괴할 수 있기 때문이다. 대신 같은 root에서 graph identity를 영구 used로 보존해 cross-request 재활성화를 차단하고, 실제 witness/lease/handle 폐기는 기존 owner context가 수행한다.

## Unavailable 기본값과 activation 경계

`UnavailableProductionAdmissionComposition`이 production 기본값이다. source/configuration/authentication/provider가 빠져도 Fake, test fixture, in-memory journal, app DB, implicit local owner 또는 no-op lock을 선택하지 않고 항상 `PRODUCTION_ADMISSION_UNAVAILABLE`로 종료한다. 내부 root의 `COMPOSITION_ROOT_READY`는 wiring Foundation 검증 상태일 뿐 production runtime active를 뜻하지 않는다.

현재 저장소에는 reviewed production private source factory, external journal provisioning/configuration, operational production authentication adapter가 없다. 따라서 FastAPI startup, Worker/runtime, API dependency에는 이 root를 연결하지 않는다. 실제 key·credential·trust root를 생성하거나 config/env/request로 provider를 선택하지 않는다.

## 비목표와 다음 dependency

Public API, frontend, Worker/runtime execution, Rights Writer/Adapter, Recovery/Transfer, production credential provisioning, schema/migration은 변경하지 않는다. Existing external journal schema v1과 Alembic `20260918_0037` single head를 유지한다.

다음 dependency는 reviewed deployment configuration과 private source/external journal factory가 exact installation·journal·source identity를 제공하고 production authentication gate와 함께 이 ceremony-scoped root를 호출하는 별도 wiring 결정이다. 실제 external authority가 준비되기 전 production activation은 계속 unavailable이다.
