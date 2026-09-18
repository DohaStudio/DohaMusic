# ADR-079: Independent Lifecycle Journal Persistence Foundation

> 상태: [제안 — 구현·검증 중, 별도 Draft PR; 운영 비활성]
> 작성일·최종 수정일: 2026-09-18
> 기준 develop: `61b91d1bfaaceca6e3befda9c09f2ad91341a4c2` (#164 squash merge)
> 관련 PR: 이 Foundation의 별도 develop 대상 Draft PR
> 관련 문서: [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [DB 계약](../07-database/deployment-lifecycle-journal.md), [검증](../10-operations/deployment-lifecycle-journal-validation.md)

## 배경·선택·대안

#164의 ADR-078 Contract를 exact-head CI·Final Validation 뒤 병합했다. 다음 최소 coherent unit은 A: 독립 public lifecycle journal persistence + strict signed event integrity + unavailable private admission/currentness ports다. B의 실제 governance/private provenance/OS ceremony serialization과 C의 Claim/binding은 아직 dependency가 없어 운영 활성화하지 않는다.

SQLite를 독립 journal public-fact 저장소의 첫 검증 backend로 선택한다. app `Base`, app engine/startup/backup/Alembic에 등록하지 않고 caller가 명시 제공한 별도 connection/Session만 사용한다. 다른 SQL backend는 deny한다. application DB에 authoritative journal을 두는 대안은 ADR-078의 독립 lifecycle 경계를 위반하여 기각했다. in-memory ledger는 restart/process CAS 증거를 제공하지 못한다. OS ceremony mutex 구현은 이번 unit에서 선택하지 않으며 SQLite writer serialization을 전체 deployment ceremony lease로 확대하지 않는다.

## 결정·schema migration

`migrate_empty_journal()`은 비어 있는 독립 SQLite database에서만 schema v1을 설치하는 명시 함수다. 자동 path/engine/UUID/provisioning, application DB backfill, 기존 schema 자동 upgrade/downgrade가 없다. transaction DDL 뒤 caller가 commit 또는 rollback한다. nonempty/app database는 거부한다. 실제 User/production DB에는 실행하지 않는다.

ADR-078 §7에 따라 external schema는 자체 version/lifecycle Gate다. app-side metadata/cache가 필요하지 않아 app Alembic의 latest single head `20260918_0037`과 기존 migrations는 변경하지 않는다. 향후 app persistence가 필요할 때만 당시 latest head에서 additive migration을 만든다. external journal schema v1을 app migration 0038이라고 가장하지 않는다.

stable singleton guard의 journal ID는 불변이다. 초기 public identity row의 revision/trust revision 0은 UNINITIALIZED metadata이며 trusted genesis가 아니다. immutable event ledger의 unique ID/revision/digest/new key ID/fingerprint와 BEFORE INSERT 충돌 차단은 default SQLite `recursive_triggers=0`의 REPLACE implicit-delete/UPSERT 우회를 거부한다. DELETE/UPDATE와 guard reset/replacement를 trigger로 차단한다.

event INSERT는 expected journal ID/revision/previous digest·current 또는 last predecessor·fingerprint·terminal non-reuse를 대조한다. AFTER INSERT가 expected ID/revision/head/trust revision의 **실제 conditional UPDATE**를 수행하고 `changes()==1`을 요구한다. ledger, monotonic head, nullable current key는 하나의 statement/transaction으로 전진한다. 실패 시 statement 전체가 rollback되며 caller transaction rollback으로 전체 attempt를 포기한다. hidden retry, Repository commit()/rollback()는 0이다. concurrency winner=1은 journal writer에 한정하며 전체 application/journal/pin 분산 원자성을 주장하지 않는다.

## Crypto·projection·권한 경계

새 verifier는 ADR-078 exact fields/domain/JCS envelope digest, strict UTF-8/duplicate/unknown/float/nonfinite, size/depth/count, canonical IDs/hash/time/base64url/safe integer, exact authoritative sorted scope manifest와 independent public key fingerprint, normal 두 교차서명·redesignation 새 서명을 검증한다. timestamp는 freshness proof가 아니다. check clock high-water rollback/future event는 deny한다. ADR-077 approval schema/domain/source는 보존한다.

public history는 local canonical bytes/hash/order/head consistency를 확인하고 event를 통해 terminal status·invalidation revision·predecessor taint를 파생한다. 이미 REVOKED/RETIRED인 predecessor의 redesignation은 status를 재작성하지 않고 새 event의 taint 관측으로 보존한다. 별도 historical taint 대상의 independently designated complete record 검증/append는 실제 admission adapter의 후속이다. 이 Foundation만으로 external redesignation ceremony를 완료했다고 주장하지 않는다.

public pin/head mismatch는 deny하고 equality도 권한이 아니다. 공개 DTO/expected scope/receipt/journal row는 caller가 구성 가능하므로 independently verified governance/provisioning/lease witness를 증명하지 않는다. private reader/admission/revalidation Protocol 골격의 유일 concrete composition은 unconditional unavailable이며 Fake fallback/runtime consumer가 없다. 실제 admission writer, trusted initialization, separately provisioned pin install/reconciliation, clock/OS mutex adapter, complete historical taint admission은 미구현이다.

## Crash·단점·영향·재검토

caller commit 전 crash/rollback은 ledger/head 변경을 남기지 않는다. journal commit 뒤 응답 유실/replay는 stale CAS로 거부하며 pin이 old head면 mismatch다. 이미 admitted event의 pin installation/reconciliation은 이번 repository가 하지 않는다. app rollback은 별도 durable journal을 되돌리지 않으며 application DB/keys까지 포함한 full clone/rollback·privileged trigger/schema 제거는 anti-rollback 보장 밖이다. local truncation/head mismatch 탐지는 cryptographic external provenance의 대체가 아니다.

실제 사람 지정/keys/credentials/Provider/production DB, Claim/Principal/WebAuthn/Recovery/Transfer/Evidence/Rights Writer/Production Adapter/Worker/Runtime/API/Frontend 구현·접근 0이다. Workspace.owner_id/Grant/OUTPUT_READ/성공 seal과 Phase/DoD 진행률은 보존한다. 장점은 작은 durable journal unit의 실행 검증이며 비용은 SQLite 전용 external schema와 아직 unavailable인 운영 chain이다. 운영 wiring/다른 backend/OS store·mutex/새 authority/기존 journal upgrade가 필요하면 별도 검증·Decision으로 재검토한다. 새 PR은 Draft로 종료하고 Ready/merge하지 않는다.
