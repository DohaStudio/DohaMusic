# ADR-101: Admission Commit Reconciler Foundation

> 상태: 제안 — Foundation 구현/로컬 검증 완료, 운영 비활성
> 작성일: 2026-09-21
> 기준 develop: `902d28c262a506c6da8779366d044393f6f5047b` (#187 squash merge)
> 관련: [ADR-099](ADR-099-admission-attempt-provider-foundation.md), [ADR-100](ADR-100-admission-journal-transaction-owner-foundation.md), [검증](../10-operations/admission-commit-reconciler-validation.md)

## 결정

ADR-100의 commit 호출이 `RECONCILIATION_REQUIRED`로 끝난 경우만 별도 `_AdmissionCommitReconciler`가 판정한다. Reconciler는 exact Transaction Owner가 registry에 mint한 opaque handoff와 그 Owner에 이미 결합된 동일 external journal engine만 받는다. Caller가 event ID, digest, revision 또는 expected head field를 복사해 새 요청을 만들 수 없다.

Reconciler는 writer가 아니다. 새 attempt/witness/candidate를 만들지 않고 append, CAS, INSERT, UPDATE, DELETE, repair, original commit retry를 수행하지 않는다. 결과 객체는 audit representation일 뿐 admission/authorization/credential/receipt authority가 아니다.

## Authoritative read와 stable snapshot

기존 journal v1의 immutable ledger와 `JournalRepository` complete-history 검증을 재사용한다. 추가한 exact event view는 canonical envelope, digest, journal/event identity, revision과 predecessor projection을 검증한 뒤에만 반환한다.

Reconciler는 caller/app Workspace Session이 아닌 동일 journal engine의 새 read Session으로 다음 흐름을 두 번 수행한다.

1. journal head read
2. complete history와 exact event view 검증
3. head reread
4. Session close

두 독립 snapshot이 다르거나 open/read/verify/close 중 예외가 발생하면 stale 결과를 반환하지 않고 `UNAVAILABLE`이다. Mutation retry는 없고 bounded read retry도 이번 Foundation에는 필요하지 않다.

## 네 결과

- `COMMITTED_EXACT`: event ID/revision/digest/journal/predecessor/canonical envelope 전체가 exact candidate와 같고 complete committed lineage에 존재한다.
- `NOT_COMMITTED`: complete readable journal이 exact expected predecessor head/revision/semantic revision에 그대로 있으며 candidate identity와 충돌하는 committed fact도 없다.
- `CONFLICT`: wrong journal, same ID/different revision·digest, same revision/different event, wrong predecessor 또는 다른 committed lineage처럼 부분 일치나 lineage 모순이 있다.
- `UNAVAILABLE`: complete authoritative 판정이 불가능한 open/read/close failure, malformed/truncated/forked history 또는 moving snapshot이다.

Event ID, digest, revision, public receipt, cached state 또는 commit 호출 사실 하나만으로 `COMMITTED_EXACT`를 반환하지 않는다. 단순 검색 miss도 `NOT_COMMITTED`가 아니며 exact predecessor가 그대로임을 함께 증명해야 한다.

## Replay, failure와 경계

동일 handoff와 동일 authoritative state의 replay는 같은 결과로 수렴하며 journal mutation은 0이다. `COMMITTED_EXACT`는 과거 durable fact의 확인이지 현재 currentness 증명이 아니다. 폐기된 CurrentnessWitness/AdmissionAttempt를 재활성화하지 않는다. Conflict와 unavailable은 자동 repair나 blind retry로 바뀌지 않는다.

기존 external journal schema v1과 app Alembic `20260918_0037`이면 충분하다. App DB reconciliation authority row, migration, backfill 또는 production wiring은 추가하지 않는다. 실제 production journal/DB/User DB/key/credential/admission에는 접근하지 않는다.

CurrentnessWitness → AdmissionAttempt → Transaction Owner → Commit Reconciler 최소 chain은 구현됐으므로 다음 dependency인 **Durable Admission Orchestration Foundation** 설계를 시작할 준비가 됐다. 이 ADR은 orchestration, Worker/runtime, API/frontend, Rights integration, Recovery/Transfer를 구현하지 않는다.
