# ADR-109: IBLA Ledger / Independent Checkpoint Persistence Foundation

> 상태: [Foundation implemented — Draft 검토 대상, 운영 비활성]
> 작성일·최종 수정일: 2026-10-01
> 기준 develop: 34c57b8ce52e623d6da85163e34d13104207b485 (#197 merged)
> 관련 결정: [ADR-108](ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md), [ADR-107](ADR-107-independent-bootstrap-lineage-authority.md), [ADR-079](ADR-079-independent-lifecycle-journal-persistence-foundation.md)
> 검증: [실행 검증 보고서](../10-operations/ibla-persistence-foundation-validation.md)
> 관련 PR: [#198](https://github.com/DohaStudio/DohaMusic/pull/198) (develop 대상 Draft)

## 배경·문제·결정

ADR-108의 A/L/H 계약 뒤 public fact persistence를 독립 구현한다. Source Verifier, 최초 등록 권한, Initial Authorization·소비 또는 target journal 생성은 구현하지 않는다. L/H 저장 성공은 외부 commissioning, source authenticity, human/위임 또는 production authentication 성공이 아니다. ADR-108을 대체하지 않는다.

선택은 **서로 다른 SQLite 파일의 L event store와 H control store**, caller-owned 실제 transaction, 전체 local history 재검증이다. app ORM metadata/Alembic 및 ADR-106 production journal을 재사용하지 않는다. 두 schema는 같은 구조의 불변성/CAS 생성기를 공유하지만 각 DB의 immutable role, version, A/L/H binding과 허용 event kinds가 달라 상호 대체할 수 없다. L/H를 같은 DB에 설치하거나 같은 file identity·같은 root·nested roots로 읽는 H correlation은 거부한다.

## 지원하는 최소 v1

하나의 commissioned domain에서 고정 A·installation/proof·deployment·lineage·L/H·designation digest·authority epoch를 public 조건으로 bind한다. 이번 subset은 L의 COMMISSION(revision 1), HISTORY_BLOCK, RETIRE만 지원한다. RETIRE 이후 새 append는 거부하며 기존 exact operation의 결과 조회만 허용한다. 다른 A/lineage/epoch·alias transitions, registration authorization, INITIAL_AUTHORIZATION_ISSUED/CONSUMED, GENESIS_OUTCOME 등 future writer는 미지원/deny다. domain의 일부 lineage만 선택해 읽는 API는 없다. 해당 subset 밖의 유효 이력도 건너뛰지 않고 unavailable로 취급한다.

A 자체의 서명/validity/외부 ceremony reader는 없다. binding의 anchor digest는 public immutable reference이며 A의 authenticity를 검증했다는 receipt가 아니다. 표준 shared require_uuid/require_digest/require_revision, lifecycle_verifier의 strict bounded JSON parser·SHA-256과 rfc8785 JCS를 재사용한다. 기존 approval/policy/journal purpose의 codec나 receipt를 다른 권한으로 승격하지 않는다.

## Wire와 물리 schema

- Ledger schema: dohamusic/ibla-ledger-event/v1. domain-separated digest는 ASCII DohaMusicIblaLedgerEventV1 + NUL + canonical envelope bytes의 SHA-256이다.
- H schema: dohamusic/ibla-checkpoint-control/v1. digest domain은 DohaMusicIblaCheckpointControlV1 + NUL이다.
- operation fingerprint: DohaMusicIblaOperationV1 + NUL + exact canonical L envelope. kind·scope·epoch·predecessor·payload·event/operation ID를 모두 포함한다.
- 16 KiB strict UTF-8 canonical envelope, 고정 fields, duplicate/unknown key·float/bool counter·nonfinite·unsupported schema/kind·safe-integer overflow를 거부한다. record digest 자체는 hash 입력에 포함하지 않는다. 서명을 만들거나 검증하는 신규 protocol은 아니다.
- L/H 각각의 recorded_at은 caller가 명시한 canonical UTC-second 감사 시각이며 기존 lifecycle의 YYYY-MM-DDTHH:MM:SSZ profile을 따른다. stored envelope/digest에 포함하지만 freshness·clock trust·권한 판단으로 사용하지 않는다. control 순서는 monotonic sequence이며 time ordering으로 history를 대체하지 않는다. clock/validity가 권한을 제공하는 future source/authorization은 미구현이다.
- 각 DB의 ibla_identity는 version=1, role L/H, exact canonical binding을 보존한다. ibla_events는 sequence/revision, record ID, operation ID/fingerprint, predecessor/digest/kind/envelope를 보존한다. ibla_head는 single current projection이다.
- UPDATE/DELETE와 identity/head INSERT/REPLACE를 trigger로 거부한다. event INSERT는 actual expected-head conditional UPDATE를 trigger로 실행하며 event+unique operation index+projection이 한 SQL statement다. REPLACE의 implicit DELETE 우회도 사전 duplicate 검사로 차단한다.
- H의 operation lookup은 (operation_id, revision) index, L은 operation unique index, revision/current head는 INTEGER PRIMARY KEY를 사용한다. complete ordered history는 revision 순서의 의도된 전체 scan이며 temp sort가 필요 없다.

## Transaction·reader·error

Repository는 commit/rollback하지 않고 flush까지만 수행한다. constructor의 exact root SessionTransaction에 수명을 묶고 종료·교체·nested transaction·실패 후 재사용을 거부한다. SQLAlchemy logical autobegin만으로는 부족하며 SQLite DBAPI의 실제 transaction이 열려 있어야 한다. fixture owner는 BEGIN IMMEDIATE로 writer 경쟁을 직렬화한다. lock failure는 blind retry하지 않고 owner가 실패 처리한다.

모든 reader는 exact schema object SQL/version/role/binding, SQLite integrity, 전체 revision continuity·uniqueness·digest·canonical envelope·projection·상태 전이를 검사한다. temp 객체에 의한 table shadowing과 attached DB는 거부하며 SQLite가 자체 생성한 빈 temp catalog만 허용한다. 이는 ADR-106에서 관찰한 SQLite 내부 temp 처리와 일치한다.

H keeper는 **별도 query_only L Session**으로 전체 이력을 직접 읽는다. L writer의 uncommitted Session, public head DTO, arbitrary digest callback을 confirmation 입력으로 받지 않는다. 반환되는 LedgerView/CheckpointView/OperationResult는 공개된 비권한 값이다. future Source Verifier capability 또는 current custody/human/외부 origin proof가 아니다.

IBLA_UNAVAILABLE / IBLA_CONFLICT / IBLA_INCONSISTENT만 repository 경계에 반환한다. SQL/path/native/credential 상세를 오류 메시지에 반사하지 않으며 I/O 오류나 충돌 뒤 repository instance는 폐기한다. 연결/commit/rollback/close와 그 실패의 보고 책임은 caller owner다. cleanup failure를 성공으로 변환하지 않는다.

## H 상태·crash·replay

최초 explicit empty H는 EMPTY이고 current authority가 아니다. exact COMMISSION candidate에 대한 첫 control record는 COMMISSIONING_PENDING이다. 실제 L revision 1이 확인된 뒤에만 CONFIRMED가 된다. 이후 CONFIRMED(n) → PREPARED(n+1) → actual durable L append → independently read CONFIRMED(n+1)을 적용한다. PREPARED와 UNCERTAIN은 이전 confirmed tuple을 유지하며 intended exact operation/envelope를 영구 보존한다.

| 상황 | 결과 |
|---|---|
| PREPARED commit 뒤 L append 전 process exit | pending retained, read_correlated deny, 자동 append/reset 없음 |
| L durable append 뒤 H confirm 전 exit | 새 process가 exact existing L을 읽고 H confirmation만 보완 |
| H confirm 뒤 response loss | same ID/fingerprint의 stable historical result, duplicate append 0 |
| missing/ambiguous L | 성공/미commit으로 추론하지 않음. pending 유지, explicit UNCERTAIN 기록 가능 |
| same operation + 다른 fingerprint | conflict |
| uncertain 뒤 existing exact L 확인 | H confirm만 가능; L을 repair/recreate하지 않음 |
| cleanup/transaction 종료 | instance 재사용 거부, fresh caller transaction 필요 |

Repository는 distributed transaction owner나 retry coordinator가 아니다. 운영에서 모든 관련 writer를 참여시키는 domain lease, H writer와 L writer 권한 분리, fresh held sources/custody, terminal revalidation은 future trusted composition의 필수 Gate다. fixture의 단계별 owner는 테스트용이며 production에 import하지 않는다.

## 독립 custody·Windows·durability 한계

파일 분리와 H의 read-only L connection은 **필요조건만 검증**한다. 동일 machine-wide restore/관리자/무제한 writer가 L/H를 함께 되돌릴 수 있는 환경을 독립 authority라고 승인하지 않는다. 별도 governed root·writer/restore 정책·native identity/exact DACL binding·external designation을 확립하는 운영 adapter는 미구현이며 유일한 production 진입점 UnavailableIblaPersistence는 항상 거부한다. 따라서 이 Foundation에서 운영 H custody를 만들거나 source authenticity를 검증했다는 주장은 없다.

이번 구현은 caller-owned SQLAlchemy connection의 public persistence만 제공하며 Windows native 경로 open/provisioning factory를 추가하지 않는다. ADR-082 serialization, ADR-083/085/086/089 held fact-file·root/leaf identity·owner/protected DACL·no reparse/hardlink·cleanup quarantine, ADR-106 existing database held handles를 감사했다. 이들은 각 purpose/readonly snapshot 또는 기존 journal filename에 묶여 있어 원본 권한·filename을 IBLA로 바꾸지 않았다. 향후 운영 source factory는 해당 mechanics를 재사용·일반화해 junction/symlink/parent/leaf/replacement/rename/delete/containment를 검증해야 하며, 그 전 운영 source는 unavailable다. 기존 Windows 직접 영향 회귀 결과는 별도 보고한다.

H도 SQLite store이므로 temp JSON 작성/atomic file replace를 사용하지 않는다. caller connection은 DELETE journal + synchronous=EXTRA를 요구한다. SQLite의 journal fsync와 commit protocol에 의존하며 OS/VFS/device가 실제 sync를 준수한다는 가정이 있다. process-exit/reopen 테스트는 전원 장애·storage controller의 내구성 실측이나 Windows production custody 증거가 아니다. [SQLite PRAGMA](https://sqlite.org/pragma.html#pragma_synchronous), [SQLite isolation](https://sqlite.org/isolation.html)을 참고한다.

L-only rollback은 current H와 mismatch, H-only confirmed-prefix rollback은 더 앞선 L과 mismatch로 거부한다. 삭제 후 fresh empty L/H는 confirmed correlation이 아니다. H의 마지막 PREPARED만 사라지고 L이 변하지 않거나 L/H 모두 일관된 과거 prefix로 복원되면 탐지가 **NOT GUARANTEED**임을 실행 예제로 보존한다. hardware anti-rollback·remote consensus는 **NOT CLAIMED**다. 무기한 이력·tombstone 보존, 자동 GC 0이며 Recovery/Transfer나 fresh commissioning으로 복구 권한을 만들지 않는다.

## 대안·영향·migration·후속

기존 JournalRepository/schema를 직접 사용하는 대안은 GENESIS/root-status 목적·field가 달라 기각했다. 같은 app DB/같은 SQLite의 두 table 대안은 독립 rollback 경계가 아니므로 기각했다. signed file P만 저장하는 대안도 independent live H가 아니므로 기각했다. 장점은 작고 테스트 가능한 durable CAS/control history다. 비용은 전체 history scan과 별도 custody/operation owner 구현이 남는 점이다.

새 app migration 0, Alembic 20260918_0037 single head 유지. 기존 journal schema/API/Frontend/config/workflow/dependencies 변경 0. 기존 ADR-076~108 의미와 user data/다른 worktree/stash를 보존한다. Phase 9는 운영 보안·Backup/Restore 승인까지 입증하지 않았으므로 0/18 유지한다.

다음은 independently provisioned custody/current source 및 authentic Commissioning Source Verifier/Capability의 별도 검증이다. A origin/complete domain membership, production L/H custody/lease, supported epoch/alias transitions가 충분하지 않으면 unavailable를 유지한다. Initial Authorization/소비 → Provisioning/GENESIS는 그 뒤다. 새로운 backend, multiple A/epoch/alias 지원, wire 확장, 운영 custody, retention 삭제 또는 stronger rollback 요구는 ADR-108 불변식을 재검토한다. 이번 작업은 Draft PR까지이며 Ready/merge하지 않는다.

## 실행 증거

Focused 106 passed, direct-impact 976 passed, source commit 366e4a8024ffff918338a6832b0a6f7d427cb7ba의 Full Backend 2887 passed/12 skipped(2899 tests, failures/errors 0, JUnit 892.455s, process exit 0). compile/Ruff check/format 및 문서 정적 검증 PASS. [상세 검증과 미실행 사유](../10-operations/ibla-persistence-foundation-validation.md)를 따른다.
