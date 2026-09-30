# IBLA Anchor / Ledger / Checkpoint Contract 검증

> 상태: [Contract 감사 — DECIDED, Draft 검토 대상, 구현·운영 비활성]
> 최종 수정일: 2026-09-30
> 기준 develop: 7831991239534be5aa7db532676646a1d5e90785
> 관련 문서: [ADR-108](../11-decisions/ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md), [ADR-107](../11-decisions/ADR-107-independent-bootstrap-lineage-authority.md), [Phase 9](../DoD/Phase-09.md)

## 범위와 기존 authority 재감사

원격 develop은 #195 merge와 같고 main은 63633d462043ad3ba78fee92473d19e90c361431이다. 기존 source 작업의 clean worktree에서 latest develop 기준 docs/ibla-anchor-ledger-checkpoint-contract를 새로 만들었다. 원래 사용자 workspace·stash·다른 worktree 및 open Draft #171/#130은 변경하지 않는다.

ADR-076~107의 역할을 다시 매핑했다. 원본 historical records를 수정하지 않으며 다음 책임을 재사용/보존한다.

| ADR | 제공하는 것 | 제공하지 않는 것 |
|---|---|---|
| 076 | 외부 designation/root·offline ceremony·seal-first·compromise 경계 | complete current IBLA history/checkpoint source |
| 077 | FIRST_OWNER_BINDING_ONLY issuance integrity | current eligibility/consumption/no-prior |
| 078 | root lifecycle/currentness 및 independent GENESIS evidence 요구 | initial commissioning source |
| 079 | 별도 SQLite public journal immutable events/actual CAS | authenticated first creation/IBLA ledger |
| 080 | private witness/lease/durable handoff 책임 | 실제 독립 authority source |
| 081 | provider-owned handle/attempt/transaction lifetime | durable history/currentness 진정성 |
| 082 | Windows ceremony exclusion mechanics | 지속 crash marker/권한 source |
| 083 | fixed native pin fact transport/비교 | provisioning authority/complete history |
| 084 | designation/provisioning authentic semantic input 요구 | concrete complete coverage store |
| 085 | held raw designation snapshot | human/위임/current provenance |
| 086 | native identity·owner/exact DACL custody 비교 | initializer 지정/rollback history |
| 087 | initializer action/provenance의 독립 연결 요구 | IBLA historical coverage reader |
| 088 | strict public action/policy binding 비교 | authenticated witness/persistence |
| 089 | original confirmation raw snapshot | source authenticity/current eligibility |
| 090 | policy-purpose canonical JCS payload | new commissioning purpose/authority |
| 091 | verifier infrastructure reuse 및 live policy-lineage mechanics | confirmation authority 자동승격/IBLA coverage |
| 092 | existing public journal와 held lineage 관측 | first-journal 전 coverage source |
| 093 | INSTALLATION_POLICY_PROVISIONING_ONLY signed authority history | GENESIS/commissioning purpose |
| 094 | held custody-bound scoped source | initial root 및 complete IBLA history |
| 095 | ACTIVE scoped verifier public material 연결 | 새 root/current commissioning authority |
| 096 | held canonical confirmation signature authenticity | first registration/consumption |
| 097 | authenticity·lineage·fresh observation exact correlation | 새 external source/authority |
| 098 | currentness witness의 exact provider lifetime handoff | 독립 commissioning history 생성 |
| 099 | 기존 lifecycle candidate preparation; GENESIS deny | initial registration/GENESIS |
| 100 | external journal transaction owner·ambiguous outcome | IBLA store/registration authority |
| 101 | exact existing outcome read-only reconciliation | write/repair/retry/권한 발급 |
| 102 | 기존 admission component graph 조정 | 새 source/root/initial path |
| 103 | production composition lifetime gate; 기본 unavailable | 운영 authenticity/provisioning 완료 |
| 104 | reviewed exact routing configuration | 허가·최초 등록 증거 |
| 105 | six-role private source descriptors | IBLA source/open/provisioning |
| 106 | 기존 journal만 검증/open하는 Factory | create/repair/GENESIS |
| 107 | IBLA root·lineage·영구 소비와 독립 checkpoint 요구 | 구체 A/L/H persistence/current read 계약 |

## Decision audit

