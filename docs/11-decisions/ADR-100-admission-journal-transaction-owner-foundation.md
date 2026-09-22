# ADR-100: Admission Journal Transaction Owner Foundation

> 상태: #187 merged — Foundation 구현/검증 완료, 운영 비활성
> 작성일: 2026-09-21
> 기준 develop: `2fba391f6c94313ba50bbe46e4c94c42efce0953` (#186 squash merge)
> 관련: [ADR-079](ADR-079-independent-lifecycle-journal-persistence-foundation.md), [ADR-098](ADR-098-currentness-witness-handoff-foundation.md), [ADR-099](ADR-099-admission-attempt-provider-foundation.md), [검증](../10-operations/admission-journal-transaction-owner-validation.md)

## 결정

ADR-099의 dependency B를 별도 내부 `_AdmissionJournalTransactionOwner`로 구현한다. Owner는 caller field나 JSON/digest가 아니라 동일 `_AdmissionAttemptProvider` registry의 live opaque attempt만 받는다. Attempt에 이미 결합된 exact independent journal `Session`과 root `SessionTransaction`을 채택하며 다른 repository/session/transaction으로 바꿀 수 없다.

Owner의 단일 호출은 다음 순서를 따른다.

1. AdmissionAttempt, CurrentnessWitness, correlation, native lease, caller root transaction과 candidate를 재검증한다.
2. 외부 journal v1 complete history와 head가 candidate의 expected journal ID/head/revision/semantic revision과 정확히 같은지 확인한다.
3. 기존 strict verifier를 다시 통과한 canonical event/manifest만 기존 trigger 기반 append/CAS에 전달한다.
4. append/flush 뒤에도 attempt registry, witness, lease, caller/journal transaction, correlation digest, authenticity와 live lineage가 그대로이고 journal head가 exact candidate projection인지 final guard로 확인한다.
5. exact external journal `Session.commit()`을 한 번 호출한다.

Application Workspace Repository의 `commit()`/`rollback()`은 호출하지 않는다. Owner는 AdmissionAttempt Provider, CurrentnessWitness issuer, Commit Reconciler, Rights/Workspace authority가 아니다.

## 성공 선형화점과 결과

Durable journal 결과가 알려진 성공이 되는 유일한 선형화점은 authoritative external journal transaction의 `commit()`이 정상 반환한 때다. Candidate validation, append 준비, event INSERT, trigger CAS, flush, post-append head, 결과 객체 생성은 성공이 아니다.

결과는 세 가지를 구분한다.

- `COMMITTED`: external commit이 정상 반환했다.
- `NOT_COMMITTED`: commit 호출 전 실패했고 rollback 또는 connection quarantine 경계를 거쳤다.
- `RECONCILIATION_REQUIRED`: commit 호출에서 예외가 발생해 결과를 알 수 없다.

결과 객체는 admission receipt, authorization, credential 또는 retry capability가 아니다. Unknown은 success나 failure로 추측하지 않고 blind retry하지 않는다. Attempt와 witness는 commit 성공 또는 unknown 뒤 one-way consume한다. Commit 전 실패도 rollback/격리 뒤 폐기하며 자동 재활성화하지 않는다.

## Stable reconciliation identity

모든 known/unknown 결과는 후속 ADR dependency C가 authoritative journal을 reread할 수 있도록 다음 immutable identity를 보존한다.

- exact installation ID 집합과 journal ID
- provider-minted attempt ID
- event ID/revision/digest
- expected predecessor head digest/revision/semantic revision
- exact correlation digest

이 identity 자체는 admission authority가 아니다. 후속 Commit Reconciler만 fresh authoritative journal read로 `COMMITTED_EXACT`, `NOT_COMMITTED`, `CONFLICT`, `UNAVAILABLE`을 결정한다.

## CAS, 동시성, failure

기존 external journal v1의 immutable event table, unique event/revision/digest/key constraints, guard trigger와 full-head conditional advance를 그대로 사용한다. `INSERT OR REPLACE`, UPSERT, OR IGNORE, revision reset, journal fork 또는 mutable history 경로는 추가하지 않는다. 동일 expected head 경쟁은 최대 하나만 durable winner가 된다.

Failure injection 경계는 begin 이전, candidate 검증, append/flush, final guard, commit 호출과 commit 직후 응답 손실이다. Commit 전 실패는 rollback하고, rollback 실패 또는 ambiguous commit은 Session을 닫아 재사용 가능한 transaction/connection을 남기지 않는다. Cleanup 예외는 registry에서 이미 제거된 witness/attempt를 부활시키거나 알려진 journal 결과를 바꾸지 않는다.

## Persistence와 비목표

기존 external journal schema v1이면 충분하다. App DB authority row, app Alembic migration, external journal migration, backfill은 없다. Alembic `20260918_0037` single head를 유지한다.

이 Foundation은 Durable Admission orchestration, production adapter/port, Worker/API/frontend, Rights Writer/Adapter, Recovery/Transfer를 구현하지 않는다. 실제 production journal/DB/User DB/private key/credential/admission에는 접근하지 않는다. Dependency C는 [ADR-101](ADR-101-admission-commit-reconciler-foundation.md)의 read-only Admission Commit Reconciler Foundation으로 구현했다.
