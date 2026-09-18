# ADR-088: Initializer Provenance / Policy Action Binding Comparison Foundation

> 상태: [제안 — 구현·로컬 검증 PASS; Foundation Draft, 운영 비활성]
> 관련 PR: 이 Foundation의 별도 develop 대상 Draft PR (Ready/merge 승인 없음)
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `655985b3432d4949ecae6d27e33ef8afb699c227` (#174 squash merge)
> 관련: [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md), [ADR-086](ADR-086-designation-source-custody-policy-foundation.md), [검증](../10-operations/initializer-provenance-binding-validation.md)

## 배경·선택·대안

ADR-087은 #174 merged로 authoritative하다. 아직 original human confirmation/authenticated source/current policy private store는 없다. A authenticated reader를 metadata callback으로 대체하거나 B persistence를 자동 enrollment로 만드는 대신, C의 가장 작은 independently testable 부분인 **strict public installation/action/initializer/policy 연결 비교**를 선택한다. 새로운 Contract만 반복하지 않고 실제 comparison module과 negative tests를 구현한다. reader+private-store+D 전체 또는 currentness/witness 발급은 이번 unit에 결합하지 않는다.

## 구현·encoding 결정

`backend.bootstrap_authority.provisioning_binding`의 frozen exact-type `PolicySnapshotFacts`, `InitializerConfirmationFacts`, `ProvisioningActionFacts`, `PolicyLineageFacts`는 **public 비교 값**이다. confirmation은 provenance ID/original immutable ref 및 exact-byte digest/initializer opaque ref/action ID/full policy digest와 complete pin binding을 연결한다. policy는 installation UUID/proof fingerprint, source UUID, immutable policy UUID/global monotonic revision/profile 및 기존 exact native root/record identity/owner SID/approved SID set/binary protected DACL을 포함한다. pin은 separately expected raw verifier/fingerprint/designation/journal/trust revision/complete scope를 보존한다.

`policy_snapshot_digest`/`action_comparison_digest`는 domain-separated SHA-256 비교 digest다. 내부 JCS object의 field names는 dataclass의 전체 fields이며 bytes는 lowercase hex, 모든 integer는 exact decimal string, tuple은 ordered array로 표현한다. native uint64 volume ID를 JCS safe integer로 반올림하지 않는다. domains는 `DohaMusicPolicySnapshotComparisonV1` 및 `DohaMusicPolicyActionComparisonV1` + NUL이다. 2 MiB digest input cap, lineage 최대 256 actions, 기존 scope 최대 4096을 적용하고 초과 시 deny한다. 이 내부 비교 encoding은 새 accepted JSON/wire/loader가 아니며 원본 외부 confirmation/designation bytes를 정규화하지 않는다.

`require_action_binding`은 모든 독립 비교 입력의 exact equality만 확인한다. `require_current_lineage_matches`는 full expected history/anchor와 observed 값 및 non-terminal head를 비교한다. `require_successor_matches`는 full expected predecessor, immutable prefix, stable installation/source/anchor, +1 revision, 새 unique action/provenance ID, exact predecessor digest와 SUPERSEDED → 새 ACTIVE action의 순수 선행 조건만 확인한다. 원래 terminal version을 다시 ACTIVE로 변경하거나 prefix status/history를 교체하지 않는다. REVOKED head의 replacement/recovery writer는 제공하지 않는다.

## Non-authority·TOCTOU·persistence 경계

생성자/digest/서명/ACL/current enum/비교 함수 성공은 **legitimate provisioning, initializer authenticity, current eligibility, currentness, admission 또는 authorization이 아니다**. original confirmation에서 human 수락/명시 위임/action/scope를 실제 독립 확인하는 source는 미구현이다. arbitrary dict/boolean/custom equality/hash/subclass는 strict input을 대체하지 못한다. 새 trust root, mandatory signature, initializer credential 또는 production ceremony는 없다. unsigned 원본 assertion 경로는 ADR-076/084/087 그대로다.

값만 비교하는 이 unit은 lease/transaction/handle을 발급·보존하지 않는다. 필수 live custody/designation/pin snapshot/provider registry/OS lease/SessionTransaction/complete locks 및 terminal fresh revalidation은 기존 ADR-080~087 책임이다. 값 변화가 관측되면 비교는 deny하나, matching 값 복원 자체를 영구 abandon으로 구현했다고 주장하지 않는다. 비교 함수의 repeated PASS도 old witness 재활성화가 아니다. production ports는 unconditional unavailable, API/runtime consumer/partial observation/witness mint/factory 0이다.

순수 CAS **precondition**은 실제 CAS가 아니다. 여러 concurrent callers가 같은 precondition을 통과할 수 있고 이 결과를 winner 1이라고 표시하지 않는다. future independently authenticated private transaction owner가 actual CAS/immutable ledger+terminal/current projection 한 transaction/high-water/history를 보장해야 한다. 기존 journal actual CAS/concurrency와 REPLACE defense는 regression으로 검증하되 policy store 구현 증거로 대체하지 않는다. snapshot file existence/ACL valid/confirmation ref digest alone로 source를 self-enroll하지 않는다.

## Migration·검증·영향·trade-off·재검토

Source module 하나와 tests 하나만 구현한다. SQL/persistence/I/O/Repository commit()/rollback()/hidden retry/OS handle/cleanup 변경 0, schema/migration 0, app Alembic `20260918_0037` single head 및 external journal v1/Phase 6 DoD 14/14 유지. 따라서 새 store rollback/commit crash/cleanup quarantine 구현은 해당 없음이며 기존 native cleanup/custody failure/transaction 교체/Windows serialization regressions를 유지한다. 실제 production/user DB/key/credential/governance/Provider 접근·발급 0.

장점은 source reader가 가져야 할 complete exact binding과 history transition 오류를 authority 없이 실행 검증하는 것이다. 비용은 역사적인 public 값만으로 source authenticity/current pointer/anti-rollback을 제공하지 못한다는 점이다. 다음 최소 dependency는 independent original-confirmation authenticity와 live same-handle action/source/current lineage reader infrastructure다. reviewed authenticated reader/transaction owner가 없으면 operational path는 unavailable다. source authenticity mechanism과 private persistence는 별도 Foundation, 새 root/법적 human 판단/Recovery authority가 필요하면 사용자 Decision으로 재검토한다. 새 PR은 Draft까지만 생성하며 Ready/merge/source 삭제하지 않는다.
