# Verified Durable Staging Authority

> 문서 상태: [승인: authority 확정, adapter·통합 미구현]
> 최종 수정일: 2026-08-25
> 기준: DohaMusic `develop` `e1b4c0007487436bfef5a4d0d0f5271898d8fa4b`
> 최종 판정: `VERIFIED_DURABLE_STAGING_LOCAL_ADAPTER_SUFFICIENT`
> 관련 결정: [ADR-041](../11-decisions/ADR-041-trusted-payload-locator-authority.md), [ADR-049](../11-decisions/ADR-049-durable-payload-locator-persistence-authority.md), [ADR-051](../11-decisions/ADR-051-verified-durable-staging-authority.md)

## 1. 결론과 범위

`PayloadLocator`를 `verified_staged`로 전이할 수 있는 byte authority는 다음 조건을 모두 만족한 `VerifiedStagedPayload`다.

```text
VerifiedStagedPayload
= DohaMusic-owned storage에 무덮어쓰기 publish된 regular object
+ 실제 bytes에서 검증한 SHA-256·size·media
+ process restart 뒤 config-owned root와 canonical key로 다시 열 수 있음
+ 최신 locator·claim·cancel·rights gate를 통과해 DB에 확정된 handoff
```

기존 `PayloadLocator`의 `staging_backend`, `staging_key`, actual facts, `verified_at`, lifecycle revision으로 이 authority를 표현할 수 있다. 별도 staging metadata table이나 Alembic은 필요하지 않다. 초기 구현은 narrow staging port와 local filesystem adapter로 충분하며 object storage 일반화를 선행 조건으로 두지 않는다.

이번 분석은 authority만 확정한다. adapter, downloader, `GetPayloadContent`, Artifact ingestion, Completion, Worker, schema와 API는 변경하지 않는다.

## 2. 현재 storage inventory

| 기존 구현 | 재사용 판정 | staging 적용 |
|---|---|---|
| `DOHA_ARTIFACT_STAGING_ROOT` | 재사용 | DohaMusic-owned pre-Artifact root; 실제 값은 config만 소유 |
| `ArtifactStorageRoots`와 root overlap 검사 | 재사용 | staging root와 Artifact domain root의 상·하위 중첩 거부 |
| `validate_local_root`, no-follow regular-file open | 재사용 | root·containment·symlink·junction·reparse 방어 |
| `calculate_artifact_integrity` | 재사용 | streaming SHA-256와 byte count |
| `validate_artifact_media` | 부분 재사용 | WAV·FLAC·JSON byte inspection을 payload role에 맞게 좁혀 사용 |
| `LocalArtifactPublisher` | primitive 재사용 | exclusive create, file `fsync`, hard-link publish, identity-safe delete 관례 |
| `ArtifactReconciliationService` | 패턴 재사용 | namespace scan·grace·safe report; staging policy와 scanner는 별도 책임 |
| `InMemoryTrustedPayloadRegistry` | test/dev 호환만 | production restart authority로 사용 금지 |

기존 Artifact publisher는 이미 검증된 staging file을 final Artifact root로 복사하는 계층이다. 새 staging adapter는 Provider byte stream을 durable staging object로 만드는 그 이전 계층이며 Artifact ID·Catalog·Completion을 알지 않는다.

## 3. identity와 root

다음 네 identity를 결합하지 않는다.

```text
PayloadLocator ID       = reconciliation identity
staging storage key     = internal byte object identity
filesystem absolute path = local adapter implementation detail
Artifact ID             = final Workspace output identity
```

초기 backend ID는 `local`이다. root는 기존 `DOHA_ARTIFACT_STAGING_ROOT` 설정이 소유하며 DB·API·로그에 저장하지 않는다. root는 실제 non-link directory여야 하고 Artifact root 및 네 domain root와 겹치면 fail closed한다. 운영자는 개인 음성 payload가 있는 root를 process-private directory로 구성해야 한다.

final key는 content hash, Provider source, 사용자 정보나 원본 파일명을 사용하지 않고 locator UUID에서 결정한다.

```text
payload-staging/v1/<locator-uuid 첫 2 hex>/<locator-uuid>.<wav|flac|json>
```

선택 이유는 다음과 같다.

- 같은 locator replay가 같은 object를 찾고 orphan을 DB row에 역연결할 수 있다.
- content hash naming의 불필요한 dedup·상관관계 노출과 공유 retention을 피한다.
- random final ID처럼 별도 metadata persistence가 필요하지 않다.
- locator는 한 번만 `source_bound → verified_staged`로 전이하므로 revision suffix가 필요 없다.

