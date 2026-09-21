# ADR-099: AdmissionAttempt Provider Foundation

> 상태: #186 merged — Product/Deployment Decision 반영·Foundation 구현/검증 완료, 운영 비활성
> 작성/최종 수정일: 2026-09-21
> 기준 develop: `82d8e1fcb3d2d8c5ef4fbb3c569e72420b5864cb` (#185 squash merge)
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-098](ADR-098-currentness-witness-handoff-foundation.md), [검증](../10-operations/admission-attempt-provider-validation.md)

## Product/Deployment 결정과 dependency

Product/Deployment governance는 Durable Admission candidate를 caller나 `CurrentnessWitness`가 만들지 않는다고 결정했다. Installation-scoped bootstrap chain 안의 별도 `AdmissionAttempt Provider`만 exact signed candidate를 준비한다. `AdmissionAttempt`는 commit/admission/currentness/authorization/Rights/reusable credential이 아닌 bounded candidate evidence다.

현행 dependency는 다음과 같다.

1. **A AdmissionAttempt Provider**: ADR-098 witness와 strict canonical candidate를 한 opaque attempt에 결합한다.
2. **B Admission Journal Transaction Owner**: 외부 journal transaction/session, expected-head CAS, final guard와 authoritative commit result를 소유한다.
3. **C Admission Commit Reconciler**: 응답 유실 뒤 외부 journal을 fresh read해 `COMMITTED_EXACT`, `NOT_COMMITTED`, `CONFLICT`, `UNAVAILABLE`만 판정한다.

A는 durable write 없이 독립 검증할 수 있고 B/C의 입력 계약을 좁히므로 이번 Foundation으로 선택한다. B와 C는 A를 소비하지만 A에 commit/reconciliation 권한을 섞지 않는다. 실제 external journal owner/reconciler와 전체 Durable Admission orchestration은 후속이다.

## strict candidate와 exact binding

`_AdmissionAttemptProvider`는 동일 provider의 live `_CurrentnessWitnessHandoff`만 받는다. Caller가 제공한 bytes와 `LifecycleExpectations`는 권한이 아니며 기존 strict lifecycle verifier를 통과한 뒤 canonical event/manifest로 다시 고정된다. Caller JSON이나 digest만으로 candidate를 인정하지 않는다.

각 attempt는 최소 다음에 exact bind된다.

- installation/workspace/existing-owner의 complete sorted admission scopes와 exact selected scope
- candidate event ID, kind, revision, semantic/trust revision, canonical bytes와 digest
- journal ID, expected head digest/revision과 expected semantic revision
- current correlation의 designation ID/record digest와 별도로 exact candidate designation ID/new record digest, deployment owner, exact ACTIVE predecessor key/fingerprint/public bytes
- CurrentnessWitness identity, provider lifetime attempt, correlation handle와 canonical correlation facts digest
- native Windows lease identity, caller `Session`과 root `SessionTransaction`
- provider가 발급한 별도 opaque attempt identity

현행 ADR-098 witness는 ACTIVE predecessor의 currentness를 전제로 하므로 이 Foundation은 `NORMAL_ROTATION`, `REVOKE`, `EXTERNAL_REDESIGNATION` candidate만 준비한다. Empty lineage `GENESIS`에는 current predecessor witness가 없으므로 별도 independently designated initial-admission 경로가 필요하며 이 API로 우회하지 않는다.

Manifest는 canonical JCS bytes와 binding의 complete scopes가 모두 같아야 한다. Candidate designation record digest는 current pin의 과거 digest를 재사용할 수 없다. Normal rotation/revoke는 같은 designation identity의 새 record를, external redesignation은 별도 designation identity와 새 record를 요구한다. Candidate signer key set은 event에 필요한 old/new key만 exact 허용하며 extra alias/key를 거부한다. Python `bool`/`int` 동등성, malformed revision/head/scope, stale predecessor, wrong current key, mutable/noncanonical bytes, duplicate attempt와 copied/forged handles는 fail closed다.

## lifetime, consumption과 non-authority

