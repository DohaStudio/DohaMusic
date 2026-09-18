# ADR-081: Provider-Owned Witness Lifetime Foundation

> 상태: [채택 — #167 merged, A 최소 선행 infrastructure; 운영 비활성]
> 작성일·최종 수정일: 2026-09-18
> 기준 develop: `e45525e0c87656c8b5b6efc8986e5d2c925b48c6` (#166 squash merge)
> 관련 PR: [#167 merged](https://github.com/DohaStudio/DohaMusic/pull/167); 다음 [ADR-082 Windows serialization](ADR-082-windows-ceremony-serialization-foundation.md). 아래 본문은 결정 당시 범위·후속 기록을 보존한다.
> 관련 문서: [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [검증](../10-operations/provider-witness-lifetime-validation.md)

## 배경·최소 unit·대안

#166 ADR-080을 exact-head CI/Final Validation 뒤 squash merge했다. public journal/verifier 및 private object ports/unavailable composition의 실제 source를 재평가한 결과, A 전체보다 작은 첫 implementation은 **trusted adapter 내부의 witness identity/attempt/lease/caller transaction lifetime bookkeeping**이다.

독립 designation/current journal reader와 OS mutex가 아직 없는 단계에서 helper를 private admission adapter로 공개하는 대안은 기각한다. public DTO/callback boolean을 provenance로 승격하는 대안도 기각한다. 새 Contract만 반복하지 않고 ADR-080의 handle lifetime 부분을 구현·negative regression으로 검증한다. pin store/admission durable owner/Claim을 함께 구현하지 않으며 다음 reviewed adapter에 직접 필요한 내부 부품 하나에 한정한다.

## 결정·권한이 아닌 결과

`CurrentnessBinding`은 immutable **PUBLIC** comparison value다. journal/pin exact equality, canonical identity/digest/reference, safe integer revision, sorted exact scope tuple, fixed domain, raw public verifier SHA-256 일치와 ACTIVE_ISSUANCE/null-current 거부를 검사한다. 독립 provisioning, complete journal history, 실제 OS lease/fresh reader provenance는 증명하지 않는다. caller-constructible dataclass는 private permission이 아니다.

comparison 전에 양쪽 journal/pin counter의 exact int 타입을 각각 검사한다. bool/float의 Python equality로 strict revision을 우회하지 않으며 incoming scope와 comparison strings의 custom equality/string subclasses를 허용하지 않는다. canonical native primitive로 검사된 값만 비교하고 malformed 값은 safe generic denial이다.

`_ProviderWitnessLifetime`은 internal helper이며 production provider/factory/Protocol 구현이 아니다. trusted reviewed adapter가 실제 independent checks를 완료한 뒤에만 내부 registration을 사용할 수 있다. fixture object lease/binding equality는 그 checks를 대체하지 않는다. `_require_live_binding()` 통과는 필요한 mechanics check이지 `require_current`, admission, durable success 또는 bootstrap 허가가 아니다. concrete production ports는 기존 `UnavailableCurrentnessPorts` 그대로이며 helper handle/public value/test fixture를 주어도 unconditional unavailable다.

handle은 public constructor를 거부하고 provider-owned registry의 **original object identity/membership**을 확인한다. 같은 type의 forged instance, 다른 provider/attempt/witness를 거부한다. copy/deepcopy/pickle을 거부하며 repr에는 IDs/path/evidence가 없다. JSON/dataclass/DB export/import API가 없다. Python module internals를 악의적으로 교체할 수 있는 privileged compromise는 ADR-076의 out-of-bound이며 opaque object만으로 방어한다고 주장하지 않는다.

## Attempt·lease·transaction lifetime

동일 lease identity는 helper lifecycle 안에서 attempt 하나에만 bind한다. strong reference를 유지해 caller의 `__eq__`/`__hash__`나 object ID reuse로 identity를 바꾸지 않는다. attempt는 exact binding, caller Session 및 active root SessionTransaction identity에 bind한다. caller transaction 종료/교체, lease release/provider close/restart는 old handle을 무효화한다. 현재 savepoint-bound use는 미지원으로 fail closed한다. 새 expiry TTL/timestamp currentness를 발명하지 않는다.

witness slot은 single-assignment이고 다른 witness를 덮어쓰지 않는다. bookkeeping registration 경쟁 winner는 1이며 loser가 winner를 삭제하지 않는다. revalidation에서 HEAD/pin/scope/identity/transaction mismatch를 관측하면 **attempt 전체를 영구 abandon**한다. old matching projection/종료한 savepoint로 reactivate하지 않는다. registration 전 transaction failure를 관측한 attempt도 폐기한다. stale retry는 fresh reviewed provider checks/new lease/new attempt를 요구한다.

RLock은 내부 dictionary만 직렬화하며 실제 OS mutex/cross-process ceremony lease가 아니다. 전체 lock order는 ADR-080/078의 sorted deployment mutexes → app bootstrap guards → external journal CAS를 보존한다. helper의 DB query/flush/commit/rollback/retry/journal/pin writes는 0이며 caller transaction 소유권을 바꾸지 않는다.

## Durable commit·reconciliation 미구현 경계

이 unit은 prepared/committed admission handle을 발급하지 않는다. partial flush/INSERT 성공/currentness registration을 durable admission success로 바꾸는 API가 없다. 실제 journal durable owner와 same-admission pin installer는 후속이며 commit 응답 불명에서 성공을 추론하지 않는다. journal/pin distributed atomicity, complete historical taint admission, production rotation/revoke writer 또는 실제 OS ceremony의 실행 증거는 제공하지 않는다.

기존 public journal v1 CAS/REPLACE/UPSERT/terminal non-reuse/thread-process rotation-revoke/crash regressions는 유지하며 그것이 private admission 증명은 아니다. 기존 crypto expiry/malformed signature checks도 독립된 수학적 evidence에 한정한다. root/custodian을 Rights issuer로 승격하거나 Workspace owner/Grant/OUTPUT_READ를 변경하지 않는다.

## Schema·rollout·영향·재검토

ephemeral process-owned bookkeeping만 있어 새 schema/pin store/app Alembic 변경이 필요하지 않다. app `20260918_0037` single head, external journal v1, 기존 migrations 및 authoritative ADR-075/076/077/078/080 semantics를 보존한다. process crash는 registry를 잃고 fresh provider는 old handle을 거부한다. registry persistence/import/restore fallback이 없다. 실제 User/production DB/keys/credential/governance/Provider 접근·생성 0이다.

장점은 작은 mechanics를 실제 테스트로 완결하는 것이다. 비용은 unavailable 운영 chain 및 trusted adapter가 항상 fresh independent reader와 actual OS lease를 확인해야 한다는 점이다. A 전체 완료/현재 authorization을 주장하지 않는다. 다음은 reviewed independent pin/journal/provenance readers와 OS serialization adapter, 이후 explicit durable admission owner/same-event pin installation의 구현·crash/concurrency Gate다. 기술 선택/production wiring/new trust root/privileged anti-rollback 요구는 별도 review/Decision으로 재검토한다.

새 Foundation PR은 OPEN/Draft로 종료하고 Ready/merge하지 않는다. Claim/Seal/Principal/binding/WebAuthn/Recovery/Transfer/Evidence/Rights Writer/Adapter/Worker/Runtime/API/Frontend는 non-goal이다.