`staging_key`는 canonical POSIX relative key만 허용한다. `/`, drive, UNC, 역슬래시, 빈·`.`·`..` segment, percent escape, URL·URI, query, control character, Windows reserved segment와 credential-like text를 거부한다. local adapter는 기존 domain-neutral `PayloadLocator` validator보다 더 엄격한 local key 검사를 수행하고 `root + key`의 containment와 모든 component의 link/reparse 여부를 다시 확인한다.

## 4. partial과 published object

partial은 DB authority가 아니고 `staging_key`로 저장하지 않는다.

```text
.partial/v1/<shard>/<locator-uuid>.<random-attempt-uuid>.partial
```

partial과 final은 반드시 같은 configured root/filesystem에 둔다. adapter는 `O_CREAT | O_EXCL`과 가능한 경우 mode `0600`으로 partial을 만들고, 실패·취소·mismatch 때 자신이 만든 동일 identity만 제거한다. downloader가 별도 network temp를 만들면 그 temp는 downloader가 소유한다. adapter 내부 partial은 adapter가 소유한다.

published namespace에는 검증을 통과한 regular file만 들어갈 수 있다. final key는 무덮어쓰기이며 기존 object를 `os.replace()`로 교체하지 않는다.

## 5. staging port와 결과

구현 PR은 downloader나 SQLAlchemy를 모르는 narrow port를 둔다.

```text
VerifiedPayloadStagingPort
  recover_published(locator, expected) -> VerifiedStagedPayload | None
  stage(locator, generic byte chunks, expected) -> VerifiedStagedPayload
  open_verified(key, actual facts) -> context-managed binary stream
  delete_verified(key, actual facts) -> deleted | already_missing
```

standalone `exists()`는 TOCTOU authority가 아니므로 핵심 계약으로 사용하지 않는다. `recover_published`와 `open_verified`는 실제 descriptor를 열어 검증한다. 입력 stream은 sync iterator 또는 `BinaryIO` 같은 generic byte source이며 HTTP response·URL·credential을 알지 않는다. 비동기 downloader는 transaction 밖에서 이 port에 bounded chunks를 전달하는 별도 orchestration 책임이다.

`VerifiedStagedPayload`는 다음 safe fact만 반환한다.

- `staging_backend=local`
- canonical `staging_key`
- `actual_checksum_algorithm=sha256`
- actual lowercase SHA-256
- actual positive size
- actual validated media type
- UTC `verified_at`

absolute path와 file descriptor는 adapter 내부 handle이며 Service DTO, DB와 로그에 포함하지 않는다.

## 6. write·verify·publish 순서

authoritative 순서는 다음과 같다.

```text
DB transaction 없이 partial exclusive open
→ bounded chunks write + byte count
→ flush + file fsync + close
→ no-follow reopen
→ full SHA-256·size 계산
→ WAV/FLAC/UTF-8 JSON 실제-byte media validation
→ 같은 identity·SHA-256·size·media 재확인
→ expected facts와 exact equality 확인
→ same-filesystem exclusive hard-link로 final key publish
→ final descriptor identity·facts 재확인
→ partial unlink
→ 가능한 platform에서 parent directory fsync
→ VerifiedStagedPayload 반환
→ 최신 authority 재검증 뒤 짧은 DB transaction에서 verified_staged CAS
```

checksum, size 또는 media가 다르면 final object를 publish하지 않고 partial을 제거한다. adapter는 locator lifecycle이나 revocation 정책을 소유하지 않는다. Reconciliation 계층은 transient transfer 오류와 확정된 integrity/security violation을 구분하고, 후자만 ADR-049의 `integrity_failure` 또는 `security_incident` revocation으로 기록한다.

local publish primitive는 저장소에서 이미 사용하는 `os.link(partial, final)` 기반 exclusive directory-entry 생성이다. target이 있으면 overwrite하지 않는다. filesystem이 same-volume hard link를 지원하지 않으면 configuration/operation failure로 닫으며 check-then-`os.replace()` fallback은 금지한다.

## 7. DB ordering과 idempotent replay

schema 변경 없이 다음 ordering을 채택한다.

```text
partial write·verify
→ final publish
→ locator/Job/claim/cancel/rights 재검증
→ PayloadLocator verified_staged CAS
```

DB를 먼저 `verified_staged`로 만들면 실제 object가 없는 authority gap이 생긴다. 별도 intent state를 추가하지 않으므로 bytes-first가 유일한 안전한 순서다. publish와 DB CAS 사이 crash는 orphan final object를 만들 수 있지만 잘못된 `verified_staged` row를 만들지 않는다.

final key는 deterministic하다. restart 또는 같은 locator replay는 acquisition 전에 `recover_published`를 호출한다. 기존 final이 expected SHA-256·size·media와 모두 같으면 새 download 없이 같은 result를 반환하고 최신 gate 뒤 DB transition을 재시도한다. 다르면 overwrite·adopt하지 않고 fail closed한다.

