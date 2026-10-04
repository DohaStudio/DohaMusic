# Independent Deployment Lifecycle Journal Schema v1

> 문서 상태: [구현 — Foundation #165 merged, 운영 비활성]
> 최종 수정일: 2026-10-04
> 관련 문서: [ADR-079](../11-decisions/ADR-079-independent-lifecycle-journal-persistence-foundation.md), [ADR-078](../11-decisions/ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [검증](../10-operations/deployment-lifecycle-journal-validation.md)

application DB와 독립 lifecycle의 SQLite public-fact store다. 앱 ORM metadata/Alembic/startup/backup/default path에 연결하지 않는다. caller 제공 isolated connection으로 empty database schema v1을 명시 설치하며 transaction을 caller가 소유한다. production 초기화/upgrade/downgrade 명령은 제공하지 않는다. app Alembic 0037 single head는 그대로다.

| table | facts / constraints |
|---|---|
| deployment_journal_schema | immutable version 1, replacement/update/delete 금지 |
| deployment_journal_guard | singleton=1, immutable journal_id, revision/trust revision, head digest, nullable current key, last admitted key |
| deployment_journal_events | immutable event ID/journal/revision/previous digest/event digest/kind/old-new key IDs+fingerprints/canonical envelope BLOB |

event ID/revision/digest/new key ID/fingerprint는 unique다. GENESIS만 revision 1/null predecessor, REVOKE만 null successor다. BEFORE INSERT는 충돌·wrong head/journal/predecessor·historical fingerprint/key reuse를 거부한다. AFTER INSERT의 conditional guard UPDATE는 동일 expected head/trust revision을 +1로 전진하며 nullable current pointer를 같이 반영한다. terminal key는 다시 current로 등록하지 못한다. latest REVOKE 뒤 EXTERNAL_REDESIGNATION만 last predecessor를 사용할 수 있다.

read_public_history는 immutable envelope의 local hash/canonicality/order/column projection/head를 대조하며 terminal 상태·taint·old-key invalidation cutoff를 파생한다. cutoff는 public audit fact이고 fresh authoritative reader/ceremony lease 없이 claim eligibility에 사용할 수 없다. pending app row를 async 수정하는 것으로 revocation을 강제했다고 주장하지 않는다.

JournalRepository는 Session.execute/flush만 사용하며 commit()/rollback()/retry 0이다. exception 발생 시 caller는 전체 transaction을 포기한다. event append SQL statement의 failure는 ledger와 pointer 모두 rollback된다. 외부 pin과는 분산 atomicity가 없고 public pin mismatch는 deny한다. production pin store와 application transaction integration은 미구현이다.

## 최초 생성의 독립 권한

[ADR-107 Independent Bootstrap Lineage Authority](../11-decisions/ADR-107-independent-bootstrap-lineage-authority.md)는 독립 registry + signed intent, 외부 root 기반 최초 등록과 GENESIS 전 영구 소비를 정의한 설계 결정이다. 설계 DECIDED와 구현·운영을 구분하며 병합 상태는 [PR #195](https://github.com/DohaStudio/DohaMusic/pull/195)를 따른다. Production External Journal Provisioning 및 Initial GENESIS 실행은 BLOCKED / NOT IMPLEMENTED, authentication·activation은 UNAVAILABLE다. [ADR-108](../11-decisions/ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md)은 Anchor / Complete-Coverage Ledger / Independent Checkpoint Contract를 DECIDED한 설계 결정이다. 검토·병합 상태는 [PR #197](https://github.com/DohaStudio/DohaMusic/pull/197)을 따른다. [ADR-109](../11-decisions/ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md)의 L/H Persistence Foundation public mechanics를 구현·검증했다. 검토·병합 상태는 [PR #198](https://github.com/DohaStudio/DohaMusic/pull/198)을 따른다. Source Verifier/Capability는 IMPLEMENTED FOUNDATION으로 구현했으며 Initial Authorization → Provisioning/GENESIS는 NOT IMPLEMENTED다. 독립 운영 custody·commissioning/authentication/activation은 unavailable다. 이 문서의 journal schema v1은 registry schema가 아니며 no-prior/소비 authority를 제공하지 않는다. ADR-109 external L/H schema는 별도이며 기존 journal/app schema·migration 변경은 0이다.


[ADR-110](../11-decisions/ADR-110-ibla-authentic-source-first-registration-contract.md)은 Authentic Source / Complete Coverage / First-Registration Eligibility / Capability Handoff Contract를 DECIDED했다. root-signed A와 독립 initializer 원본·complete scope inventory·전체 L/current H를 결합하며, PRE-REGISTRATION capability와 L durable REGISTRATION_COMMITTED 이후 POST 경계를 구분한다. 계약에 따른 Authentic IBLA Source Verifier + First-Registration Capability Foundation을 구현했다. 검토·병합 상태는 [PR #200](https://github.com/DohaStudio/DohaMusic/pull/200)을 따른다. L/H와 Source Verifier/Capability는 IMPLEMENTED FOUNDATION, Initial Authorization·Provisioning/GENESIS·Recovery/Transfer는 NOT IMPLEMENTED; Registration Commit Writer는 이 작업 브랜치의 Foundation이며 production port는 unavailable, Authentication/Activation은 UNAVAILABLE다. Phase 9는 0/18, 0%를 유지한다. capability는 등록 완료·Authorization이 아니며 Verifier/Capability mint 자체의 L/H/app DB/journal mutation은 0이다. 별도 Writer owners가 외부 L/H만 변경한다. 실제 production source는 unavailable를 유지한다. [구현 검증 보고서](../10-operations/ibla-source-verifier-capability-validation.md)를 따른다.

등록 시도의 durable 예약은 external H full candidate, irreversible POST는 external L REGISTRATION_COMMITTED가 소유한다. app DB/journal은 재시작 authority가 아니며 [ADR-112](../11-decisions/ADR-112-ibla-registration-attempt-durable-boundary-restart-contract.md)의 pending reset/new cap/automatic append를 제공하지 않는다. 이 작업 브랜치의 Writer v2와 forward-only keeper는 journal provisioning/GENESIS/IA 소비를 수행하지 않는다. [검증](../10-operations/ibla-registration-commit-writer-validation.md)을 따른다.