한 CurrentnessWitness는 최대 한 live AdmissionAttempt에만 결합된다. Attempt 준비 전후와 매 사용 시 ADR-098의 correlation, journal/current lineage, native lease, root transaction과 exact arguments를 재검증한다. Mismatch, source/head/lineage 이동, transaction 교체, consumer exception 또는 context 종료는 attempt와 witness chain을 one-way invalidation한다. 이미 발급된 winner가 있는 duplicate prepare는 winner를 파괴하지 않는다.

Attempt는 public constructor/subclass/copy/deepcopy/pickle/JSON/DB import를 허용하지 않는다. Provider registry identity가 없는 object, bool/int, copied fields 또는 event digest는 attempt가 아니다. Attempt에는 `commit`, `admit`, `authorize`, Rights 또는 receipt API가 없다.

`VerifierLifecycleAdmissionPort.prepare(lease, provisioning, artifact, manifest)` 계약은 production port에 명시하지만 `UnavailableCurrentnessPorts`는 항상 `DEPLOYMENT_CURRENTNESS_UNAVAILABLE`을 반환한다. Internal Foundation을 test Fake나 request/config-selected provider로 production에 자동 승격하지 않는다.

## transaction owner, final guard와 linearization

후속 B의 `Admission Journal Transaction Owner`만 exact installation journal/candidate/expected head/transaction/one commit attempt 범위에서 다음을 소유한다.

- external journal transaction/session open
- attempt와 witness, lease, root transaction, correlation의 final revalidation
- expected head/predecessor/semantic revision 및 verifier/material/lineage currentness 재검증
- strict candidate append와 full-head CAS
- authoritative external commit 및 canonical committed result

성공 linearization point는 external journal transaction의 authoritative commit이다. Candidate preparation, app DB row/flush, journal append 준비, receipt/response 생성은 성공이 아니다. Application Repository `commit()`/`rollback()`은 0이며 Workspace/Rights authority로 transaction owner를 대체하지 않는다.

## 응답 유실, reconciliation, replay와 crash

Commit 응답 유실 또는 commit 직후 process failure에는 성공을 추론하거나 witness/attempt를 재발급하거나 blind retry하지 않는다. 후속 C의 별도 `Admission Commit Reconciler`만 authoritative external journal을 읽어 exact committed candidate, not committed, conflicting state 또는 unavailable을 판정한다. Reconciler는 새 admission/event를 만들지 않는다.

`COMMITTED_EXACT`만 canonical committed result로 복구할 수 있다. 동일 installation/admission/event ID/revision/digest와 journal committed fact의 replay는 append side effect 없이 같은 결과를 반환할 수 있다. Conflicting replay, fork, duplicate ID, stale head, rotate/revoke/lineage movement는 fail closed다. `NOT_COMMITTED`의 재시도 가능성은 기존 attempt/witness가 여전히 유효하다고 추론하지 않고 후속 B/C contract에서 명시한다.

Prepare 전/후, append 전/후, final guard, commit 중, commit 성공 후 response 전, reconciliation 중 crash에서 ghost success·partial admission·duplicate commit·witness resurrection은 0이어야 한다. Candidate/candidate, admit/admit, append/append, admit/revoke/rotate/head/lineage 이동 경쟁은 기존 journal CAS와 stable guard를 사용해 durable winner 최대 하나를 보장해야 한다.

## persistence와 production 경계

AdmissionAttempt와 CurrentnessWitness는 ephemeral이다. Durable success는 외부 journal authority에만 기록한다. App DB success row를 admission authority로 사용하지 않으며 새 app schema, migration, backfill 또는 external journal schema 변경은 없다. Alembic `20260918_0037` single head와 journal schema v1을 유지한다.

실제 production journal/DB/User DB/private key/credential/admission에는 접근하지 않는다. 이 internal Foundation의 disposable signed candidate는 mechanics 검증용이며 production에서 independently designated record를 대신하지 않는다. 실제 concrete provider는 trusted deployment composition에서 candidate designation source를 독립 검증해야 하고 그 전 production port는 unconditional unavailable이다. Rights, Workspace ownership, Recovery/Transfer, Worker/runtime, public API, frontend, WebAuthn과 pin installer는 non-goal이다. Dependency B는 [ADR-100](ADR-100-admission-journal-transaction-owner-foundation.md)의 Admission Journal Transaction Owner Foundation으로 구현했다. Lost-response **Commit Reconciliation Foundation(C)**은 후속이다.
