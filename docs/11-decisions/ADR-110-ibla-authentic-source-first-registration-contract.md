# ADR-110: IBLA Authentic Source / Complete Coverage / First-Registration Eligibility & Capability Handoff Contract

> 상태: [설계 결정 — DECIDED — Source Verifier/Capability IMPLEMENTED FOUNDATION]
> 작성일: 2026-10-02
> 최종 수정일: 2026-10-04
> 기준 develop: dd6181a6eebff3001e171ba167055af760272fb7 (#198 merged)
> 구현 준비 판정: IMPLEMENTATION_READY — 아래 제한된 Source Verifier + Capability Foundation에 한함
> 관련 PR: 계약 결정 [#199](https://github.com/DohaStudio/DohaMusic/pull/199), Foundation 구현·최종 검토 [#200](https://github.com/DohaStudio/DohaMusic/pull/200). 상태는 각 PR 기록을 따른다.
> 관련 결정: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md), [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-107](ADR-107-independent-bootstrap-lineage-authority.md), [ADR-108](ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md), [ADR-109](ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md)
> 감사·검증: [Authority Audit / 문서 Gate 보고서](../10-operations/ibla-source-registration-contract-validation.md)

> 등록 Writer 통합 보충: [ADR-112](ADR-112-ibla-registration-attempt-durable-boundary-restart-contract.md)는 마지막 전체 PRE revalidation → keeper의 exact H PREPARED durable 예약 → 자기 pending의 operation-specific checks → final one-shot handoff 순서를 정의한다. Source Verifier/Capability mint의 read-only·opaque prerequisite·one-delivery 의미는 유지하며 이 등록 준비는 별도 Writer owner 책임이다. 다른 consumer의 기존 handoff와 아래 원 결정 이력은 보존한다.

> 현재 구현 상태 (이 작업 브랜치): ADR-111/112 Registration Commit Writer·v2 L/H·original frame/forward reconciliation Foundation을 구현·검증했다. [Writer 검증 보고서](../10-operations/ibla-registration-commit-writer-validation.md)를 따른다. 아래 NOT IMPLEMENTED/docs-only/Draft 제출 문구는 최초 Decision 당시 이력이며 이번 Writer 구현 또는 production 완료를 뜻하지 않는다. 후속 develop 병합은 PR 기록으로 확인한다.

## 1. 배경·문제·결정 권한

#198은 L/H public persistence를 구현했으나 A의 anchor_digest는 외부 commissioning 진정성 증명이 아니다. 직전 Source Verifier 구현 감사는 승인 입력/coverage와 최초 등록 eligibility/handoff 부재로 MISSING_DECIDED_CONTRACT에서 중단했다. 이번 사용자 요청은 이 두 gap만 결정하도록 허용한다. Production code·tests·새 DB/schema·credential·실제 ceremony·Initial Authorization·GENESIS를 구현하지 않는다.

선택은 **기존 ADR-076 external root의 exact signed A + 독립 initializer의 original commissioning confirmation + A에 결박된 complete scope inventory + 전체 L/current H + held lifetime**이다. 외부 governance가 원래 소유하는 commissioning originals를 읽는 purpose-specific source role을 구체화한다. 별도 registration registry, 새로운 상위 signing root, generic authority framework, 새 persistence subsystem은 없다. 아래 새 schema/domain은 기존 policy-purpose artifact를 재해석하지 않는 IBLA 전용 read profile의 결정이며 구현·실제 credential 발급이 아니다.

ADR-107의 governance assertion/독립 human 대조에서 최초 신뢰를 끝낸다. 전세계 이력 부재를 암호학으로 증명하지 않는다. initializer와 root의 실제 외부 지정·original source provisioning은 운영 선행 조건이며 Foundation에서는 disposable independently provisioned fixtures로 같은 read/verification 계약을 구현할 수 있다. 실제 source가 없는 production port는 항상 IBLA_UNAVAILABLE다. 실제 ceremony를 수행하기 위해 또 다른 Foundation을 먼저 삽입하지 않는다.

## 2. Authority chain과 목적

외부 accepted designation/명시 수락 → independently provisioned root verifier와 initializer 위임·verifier pin → root의 exact commissioning A → initializer의 독립 human/origin/inventory 대조 원본 confirmation C → independently retained domain→A/L/H mapping → complete L와 live H → verified source observation → ephemeral First-Registration Capability 순서다.

첫 두 연결은 ADR-076/084/087의 trusted offline initialization boundary다. source에서 발견한 key·SID·ACL·record ref를 그 자리에서 trust-enroll하지 않는다. provisioning 원본과 initializer 위임을 독립 확인해 둔 trusted composition만 source instance 및 기대 native identities/custody/pins를 주입한다. 값 비교 DTO를 만들거나 callback True를 반환하는 것은 그 확인이 아니다. Signed A/C의 public key를 artifact에서 채택하지 않는다. unsigned 서면 designation을 mandatory signature로 바꾸지 않는다.

C의 signer는 designation에서 commissioning initializer로 명시 지정된 수행자이며 A가 그 exact initializer/proof verifier를 승인해야 한다. 기존 registry custodian과 같은 human/key가 역할을 겸할 수 있으나 INITIAL_AUTHORIZATION/Rights/Recovery/Transfer 권한은 없다. initializer public bytes/fingerprint는 A 외부의 independently provisioned governance pin과도 같아야 한다. A에 키를 넣어 스스로 initializer를 등록하는 것은 불가다. 기존 INSTALLATION_POLICY_PROVISIONING_ONLY producer나 FIRST_OWNER_BINDING_ONLY custodian receipt는 이 위임의 증거가 아니다.

현재 root/initializer/ledger custodian/checkpoint keeper의 eligibility 변경은 해당 domain lease와 L/H protocol에 참여하고 retained external governance history에도 남아야 한다. 변경을 L 밖에서 숨길 수 있는 배치는 complete/current source로 승인하지 않는다. 이 read profile은 고정 단일 epoch/위임만 지원하므로 rotation/revocation/supersession/추가 위임·불명 external transition은 성공 없이 차단한다. 원격 인증/상위 root를 새로 만들지 않는다.

## 3. SourceVerifier input port와 원본 bundle

다음은 후속 internal port의 계약 이름이며 현재 Python API가 아니다. trusted composition이 source provider를 고정하고 open_verified_source(expected_scope, observation_context)를 호출한다. expected_scope는 exact comparison condition이며 authority가 아니다. request/env/app DB가 provider를 선택할 수 없다. verifier는 아래 원본을 직접 held read하고 검증한다. caller가 공급한 verified=true, receipt, public LedgerView/CheckpointView, summary 또는 digest callback을 대신 받지 않는다.

| Logical input | Authoritative source / 제공 주체 | 필수 읽기·검증 / holder |
|---|---|---|
| Original designation와 provisioning provenance | ADR-076 governance custody, 독립 initializer가 확인한 원본 | exact bytes/reference/digest, human 수락·initializer 위임·deployment 범위와 독립 provisioned root/initializer pin의 연결. provider가 원본 handles를 hold |
| Signed Anchor A | 같은 governance commissioning custody의 original A | root Ed25519 서명, exact purpose/validity/origin/inventory/identities. source 밖에서 pin한 root public verifier 사용 |
| Original initializer confirmation C | initializer가 실제 독립 대조 뒤 governance custody에 보존한 original record | IBLA 전용 서명 및 원래 initializer pin/위임, A digest·inventory·origin·custody provisioning 연결. raw originals/ref로 human ceremony 연결 검증 |
| Complete scope inventory I | root가 책임지고 A에 서명으로 포함한 전체 inventory | C가 동일 I digest와 complete external history 관측을 확인. 다른 caller list로 대체 불가 |
| Domain→A/L/H commissioning mapping | ADR-108 H governance custody에 independently retained original mapping | 최초 domain/namespace 배정·고정 A/L/H/epoch와 private source native custody의 independently provisioned expectation. L의 자기 주장으로 구성 불가 |
| L와 H | 각각 commissioned separate writer/restore boundary의 실제 existing DB | 독립 query_only root transactions와 retained native handles에서 전체 history/schema/identity/projection을 읽음. read transactions는 각 verification pass에만 열고 닫음. H는 live authoritative source이고 P/cache는 제외 |
| Fresh installation proof | A/I가 지정한 installation proof public key의 fresh challenge response | provider-generated nonce에 대한 exact installation Ed25519 possession 검증. key bytes는 independent pin이며 caller key로 대체 불가 |
| Observation context | provider owner의 opaque domain lease, read transactions, native source lifetime, trusted check clock | pid/native owning thread/provider/one attempt에 bind. L/H/app writer capability가 아니며 app Session을 요구하지 않음 |

Bundle의 원본 bytes와 native handles는 provider 내부에만 남는다. 검증 output인 verified source bundle은 immutable primitive correlation을 provider registry에 보관한 opaque handle이다. 원본·partial integrity receipt를 외부에 넘긴 뒤 caller가 재조립하는 경로는 없다. 부분 검증은 capability를 발급하지 않는다. 모든 입력이 존재해도 authenticity와 coverage/eligibility는 각각 검증한다.

### 각 immutable identity의 결정·authority·currentness

| 값 | 누가 정함 / 어디서 읽음 | exact correlation / freshness·수명 |
|---|---|---|
| domain_id | external root commissioning / A와 독립 mapping | namespace inventory와 mapping의 유일한 일치. 새 UUID만으로 새 domain 불가 |
| deployment_id | 외부 governance / original designation·A·I | 승인된 deployment와 전체 관련 scope. 현재 designation 및 held lifetime 필요 |
| installation_id | trusted initialization 생성 뒤 root 승인 / A·I·pin | clone/재설치 alias 전체 대조와 fresh proof. hostname/path는 제외 |
| installation proof identity | installation proof key를 initializer가 독립 pin, root 승인 / public bytes·A·I | raw key SHA-256 fingerprint = ADR-109 installation_proof_digest. 별도 임의 proof UUID를 발명하지 않음 |
| lineage_id / intended journal_id | root exact new scope 승인 / A·I | reverse mapping의 유일한 동일 lineage. journal 존재/파일 부재로 결정하지 않음 |
| anchor_id / anchor_digest | root action의 immutable ID / signed A | digest는 아래 canonical payload digest. 원본 서명·C·independent mapping도 필요 |
| ledger_id / checkpoint_id | root와 initializer commissioning / A·독립 mapping·actual L/H identity | logical IDs 및 native physical identities 모두 exact, L/H same file/root/nested roots 금지 |
| designation_id / designation_digest | governance original accepted record / raw original·A·C | exact-byte digest, current accepted designation·root binding. signed A 단독 대체 불가 |
| authority_epoch | original commissioning / A·mapping·L/H | fixed positive safe integer, 전체 관측이 동일. 다른 epoch/transition 미지원 |
| initializer / L custodian / H keeper | external designation의 명시 위임 / 원본·A·C·mapping | opaque refs/proof verifier pin·목적·current delegation. OS token/파일 owner가 위임 아님 |

모든 source와 proof는 하나의 observation lifetime 동안만 유효하다. public identity/digest는 audit/reference이지 authority bearer가 아니다.

## 4. Positive Origin와 accepted read profile

Positive origin은 root가 실제 새로운 exact deployment/scope를 지정한 외부 origin record + root-signed A + 독립 initializer가 원래 record/당사자/기존 history를 대조한 C의 결합이다. 새로운 installation/journal/lineage ID가 있어도 기존 deployment/Workspace scope와 겹치거나 imported/restored/reinstalled/legacy/unknown이면 최초 등록을 허용하지 않는다. A의 존재·서명만으로 human 지정·현재 위임·C를 생략할 수 없다.

I는 A payload에 포함하며 별도 mutable inventory store를 만들지 않는다. C/original designation/provisioning originals와 mapping은 이미 ADR-107/108이 governance custody에 보존하도록 결정한 원본 역할을 읽는 것이다. 새 source writer/provisioning API는 이번 또는 다음 verifier Foundation에 만들지 않는다.

### 동결하는 wire/검증 규칙

commissioning mapping 비교 payload는 domain_id, anchor_id, ledger_id, checkpoint_id, deployment_id, installation_id, installation_proof_digest, lineage_id, journal_id, designation_digest, authority_epoch, commissioning_action_id, ledger_custodian_ref, checkpoint_keeper_ref만 포함한다. digest는 ASCII DohaMusicIblaCommissioningMappingV1 + NUL + JCS(payload)의 SHA-256이다. A의 anchor_digest/signature/C digest는 이 선행 payload에 넣지 않아 순환 hash를 만들지 않는다. 최종 retained mapping이 별도로 보존한 A digest는 A 계산 후 exact 대조한다. custody comparison도 native policy·source role/logical IDs를 입력으로 하고 A/C의 결과 digest를 hash 입력에 넣지 않는다.


- A envelope: payload와 signature만. schema dohamusic/ibla-commissioning-anchor/v1, algorithm Ed25519, purpose IBLA_COMMISSIONING_ONLY. signature message ASCII DohaMusicIblaCommissioningAnchorV1 + NUL + JCS(payload). anchor_digest = SHA-256(같은 domain-separated payload bytes); 자기 digest/signature는 payload에 넣지 않는다.
- A payload의 exact fields: schema, algorithm, purpose, anchor_id, domain_id, deployment_id, installation_id, installation_proof_digest, lineage_id, journal_id, ledger_id, checkpoint_id, designation_id, designation_digest, root_key_id, root_fingerprint, authority_epoch, commissioning_action_id, governance_provenance_ref, governance_provenance_digest, positive_origin_ref, positive_origin_digest, inventory, inventory_digest, initializer_ref, initializer_key_id, initializer_fingerprint, ledger_custodian_ref, checkpoint_keeper_ref, commissioning_mapping_digest, custody_provisioning_digest, issued_at, not_before, expires_at. 모든 fields 필수, nullable/wildcard 없음.
- C envelope 역시 payload/signature만. schema dohamusic/ibla-initializer-confirmation/v1, algorithm Ed25519, purpose IBLA_COMMISSIONING_CONFIRMATION_ONLY. signature domain ASCII DohaMusicIblaInitializerConfirmationV1 + NUL. exact payload fields: schema, algorithm, purpose, confirmation_id, commissioning_action_id, anchor_digest, designation_id, designation_digest, initializer_ref, initializer_key_id, initializer_fingerprint, positive_origin_ref, positive_origin_digest, inventory_digest, commissioning_mapping_digest, custody_provisioning_digest, original_confirmation_ref, original_confirmation_digest, issued_at, not_before, expires_at. original_confirmation_digest는 C 자체가 아니라 독립 human/action confirmation 원본의 exact-byte SHA-256이다.
- 원본 designation/confirmation은 1..1 MiB strict UTF-8 nonblank, BOM/NUL 불가, exact bytes SHA-256. 원본을 JCS/Unicode/line-ending normalization하지 않는다. source authenticator는 independently provisioned 원본 identity/pin과 위임·실제 action 연결을 확인한다. 아무 텍스트의 digest 일치만으로 통과하지 않는다.
- A는 canonical JCS envelope 최대 1 MiB, C는 canonical envelope 최대 16 KiB. existing bounded strict parser·rfc8785·PyCA Ed25519 infrastructure를 재사용한다. signature는 canonical unpadded base64url 64 bytes, public Ed25519 key는 32 bytes이며 independently pin한 key SHA-256과 fingerprint 일치 필요. UUID/digest/opaque refs/UTC-second는 ADR-077/078 conventions, counters exact int 1..2^53-1; bool/float/custom type/duplicate·unknown keys/invalid Unicode/noncanonical bytes는 거부한다.
- A/C issued_at <= not_before < expires_at, issued_at부터 expires_at까지 최대 24시간. check time은 issued_at <= checked_at, not_before <= checked_at < expires_at. A expiry는 commissioning action/first-registration eligibility에만 적용하며 retained historical A/identity를 삭제하지 않는다. 만료한 A의 validity를 소급 연장하거나 새 A로 history reset하지 않는다.
- 원본/키/정책을 별도 독립 provisioned trusted composition이 고정한다. source filename은 IBLA role에 고정: ibla-commissioning-anchor-v1.json, ibla-initializer-confirmation-v1.json. original designation/confirmation은 기존 raw profile의 IBLA 전용 fixed roles(ibla-designation-original-v1.txt, ibla-ceremony-original-v1.txt)이며 기존 policy-purpose source instance를 대체하지 않는다. 이 implementation에서 고정할 DB basename/routing은 authority가 아닌 기술 세부사항이며 schema/권한 의미를 변경할 수 없다.
- fresh installation proof message: ASCII DohaMusicIblaInstallationPossessionV1 + NUL + JCS({domain_id, anchor_digest, installation_id, installation_proof_digest, lineage_id, inventory_digest, observation_id, challenge}). observation_id는 provider-generated canonical UUID, challenge는 CSPRNG 32 bytes canonical unpadded base64url. 동일 challenge는 original observation registry에서 한 번만 받아들이고 재사용/외부 공급 불가. nonce 발급부터 monotonic 15분 이내 및 A/C validity 안에서만 유효. private key 접근/서명은 external proof owner 책임이며 verifier는 public verification만 한다.

이 profile의 source/pin provisioning 증거는 fixture의 test-only trusted setup에서 공급할 수 있다. 운영 source에서 증명할 수 없으면 production unavailable를 유지하며 dictionary/serializer/public constructor를 authentication port로 만들지 않는다.

## 5. Source custody / identity / currentness

private source roots와 leaf의 independently provisioned native volume/file identity, explicit owner SID, approved SID set, exact protected binary DACL과 source role/purpose/domain/deployment/installation/lineage를 하나의 private custody binding으로 결박한다. custody_provisioning_digest는 ADR-088처럼 전체 정책·역할·logical identity를 domain-separated comparison encoding으로 보존한다(ASCII DohaMusicIblaCustodyComparisonV1 + NUL; bytes lowercase hex, native uint64는 exact decimal string). 이는 public comparison이지 provisioning authority가 아니다.

원본 root pin·initializer pin·mapping/provisioning 원본은 대상 A/L에서 self-discover하지 않는다. governance custody의 original trusted pin을 독립 확인한 composition만 제공한다. L writer가 A/C/H governance root를 수정할 수 없는 권한·backup/restore 분리를 확인해야 한다. 경로 문자열이 다르거나 보호된 DACL이 있다는 사실만으로 external provenance/independence를 증명하지 않는다.

Windows ADR-083/086/089의 OPEN_EXISTING, 각 ancestor/leaf OPEN_REPARSE_POINT, local DOS path profile, resolved path/disk/directory, volume/128-bit file ID, no reparse·hardlink count 1, held same-handle bounded read/reread, no write/delete sharing, owner/protected exact DACL revalidation, retained cleanup quarantine를 재사용한다. IBLA fixed-role internal reader에서 mechanics를 직접 확장하며 기존 file purpose·typed policy handles를 승격하지 않는다. ADR-106 SQLite existing-file/native-handle/connection identity 검증 pattern은 L/H read-only 역할에만 적용한다. journal factory를 L/H factory로 호출하지 않는다.

currentness는 timestamp 최신값이 아니라 독립 live H 전체 control history/current confirmed tuple, complete L, held 원본/custody/위임·proof와 domain lease의 동시 검증이다. mutable bytes/ACL/native identity/head/manifest/위임 변화·read 중 예상 밖 transaction 변화·cleanup 불명은 observation 전체를 영구 abandon한다. 값 복원·matching ACL·새 transaction으로 old observation을 되살리지 않는다.

## 6. Complete Coverage와 authoritative Scope Inventory

I exact fields: schema = dohamusic/ibla-scope-inventory/v1, domain_id, deployment_id, lineage_id, installation_id, installation_proof_digest, journal_id, coverage_start_ref, coverage_start_digest, positive_origin_ref, positive_origin_digest, scopes, installation_aliases, lineage_aliases, journal_aliases, imported_scope_refs, external_history. inventory_digest = SHA-256(ASCII DohaMusicIblaScopeInventoryV1 + NUL + JCS(I)). 자체 digest는 I 안에 없다.

scopes는 ADR-078 exact tuples의 sorted unique array, 각 항목 installation_id/workspace_id/existing_owner_id 세 UUID만. 최소 1, 최대 4096; caller 일부 scope를 선택할 수 없다. aliases는 source가 책임지는 retained mappings이며 각 installation alias는 installation_id/installation_proof_digest/lineage_id, lineage alias는 lineage_id/domain_id, journal alias는 journal_id/lineage_id다. imported_scope_refs는 opaque original evidence ref/digest 배열이다. external_history 각 항목은 record_ref, record_digest, fact_kind, affected_scopes와 exact original evidence를 연결한다. scopes 전부와 domain에 relevant한 이전/가져온 installation/deployment/Workspace/owner/journal/lineage를 cover해야 한다. 모든 arrays sorted unique; bounded parser 전체 1 MiB 초과는 UNAVAILABLE이며 prefix만 성공시키지 않는다.

성공 가능한 ADR-109 subset은 **하나의 A/lineage/installation/proof/journal/epoch**다. aliases/imported_scope_refs는 빈 배열이어야 하고 external_history도 빈 배열이어야 한다. 빈 배열 자체가 no-prior proof는 아니다. root의 서명으로 범위를 책임진 positive origin + initializer의 기존 deployment/import/restore/재설치/과거 bootstrap/binding/SEALED 대조 + independently authenticated originals + 전체 L/H가 있어야 빈 inventory에 의미가 있다. 관련 과거/alias 자료가 있으면 삭제해 이 profile에 맞추지 않는다. valid하지만 미지원이면 UNAVAILABLE, 검증된 prior/terminal safety fact이면 deny한다. malformed/중복/ambiguity는 INCONSISTENT다.

Complete Coverage는 다음을 모두 충족한다.

1. 독립 original A/C/I/mapping이 같은 domain과 retained namespace를 지정한다. root와 initializer의 coverage boundary는 commissioning 이전 이력까지 포함하며 legacy/import/unknown에 INITIAL backfill 없음.
2. L domain 전체 revision 1..N, events/operations uniqueness, canonical digest/predecessor, exact Binding, 모든 state transition과 current projection 일치. selected-lineage/current-row 쿼리만 사용하지 않는다.
3. revision 1 COMMISSION의 binding은 A와 동일하며 evidence_digest는 **anchor_digest**와 같아야 한다. ADR-109의 generic digest를 이 reader의 origin correlation으로 제한한다. root/A authenticity는 별도 원본 검증이고 COMMISSION은 그것을 만들지 않는다.
4. H 전체 control sequence/history/projection을 검증하고 state=CONFIRMED, pending=null, confirmed=(N,L head digest), H binding의 L/H/A/domain/epoch 모두 L/A/mapping과 같다. EMPTY/PENDING/PREPARED/UNCERTAIN은 차단한다.
5. 외부 relevant history/위임·epochs·aliases·terminal을 하나도 생략하지 않는다. 현재 subset에 지원하지 않는 유효 event/schema/epoch/membership이 있으면 UNAVAILABLE. H가 가리키는 suffix를 숨긴 prefix는 INCONSISTENT.
6. 모든 writer가 같은 domain governance lease와 L/H protocol에 참여한다. source 확인 → lease 획득 → 전체 source/coverage 재확인 → read → capability handoff 직전 fresh 재확인을 수행한다. membership 변경은 전체 attempt abandon이며 일부 lock으로 계속하지 않는다.

Authoritative Scope Inventory는 root가 책임지는 I와 initializer의 original external-history 대조 및 L의 전체 domain history를 합친 검증 범위다. 이를 위한 두 번째 registry/absence DB는 없다. 기존 registration/authorization/GENESIS 부재는 그 범위 안에서 **positive origin이 확인되고, retained external prior evidence가 없고, full current L replay에도 해당 fact가 없을 때만** 인정한다. app row 없음·journal 없음·빈 L/H만으로 부재를 증명하지 않는다. domain 밖 세상 전체에 대한 absence proof가 아니라 ADR-107의 명시된 governance trust boundary다. 외부 complete evidence를 읽을 수 없거나 누락 의심이면 UNAVAILABLE다.

## 7. First-Registration eligibility와 PRE/POST boundary

FIRST_REGISTRATION_ELIGIBLE은 아래 conjunction이다. 검증되지 않은 absence는 true가 아니고 UNKNOWN이다.

| Predicate | 정확한 의미 |
|---|---|
| authentic_origin | accepted original designation/independent pins + root-signed A + separately authenticated original initializer confirmation C + fresh installation proof 통과 |
| exact_commissioned_domain | A/I/independent mapping/actual L/H/reverse scope lookup가 전부 같은 유일 domain/lineage이며 namespace overlap/unknown 없음 |
| complete_supported_coverage | §6 전체 coverage, 하나의 fixed A/lineage/epoch, 모든 relevant prior/alias/외부 history 확인; 미지원 0 |
| current_confirmed | live H CONFIRMED/pending null 및 L exact tuple, current designation/root/위임/proof와 source lifetime 동시 유효 |
| no_prior_registration | original external inventory와 full L 어디에도 REGISTRATION_COMMITTED/기존 independent registration 없음 |
| no_prior_initial_authorization_or_genesis | 전체 authoritative 범위 어디에도 authorization issued/consumed/cancelled/superseded/GENESIS/prior binding/seal/outcome 없음 |
| no_block_or_terminal | HISTORY_BLOCK/RETIRE/UNCERTAIN/RECOVERY_REQUIRED/취소·폐기·conflicting origin/과거 unknown 없음 |
| live_observation | same provider/pid/thread/attempt/lease/read transactions/native sources, validity/monotonic deadline·handoff fresh checks 모두 통과 |

현재 schema의 N=1 COMMISSION만 있는 상태는 **성공 가능한 필요 형태**이며 충분조건은 아니다. 이후 지원 event HISTORY_BLOCK/RETIRE가 하나라도 있으면 false다. 알 수 없는 registration/authorization/GENESIS kind를 무시하고 no-prior=true로 만들지 않는다. future valid 등록 kind를 현재 reader가 지원하지 않으면 UNAVAILABLE로 닫히므로 이미 등록된 domain을 first로 다시 승인하지 않는다.

PRE-REGISTRATION은 위 독립 commissioning과 coverage가 있으나 irreversible registration fact가 아직 없다고 검증된 관측 상태다. application runtime UNREGISTERED lookup의 UNKNOWN과 다르다. PRE가 REGISTERED_INITIAL은 아니다. Source Verifier/Capability는 등록 fact를 만들지 않는다.

**POST-REGISTRATION / irreversible boundary는 ADR-108 REGISTRATION_COMMITTED 의미의 exact lineage 최초 등록 event가 L의 authority transaction에 durable commit되는 시점**이다. current root exact signed registration intent + independently checked initializer evidence를 받은 authorized Registry Custodian이 실제 기록한 fact만 해당하며 application row/response/flush/CAPABILITY 발급/REGISTRATION_AUTHORIZED/COMMISSION/H confirmation은 경계가 아니다. commit 뒤 H가 아직 PREPARED/불명이어도 이미 최초 등록 재승인은 불가다. H 확인은 fresh registered 상태를 다음 단계에 노출하는 조건이며 irreversible point를 뒤로 미루지 않는다.

이 경계는 기존 ADR-107 independent registration → REGISTERED_INITIAL을 구체화한다. 이후 이력이 등록 취소·retire·응답 유실·DB/journal 삭제여도 first-registration으로 복귀하지 않는다. 최초 registration event의 writer/wire/schema 확장은 이번 및 다음 verifier Foundation 범위 밖이다. 현재 L v1을 바꾸지 않아도 reader는 해당 미지원 이력을 성공으로 수용하지 않으므로 PRE-only capability를 안전하게 구현할 수 있다.

## 8. Capability semantics와 exact binding

First-Registration Capability는 **특정 live observation에서 exact commissioned domain이 authentic/complete/current하고 최초 등록 직전 predicate를 충족했음**을 증명하는 provider-owned opaque prerequisite evidence다. 첫 등록 commit이나 독립 registration authority의 행사를 증명하지 않는다.

Initial Authorization, GENESIS authorization, human approval 자체, authenticated runtime principal, activation, journal creation permission, Recovery/Transfer, future currentness, 영구 one-time entitlement 또는 REGISTERED_INITIAL receipt를 증명하지 않는다. issuer가 이 handle을 받는 것만으로 ADR-107의 fresh REGISTERED_INITIAL 요구를 충족했다고 판단할 수 없다.

내부 record는 다음 immutable exact tuple에 결박된다: provider identity/pid/native thread/observation+attempt identities, domain/deployment/installation/proof fingerprint/public proof pin, lineage/intended journal, A ID/digest/action/positive origin ref+digest, original designation ID/digest/root pin/initializer C digest, inventory digest+complete scopes/coverage boundary, independently retained mapping+custody provisioning digest, L ID/revision/head digest, H ID/control sequence/control digest/CONFIRMED tuple, authority epoch/위임, held source identities, original L/H read connection owners와 각 read pass의 verified snapshot tuple, original domain lease, nonce proof identity·checked validity·monotonic deadline. caller가 tuple 일부를 교체할 수 없다.

verified source handle과 capability는 별도 registry identities다. source observation은 검증된 source 상관관계일 뿐이며 eligibility 후 single assignment가 성공할 때만 capability를 발급한다. public DTO/boolean/digest/serializer를 capability constructor로 사용하지 않는다.

## 9. Lifetime / replay / handoff

- ephemeral, non-exportable/non-serializable. public construction/subclass/copy/deepcopy/pickle/JSON/import/export/persistent token API 없음. repr/error에는 고정 안전 이름만. provider 원본 registry membership/object identity로 확인한다.
- lifetime은 original provider process/native owning thread/단일 observation context/opaque domain lease/held original sources/고정 L/H read connection owners/fresh proof deadline/A·C validity의 교집합이다. 최대 nonce 발급 후 monotonic 15분이다. app transaction·runtime session·미래 request에 보관하지 않는다.
- domain lease는 ADR-108 governance domain을 가장 바깥에서 직렬화한다. ADR-082의 Global named mutex mechanics를 domain-specific 이름으로 확장할 수 있다(DohaMusic.IblaDomainV1 + canonical domain UUID의 SHA-256). 기존 Workspace scope mutex receipt를 이 lease로 재해석하지 않는다. process-only lock, read snapshot, PID/mtime lock은 대체 불가다.
- same observation에서 capability mint는 single assignment 1회. duplicate mint는 deny하고 기존 winner를 자동 폐기하지 않는다. capability **handoff도 한 번**이며 registry에서 원래 consumer/provider/exact domain을 확인하고 모든 fresh checks를 완료한 뒤 delivered로 원자적 표시한다. callback/consumer 예외 또는 응답 유실도 재전달하지 않고 전체 observation을 abandon한다.
- handoff mark는 ephemeral replay bookkeeping이고 durable registration/Initial Authorization consume가 아니다. 후속 issue/consume/cancel을 설계하지 않는다. registered/consumed 사실이 없고 fresh coverage가 다시 검증되면 별도 새로운 observation을 시작할 수 있다. read-only capability mint만으로 domain-wide durable winner 1을 주장하지 않는다. 실제 first-registration writer의 existing expected-head CAS/irreversible boundary가 durable 경쟁 winner를 결정한다.
- handoff의 input은 **opaque capability 하나**다. consumer는 mint한 provider의 internal validator로 exact registry/binding을 확인한다. raw A/L/H/head/lineage/eligible bool을 다시 조립해서 받는 overload/fallback 없음. consumer 이름이 Initial Authorization issuer여도 이 PRE prerequisite만으로 issue 불가: ADR-107의 실제 registration fact 및 그 fresh H-confirmed currentness를 별도로 갖춰야 한다. capability를 POST receipt로 승격하거나 registration 이전에 issue하지 않는다. 그 future writer는 이 문서의 PRE/POST 경계와 동일 domain serialization을 유지해야 한다. 이 handle 외에 root intent 등 후속 단계 자신의 purpose-specific 입력이 필요할 수 있지만 verifier 검증 facts를 caller가 raw로 다시 전달할 수는 없다.
- H/L/source/manifest/위임/clock rollback 관측, context exit/release/read 중 예상 밖 transaction end·replacement/savepoint/provider shutdown/restart/thread 이동/거절/cleanup 불명은 permanently stale. 모든 derived handles도 무효화하며 값 복원으로 재활성화 없음. OS handles는 original owner가 explicit cleanup하며 실패는 retained quarantine다.
- 각 source/eligibility verification pass는 original read connection owners에서 별도의 짧은 query_only root transactions를 열고 전체 L/H를 읽은 뒤 owner가 확실히 종료한다. repository instance는 해당 transaction 종료와 함께 폐기한다. capability는 read snapshot tuple을 보존하지만 끝난 SessionTransaction을 live라고 주장하지 않는다. capability mint/handoff 전에 같은 held source/lease/custody를 재확인하고 매 handoff에 새 전체 read pass를 수행해 exact head/eligibility를 다시 검증한다. 정상적인 pass 종료는 source observation 종료가 아니며 read 중 transaction 교체/불명 종료는 whole observation을 abandon한다. 이 결정은 IBLA 전용이며 기존 policy witnesses의 caller/journal transaction 수명을 완화하지 않는다.
- 후속 consumer가 mutation transaction을 열기 전에 verifier의 read pass를 종료하므로 SQLite reader를 자신의 commit과 경합시키지 않는다. 같은 source context와 domain lease는 유지하며 consumer는 자신의 authority transaction/expected-head CAS/currentness를 별도로 검증해야 한다. delivered prerequisite를 context 밖의 영구 권한으로 보관하거나 과거 tuple을 writer의 현재 승인으로 사용하지 않는다. 다음 read-only Foundation에서는 consumer stub의 handoff/lifetime tests만 구현하며 registration/IA writer를 구현하지 않는다.

## 10. Fail-closed / transaction / redaction

성공 결과는 capability이며 실패 결과는 기존 safe IBLA_UNAVAILABLE / IBLA_CONFLICT / IBLA_INCONSISTENT다. 표의 deny는 실패 의미이지 새 IBLA_DENIED API enum이 아니다. failure reason은 테스트/내부 분류이고 private detail이 외부 exception에 반사되지 않는다. unknown을 negative proof로 바꾸지 않는다.

| 상황 | 결과 / capability |
|---|---|
| origin missing·authenticator/source/production port 없음 | IBLA_UNAVAILABLE / 0 |
| origin ambiguous·identity/mapping 불일치·scope overlap | IBLA_INCONSISTENT / 0 |
| signature/purpose/validity/proof mismatch·replaced source | IBLA_INCONSISTENT / 0, whole observation abandon |
| incomplete L/H chain·gap·projection/mapping/digest mismatch | IBLA_INCONSISTENT / 0 |
| unsupported valid epoch·alias·event·external history | IBLA_UNAVAILABLE / 0, skip 금지 |
| unavailable/incomplete authoritative external scope inventory | IBLA_UNAVAILABLE / 0 |
| H EMPTY/COMMISSIONING_PENDING/PREPARED/UNCERTAIN | IBLA_UNAVAILABLE / 0 |
| L/H mismatch·hidden suffix | IBLA_INCONSISTENT / 0 |
| verified HISTORY_BLOCK/RETIRE/terminal·prior registration/IA/GENESIS | IBLA_CONFLICT / 0; kind가 미지원이면 UNAVAILABLE / 0 |
| stale·foreign/cross-domain/copied/forged capability | IBLA_UNAVAILABLE / 0, original valid foreign attempt를 임의 폐기하지 않음 |
| same observation duplicate mint / delivered handle replay | IBLA_CONFLICT / 새 capability·handoff 0 |
| lease busy/abandoned·read transaction/cleanup/I/O uncertain | IBLA_UNAVAILABLE / 0, retained cleanup |
| limits exceeded·unsupported platform/crypto unavailable | IBLA_UNAVAILABLE / 0, fallback 없음 |

Verifier/capability issuance/handoff의 mutation: L=0, H=0, app DB=0, production journal=0, registration=0, GENESIS=0. source writer/provisioning/repair/reset/hidden retry도 0. memory registry의 mint/delivered/abandon만 변경한다. 실패 시 partial authoritative state=0; cleanup resource 불명은 retained ownership과 failure로 보고한다.

read connection/native handles/domain lease와 각 짧은 read transaction은 observation owner가 소유하고 provider는 caller-owned repository를 commit/rollback하지 않는다. L/H 둘 다 query_only, 독립 existing-file connections/root transactions, nested/attached/temp shadowing/schema drift 금지다. H를 fresh correlated read하려고 write capability를 부여하지 않는다. SQLite snapshot만으로 외부 root currentness를 주장하지 않는다.

capability/verifier result/log/error에 absolute/private path, DB path, native handle/identity bytes, owner SID/DACL raw details, credential/private key, raw commissioning/confirmation/source contents, human 자료, stack trace를 노출하지 않는다. 내부 correlation은 필요한 private identity를 보관하지만 public durable evidence에 넣지 않는다. safe audit는 opaque domain/observation ref, decision category, public digest/revision만이며 원본 내용을 출력하지 않는다.

## 11. Self-enrollment / circular trust / 한계

new UUID, empty L/H, caller 첫 COMMISSION, config 생성, registration row 없음, missing journal, new provisioned path, caller A/digest로 authority를 만들 수 없다. externally accepted designation/pins/origin/C/inventory가 없으면 source provenance는 UNKNOWN이다. source 발견 당시 ACL/key/native identity를 기대 policy로 채택하는 self-pinning도 금지다.

금지 순환: L이 A를 승인 → A가 L을 승인 → 둘의 존재로 성공; H가 L을 confirm → H만으로 external origin 생성; C가 자기 initializer key 제공 → 그 키로 C 진정성 승인; capability가 first라고 말함 → register 없이 REGISTERED_INITIAL/IA 승인. 원래 외부 root와 initializer/pins/custody의 independent initialization 연결이 이 순환을 끊는다. target journal ACTIVE/GENESIS를 A 최초 신뢰의 입력으로 요구하지 않는다.

실제 Production custody/ceremony/private source는 미검증·미실행·미접근이다. software는 H 마지막 PREPARED만 rollback되거나 L/H가 일관된 과거로 함께 rollback된 경우 완전 탐지를 보장하지 않는다. hardware anti-rollback/remote consensus 미지원, power-loss/storage-controller durability 미검증. malicious root/initializer 공모·hidden external history·privileged custody compromise/모든 proof material clone에 대한 보장 없음. 알려진 compromise/restore/source loss는 unavailable이며 새 빈 store fallback 없음. 서명이나 이 ADR 작성으로 위 한계를 해결했다고 표현하지 않는다.

## 12. 대안·선택 이유·영향·이행·재검토

| 대안 | 보안/self-enrollment | 복구/TOCTOU/운영 비용 | 결정 |
|---|---|---|---|
| A policy-purpose source 승격 | purpose confusion, IBLA origin/inventory 미증명 | 기존 ACTIVE journal 의존 순환 가능 | 기각 |
| B A digest + L/H correlation | 내용 일치만 증명, 자기 commissioning 허용 위험 | 원본·human/custody·external prior scope 없음 | 기각 |
| C external positive-origin + complete coverage + current H | ADR-076 external root와 독립 initializer/pin, no-prior와 current history 분리 | held lease/source·별도 custody 운영, 장애 때 가용성 포기 | 선택 |
| D persistent registration token | replay/stale token이 durable authority처럼 사용될 위험 | token revocation/백업/restore라는 불필요한 추가 store | 기각 |

장점은 승인 source와 registration 이전 관측/이후 durable fact를 분리하고 다음 verifier의 성공·거절 입력을 고정하는 것이다. 비용은 complete history scan·independent provenance/custody provisioning·short held lifetime과 read profile의 좁은 지원 범위다. 운영 topology/backup·restore·키/실제 human 지정은 구현됐다고 주장하지 않는다.

app DB/schema/Alembic/L/H v1/wire의 기존 event 종류·API/Frontend/Worker/runtime 변경 0. 새 A/C/I read codec은 다음 verifier 구현 PR 내부에서 구현한다. current L v1은 COMMISSION/HISTORY_BLOCK/RETIRE 그대로다. migration/자동 backfill/새 public API 없음. 기존 ADR-107~109는 보존하고 이 ADR로 미결 input/eligibility/handoff만 상세화한다. stronger rollback, multi-root/remote, alias/epoch/registration event read 지원, source retention 삭제, Recovery/Transfer 또는 trust purpose 변경이 필요하면 별도 재검토한다.

## 13. Implementation-ready exit / 다음 순서 / 상태

2026-10-03 구현 상태: 이 결정의 계약을 재설계하지 않고 read-only Source Verifier/Capability를 구현했다. [구현 검증 보고서](../10-operations/ibla-source-verifier-capability-validation.md)에 코드 경계·새 검증을 기록한다. production source는 unavailable이며 Initial Authorization·registration writer 등 다음 단계는 미구현이다. 아래 당시 Decision 제출 기록은 보존한다.

IMPLEMENTATION_READY: §3~10은 input port, 원본 authenticated bundle·A/C/I codec, correlation·coverage·scope absence, eligibility, opaque capability/registry/lifetime/handoff·error/redaction·negative tests를 추가 architecture Decision 없이 구현하도록 결정했다. 이는 production readiness가 아니다. 실제 operating source가 없는 adapter는 unavailable가 맞고, disposable fixture를 production source로 자동 선택하지 않는다. source-specific mechanics/codec/read-only adapters는 **다음 하나의 구현 PR 안에서 직접 확장**한다. 별도 중간 Foundation을 삽입하지 않는다.

후속 test matrix는 [보고서의 28개 exit 질문과 acceptance matrix](../10-operations/ibla-source-registration-contract-validation.md)를 따른다. signed A/C만 있고 independent provenance가 없는 경우, root/initializer key self-enrollment, external unknown/prior/alias/epoch, incomplete domain history/H prefix/pending, each identity mismatch, stale/foreign/copied handle, mint/handoff 경쟁, transaction/lease/source release·cleanup quarantine, source replacement/ACL drift, proof replay/expiry/clock rollback, mutation 0을 검증한다. 이번 tests 실행 결과가 아니다.

| 항목 | 현재 상태 |
|---|---|
| L/H Persistence | IMPLEMENTED FOUNDATION / #198 merged |
| Authentic Source Contract | DECIDED / read-only Foundation 구현 |
| First-Registration Eligibility Contract | DECIDED / read-only Foundation 구현 |
| Source Verifier | IMPLEMENTED FOUNDATION / 검토·병합 상태는 PR #200 참조 |
| First-Registration Capability | IMPLEMENTED FOUNDATION / 검토·병합 상태는 PR #200 참조 |
| Initial Authorization | NOT IMPLEMENTED |
| Provisioning / GENESIS | NOT IMPLEMENTED |
| Authentication / Activation | UNAVAILABLE |
| Phase 9 | 0/18, 0% |

고정 dependency chain: #198 L/H Persistence Foundation → ADR-110 이 계약 → **Authentic IBLA Source Verifier + First-Registration Capability Foundation** → Initial Authorization issue/consume/cancel → Production Journal Provisioning/GENESIS → Authentication/Activation Production integration. 실제 새 BLOCKER가 없는 한 chain을 임의로 늘리지 않는다. 다음 구현도 Initial Authorization issue/consume/cancel, registration writer/schema 확장, journal provisioning/GENESIS/Auth/Activation/Recovery/Transfer/실제 production provisioning은 제외한다. 이번 제출은 검증된 문서 Commit/Push/Draft PR까지만, Ready/merge/auto merge/branch 삭제 없음.
