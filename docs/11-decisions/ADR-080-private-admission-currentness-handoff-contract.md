# ADR-080: Private Admission / Currentness Handoff Contract

> 상태: [제안 — 최소 선행 Contract D; 구현·운영 비활성]
> 작성일·최종 수정일: 2026-09-18
> 기준 develop: `98d8f07163bfc6bd9dc15c5fc7e41c0b906b01c9` (#165 squash merge)
> 관련 문서: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-079](ADR-079-independent-lifecycle-journal-persistence-foundation.md), [검증](../10-operations/private-admission-currentness-contract-validation.md)

## 배경·선택·대안

#165의 public journal schema v1/verifier/actual CAS는 merged지만 `currentness_ports.py`는 `object` witness와 unconditional unavailable 골격이다. `DeploymentJournalReader` concrete/private reader, lease 수명, admission transaction 결과와 pin 설치의 연결은 source에 없다. Public `JournalHead`, `LifecycleExpectations`, `LifecycleIntegrityReceipt`를 이 빈 곳에 그대로 연결하면 수학적 무결성을 현재 권한으로 승격시키게 된다.

후보 A는 다음 implementation 목표다. 다만 A 전체를 먼저 구현하며 opaque witness를 caller DTO나 boolean callback으로 대체하는 대안은 기각한다. B의 pin 설치만 먼저 만들면 미승인 public event를 설치할 위험이 있으며 C의 Claim/Seal은 A/B 및 별도 actor/installation dependencies를 요구한다. 이번 단위는 허용된 D: **A의 provider-owned witness / lease / durable-admission handoff 계약** 하나다. ADR-076/078의 actor/root/permission/wire/lock order를 바꾸지 않는다. Contract Draft의 채택 후 별도 A infrastructure PR에서 구현하며 실제 외부 keys/credentials를 만들지 않는다.

## Public value와 private witness

Public diagnostics는 journal/designation ID, immutable designation record digest, owner opaque ref, exact sorted affected scope tuples, event schema/domain, key ID/raw public bytes/fingerprint, journal revision/trust revision/head digest/current status를 표현할 수 있다. 필드는 ADR-077/078 canonical type 규칙을 따른다. bool/float revision, malformed UUID/hash/reference, scope 중복/누락, noncanonical key encoding은 deny한다. 이 값의 생성자·동등성·서명·hash·상태 enum은 admission provenance가 아니다.

Private witness는 trusted adapter 인스턴스가 **실제 독립 확인을 수행한 attempt에서만** 발급·보유한다. witness는 public constructor/JSON/pickle/DB row/receipt export/import로 재구성하지 않는다. dataclass의 private-looking field나 random token 자체도 proof가 아니다. provider는 발급한 identity와 exact binding을 내부에서 대조하며 다른 provider/attempt/lease/transaction의 witness를 거부한다. 단순 `isinstance`, `verified=True`, caller callback의 `True` 또는 witness 필드 복사로 통과시키지 않는다.

Trusted composition은 reviewed concrete adapters만 명시 주입한다. caller/request/config/env에서 provider를 선택하거나 dev/test fixture를 자동 fallback으로 사용하는 factory는 없다. Python 내부 코드를 악의적으로 교체할 수 있는 privileged compromise는 ADR-076의 out-of-bound를 그대로 따른다. witness 객체 기법만으로 malicious process를 방어한다고 주장하지 않는다.

## Provider responsibility와 internal handoff

아래 method 명세는 **후속 구현 계약이지 현재 Python API가 아니다**. public parameters는 요청 조건이고 private handles는 provider가 독립 대조한 evidence다.