- 기존 root 재사용: A와 최초 H mapping은 ADR-076 external designation/독립 ceremony에서 시작한다. row/file absence 또는 서명 artifact의 자체 key는 root가 아니다.
- 별도 authority 중복 0: L은 ADR-107 IBLA registry의 event ledger이며 별도 registration store와 중복되지 않는다. H는 current high-water/intent barrier의 authority, P는 portable audit artifact다.
- complete coverage: commissioned domain의 revision 1..N, 모든 epoch·alias·terminal/consumed records, independent current H 일치가 필요하다. scope-filtered rows 또는 signed complete=true만으로 충분하지 않다.
- 최초 H의 COMMISSIONING_PENDING은 permission이나 confirmed empty history가 아니다. exact A에 연결한 L revision 1을 keeper가 직접 검증해야 첫 confirmed checkpoint가 된다.
- Ledger commit 후 checkpoint 실패를 선행 PREPARED barrier가 차단한다. restart에서 missing event를 NOT_COMMITTED로 추정해 재시도하지 않고 UNCERTAIN으로 남긴다. 실제 confirmed head 전진은 ledger commit 뒤이므로 ADR-107 순서를 유지한다.
- same ID/different fingerprint conflict, exact replay는 결과 조회이고 새 permission이 아니다. cancel/consume/registration 관련 future semantics도 별도 purpose를 유지한다.
- ADR-093/094 purpose, ADR-099 GENESIS deny, ADR-106 existing-only를 변경하지 않는다. Recovery/Transfer로 old lineage를 삭제하지 않는다.

### Checkpoint rollback 보장 해석

독립 H가 intact인 경계에서 L/P/app/journal rollback은 비교 가능하다. H 자체의 마지막 단독 mutation을 되돌리거나 L/H 모두 동일한 과거 authoritative state로 되돌리면 관측만으로 항상 검출할 수 없음을 명시했다. 이는 완전 anti-rollback을 주장하지 않는 ADR-076/107의 independent private custody·privileged compromise 경계다. checkpoint 서명만으로 이 한계를 제거한다고 주장하지 않는다. 이 threat model 안에서 A/L/H 역할과 처리 계약은 DECIDED다. H 자체를 공격자가 임의 rewind할 수 있는데도 탐지를 보장하라는 강화 요구라면 별도 hardware/remote trust Decision 전 BLOCKED다.

새 원격 governance network나 실제 credential이 먼저 있어야 이 설계를 할 수 있다고 가정하지 않는다. local 독립 custody의 keeper/store는 다음 persistence Foundation의 구현 대상이며 현재 운영 중인 source가 아니다. 실제 WebAuthn을 commissioning root의 선행 요건으로 추가하지 않으며 runtime Authentication/Activation은 UNAVAILABLE다.

## 정적 검증 범위

변경 Markdown strict UTF-8·fences·상대 파일 링크·ADR index/numbering 및 git diff --check를 검사한다. Root current docs와 docs/·planning/ 전체에서 IBLA/commissioning/anchor/ledger/complete coverage/checkpoint/registration/GENESIS/provisioning을 검색하고 source-first라고 남은 CURRENT 실행 순서를 persistence-first로 정렬한다. 과거 validation의 당시 NEXT는 보존한다. 현재 검증은 Markdown 15개, 상대 파일 링크 593개, fence marker 18개, ADR 108개 중 번호 중복 0 및 ADR-108 index 1개를 확인했다. 전체 검색은 336개 Markdown이며 관련 CURRENT 실행 순서·authority/미구현 상태의 contradiction 0을 확인했다. 외부 HTTP 응답 및 모든 fragment anchor 전수 검사는 실행하지 않았다.

코드·설정·tests·schema·migration 변경 0이며 Full Backend/compileall/Ruff를 실행하지 않는다. Alembic heads를 확인하되 실제 사용자 DB에 접속하거나 migration하지 않는다. private paths/keys/credential/raw ACL/OS identity/production data를 추가하지 않는다. native rollback/crash/concurrency는 문서의 test obligations이고 실행된 테스트가 아니다.

## 다음 실제 구현 unit

IBLA Ledger / Independent Checkpoint Persistence Foundation: immutable events/operation identity/projection/actual CAS, H control states와 independent persistence, exact replay/conflict 및 PREPARED→L commit→H confirmation의 crash fixtures. 초기 anchor persistence는 public fact이고 외부 ceremony를 수행한 것으로 표시하지 않는다. production ports는 unavailable를 유지한다.

그 뒤 Commissioning Source Verifier/Capability → Initial Authorization → 소비/provisioning/GENESIS 순서다. 기존 Source Foundation의 BLOCKER는 필요한 logical contract 정의로 해소하지만 그 capability를 지금 발급할 수 있다는 의미는 아니다. 구현·운영 차단, Phase 9 0/18과 app Alembic 20260918_0037은 유지한다.