동시 같은-locator publish에서 한 attempt만 final entry를 만든다. loser는 기존 final을 full verify한다. DB CAS loser는 locator를 다시 읽어 같은 backend/key/actual facts의 `verified_staged`면 idempotent success로 해석하고 object를 삭제하지 않는다. DB가 불가하거나 authority를 판단할 수 없으면 final을 보존해 orphan reconciliation에 맡긴다.

## 8. open, missing과 tamper

local filesystem object는 storage 차원에서 immutable version을 제공하지 않는다. 따라서 `verified_staged` resolve마다 다음을 전부 수행한다.

- key validation, root containment와 link/reparse 검사
- no-follow regular descriptor open과 path/descriptor identity 비교
- full streaming SHA-256와 size 재계산
- actual media 재검증
- DB의 actual facts와 exact equality

mtime, extension, Content-Type, 기존 file identity cache만으로 full verification을 생략하지 않는다. future object storage에서 immutable object version과 checksum authority가 승인되기 전까지 이 비용을 최적화하지 않는다.

DB는 `verified_staged`인데 object가 없거나 바뀌었으면 backward transition이나 같은 locator reacquisition을 허용하지 않는다. `integrity_failure`로 fail closed하고, object가 남아 있으면 cleanup 대상으로 보낸다. 새 execution이 필요하면 명시적 RetryJob/new binding이 새 locator authority를 만들어야 한다. `cleaned → verified_staged` resurrection은 없다.

audio는 확장자나 HTTP Content-Type이 아니라 실제 WAV parser·FLAC STREAMINFO와 frame 존재를 확인한다. analysis는 제한된 크기의 strict UTF-8 JSON parse를 요구한다. 현재 payload allowlist는 `audio/wav`, `audio/flac`, `application/json`이며 MP3와 임의 binary는 허용하지 않는다.

## 9. claim·rights·cancel race와 transaction

byte stream/file I/O 동안 DB transaction은 0개다. publish 뒤 DB transition 직전에 application reconciliation owner가 다음 최신 authority를 다시 확인한다.

- 현재 Workspace Job claim token과 owner
- Job nonterminal·non-cancelled 상태
- 최신 owner·Consent/access/rights
- locator Workspace scope, lifecycle, revocation, policy expiry와 expected revision

cancellation과 revocation이 acquisition보다 우선한다. gate 실패 시 `verified_staged` 전이를 금지한다. 다만 동시 worker가 같은 object를 이미 정상 확정했는지 먼저 재조회하고, 그렇지 않을 때만 identity/facts가 일치하는 이번 orphan의 physical cleanup을 요청한다. Repository는 filesystem, `commit()`과 `rollback()`을 수행하지 않는다.

## 10. crash matrix

| # | crash point | object / DB authority | restart action | cleanup owner | same locator reacquire |
|---:|---|---|---|---|---:|
| 1 | stage 전 | object 없음 / `source_bound` | expiry·rights 후 acquire | 없음 | 예 |
| 2 | partial 생성 후 | partial / `source_bound` | active attempt 아님을 확인하고 grace 뒤 제거 | adapter 또는 janitor | 예 |
| 3 | partial write 중 | incomplete partial / `source_bound` | partial 제거 후 재시도 | adapter 또는 janitor | 예 |
| 4 | full write 후 | unverified partial / `source_bound` | 재검증하거나 stale partial 제거 | janitor | 예 |
| 5 | checksum·size·media mismatch | partial / `source_bound` | partial 제거, final publish 금지 | adapter | 정책상 예 |
| 6 | verify PASS 후 publish 전 | verified partial / `source_bound` | partial은 authority 아님; 제거 또는 새 attempt | janitor | 예 |
| 7 | publish 후 DB 전 | orphan final / `source_bound` | deterministic key full verify 후 adopt·CAS | Reconciliation + adapter | download 불필요 |
| 8 | DB transition 후 | final / `verified_staged` | full open verification 뒤 reuse | 없음 | 금지 |
| 9 | restart open | final / `verified_staged` | containment·hash·size·media 재검증 | 없음 | 금지 |
| 10 | DB verified, object missing | 없음 / `verified_staged` | integrity failure·fail closed | Reconciliation | 금지 |
| 11 | object tampered | unsafe object / `verified_staged` | open/reuse/ingestion 금지, revoke·cleanup | Reconciliation + adapter | 금지 |
| 12 | Artifact ingestion 전 | final / `verified_staged` | verified open 뒤 ingestion 재시도 | 없음 | 금지 |
| 13 | ingestion 후 cleanup 전 | final / `ingested` 또는 `cleanup_pending` | cleanup lifecycle 재개 | Reconciliation/janitor | 금지 |
| 14 | cleanup 중 crash | object 있거나 없음 / `cleanup_pending` | idempotent delete 재실행 후 CAS | janitor + adapter | 금지 |
| 15 | cleanup 완료 | 없음 / `cleaned` | no-op, audit 유지 | 없음 | 금지 |

