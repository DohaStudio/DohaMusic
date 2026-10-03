# Authentic IBLA Source Verifier / First-Registration Capability 구현 검증

> 문서 상태: [완료 — local Foundation Gate 검증 / 검토·병합 상태는 PR #200 참조]
> 작성일·최종 수정일: 2026-10-03
> 관련 계약: [ADR-110](../11-decisions/ADR-110-ibla-authentic-source-first-registration-contract.md)
> 기준 develop: e3488cc6efa7e286f2c8504867a02663237ba111
> 최초 제출: 작업 브랜치 → develop Draft PR. 후속 최종 감사·Ready·guarded squash merge 상태는 [PR #200](https://github.com/DohaStudio/DohaMusic/pull/200)을 따른다. auto-merge·branch 삭제 없음.

## 구현 경계와 최초 신뢰

Source Verifier와 First-Registration Capability는 IMPLEMENTED FOUNDATION이다. 이는 PRE prerequisite이며 registered receipt, Initial Authorization, GENESIS 또는 운영 readiness가 아니다. production port는 UnavailableIblaSourceVerifier로 고정되어 항상 IBLA_UNAVAILABLE이며 env/request/app DB가 provider를 선택하거나 fixture로 fallback할 수 없다. 새로운 Architecture Decision, app migration/schema, L/H schema, HTTP endpoint, Frontend 또는 registration/IA/journal writer를 추가하지 않았다. Phase 9는 0/18, 0%다.

private reviewed composition만 원래 accepted designation/initializer action의 독립 retained expectations·public pins·위임·complete inventory와 mapping/native custody를 고정한다. _CommissionedSource는 이 offline boundary의 comparison 입력이며 constructor 자체가 human acceptance나 provisioning을 증명하지 않는다. 실제 운영 initializer/source factory는 없다. tests의 disposable trusted setup은 원본 action/pins/policies를 reader open 이전에 고정하며 운영 source로 자동 선택되지 않는다. Software가 사람의 실제 수락이나 전세계 absence를 암호학으로 증명한다는 주장은 하지 않는다.

source 발견 당시의 키/SID/ACL/native identity를 pin으로 채택하지 않는다. 같은 signature/digest/public L/H DTO만으로 성공하지 않는다. independently retained accepted A/C action을 exact 비교하고 protected original designation/ceremony bytes, root/initializer/proof pins 및 original retained mapping을 직접 held read한 뒤 full L/current H와 fresh possession을 확인한다. C의 원래 human/action bytes는 C 자체의 digest와 구분한다. 외부 accepted designation/provisioning/custody/backup·restore 분리의 실제 운영 확인은 수행하지 않았다.

## 코드와 재사용 inventory

| 신규 코드 | 책임 | 재사용한 mechanics / 승격하지 않은 authority |
|---|---|---|
| backend/bootstrap_authority/ibla/source_codec.py | ADR-110 exact A/C/I field/schema/domain·bounded strict parser·JCS/Ed25519·validity·original bytes | lifecycle_verifier._read/digest, approval_verifier canonical timestamp/signature profile, 기존 UUID/digest/ref/counter validators. policy-purpose receipt 재사용 없음 |
| backend/bootstrap_authority/ibla/source_native.py | IBLA fixed roles/protected root·leaf·held identity와 original-thread Global domain mutex | _CustodyDesignationRecordFiles, _WindowsExistingJournal transport, _SecurityDescriptors, _KernelMutexes 및 reservations. 기존 Workspace lease나 journal factory를 IBLA authority로 쓰지 않음 |
| backend/bootstrap_authority/ibla/source_reader.py | independently retained original/action/pin/mapping/custody correlation, query-only existing L/H full passes | LedgerRepository/CheckpointRepository의 전체 history/schema/projection/current confirmed validation. writer를 호출하지 않음 |
| backend/bootstrap_authority/ibla/source_verifier.py | provider nonce·fresh proof·8 predicates·opaque registries·bounded lifetime·mint/handoff once | 기존 opaque identity/owner/cleanup discipline을 IBLA purpose에 한정. 외부 DTO/boolean/serializer로 mint하지 않음 |

고정 source roles는 ibla-commissioning-anchor-v1.json, ibla-initializer-confirmation-v1.json, ibla-designation-original-v1.txt, ibla-ceremony-original-v1.txt, ibla-commissioning-mapping-v1.json이다. L/H technical basenames는 ibla-ledger-v1.sqlite3 / ibla-checkpoint-v1.sqlite3이며 READ ONLY + OPEN_EXISTING이다. mapping payload/anchor_digest canonical shape는 ADR-110 그대로다. 새 authority field나 persistence schema를 추가하지 않는다. Native policy는 root/leaf volume·128-bit ID, owner/approved SIDs/protected exact DACL에 결박한다. L/H는 서로 다른 file/root/non-nested boundaries를 확인한다. Original text roles는 write/delete sharing을 허용하지 않으며 DB held path mechanics는 기존 ADR-106처럼 SQLite write sharing과 no-delete sharing을 유지한다. mode=ro도 WAL sidecar를 만들 수 있으므로 original held DB handle에서 bounded SQLite header/rollback-journal format을 확인한 뒤에만 SQLite를 연다. WAL/unknown profile의 failure에서도 auxiliary file mutation 0을 검증했다.

_correlate는 하나의 exact original bundle을 검증하는 책임으로 유지했다. 비교 대상은 A/C/I/retained mapping/native custody이며 private partial 결과를 외부로 반환하지 않는다. 짧은 read pass와 capability lifecycle은 별도 모듈로 분리했다.

## Eligibility / absence / PRE와 POST

| Canonical predicate | 내부 검증 근거 |
|---|---|
| authentic_origin | held accepted originals, independently retained root/initializer pins/delegation/action, exact signed A/C 및 fresh installation proof |
| exact_commissioned_domain | original accepted action·whole I/scopes·independent retained mapping·native policies·actual L/H Binding exact equality |
| complete_supported_coverage | A-bound whole inventory와 full L 1..N/H control history; alias/import/external relevant facts를 validation 후 deny |
| current_confirmed | live H CONFIRMED/pending null, exact L head 및 held source/lease/connection owners |
| no_prior_registration | independent complete I/original history와 full supported L에 prior evidence 없음; N=1 exact A-evidence COMMISSION |
| no_prior_initial_authorization_or_genesis | same bounded authoritative coverage에서 prior IA/GENESIS evidence 없음 |
| no_block_or_terminal | known prior/terminal external facts와 verified L HISTORY_BLOCK/RETIRE는 conflict; unknown unsupported facts는 unavailable |
| live_observation | original provider/source registry, process/native thread, lease, proof, physical sources, monotonic deadline/validity/currentness 동시 통과 |

8개는 verifier 내부에서 AND한다. row/file/API absence, new UUID, empty L/H, arbitrary caller eligible=true는 authority input이 아니다. future REGISTRATION_COMMITTED/IA/GENESIS L kind는 지원되지 않으므로 fail-closed IBLA_UNAVAILABLE이며 no-prior=true로 skip하지 않는다. full reader의 integrity failure와 unknown fact discrimination을 분리하고 happy path에는 추가 history scan을 만들지 않는다. 실제 POST boundary는 future authorized writer의 durable REGISTRATION_COMMITTED이며 이번 코드가 이를 기록하거나 first-registration eligibility로 되돌리지 않는다.

## Lifetime / handoff / mutation

provider registry가 context, verified-source, capability의 별도 object identities를 소유한다. capability는 slots-only·public construction/subclass/copy/deepcopy/pickle 불가이고 repr은 고정 안전 이름이다. fixed consumer는 opaque capability 하나만 받으며 original provider registry/delivery context로 검증한다. source facts/head DTO overload가 없다.

Fresh installation proof의 message/domain/UUID/32-byte CSPRNG nonce는 ADR-110 그대로다. challenge는 original observation에서 한 번 accept하며 signed A/C validity와 nonce 시작 후 최대 monotonic 900초의 교집합에 한정한다. clock rollback, expiry, source/ACL/identity/head change, owner connection closure, lease end, provider close, wrong-thread 사용, transaction 교체/중첩, cleanup uncertainty를 승인하지 않는다. 값 복원으로 invalid observation을 되살리지 않는다. foreign invalid handle/use는 원래 valid foreign owner의 winner를 임의 폐기하지 않는다.

RLock single assignment로 observation별 mint 1회·handoff 1회를 관리한다. 전체 fresh read pass가 끝난 뒤 delivered를 표시하고 fixed consumer를 호출한다. callback exception/response loss는 abandon하며 retry delivery가 없다. callback 도중 release도 반환 전에 held original source와 original connection owners의 생존 검사로 deny한다. domain-wide durable winner를 주장하지 않는다.

Original read connection owners는 mode=ro, query_only=ON, synchronous=EXTRA이다. 매 pass에 실제 BEGIN root transaction을 열고 독립 L/H 전체를 읽으며 정상 종료 후 repository를 폐기한다. owner가 read transaction을 종료하며 신규 repository direct commit()/rollback() 호출 0이다. persistent mutation은 L/H/app DB/production journal/registration/IA/GENESIS 모두 0이다. mint/delivered/abandon은 memory bookkeeping뿐이다. uncertain native cleanup은 retained quarantine와 safe failure이며 provider를 재사용하지 않는다.

## 검증 결과

| Gate | 결과 |
|---|---|
| Focused | 103 tests / 103 passed / failures 0 / errors 0 / skipped 0; 11.004s; process exit 0; JUnit exists/parseable |
| Direct impact | 33개 실제 bootstrap authority import/use 관련 파일. 1,208 tests / 1,208 passed / failures 0 / errors 0 / skipped 0; 76.353s; exit 0; JUnit exists/parseable |
| Full Backend local Gate | 3,002 tests / 2,990 passed / failures 0 / errors 0 / skipped 12; 858.428s; process exit 0; JUnit exists/parseable. 신규 native focused skip 0 |
| Source authority | Python 3.12.5 / Windows / first-party Python 560 files; source manifest SHA-256 ed8c12c35c4ca628cd7d571717f971486e851ec192992f6cc5b89a156004b582 |
| External fixture | CI pinned clean DohaVocal e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed; disposable Fake Runtime/ASGI·FFmpeg만 사용 |
| Static | compileall backend/ai_worker, Ruff check, Ruff format check(560 files), git diff --check PASS |
| Query plan | L/H ordered revision history scan: TEMP B-TREE 없음. operation lookup: 기존 unique index 사용. 새 index/migration 없음 |
| App DB | Alembic 20260918_0037 single head / metadata 67 / migration 0, baseline와 동일 |
| API | Route 114 / APIRoute 110 / OpenAPI Path 89 / Operation 110 / duplicate operation ID 0, baseline와 동일 |

Focused tests는 실제 disposable protected Windows roots/leafs/original handles/SQLite L/H를 사용한다. happy path, native identity 각 role mismatch, wrong independent pins/original/delegation/action/signature/domain, incomplete inventory/unsupported alias/import/external prior IA/GENESIS/registration, corrupt full history/head/hidden suffix, unconfirmed/uncertain H, proof replay, cap copy/serialize/duplicate, original-thread deterministic Barrier 경쟁, source/lease/clock/provider release, ACL drift/restore, read transaction/savepoint change, callback loss/release, held source write/rename/delete/hardlink 방어, cleanup quarantine 및 mutation 0을 확인했다. Linux native tests는 명시 skip하며 기존 ffmpeg-windows의 disposable non-admin fixture 실행 목록에 신규 native test file만 추가했다. required check 완화 없음.

Python 코드 변경으로 중단한 진단 Full Backend 및 WAL guard 보강 전 완료된 구버전 run(2,988 passed/12 skipped, exit 0, 861.99s)은 최종 gate/authority에서 제외했다. 소스 manifest를 고정한 뒤 focused/direct PASS 후 시작한 새 gate의 exit/JUnit만 인정한다. 최종 구현 HEAD dd96f70783d080884ea1208fc6662d06427e6bd9의 별도 Full Backend는 3,002 tests / 2,990 passed / skipped 12 / failures·errors 0, 823.725s, exit 0이며 JUnit이 존재하고 parseable하다. 최종 감사에서 560개 소스 manifest와 pinned fixture의 불변을 재확인했다. 이후 문서 상태 정정만 추가하며 Python/code/tests/schema/workflow 변경은 없다. 새 PR head의 CI·review/race 결과는 PR 기록에서 확인한다. precommit gate의 Git HEAD는 기준 develop이며 실제 신규 Python 소스는 위 manifest로 고정·전후 대조했다. commit 뒤 동일 소스의 exact final HEAD Full Backend/JUnit 및 Draft exact-head CI를 최종 보고에서 별도로 확인한다. 구버전 HEAD의 테스트를 새 구현 검증으로 재사용하지 않는다. JUnit/logs/test DB/source files/cache는 commit하지 않는다.

## 문서 영향 / 안전 / 후속

README/ROADMAP/MASTER_ROADMAP, bootstrap/deployment/current lifecycle/issuance architecture, security, DB responsibility, Phase-09 DoD 및 ADR-110/index를 실제 구현 상태와 미구현 다음 단계로 동기화했다. CHANGELOG Unreleased에 기능 경계와 검증을 기록했다. 과거 ADR/CHANGELOG/validation 당시 사실은 보존하며 새 Decision을 만들지 않는다. 모델 실행/GPU 실험이 없어 실험 보고서는 작성하지 않는다.

실제 user DB/음성/Artifact/production source/credential/private key 접근 0이다. Full Backend의 기존 opt-in/Windows privilege skip 12건과 기존 dependency deprecation warnings 16,845건을 기록하며 관련 없는 dependency 업그레이드를 섞지 않았다. tests는 ephemeral generated signing/proof keys를 memory에만 사용하며 private key material을 source/PR에 보관하지 않는다. real paid/production Provider 호출 0, source/verifier/cap repr/error에서 raw original/path/key/native handle/ACL/PID를 반사하지 않는다. main/develop 직접 변경, 다른 사용자 worktree/6 stash/#171/#130 변경을 하지 않는다.

운영 custody/ceremony/source와 backup·restore separation은 미검증·미실행이다. power-loss/storage-controller durability, hardware anti-rollback/remote consensus는 미검증/미지원이며 H standalone rollback 및 consistent L/H historical rollback limitation을 해결했다고 주장하지 않는다. 실제 Initial Authorization, REGISTRATION_COMMITTED writer, production journal provisioning/GENESIS, Authentication/Activation, Recovery/Transfer는 미구현/unavailable다.

최초 구현 제출은 Draft PR까지였다. 후속 최종 감사는 PR #200의 exact-head 검증·review/race Gate 뒤 Ready·guarded squash merge를 수행한다. develop 병합 검증 뒤에는 Initial Authorization issue/consume/cancel의 authoritative 계약을 먼저 재확인하고, implementation-ready가 아니면 누락된 Decision만 확정한다.
