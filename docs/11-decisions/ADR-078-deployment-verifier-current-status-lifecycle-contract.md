# ADR-078: Deployment Verifier Current-Status / Lifecycle Admission Contract

> 상태: [제안 — Contract Resolution, 별도 Draft PR; 구현·운영 비활성]
> 작성일·최종 수정일: 2026-09-18
> 기준 develop: `fdf71b4202486a99b9ababec898fd3ae3b664883` (#163 squash merge)
> 관련 PR: 이 Contract의 develop 대상 Draft PR
> 관련 문서: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [Architecture](../03-architecture/deployment-verifier-current-status.md), [검증](../10-operations/deployment-verifier-current-status-validation.md)

## 1. 문제·dependency와 범위

#163은 issuance의 수학적 무결성만 검증한다. `PinnedRootVerifier`, `ApprovalIntegrityReceipt`, application DB의 ACTIVE enum 또는 caller의 expected revision은 independently provisioned/current root라는 증거가 아니다. source/schema에는 root-status journal, admission writer, 독립 high-water mark, trusted pin loader가 없다. existing Rights guard는 이 authority를 제공하지 않는다.

| 후보 | source/authority dependency | 선택 |
|---|---|---|
| A installation/provisioning persistence | 등록의 provenance, trusted pin loading과 status currentness 필요 | 후속 |
| B verifier lifecycle persistence | rotation/revocation admission·head freshness·crash 경계 필요 | 이 Contract 다음 구현 unit |
| C journal/claim persistence 전체 | B + installation/Custodian/target principal/binding/history/seal-first 필요 | 더 큰 후속, 이번 PR 제외 |
| D B의 최소 선행 Contract | ADR-076 root 그대로 admission/currentness·journal persistence 경계를 정의 가능 | 선택 |

이 ADR은 B의 직접 선행 계약 하나다. normal cross-signature의 admission, compromised key의 외부 재지정, current head의 authoritative reader, journal/pin mismatch의 crash 처리 없이 먼저 DB status Writer를 만들면 공급한 metadata를 권한으로 오인할 수 있다. 안전한 결정을 문서로 완결하되 새로운 security-critical admission/store를 unmerged Contract와 같은 PR에 활성화하지 않는다. 사용자에게 다음 작업 허가를 다시 묻지 않고 이 계약의 검증·commit·normal push·Draft PR까지 진행한다. 실 구현은 이 Decision 검증/채택 뒤 별도 Foundation PR이다. 새로운 actor/root/permission/Recovery authority를 정의하지 않는다.

## 2. 대안·선택·trust custody

application DB current enum/업로드한 public key를 anchor로 삼는 모델은 기각한다. signed snapshot 단독도 signature가 과거 상태를 현재로 만들지 못하므로 기각한다. 선택은 ADR-076의 **독립 deployment journal + separately provisioned pin + ceremony serialization**이다. DB cache는 감사/조회용 projection만 가능하며 journal unavailable/mismatch 때 fallback으로 사용하지 않는다. storage technology/OS key store를 지금 선택하지 않는다.

하나의 external designation이 관리하는 deployment journal의 immutable random `journal_id`와 pin의 journal/designation/deployment scope는 trusted initialization에서 독립 확인한다. journal을 request/startup/빈 DB에서 자동 생성하거나 caller UUID로 교체하지 않는다. imported DB/new installation을 새로운 history 없는 genesis로 간주하지 않는다. journal/private store의 전체 clone/rollback과 privileged/root compromise는 ADR-076의 out-of-bound 한계를 그대로 가진다.

Admission은 기존 external designation이 명시한 human/위임 initializer의 ceremony 검증 책임이다. root/custodian/OS admin/CLI 실행자는 그 사실만으로 writer가 아니다. 외부 record/proof는 실제 독립 대조를 완료한 trusted implementation이 private witness로 증명해야 하며 public dataclass/reference/digest만으로 VERIFIED를 만들지 않는다. 실제 사람 지정/서명/키/credential 발급은 이번 작업에서 수행하지 않는다.

## 3. Currentness port 계약

후속 internal port는 다음 책임을 갖는다(현재 production/Python Protocol 구현 아님).

- `ProvisionedVerifierReader`: 독립 deployment trust store의 journal ID/designation/provenance, key ID/raw PUBLIC verifier/fingerprint, monotonic trust revision과 last admission digest를 load. request/approval/application DB에서 자동 pin하지 않는다.
- `DeploymentJournalReader`: ceremony lease 안에서 authoritative durable HEAD와 complete root lifecycle projection/history를 fresh read. journal identity, hash lineage, expected installed admission과 root eligibility를 검증한다. local cached snapshot의 timestamp/서명만으로 currentness를 승인하지 않는다.
- `VerifierLifecycleAdmissionPort`: external designation verification과 normal cross-signature 또는 independent compromise redesignation proof를 재검증하고, expected journal head/revision을 conditional CAS로 전진. caller DB Session을 commit()/rollback()하거나 숨은 retry하지 않는다.
- `CurrentVerifierRevalidationPort`: reader-issued private provenance 및 lease/transaction/observed head를 terminal action 직전에 재검증. public `CurrentRootStatus` 값 자체를 authorization capability로 반환하지 않는다. lease 종료·revision 변경·reader unavailable·test-only provider는 deny다.

caller는 current status witness를 acquisition/issuance receipt로 바꿔치기할 수 없다. terminal bootstrap은 root status뿐 아니라 approval/assignment currentness, installation/Custodian fresh possession, target principal/fresh WebAuthn, Workspace owner/history·seal-first를 별도로 요구한다. 이 Contract만으로 first binding/Grant/OUTPUT_READ를 허용하지 않는다.

## 4. Lifecycle facts·state와 strict signed record

logical facts는 immutable root key/public fingerprint/designation/provenance, append-only admission/status events, stable journal guard, nullable current-issuance-key projection, monotonic journal revision/head digest와 trust revision이다. key ID/fingerprint를 다른 key에 재사용하거나 terminal key를 다시 ACTIVE로 만들지 않는다. zero는 미초기화 상태의 counter일 뿐 ACTIVE authority가 아니며 admitted genesis에서 revision/trust revision 1로 시작한다.

key states는 `ACTIVE_ISSUANCE`, `RETIRED`, `REVOKED`, `COMPROMISED`다. ACTIVE → RETIRED/REVOKED/COMPROMISED만 허용하고 나머지는 terminal이다. 과거 terminal key의 compromise 발견은 기존 terminal status를 다시 쓰지 않고 independently verified external designation record에 연결한 immutable audit-taint fact로 추가한다. 이 기록도 동일 serialized journal admission의 일부여야 하며 old key 서명만으로 추가하지 않는다. RETIRED public key는 역사적 수학 검증에만 남으며 새 bootstrap eligibility를 주지 않는다. 정상 rotation에서도 old-key pending issuance/claims를 자동 carry-forward하지 않고 deny한다. 이는 V1 availability를 줄이는 보수적 선택이며 old-key 자동 재활성화가 아니다. 새 approval은 새 admitted key로 새 immutable issuance가 필요하다. revocation/compromise는 old-key의 모든 unconsumed approvals/claims를 논리적으로 차단하며 성공한 binding/seal을 reset하지 않는다.

root-status event payload는 fixed `schema=dohamusic/deployment-root-status-event/v1`, `algorithm=Ed25519`, `journal_id`, `event_id`, `revision`, `previous_event_digest`, `previous_trust_revision`, `trust_revision`, `designation_id`, `deployment_owner_ref`, `event_kind`, `old_key_id`, `old_key_fingerprint`, `new_key_id`, `new_key_fingerprint`, `designation_record_digest`, `occurred_at`, `affected_scope_manifest_digest`, `admission_mode`로 정의한다. kind는 `GENESIS`, `NORMAL_ROTATION`, `REVOKE`, `EXTERNAL_REDESIGNATION`; mode는 `EXTERNAL_DESIGNATION` 또는 `CROSS_SIGNED_DESIGNATION`이며 허용 조합은 다음 절에 한정한다. GENESIS의 old-key fields만 null, REVOKE의 new-key fields만 null; 그 외 nullable/wildcard/unknown fields는 deny. genesis previous digest는 independently admitted empty genesis sentinel(null)이고 이후는 exact 이전 durable event digest다. `previous_trust_revision`은 현재 durable trust revision과 같고 새 `trust_revision`은 정확히 +1이다(genesis 0→1). 어느 counter든 safe integer 상한에 도달하면 reset/overflow 없이 deny한다.

envelope는 `payload`와 key-ID 정렬된 `signatures` list만 가진다. signature item은 `signer_key_id`/`signature` 두 fields, signer ID 중복 불가, 실제 signature는 64-byte unpadded canonical base64url이다. NORMAL_ROTATION은 old/new ID의 정확히 두 서명, GENESIS/EXTERNAL_REDESIGNATION은 new ID의 한 서명, REVOKE는 old ID의 한 서명만 허용한다. 서명 대상은 ASCII `DohaMusicDeploymentRootStatusEventV1` + NUL + JCS(payload); event digest는 JCS(envelope)의 SHA-256이다. payload fingerprint는 pin/외부 designation과 별도 public bytes의 SHA-256으로 대조하고 artifact가 제공한 key로 self-enroll하지 않는다. affected scope manifest는 별도 immutable canonical public manifest의 digest와 exact authoritative scope set 대조를 요구하며 scope 누락을 caller list로 허용하지 않는다. bootstrap claim/seal event wire는 이번 root-status schema에 임의 추가하지 않는다.

UUID/ref/sha256/revision/time/base64url 기본 형식과 strict UTF-8·duplicate/nonfinite·unknown key 거부는 ADR-077 관례를 따르되 **ADR-077 approval schema/domain/코드/receipt는 변경하지 않는다**. root-status schema에는 signed approval의 24시간 issuance TTL을 복사하지 않는다. event 시각은 감사 정보이지 freshness proof가 아니며 future occurred_at/관측 clock high-water 후퇴·시각 신뢰 불명은 deny한다. signed chain/high-water mark/lease 없이 최신 timestamp를 선택하는 것은 금지다. event envelope 최대 16 KiB·JSON 최대 nesting depth 4·signatures 최대 2, scope manifest 최대 1 MiB/4096 entries를 V1 구현 상한으로 선택한다. 이는 측정 성능값이 아니라 bounded parsing/lock fan-out의 보수적 availability 제한이고 초과 시 분할 승인으로 우회하지 않는다. manifest entry는 exact installation_id/workspace_id/existing_owner_id UUID tuple만, lexical tuple 정렬·중복 없음·trusted authoritative scope membership과 exact equality를 요구한다. 후속 구현에서 UTF-8 bytes/depth/count 경계를 검증한다.

## 5. Admission과 rotation/revocation

GENESIS/EXTERNAL_DESIGNATION: external designation·human 수락·journal lineage·새 public fingerprint를 independent ceremony에서 대조한 witness + 새 root의 event signature를 요구한다. 최초 genesis는 기존 bootstrap/binding lineage가 없다는 독립 evidence 없이는 허용하지 않는다. application DB가 비었다는 사실은 충분하지 않다.

NORMAL_ROTATION/CROSS_SIGNED_DESIGNATION: old key가 fresh ACTIVE이고 expected journal head/trust revision이 일치해야 한다. external designation update digest/새 fingerprint independent 대조에 더해 **동일 event payload의 old/new Ed25519 교차서명**을 모두 요구한다. new key signature 단독·old signature 단독·새 key upload·old designation 재사용은 deny. admitted event 한 개에서 old RETIRED + new ACTIVE + trust revision 증가 + affected old-key unconsumed eligibility 차단을 함께 확정한다. 정상 rotation은 Recovery/owner 변경이나 successful seal 해제가 아니다.

REVOKE/EXTERNAL_DESIGNATION: 아직 active인 root의 유효 서명과 fresh external designation witness로 issuance를 중단할 수 있다. successor가 없으므로 current key projection은 null이며 bootstrap deny다. 이미 compromised key의 서명만으로 상태를 신뢰하거나 successor를 만들 수 없다.

EXTERNAL_REDESIGNATION/EXTERNAL_DESIGNATION: compromised/lost/unknown old authority 대신 **기존 ADR-076 외부 governance의 재지정·독립 새 fingerprint 확인**과 새 key 서명으로 admission한다. old-key cross-signature는 대체 proof가 아니다. old-key fields는 fresh journal의 current 또는 current가 null일 때 last-admitted key와 일치해야 하고 다른 historical key를 current predecessor로 가장하지 않는다. 아직 ACTIVE인 predecessor는 COMPROMISED로 끝내고 이미 terminal이면 status는 보존하되 immutable taint fact를 연결한다. taint 대상 historical keys와 근거는 event의 designation_record_digest가 bind하는 독립 검증된 external record에서 읽어 journal transaction에 함께 append한다. 미소비 approvals/claims는 deny하고 immutable 과거 facts는 보존한다. 실제 외부 ceremony가 없으면 unavailable이지 Fake로 시뮬레이션해 운영 통과시키지 않는다. journal lineage/head를 증명하지 못하는 restore는 새 event/genesis로 우회하지 않고 별도 Recovery Decision 전 차단한다.

## 6. Serialization·CAS·crash와 persistence boundary

전역 순서는 ADR-076 그대로 sorted affected deployment ceremony mutexes → application DB bootstrap/binding guards → external journal CAS다. root-status 변경은 authoritative scope manifest의 모든 affected scopes를 확보하고 신규 scope enrollment도 같은 serialization에 참여해야 한다. 서로 다른 lock order/process-memory-only mutex/SELECT FOR UPDATE reader-only proof는 금지한다. status reader는 lock/lease 유지 중 fresh HEAD를 읽고 action 전 다시 검증한다.

journal은 stable guard의 actual conditional UPDATE(expected ID/revision/head digest/trust revision), unique event ID·revision·key identity, immutable ledger+projection+invalidation cutoff를 **하나의 durable journal transaction**으로 append한다. competing same-head writers의 winner는 1, stale caller는 전체 attempt를 abandon한다. REPLACE/DELETE·head/epoch reset·mutable event·terminal reactivation 금지다. existing Rights guard/integrity 패턴은 구현 참고일 뿐 같은 guard/table authority를 재사용하지 않는다.

external journal commit 후 separately provisioned pin store에 exact admitted public key/trust revision/event digest를 설치한다. journal/pin 간 distributed atomic commit을 가정하지 않는다. 어느 단계에서 crash/응답 유실/mismatch가 생겨도 두 store의 exact admitted head 연결을 다시 독립 확인하기 전 bootstrap deny다. 이미 durable revocation/rotation을 DB rollback으로 되돌리지 않는다. 확인 작업은 **이미 승인된 동일 admission event의 public projection installation**만 가능하며 새 authority/event 발급·old-key reactivation·binding 생성·seal 해제는 아니다. 새 designation 또는 unknown lineage 문제는 별도 external admission/Recovery Gate다.

application DB의 claims/current cache가 rollback돼도 current journal의 key eligibility/invalidation cutoff와 fresh proof가 deny해야 한다. pending invalidation을 비동기 DB row 갱신만으로 강제하지 않는다. Repository는 caller-owned Session, flush-only, commit()/rollback()/hidden retry 0; external journal adapter는 별도 journal durable transaction의 책임이므로 DB repository 안에 숨겨 실행하지 않는다. journal durability·OS mutex·pin provisioning 구현을 이번 PR에서 제공하지 않는다.

## 7. Schema·rollout·검증·non-goals

분류: **DEPLOYMENT_VERIFIER_CURRENT_STATUS_CONTRACT_RESOLVED / PERSISTENCE_IMPLEMENTATION_REQUIRED**. journal/pin records는 application DB·backup과 독립 lifecycle 경계다. Alembic `20260918_0037` app tables가 이를 충족한다고 주장하지 않는다. app-side metadata/cache가 실제 필요하면 당시 latest single head에서 additive migration만 허용하고 external store schema는 독립 version/lifecycle Gate를 갖는다. 기존 migrations/ADR-077/Auth/Workspace/Rights source·data 변경 및 authority backfill 0이다. 이 Contract PR은 docs-only다.

다음 coherent 구현 unit은 B의 **journal public lifecycle fact persistence + strict event validation + private admission/currentness port skeleton**이다. 실제 root/private key 생성/provisioning/signing·external governance 수행은 test fixture로 대체할 수 없다. admitted production writer/Runtime를 켜지 않는다는 것과 public fact persistence를 권한으로 쓰지 않는 것을 검증해야 한다. storage technology/OS serialization을 선택·검증하는 별도 implementation PR에서 constraint/REPLACE/CAS concurrency, normal two-signature/mismatch, compromised signer deny, stale replay/rollback/uncertain commit·pin mismatch, missing/old journal/clone/restore, safe errors·Fake fallback 0을 실행한다. 설계상의 winner=1을 실행 증거로 표시하지 않는다.

Trade-off는 bootstrap availability/운영 비용을 포기하고 history/currentness를 보존하는 것이다. 현재 단점은 journal/pin/admission adapter가 아직 없어 운영이 unavailable라는 점이다. installation/Custodian/claim/principal-owner binding/WebAuthn/Recovery/Transfer/Evidence/Writer/Production Adapter/API/Frontend/Worker는 별도 후속이며 원래 Workspace.owner_id·Approval/Consent·Grant·OUTPUT_READ를 변경하지 않는다. fresh status witness 하나로 이 chain을 생략할 수 없다. 새 Contract Draft PR 생성에서 종료하고 Ready/merge하지 않는다. hardware anti-rollback/multi-root topology/다른 crypto trust semantics가 필요하면 새 Decision으로 재검토한다.