partial·orphan grace는 active write와 crash residue를 구분하는 운영 안전값이지 healthy verified payload의 business TTL이 아니다. 고정 production TTL을 이번 authority에서 만들지 않는다.

## 11. cleanup과 retention

책임은 하나씩만 둔다.

| 책임 | owner |
|---|---|
| adapter 내부 partial 실패 정리 | staging adapter |
| downloader가 별도로 만든 network temp | downloader |
| locator cleanup 정책·revocation 판단 | Payload reconciliation Service |
| exact key의 physical open/delete | staging adapter |
| stale partial·orphan scan과 승인된 cleanup 실행 | staging janitor |

정상 cleanup ordering은 `cleanup_pending → physical delete → cleaned`다. delete 시 object가 이미 없으면 idempotent success지만 unsafe key, identity/facts mismatch와 권한 오류는 success로 바꾸지 않는다. delete와 `cleaned` CAS 사이 crash는 `cleanup_pending`에서 반복한다.

healthy verified staging은 임의 TTL이 아니라 lifecycle로 유지한다. Artifact ingestion 뒤 cleanup policy가 `cleanup_pending`을 만들 때까지 보존한다. source `available_until` 만료는 이미 검증된 staging을 자동 무효화하지 않으며 locator policy와 최신 rights가 사용 가능성을 결정한다. rights revocation 뒤에는 open·reuse·ingestion·reacquire를 금지하고 cleanup만 허용한다.

## 12. local durability와 보안 한계

초기 구현은 process crash/restart와 정상 OS filesystem semantics에서 restart-safe하다. file `fsync`는 publish 전 필수이고 POSIX directory `fsync`는 시도한다. Windows에서 directory `fsync`와 갑작스러운 전원 손실 전체에 대한 완전한 durability는 보장하지 않는다. 문서와 운영 preflight에서 이 한계를 유지하며 확인하지 않은 guarantee를 선언하지 않는다.

partial과 final file은 POSIX에서 `0600`, 생성 directory는 가능한 경우 `0700`을 사용한다. Windows는 process-private root에 설정된 ACL 상속을 운영 전제조건으로 둔다. root를 정적 제공하거나 공개 API로 노출하지 않고 filename에 user ID, Job title, 원본 filename, Provider source, model·voice identity를 넣지 않는다. 오류와 로그에는 locator ID 또는 canonical safe key와 reason code만 허용하고 absolute path, URL, credential, raw response와 bytes를 넣지 않는다.

root에 대한 비협조적 외부 writer까지 application code만으로 완전히 방어할 수 없다. 운영 권한은 staging owner process로 제한해야 하며 link/reparse·identity·full integrity 검사는 그 전제 위의 fail-closed 방어다.

## 13. schema와 future backend 판정

최종 schema 판정은 다음과 같다.

```text
NO_NEW_SCHEMA_REQUIRED
NO_NEW_ALEMBIC_REQUIRED
```

partial은 execution residue이고 orphan final은 deterministic locator key와 existing DB row로 복구하므로 별도 manifest/table이 business authority를 중복한다. current local adapter는 immutable object version을 DB에 저장할 필요가 없고 매 open actual facts를 재검증한다.

port는 backend-neutral DTO와 operation 의미만 유지하되 첫 adapter는 local filesystem이다. future object storage는 conditional create, immutable object version, provider checksum 의미, consistency, retention lock과 credential boundary를 별도 ADR에서 검증한다. 그때 object version identity가 필요하면 schema 변경을 다시 판단하며 현재 local 구현을 미리 일반화하지 않는다.

## 14. 다음 implementation PR 최대 범위

허용 범위는 다음뿐이다.

```text
VerifiedPayloadStagingPort
→ LocalFilesystemStagingAdapter
→ deterministic final / random partial naming
→ streaming hash·size와 WAV/FLAC/JSON 검증
→ file fsync + exclusive atomic publish
→ recover/open/delete
→ restart·orphan·race·security tests
→ PayloadLocator verified_staged integration
```

필수 검증은 same-locator replay, collision, partial cleanup, crash-after-publish adoption, missing/tampered object, Windows drive·UNC·reserved name, traversal·URL·credential, symlink/junction/reparse, rights/cancel/revocation race, cleanup idempotency와 DB transaction 0 during I/O다.

downloader orchestration, `GetPayloadContent` Worker 연결, Artifact ingestion/Completion, reclaim, dispatcher, daemon, production authentication, DohaVocal Runtime과 model/GPU는 그 다음 작업이다.
