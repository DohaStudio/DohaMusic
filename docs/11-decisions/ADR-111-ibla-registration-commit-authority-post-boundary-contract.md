# ADR-111: IBLA Registration Commit Authority and POST Boundary Contract

> 상태: [설계 결정 — DECIDED — ordering/restart 부분 대체됨 — Writer IMPLEMENTED FOUNDATION (작업 브랜치)]
> 작성일: 2026-10-04
> 최종 수정일: 2026-10-04
> 기준 develop: 26452a675c2bf2ab6ae327d6e17e282bbc818a1f (#200 merged)
> 구현 준비 판정: 원 판정은 IMPLEMENTATION_READY였으나 pre-PREPARED restart 모순이 재현됐다. 해당 경로의 현행 판정·계약은 ADR-112를 따른다.
> 관련 PR: [#201](https://github.com/DohaStudio/DohaMusic/pull/201). 최초 Decision은 Draft 제출에서 종료했으며 후속 최종 감사·Ready·병합 상태는 PR 기록과 [검증 보고서](../10-operations/ibla-registration-commit-authority-contract-validation.md)를 따른다.
> 관련 결정: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [ADR-107](ADR-107-independent-bootstrap-lineage-authority.md), [ADR-108](ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md), [ADR-109](ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md), [ADR-110](ADR-110-ibla-authentic-source-first-registration-contract.md)

> 부분 대체: [ADR-112](ADR-112-ibla-registration-attempt-durable-boundary-restart-contract.md)가 §2 authority-chain 순서, §5 final handoff/deadline, §8 steps 1~3, §9 pre-PREPARED/restart/prepare 응답 유실 정책 및 이에 의존한 구현 준비 판정을 부분 대체한다. 아래 원문 순서·restart 제한은 역사이며 해당 범위의 구현 근거로 사용하지 않는다. 나머지 R/Q/wire/v2/POST/독립 H 확인 계약은 보존한다.

> 현재 구현 상태 (이 작업 브랜치): ADR-111/112 Registration Commit Writer·v2 L/H·original frame/forward reconciliation Foundation을 구현·검증했다. [Writer 검증 보고서](../10-operations/ibla-registration-commit-writer-validation.md)를 따른다. 아래 NOT IMPLEMENTED/docs-only/Draft 제출 문구는 최초 Decision 당시 이력이며 이번 Writer 구현 또는 production 완료를 뜻하지 않는다. 후속 develop 병합은 PR 기록으로 확인한다.

## 1. 배경·문제·기존 결정 보존

직전 IA Decision 요청은 Initial Authorization을 PRE-registration writer permission으로 취급하여 IA_PURPOSE_PRE_POST_ORDERING_CONFLICT에서 중단했다. 충돌은 기존 ADR 사이가 아니라 그 요청의 목적 혼동이다. ADR-107 §5의 register lineage는 현 root의 exact signed registration과 독립 initializer 확인을 받은 Registry Custodian의 동작이다. 같은 절의 issue는 이미 등록된 lineage의 fresh registration/currentness와 설치 proof를 요구한다. IA consume은 INITIAL_SEALED와 같은 registry transaction에서 영구 소비하며 GENESIS 성공 전에도 되돌리지 않는다.

ADR-110 §7~9의 First-Registration Capability는 PRE prerequisite이고 등록 완료·IA가 아니다. L의 REGISTRATION_COMMITTED durable commit이 irreversible PRE → POST 경계다. 등록 전 IA issue는 허용하지 않는다. 이 ADR은 ADR-107/110을 supersede하거나 그 의미·기존 파일을 변경하지 않는다. ADR-108의 registration과 IA event family도 구분한다.

결정 끝점은 등록을 안전하게 한 번 기록하고 POST로 전환하는 것이다. IA wire/TTL/issue·consume·cancel 상세, INITIAL_SEALED protocol, Provisioning/GENESIS/Auth/Activation/Recovery/Transfer는 결정·구현하지 않는다. Production code/tests/schema/Alembic/API 변경도 없다.

## 2. 선택·대안·authority chain

**Option A: First-Registration Capability를 fixed exact Registration Writer로 직접 one-shot handoff한다. 별도 Registration Commit Authority를 mint하지 않는다.** capability만으로 write를 승인하지 않는다. live PRE prerequisite + 현 root의 등록 전용 exact signed intent R + 독립 initializer 등록 확인 Q + 현재 명시 위임된 Registry Custodian의 exact writer provenance를 모두 결합한 private execution만 등록 permission이다. public receipt/DTO/constructor/config flag가 이를 대신할 수 없다.

| 기준 | A: direct exact writer (선택) | B: 별도 opaque authority | C: 기존 IA 재사용 (기각) |
|---|---|---|---|
| 목적·기존 계약 | 등록 1건만; cap은 prerequisite 유지 | 별도 등록 purpose라면 가능 | POST IA를 PRE에 요구하므로 순환·ADR-107/110 위반 |
| 최소 권한·writer binding | fixed callback과 R/Q exact subject, arbitrary append 없음 | 동일 binding을 새 registry에 복제해야 함 | IA/seal 권한이 등록으로 섞임 |
| lifetime | live source/lease/transaction 교집합 | 추가 객체가 원본보다 오래 살지 못하도록 별도 관리 | 기존 IA 수명이 PRE permission과 다름 |
| crash·replay | memory handoff + 기존 H barrier/L operation | 두 memory 소비 상태와 L/H를 대조해야 함; 내구성 개선 없음 | seal 소비와 등록 소비가 혼동됨 |
| serialization·custody | opaque cap만, 원본은 held provider custody | opaque라도 별도 holder/registry 필요 | IA artifact 재사용 금지 위반 |
| auditability | R/Q digests + exact L event/H pending | 같은 facts 외에 mint 상관관계 추가 | purpose별 감사 불가 |
| circular trust·self-enrollment | 외부 pins/위임을 독립 검증; L 자기 승인 금지 | 외부 pins 없으면 새 token도 해결 못함 | 아직 없는 등록이 IA의 전제 |
| 구현 복잡성 | 기존 one-handoff/H/CAS 확장 | 추가 mint/handoff/revoke lifetime 처리, 현재 필요 없음 | 적용 불가 |

B는 향후 실제로 독립 consumer/비동기 전달이 필요할 때만 새 Decision으로 재검토한다. 장기 bearer/persistent token store/generic authority framework는 선택하지 않는다. REGISTRATION_AUTHORIZED 별도 L event도 만들지 않는다. R/Q는 외부 승인 evidence이며 L event와 live permission을 혼동하지 않는다.

외부 accepted designation/current delegation → independently provisioned root/initializer pins와 commissioning originals → Authentic Source Verifier → First-Registration Capability → R/Q를 확인한 fixed Registry Custodian Registration Writer → H PREPARED → L REGISTRATION_COMMITTED durable (**POST**) → 독립 H CONFIRMED와 fresh registered-currentness → 후속 기존 IA issue → 기존 INITIAL_SEALED consume → 후속 Provisioning/GENESIS 순서다. 마지막 단계들은 미구현이며 이 permission으로 실행하지 않는다.

## 3. Exact writer·소유자·신뢰 입력

후속 internal role 이름은 RegistrationCommitWriter다. 이것은 공개 Python API 선언이 아니다. ADR-107 Registry Custodian의 등록 역할을 ADR-110 original accepted designation/A의 ledger_custodian_ref에 exact bind한다. root가 등록 동작과 이 custodian을 명시 승인하고 독립 initializer가 등록 원본·scope·위임을 확인해야 한다. A의 commissioning 위임 또는 key possession만으로 R/Q를 생략할 수 없다. root/initializer/custodian의 겸임은 원래 accepted designation의 명시 위임과 독립 대조가 있을 때만 가능하다. 별도 external writer signing key는 만들지 않는다.

trusted offline composition만 원래 provider·R/Q retained originals·independent pins·custodian provenance·L writer owner·독립 H keeper를 고정한다. env/request/app DB에서 writer/source/pin을 고르거나 callback을 바꿀 수 없다. OS 관리자/파일 owner/CLI 문자열은 authority가 아니다. R/Q는 commissioning A/C, policy receipt, IA signature, journal GENESIS로부터 재해석하지 않는다.

RegistrationCommitOwner는 이 exact 실행의 domain lease와 L root SessionTransaction을 소유한다. HKeeperOwner는 별도 custody의 H root transaction과 별도 query_only L reader를 소유한다. SourceObservationOwner는 원본/native/read connection/proof/lease lifetime을 hold하며 각 verification read pass의 transaction만 닫는다. reader pass 종료 후에만 writer transaction을 연다. repository는 flush만 하고 commit()/rollback()하지 않는다. owner가 실제 SQLite BEGIN IMMEDIATE 및 commit/rollback을 수행한다. nested/replaced/ended transaction, 다른 pid/native thread 또는 임의 L repository caller는 등록할 수 없다.

v2의 public/generic repository append는 정상 canonical REGISTRATION_COMMITTED 입력도 IBLA_UNAVAILABLE로 거부한다. reader/codec가 새 kind를 이해하는 것은 write 위임이 아니다. 기존 CAS/insert/flush mechanics는 fixed Writer 내부의 private append 경로에서만 재사용하며, provider registry의 delivered-and-delivering 실행 frame와 위 R/Q/current role/exact root transaction을 실제로 대조해야 한다. caller-supplied guard bool/DTO/receipt로 private 경로를 열지 않는다. 별도 transferable authority 객체를 mint하지 않으며 이 실행 frame는 callback 종료와 함께 끝난다.

## 4. Registration 전용 승인 원본 R/Q

R/Q는 기존 외부 root·독립 initializer가 보존하는 목적별 원본이다. 새 권한 issuer/key/store가 아니다. trusted composition은 실제 원본을 held read하고 원래 독립 provisioned verifier로 Ed25519 검증한다. 원본 안의 key를 trust-enroll하지 않는다. 원본 ref는 조회 조건이지 bearer가 아니다. deployment 자체가 R/Q를 생성·자기 승인할 수 없다. fixture에서만 독립 생성한 disposable 원본을 사용할 수 있고 production source는 unavailable를 유지한다.

공통 wire는 strict UTF-8 RFC8785 JCS, exact object fields, duplicate/unknown keys·float·bool counter·nonfinite·overflow 거부다. UUID는 기존 require_uuid profile, digests는 소문자 SHA-256 64 hex, opaque refs는 기존 require_reference에 추가 ASCII 1~128 bytes 제한, counters는 실제 int 1..2^53-1, 시각은 UTC-second YYYY-MM-DDTHH:MM:SSZ다. 서명 envelope는 정확히 {payload, signature}; signature는 기존 unpadded base64url Ed25519 64 bytes다. root/initializer verifier key는 envelope 필드가 아니다. validity는 issued_at < expires_at, 최대 24시간이며 A/C·current delegation과 교집합이다. 긴 문서 validity는 live permission 수명을 연장하지 않는다.

R payload의 정확한 fields:

| field | exact 값·생성/확인 책임 |
|---|---|
| schema / purpose | dohamusic/ibla-registration-intent/v1 / IBLA_REGISTRATION_COMMIT_ONLY |
| registration_id / operation_id | root가 동작에 부여한 서로 독립 UUID; retry 때 유지 |
| binding | ADR-109 Binding의 11 fields 전체; A/C/mapping/actual L/H와 exact |
| inventory_digest / registration_scope_digest | A의 inventory digest / 해당 inventory의 scopes JCS에 아래 scope domain을 붙인 digest |
| intended_journal_id | A/I가 지정한 UUID; journal 생성 권한 아님 |
| expected_l_head | {revision:1,digest:exact COMMISSION event digest}; caller wildcard/최신 자동 대체 없음 |
| expected_h_head | {revision:실제 H control sequence,digest:실제 H control digest}; initial CONFIRMED만 허용 |
| expected_h_confirmed | expected_l_head와 같은 {revision,digest} |
| writer_ref / initializer_ref | accepted delegation + A의 ledger custodian / independently delegated initializer exact ref |
| root_key_id / initializer_key_id | 원래 independently pinned public verifier ref와 exact; 신규 key 채택 불가 |
| positive_origin_digest / commissioning_confirmation_digest | 원래 A의 positive origin / 원래 C payload comparison digest |
| issued_at / expires_at / recorded_at | root가 고정한 validity / event의 고정 audit 시각; recorded_at=issued_at |

Q payload의 정확한 fields는 schema, purpose, intent_digest, initializer_ref, initializer_key_id, original_confirmation_ref, original_confirmation_digest, issued_at, expires_at이다. schema=dohamusic/ibla-registration-confirmation/v1, purpose=IBLA_REGISTRATION_CONFIRMATION_ONLY. intent_digest는 아래 R canonical payload digest와 exact. original_confirmation_ref/digest는 initializer가 독립 대조·명시 수락한 **등록 확인** 원본의 reference/exact-byte SHA-256이다. commissioning C를 이 등록 원본으로 바꿔 쓰지 않는다. 실제 외부 위임·human acceptance와 R에 포함된 whole scope/root/custodian/native custody를 독립 확인한 original provenance를 source owner가 hold한다. Q validity는 R validity 안에 들어야 한다. write 시각은 R/Q 모두 issued_at ≤ trusted now < expires_at이어야 하며 미래 발급 시각을 허용하지 않는다. current initializer 위임이 없으면 deny한다.

R payload ≤8 KiB, Q payload ≤4 KiB, 각각 signature envelope ≤16 KiB. digest/signature domain은 ASCII 다음 문자열 + NUL + canonical payload bytes의 SHA-256 / Ed25519 message다. digest는 같은 domain+payload의 SHA-256, signature는 domain+payload bytes 자체에 대한 Ed25519다.

| 대상 | 정확한 domain |
|---|---|
| R payload digest·서명 | DohaMusicIblaRegistrationIntentV1 |
| Q payload digest·서명 | DohaMusicIblaRegistrationConfirmationV1 |
| scopes digest | DohaMusicIblaRegistrationScopeV1 |

R/Q는 serializable durable **승인·감사 evidence**다. 이것만 deserialize/재생하여 write할 수 없다. live permission은 다음 절의 exact provider registry와 one-handoff 실행이다. R/Q validity 만료가 이미 durable한 등록 사실을 없애지 않는다. 최초 원본 보존은 외부 governance custody이며 별도 generic token DB는 없다.

## 5. Binding·lifetime·one-shot

permission은 domain/deployment/installation/proof/lineage/A ID+digest/designation digest/epoch/I digest/whole registration scopes/intended journal/L ID+native identity+expected head/H ID+native identity+expected head+confirmed tuple/root·initializer·custodian provenance/R·Q digests/operation+registration IDs/fixed writer instance/source observation/provider/attempt/domain lease/pid/native thread/exact L root transaction에 결박된다. source observation UUID는 provider가 만들고 private registry에서 대조한다. 공개 UUID를 받아 재구성하지 않는다. 전체 I는 held source 내부에서 원본과 대조하며 digest만으로 coverage 검증을 생략하지 않는다. scope widening/subset 선택/cross-domain/reinstallation/new A/reset은 금지한다.

최종 handoff revalidation 직후 fixed writer callback 진입 시 monotonic writer deadline = min(original capability deadline, callback 진입 monotonic+30초)다. 동시에 source/lease/process/native thread/current R/Q/A/C validity/fresh proof/원본 native custody 및 실제 writer transaction lifetime의 교집합이다. 기존 최대 15분을 복사하거나 새 15분으로 reset하지 않는다. wall/monotonic rollback·source release·transaction 교체/종료·lease 상실은 즉시 invalidate한다. writer는 H prepare 직전, L transaction의 검증 직전 및 durable commit 직전에 deadline/current ownership을 검사한다. commit 자체가 deadline을 넘어 응답해도 already committed fact를 취소하지 않고 불명 응답은 reconcile한다. restart 후 live permission은 0이다.

ADR-110과 같이 provider lock 아래 delivered를 먼저 단조롭게 표시한 뒤 fixed consumer를 한 번 호출한다. constructor 직접 생성/copy/deepcopy/pickle/JSON/subclass/export/import, handle 저장·공유, 다른 consumer invocation은 거부한다. delivered → abandoned/finished만 가능하고 original cap을 복원하지 않는다. callback exception/timeout/응답 유실도 재전달하지 않는다. mint 이후 별도 authority mint 단계는 **N/A**다. cap 전달 전 위의 R/Q·writer binding이 완료돼 있어야 하며 generic caller data를 handoff에서 끼워 넣지 않는다.

writer의 자체 H PREPARED/L append로 source 관측 head가 바뀌는 것은 operation-specific 진행이다. handoff 전 canonical 8개 PRE 조건은 전부 fresh 검증하고 그 read pass를 닫는다. H prepare 뒤 그 8개를 다시 적용해 H CONFIRMED를 요구하지 않는다. 대신 held 원본/lease/native/proof/current delegation을 계속 검증하고 H의 exact 자기 PREPARED candidate와 expected predecessor를 확인한다. 다른 operation/head 변경은 conflict다. POST 이후에는 First-Registration verifier를 registered-currentness reader로 승격하지 않는다.

## 6. REGISTRATION_COMMITTED exact wire

신규 kind는 REGISTRATION_COMMITTED 하나다. schema=dohamusic/ibla-ledger-event/v2이고 이 v2 event profile은 등록에만 쓰인다. exact envelope fields는 schema, binding, event_id, operation_id, revision, previous_digest, kind, evidence_digest, recorded_at, registration이다. 앞 9개 fields는 ADR-109 관례를 따른다. event_id=R.registration_id, operation_id=R.operation_id, revision=expected_l_head.revision+1=2, previous_digest=expected_l_head.digest, kind=REGISTRATION_COMMITTED, evidence_digest=R intent digest, recorded_at=R.recorded_at로 고정한다. writer가 시각/UUID를 retry마다 다시 만들지 않는다.

registration nested object의 **정확한 fields**:

| fields | 값·검증 |
|---|---|
| registration_id / purpose | event_id와 동일 / IBLA_REGISTRATION_COMMIT_ONLY |
| inventory_digest / registration_scope_digest / intended_journal_id | R 및 held A/I와 동일 |
| expected_l_head / expected_h_head / expected_h_confirmed | R와 exact; L predecessor와 H prepare 이전 control tuple |
| writer_ref / initializer_ref / root_key_id / initializer_key_id | R/Q/current original delegation와 exact |
| intent_digest / confirmation_digest | R payload digest / Q payload digest; evidence_digest와 intent_digest 동일 |
| commissioning_confirmation_digest / positive_origin_digest | R/A/C와 exact; 등록 Q와 commissioning C 구별 |
| observation_id | original provider가 발급한 one observation UUID; audit correlation만, 권한 객체 아님 |

domain 전체 binding의 11 fields는 domain_id, anchor_id, anchor_digest, ledger_id, checkpoint_id, installation_id, installation_proof_digest, deployment_id, lineage_id, designation_digest, authority_epoch다. 새로운 caller flag/OS path/key bytes/ACL/source handle/raw R/Q/I/installation signature는 event에 넣지 않는다. private registry가 original observation_id와 writer binding을 검증하며 UUID 일치만으로 승인하지 않는다.

L event ≤8 KiB이고 이를 embedded pending으로 담은 각 H control ≤16 KiB도 **H prepare 전** JCS encode/parse 검증한다. 신규 nested object depth에 맞게 bounded parser 최대 object depth 6을 명시한다. R/Q/I raw를 embedded하지 않는다. unsupported fields/schema/kind·counter/type·signature·scope 불일치는 fail closed다.

event digest = SHA-256(ASCII DohaMusicIblaLedgerEventV2 + NUL + exact canonical event bytes). operation fingerprint = SHA-256(ASCII DohaMusicIblaOperationV2 + NUL + 같은 event bytes). digest/fingerprint 자체는 envelope hash 입력 필드가 아니다. event/operation IDs, purpose, all binding, predecessor, R/Q authority correlation, observation UUID, audit time까지 fingerprint에 포함한다. full canonical event는 H PREPARED에 영속하므로 restart에서 observation UUID나 시각을 새로 만들어 fingerprint를 바꾸지 않는다.

## 7. L/H schema version·reader·migration

실제 ADR-109 schema.py는 L kind CHECK(COMMISSION,HISTORY_BLOCK,RETIRE), identity version CHECK=1, exact catalog SQL 비교를 사용한다. 따라서 **v1 additive로 가장하지 않고 external L/H physical schema version 2를 결정한다.** v1은 수정하지 않고 기존 Foundation profile로 남는다. app Alembic/journal schema와 관계없다. 이번 PR의 실제 schema/migration 변경은 0이다.

v2 physical contract는 ADR-109의 세 table/불변 trigger/CAS/uniqueness/native separation/DELETE journal/synchronous EXTRA를 그대로 유지하며 다음 변경만 허용한다.

- 양쪽 ibla_identity version 및 CHECK를 2로 변경한다. role/binding은 불변이다.
- L ibla_events.kind CHECK에 REGISTRATION_COMMITTED 하나를 추가한다.
- L에 partial unique index **CREATE UNIQUE INDEX ibla_single_registration ON ibla_events(kind) WHERE kind='REGISTRATION_COMMITTED'**를 추가한다. DB가 한 고정 domain/binding을 소유하므로 domain당 등록 1건을 강제한다. registration_id=unique record_id와 UNIQUE(operation_id)도 그대로다.
- H의 state/kind/operation+kind uniqueness는 변경하지 않는다. 새 H control schema=dohamusic/ibla-checkpoint-control/v2, domain=ASCII DohaMusicIblaCheckpointControlV2+NUL, exact fields는 ADR-109와 같다. pending은 strict supported v1 legacy event 또는 위 v2 등록 event를 담는다. H 상태 머신은 동일하다.

v2 reader는 original v1 L events/원래 digests/fingerprints와 H v1 control prefix를 byte-for-byte 검증하고, 새 등록 event 및 H v2 suffix를 지원한다. H v2 최초 record는 original H 마지막 digest/sequence를 predecessor로 이어야 하며 v2 시작 후 H v1 append는 금지한다. L의 COMMISSION/HISTORY_BLOCK/RETIRE는 원래 v1 wire/digest를 유지하고 REGISTRATION_COMMITTED만 v2다. unknown kind 또는 malformed mixed history를 건너뛰지 않는다. v1-only reader는 v2 store/history를 fail closed로 거부한다. H의 independent L reader와 Source Verifier의 exact schema 검사도 같은 최소 구현 단위에서 v2를 지원해야 한다. First-Registration eligibility는 v2 store에서도 L의 exact original COMMISSION revision 1만 허용한다. 등록 이력을 알고 거부하는 것과 POST authority를 발급하는 것은 다르다.

기존 v1 store는 runtime/startup 자동 migration·backfill·새 empty L/H 교체를 하지 않는다. v2 fixture는 explicit disposable setup으로만 만든다. 기존 production v1의 이행은 original root/custodian/독립 H keeper가 승인한 **offline external schema maintenance**이며 아직 미구현·미수행이다. 두 custody를 멈추고 domain lease/exclusive access 아래 각 DB의 별도 local schema transaction에서 version/CHECK/index만 이행한다. 기존 event/control envelope·IDs·digests·fingerprints·revision·head·binding과 native file identities를 그대로 보존하고, immutable guards를 restore한 exact v2 catalog/integrity/full-history 검증을 완료해야 한다. root의 exact maintenance approval와 initializer 대조 원본은 기존 external governance custody에 보존하며 R/Q 등록 승인으로 migration을 승인하지 않는다. reader가 migration 도중 실행되거나 L v2/H v1 혼합 상태면 unavailable다. app migration, authority reset, history rewrite, A/epoch 새 발급, pending 소거 또는 file replace는 허용하지 않는다. active PREPARED/UNCERTAIN이면 migration을 중단한다. 두 DB 이행은 distributed atomic이 아니며 interruption 뒤 승인된 maintenance owner가 원래 exact facts 보존 검증을 마칠 때까지 runtime을 차단한다.

Writer Foundation은 v2 public fixtures/strict dual reader와 위 exact profile을 구현한다. 실제 production maintenance tool/ceremony는 이번·다음 Foundation의 성공 조건이 아니며 production unavailable를 해제하지 않는다. 별도 중간 Foundation을 삽입하지 않는다. physical v2/catalog와 byte-preserving migration postconditions가 고정됐으므로 다음 writer 구현자가 버전 정책을 새로 결정할 필요가 없다.

## 8. Prepare → append → confirm·원자성

1. original domain lease 아래 PRE source/full L/H read + R/Q/current delegation/proof/native 확인 및 exact immutable event compile를 끝낸다. candidate fingerprint/size를 검증한다. writer callback 전에 original source verification read pass를 닫고 handoff를 1회 기록한다.
2. HKeeperOwner의 short root transaction: 실제 whole L head가 R.expected_l_head이고 H가 exact R.expected_h_head 및 CONFIRMED(expected_h_confirmed)인지 독립 read한다. exact candidate로 PREPARED를 append/commit한다. confirmed tuple은 그대로, pending에 full candidate를 영구 보존한다. H transaction/read snapshot을 닫는다. 응답 불명이면 L append로 진행하지 않는다.
3. H의 exact committed PREPARED를 별도 short query-only pass에서 먼저 검증하고 종료한 뒤 RegistrationCommitOwner의 short actual L root transaction: whole history/catalog/native/source/lease/deadline/current delegation, original rev1 no-prior, exact operation 부재와 expected head 및 exact committed H PREPARED를 재검증한다. event+operation uniqueness+single registration constraint+head CAS를 한 L transaction에서 flush/commit한다. repository가 transaction을 commit하지 않는다. 이 durable commit이 POST다. live 등록 permission은 이 L transaction 종료로 끝나며 H confirmation은 별도 keeper 권한으로만 진행한다. H PREPARED 검사는 별도 short read를 닫고 L 쓰기 전에 끝내며 H write transaction과 L write transaction을 겹치지 않는다. 같은 domain lease가 검사 이후 다른 eligibility writer를 차단한다. L root transaction은 H 검사 pass 종료 후 시작한다.
4. L transaction 종료 뒤 HKeeperOwner가 **별도 query_only L connection/root transaction**으로 전체 실제 committed history를 읽는다. pending exact envelope/fingerprint/predecessor와 실제 L event/head가 동일할 때만 H short transaction에서 CONFIRMED를 append/commit한다. writer의 head DTO/uncommitted Session/callback True를 받아 confirm하지 않는다. H 응답이 불명이면 correlated success를 반환하지 않는다.
5. fresh separate actual L/H correlation을 완료하면 read-only audit result를 반환한다. result는 registration_id, operation_id, fingerprint, L event/head, H control/head, 상태를 담는 비교 facts이며 IA permission이 아니다. source closure 뒤 전달된 facts를 downstream authority로 재사용하지 않는다.

단일 L transaction의 event/unique indexes/head CAS만 원자적이다. memory delivered, H PREPARED, L commit, H CONFIRMED 사이 distributed transaction/atomic rollback은 없다. pending은 무기한 retain하고 timeout으로 지우지 않는다. PREPARED 성공을 확인한 바로 그 live callback만 append 1회를 시도한다. callback이 끝난 후 fresh permission으로 pending을 채워 넣는 경로는 없다.

## 9. Crash·replay·reconciliation

| crash/실패 시점 | authoritative state·POST 판단 | retry/reconcile·duplicate 차단 |
|---|---|---|
| capability handoff 전 | L rev1/H CONFIRMED; live cap은 process와 종료 | 새 original source observation으로 eligibility 전부 검증 후 새 cap 가능; 기존 handle 복원 없음 |
| 별도 writer authority mint 전/후 | Option A이므로 mint 단계 N/A | 별도 token 생성·복원 없음; 다음 행을 적용 |
| handoff 후 H prepare 전 / append 전 준비 단계 | cap delivered; H/L 미변경이 실제 확인되면 PRE | 원 cap 재전달 금지. H prepare 미시도 또는 같은 live owner의 확정 rollback이면 새 observation/R/Q-currentness로 새 cap 가능. 불명/restart이면 다음 barrier 정책 적용 |
| H PREPARED durable 후 L append 전 | old L confirmed tuple + pending, POST 증거 없음; 안전 상태 UNCERTAIN | 새 process의 자동 append/prepare 취소/TTL reset 금지. 기존 L만 read, 없으면 pending retained unavailable |
| H prepare 응답 유실 | durable 여부 불명; writer는 L에 접근하지 않음 | independent existing H/L read만. pending이 없다는 관측도 restart 뒤 never-prepared 증명 아님; original operation 자동 retry 없음 |
| L append 중 ambiguous / commit exception | memory 권한 abandoned; H pending 존재 | full existing L+H read. exact event 있으면 POST; 없으면 UNCERTAIN 유지. append 재시도 없음 |
| L durable append 뒤 response loss | 이미 POST, cap permanently invalid | same ID/fingerprint stable read-only event result; keeper만 H 확인 보완. 두 번째 L append 0 |
| L append 후 H update 전 crash | POST + H PREPARED/UNCERTAIN, downstream unavailable | 독립 keeper가 실제 full L을 읽고 exact H CONFIRMED만 전진 |
| H confirm 실패/응답 유실 | POST; fresh confirmed correlation 확인 전 IA readiness 없음 | actual H/full L read 후 exact already confirmed result 또는 동일 pending의 forward confirm; 새로운 L write 없음 |
| writer callback 예외/timeout/postcheck 실패 | delivered는 복원 안 함; durable facts는 따로 판단 | caller failure를 L rollback/등록 부재로 변환하지 않음. 위 실제 단계에 맞춰 read-only reconcile |
| process restart | source/cap/live writer permission 0 | OriginalReconciliationReader와 독립 H keeper만 기존 operation 대조. new writer permission으로 기존 pending append 금지 |

OriginalReconciliationReader는 trusted composition의 held original domain mapping/custody와 actual query_only whole L/H를 소유하는 목적별 reader다. registration-authority/IA issuer가 아니며 비교 DTO로 enroll할 수 없다. L을 쓰거나 permission을 mint하지 않는다. keeper만 이미 durable한 exact existing L candidate를 H PREPARED/UNCERTAIN에서 CONFIRMED로 전진할 수 있다. 이 keeper의 H root transaction은 HKeeperOwner 소유다. exact L 부재는 rollback/hidden success를 구별하지 못하므로 pending/UNCERTAIN을 유지한다. manually clearing pending/new A/new epoch/Recovery/Transfer로 재개하지 않는다.

same operation+same fingerprint의 조회는 저장된 exact event와 historical L result를 byte-stable 반환한다. current H readiness/status는 별도로 fresh 읽으며 과거 success와 혼동하지 않는다. 같은 operation+다른 fingerprint는 IBLA_CONFLICT, 같은 registration_id+다른 operation 또는 다른 domain/binding은 conflict다. 이전 R/Q/observation이 만료돼도 stored fact 조회는 가능하지만 새 write 권한은 없다. old operation 전체 candidate는 H pending/L에 보존되므로 replay에서 observation_id/recorded_at을 재생성하지 않는다.

등록 event가 있으면 same operation 조회 이외 second registration은 new cap/new R/new registration UUID로도 불가다. source의 no-prior 검사 + fixed rev1 predecessor + domain lease + unique registration index + operation/record uniqueness + expected-head CAS가 중복을 막는다. app row 삭제/rollback/journal 부재/새 설치 ID는 PRE 복귀 근거가 아니다. H가 lagging/pending이면 새 cap 발급도 unavailable이며 retained history를 우회할 수 없다.

## 10. POST와 IA readiness의 구분

**irreversible POST는 L durable REGISTRATION_COMMITTED의 존재다.** H confirm 지연/유실, callback failure, app row 삭제는 이를 취소하지 않는다. evidence가 불명이면 상태를 PRE로 추정하지 않고 UNKNOWN/UNAVAILABLE로 남긴다. UNKNOWN은 새로운 H 상태가 아니라 caller가 현재 사실을 확정하지 못한 비교 결과다.

후속 IA issue의 최소 진입 조건은 fresh authentic registered-currentness reader가 같은 original domain/A/deployment/installation/proof/lineage/registration ID/scope를 검증하고, current supported **whole** L history에 exact registration event가 있으며 block/terminal/불명 위임이 없고, independent H가 실제 current L head를 CONFIRMED하고, 원래 designation의 **current IA issuer authority**와 fresh installation proof를 별도로 확인하는 것이다. 과거 registration head만 확인해 current L을 건너뛰지 않는다. ADR-110 PRE verifier/cap은 이 reader 또는 IA issuer가 아니다. registration writer의 custodian 역할이 IA issue 역할을 자동 부여하지 않는다.

L durable/H pending이면 POST이나 IA issue unavailable다. L/H confirmed도 IA 발급 자체는 아니다. R/Q/cap/registration audit result/token/receipt/signature를 IA intent·consume·seal 또는 GENESIS 권한으로 재사용하지 않는다. IA 상세 계약 보완 필요 여부는 Writer가 develop에 병합된 뒤 별도 감사한다. INITIAL_SEALED의 기존 consume 의미는 보존하고 여기서 설계하지 않는다.

## 11. Security·검증·한계

private repr는 fixed opaque 문자열만, public error는 IBLA_UNAVAILABLE/IBLA_CONFLICT/IBLA_INCONSISTENT만 사용한다. debug response/log/stack trace에 private path/key/native handle/ACL/raw authority source/R/Q/signature/proof/개인 데이터를 노출하지 않는다. audit IDs/digests도 governance access 경계 내에서만 제공하며 임의 public API를 만들지 않는다. TTL flag, caller-created receipt, arbitrary writer repository, serialized cap으로 authority를 만들 수 없다.

다음 Writer Foundation의 acceptance tests는 새 immutable profile encode/decode, pinned R/Q purpose/signature/delegation, all binding/lifetime/thread/custody/lease checks, one-handoff concurrent winner, direct repository unauthorized append deny, rev1→reg CAS/index uniqueness, mixed v1/v2 full-history reader, unknown-kind fail closed, actual H prepare/independent confirm, 위 crash/replay 모든 행, POST와 IA readiness 구분, repr/redaction을 포함해야 한다. 이번 docs-only 작업은 이 tests를 작성/실행하지 않는다.

실제 production custody/commissioning ceremony/private authority source/production maintenance는 미검증·미수행이다. power-loss/storage-controller durability 미검증, hardware anti-rollback/remote consensus 미지원, H standalone 마지막 PREPARED rollback 및 consistent L/H historical rollback 탐지 기존 한계가 남는다. source/root/privileged authority compromise를 해결했다고 주장하지 않는다. registered fact의 영구성은 승인된 custody/history 보존 가정 아래이며 stronger anti-rollback을 뜻하지 않는다.

## 12. 영향·재검토·후속·구현 준비

L/H·Source Verifier·First-Registration Capability는 IMPLEMENTED FOUNDATION. Registration Commit Contract는 DECIDED. Registration Commit Writer·Initial Authorization·Provisioning·GENESIS는 NOT IMPLEMENTED. Authentication/Activation은 UNAVAILABLE. Phase 9는 0/18, 0%다. runtime code/tests/app schema/API/Frontend/workflow delta 0이다. v2 external schema는 결정만 했으며 현재 구현은 여전히 ADR-109 v1이다.

별도 consumer/lifetime, multiple A/epoch/lineage, 다른 native identity, external migration policy 변경, stronger durability/anti-rollback, IA 목적 변경 필요가 실제 발생하면 새 Decision을 요청한다. 현재의 new intermediate Foundation은 필요 없다. [검증 보고서](../10-operations/ibla-registration-commit-authority-contract-validation.md)의 25/25 exit questions가 이 exact 계약에 답한다.

판정은 **IMPLEMENTATION_READY**: First-Registration Capability direct handoff → exact Registration Commit permission/Writer → REGISTRATION_COMMITTED → H/reconciliation → POST handoff만이다. IA 전체 구현 준비 완료가 아니다. 이 Decision이 별도 최종 검증·Ready·guarded squash merge로 develop authority가 된 경우에만 다음 작업 **Registration Commit Writer Foundation**을 시작한다. 최초 Decision 작업은 Draft 제출에서 종료했다. 후속 최종 감사·Ready·guarded squash merge 상태는 PR #201 기록을 따르며 writer 구현은 별도 작업이다.