| 경계 | 후속 method / 결과 | 책임 |
|---|---|---|
| Ceremony serialization | `acquire(affected_scopes) -> CeremonyLease` | authoritative complete sorted manifest와 cross-process mutex 확보; 신규 scope enrollment도 같은 discipline |
| ProvisionedVerifierReader | `read(lease, exact_scope) -> ProvisioningWitness` | 독립 designation/provenance, journal identity와 separately provisioned public pin을 load; request/app DB 자동 pin 없음 |
| DeploymentJournalReader | `read_fresh(lease, provisioning) -> CurrentnessWitness` | durable HEAD·complete lifecycle/history·invalidation cutoff와 exact pin 연결 검증; public repository 결과만으로 발급하지 않음 |
| VerifierLifecycleAdmissionPort | `prepare(lease, provisioning, artifact, manifest) -> AdmissionAttempt` | independent ceremony/designation evidence 및 exact signed event/predecessor/scope 확인; no durable mutation yet |
| External journal transaction owner | `commit_admission(attempt) -> CommittedAdmissionWitness` | expected full head CAS와 ledger/projection/cutoff의 단일 durable transaction; commit 성공을 독립 확인 |
| Pin projection installer | `install_same_admission(lease, committed) -> None` | fresh durable admitted event와 같은 public projection만 별도 store에 설치; 새 authority/event 발급 없음 |
| CurrentVerifierRevalidationPort | `require_current(lease, currentness, exact_scope, caller_transaction) -> None` | terminal action 직전 동일 live provider/lease/transaction·fresh HEAD·eligibility 재검증; bootstrap 허가 전체를 반환하지 않음 |

External transaction owner의 commit 책임과 SQL Repository의 caller-owned Session은 구분한다. Repository는 flush-only이고 commit()/rollback()/hidden retry 0이다. explicit external transaction owner만 journal transaction을 끝내며 caller application DB transaction을 끝내지 않는다. `AdmissionAttempt`는 uncommitted이므로 pin 설치에 사용할 수 없다. commit 응답 유실/결과 불명에는 `CommittedAdmissionWitness`를 발급하지 않는다. DB row 존재나 SQLite INSERT 성공은 durable admission completion proof가 아니다.

`CommittedAdmissionWitness`는 same-admission reconciliation에만 쓸 수 있고 현재 issuer permission은 아니다. 후속 rotation/revoke로 stale이 된 admission을 현재 pin으로 설치할 수 없다. currentness witness는 lease가 살아 있고 terminal caller transaction이 동일할 때만 검사에 사용할 수 있다. lease release, provider restart, journal unavailable/head 변경, transaction 종료/교체는 해당 attempt witness를 무효화한다. 재시도는 새 attempt와 fresh independently verified evidence를 요구하며 stale CAS를 숨겨 자동 재시도하지 않는다.

## Exact binding과 admission negatives

모든 단계는 journal ID/designation ID/owner ref/record digest, exact installation/workspace/existing owner scope, event schema/domain, expected journal revision/head digest/trust revision, old/current 또는 revoked 상태의 last-admitted predecessor, separately verified new raw public key fingerprint를 bind한다. installed pin의 monotonic trust revision·last admitted event digest와 fresh journal projection/history가 모두 일치해야 한다. timestamp latest로 고르지 않는다. Revoked null-current projection은 일치하더라도 issuance eligibility deny다.

GENESIS는 외부 designation 수락과 independent empty lineage evidence 및 new signature를 요구한다. 비어 있는 app DB/public journal 생성은 그 evidence가 아니다. NORMAL_ROTATION은 fresh ACTIVE predecessor, independent designation update/new fingerprint, exact same payload old/new signatures를 모두 요구한다. REVOKE는 fresh ACTIVE old key signature와 external designation witness, successor null을 요구한다. EXTERNAL_REDESIGNATION은 기존 외부 governance의 재지정/new fingerprint independent 확인과 new signature를 요구하며 compromised old signature는 대체 proof가 아니다.

Historical taint 대상은 verified external record가 지정한 집합을 같은 journal transaction에 append한다. public caller list 또는 predecessor-only projection이 complete record 검증을 대체하지 않는다. additional historical taint persistence가 필요한 경우 독립 journal의 additive version 검증을 별도 A 구현에서 수행하고 v1 기존 schema를 조용히 덮어쓰지 않는다. terminal key status 보존/non-reuse/invalidation 및 성공 binding/seal reset 금지는 ADR-078 그대로다.

Signed approval의 expiry는 ADR-077 verifier와 current approval/assignment reader가 확인한다. root lifecycle event에 approval 24시간 TTL을 복사하지 않는다. root currentness만 통과해도 installation/Custodian fresh possession, principal/WebAuthn, Workspace/binding/history, approval/assignment 및 seal-first gates는 별도로 필요하다. root/custodian을 Rights issuer/Workspace owner/OUTPUT_READ authority로 확대하지 않는다.

