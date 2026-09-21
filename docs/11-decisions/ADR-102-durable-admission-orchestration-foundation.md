# ADR-102: Durable Admission Orchestration Foundation

> 상태: 제안 — Foundation 구현/로컬 검증 완료, 운영 비활성
> 작성일: 2026-09-22
> 기준 develop: `3347a94dc0e48111f1d14a69ec1e5411c1467604` (#188 squash merge)
> 관련: [ADR-098](ADR-098-currentness-witness-handoff-foundation.md), [ADR-099](ADR-099-admission-attempt-provider-foundation.md), [ADR-100](ADR-100-admission-journal-transaction-owner-foundation.md), [ADR-101](ADR-101-admission-commit-reconciler-foundation.md), [검증](../10-operations/durable-admission-orchestration-validation.md)

## 결정

`_DurableAdmissionOrchestrator`는 이미 발급된 live CurrentnessWitness를 `_AdmissionAttemptProvider`에 전달하고, 그 provider와 exact identity로 연결된 `_AdmissionJournalTransactionOwner`, 다시 그 Owner와 연결된 `_AdmissionCommitReconciler`만 순서대로 호출하는 내부 coordinator다. Constructor는 세 component의 exact object graph를 검증한다. Orchestrator는 witness, attempt, candidate, transaction, reconciliation authority를 새로 만들거나 복제하지 않는다.

호출 순서는 다음과 같다.

1. Provider가 live witness와 strict canonical candidate를 one-shot opaque AdmissionAttempt로 결합한다.
2. Transaction Owner가 해당 attempt의 독립 journal transaction에서 CAS, append, final guard와 유일한 external commit을 소유한다.
3. Owner의 exact minted result와 현재 attempt identity를 재검증한다.
4. `COMMITTED`는 direct exact success로, `NOT_COMMITTED`는 definitive failure로 반환한다.
5. `RECONCILIATION_REQUIRED`는 같은 Owner가 mint한 opaque handoff를 Reconciler에 전달한다.
6. Reconciler가 mint한 exact result provenance를 검증하고 `COMMITTED_EXACT`, `NOT_COMMITTED`, `CONFLICT`, `UNAVAILABLE` 중 하나로 반환한다.

Orchestrator는 journal SQL, CAS, append, flush, commit, rollback 또는 repair를 직접 수행하지 않는다. Application Repository transaction도 소유하지 않는다.

## 결과와 성공 경계

Canonical internal result는 installation 집합, journal ID, attempt ID, event ID/revision/digest, expected predecessor와 semantic revision, correlation digest를 기존 immutable reconciliation identity로 보존하고 결과 provenance를 별도로 기록한다. Result는 audit/control-flow representation이며 credential, Rights authorization, Workspace ownership 또는 독립 authority가 아니다. Authority는 verified external journal의 exact committed fact다.

성공은 다음 두 경우뿐이다.

- `DIRECT_COMMIT`: Transaction Owner의 authenticated `COMMITTED`
- `RECONCILED_COMMIT`: exact handoff에 대한 authenticated `COMMITTED_EXACT`

둘은 orchestration 결과 `COMMITTED_EXACT`로 수렴한다. Direct `NOT_COMMITTED`와 reconciled `NOT_COMMITTED`는 자동 retry하지 않는다. `CONFLICT`는 repair하지 않고 종료한다. `UNAVAILABLE`은 성공이나 실패로 추정하지 않으며 동일 opaque handoff의 read-only reconciliation replay만 허용한다. Replay는 새 witness, attempt, candidate, append 또는 commit을 만들지 않는다.

## Consumption, concurrency와 cleanup

Provider/Owner의 기존 one-way witness·attempt consumption을 유지한다. Commit ambiguity나 `NOT_COMMITTED`는 stale witness/attempt를 되살리지 않는다. 같은 witness의 중첩 orchestration은 최대 한 attempt만 통과한다. Same-head journal 경쟁의 durable winner는 기존 external journal CAS가 결정하며 Orchestrator는 loser를 성공으로 바꾸지 않는다.

Owner result는 exact Owner registry, result object, identity object와 현재 attempt를 모두 일치시켜 cached/foreign/forged result 재사용을 거부한다. Direct known 결과는 orchestration이 소비한 뒤 registry에서 제거한다. Ambiguous handoff만 authoritative read replay를 위해 유지한다. Reconciler result도 exact mint registry로 확인하고 orchestration 즉시 소비한다.

## Persistence와 비목표

새 app persistence는 필요하지 않다. `admitted=true`, `success=true`, receipt 존재 또는 cached state는 authority가 아니다. 기존 external journal schema v1과 Alembic `20260918_0037` single head를 유지하며 migration/backfill을 추가하지 않는다.

이 Foundation은 production composition, Worker/runtime, public API, frontend, production WebAuthn, Rights Adapter, Recovery/Transfer를 구현하지 않는다. 실제 production journal/DB/User DB/private key/credential/admission에는 접근하지 않는다. 다음 dependency는 trusted deployment composition에서 이 internal orchestration을 선택·주입하는 **Durable Admission Production Composition Foundation**이다.
