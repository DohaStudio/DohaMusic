# Independent Deployment Lifecycle Journal Schema v1

> 문서 상태: [구현 — Foundation Draft 검증 중, 운영 비활성]
> 최종 수정일: 2026-09-18
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