## Serialization·crash·reconciliation

전역 순서는 complete sorted deployment ceremony mutexes → application bootstrap/binding guards → external journal CAS다. lease는 fresh read 전부터 caller DB commit/rollback까지 유지한다. scope manifest가 discovery 뒤 바뀌면 일부 locks로 계속하지 않고 attempt를 abandon한다. process-memory-only lock 또는 SQLite journal write serialization은 전체 ceremony lease의 대체가 아니다.

| failure point | 결과·허용되는 후속 |
|---|---|
| admission 준비 또는 journal commit 전 crash/rollback | committed witness 없음; bootstrap deny, 자동 pin 설치 없음 |
| durable journal commit 후 pin 설치 전 crash | journal 전진 보존, pin mismatch deny; 동일 admitted event만 독립 fresh 대조 후 설치 가능 |
| journal commit 응답 유실/uncertain | 성공 추론/재발급/old pin fallback 금지; durable admission provenance와 exact fresh head를 독립 확인하기 전 deny |
| pin 설치 실패 또는 pin/journal rollback mismatch | bootstrap deny; app DB cache/과거 signed snapshot로 대체하지 않음 |
| 다음 rotation/revoke가 이미 commit | 이전 committed handle로 current pin 재설치 금지; fresh current admitted lineage를 검증 |
| unknown designation/journal lineage 또는 full restore | 새 GENESIS/reset으로 우회 금지; 별도 external admission/Recovery Decision 필요 |

Reconciliation은 이미 승인된 동일 event의 public projection installation만 보완한다. 새 root/designation, authority issuance, binding/claim 생성, seal 해제, terminal reactivation, history truncate는 하지 않는다. journal/pin/app DB의 distributed atomic commit은 주장하지 않는다. full journal/private-key privileged clone/rollback에 hardware anti-rollback 보장은 추가하지 않는다.

## 후속 executable Gate·rollout·schema

A implementation은 disposable test-only adapters로 infrastructure를 검증할 수 있으나 production provenance 검증을 Fake 성공으로 대체하지 않는다. 최소 regressions는 다음과 같다. **아래는 새 구현의 필수 테스트 계획이며 이번 docs-only 작업에서 실행된 결과가 아니다.**

- public DTO/crypto receipt/journal head/forged handle/다른 provider/끝난 lease/교체 transaction 모두 deny; unavailable production composition 불변.
- wrong installation/workspace/owner/domain/designation/fingerprint, stale pin/revision/head/status, malformed JCS/signature/expired approval, duplicate/replayed event와 revoked/terminal key reuse deny.
- REPLACE/UPSERT/revision reset/duplicate current pin/journal truncation deny; public schema v1 regression 보존.
- process 간 rotation/rotation, revoke/revoke, rotation/revoke winner 1; final reader와 writer가 lease 종료까지 같은 lock protocol에 참여.
- journal/current projection 한 transaction rollback, journal commit→pin install 사이 모든 crash/응답 유실; mismatch deny와 exact same-admission reconciliation만 허용.
- Repository commit()/rollback() 0, raw secrets/private keys/log paths 0, private witness export/import·request-provider selection·unsafe Fake fallback 0.

이 Contract는 source/tests/schema/migration/OS adapter를 변경하지 않는다. app Alembic `20260918_0037` single head와 external public journal v1은 보존한다. 실제 independent store/OS mutex/provider의 기술 선택 및 production approval/provisioning은 제공하지 않는다. 후속 A PR은 reviewed providers와 deterministic infrastructure를 구현하되 real root/credential ceremony는 수행하지 않으며 완료 전 concrete production composition은 unavailable다.

장점은 public integrity와 private admission 사이 handoff를 실행 가능한 책임 단위로 한정하는 것이다. 비용은 별도 Contract 채택 단계와 아직 미구현인 reviewed OS/provenance adapters다. 새 Draft PR에서 종료하고 Ready/merge하지 않는다. principal/binding/WebAuthn/Claim/Seal/Rights Writer/Adapter/Worker/Runtime/API/Frontend는 non-goal이다. 새로운 trust root, external record의 법적/사람 판단, ADR semantic 변경 또는 hardware/remote anti-rollback 요구는 별도 Decision/사용자 방향이 필요하다.
