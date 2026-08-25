# ADR-050: Verified Durable Staging Authority

> 상태: 승인·구현 대기
> 작성일: 2026-08-25
> 최종 수정일: 2026-08-25
> 관련 기능: PayloadLocator `verified_staged` restart-safe byte authority
> 관련 문서: [Verified Durable Staging Authority](../03-architecture/verified-durable-staging-authority.md), [ADR-049](ADR-049-durable-payload-locator-persistence-authority.md), [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md)

## 배경과 문제

ADR-049와 PR #126은 `PayloadLocator`의 immutable source expectation, mutable actual staging facts와 lifecycle을 DB에 보존한다. 그러나 actual bytes를 durable하게 publish·resolve·delete하는 adapter는 없으므로 DB의 `verified_staged`만으로 restart-safe byte authority가 완성되지 않는다.

Repository에는 config-owned `DOHA_ARTIFACT_STAGING_ROOT`, root overlap·symlink/junction/reparse 방어, no-follow regular-file open, streaming SHA-256, WAV·FLAC·JSON byte validation, file `fsync`, exclusive hard-link publish와 identity-safe cleanup primitive가 이미 있다. 이 기반으로 별도 metadata persistence 없이 crash window를 닫을 수 있는지 결정해야 한다.

## 결정

최종 판정은 다음과 같다.

```text
VERIFIED_DURABLE_STAGING_LOCAL_ADAPTER_SUFFICIENT
```

1. `VerifiedStagedPayload`는 DohaMusic-owned root에 무덮어쓰기 publish되고 actual SHA-256·size·media를 통과해 restart 뒤 canonical key로 full revalidation 가능한 regular object다.
2. `PayloadLocator ID`, staging key, absolute path와 Artifact ID를 분리한다. DB에는 `staging_backend=local`과 safe relative key만 저장한다.
3. 기존 `DOHA_ARTIFACT_STAGING_ROOT`를 재사용하고 Artifact root와 중첩을 금지한다. 새 환경 변수와 운영 절대 경로 persistence를 추가하지 않는다.
4. final key는 locator UUID 기반 `payload-staging/v1/<shard>/<locator>.<validated-extension>`으로 결정한다. content hash dedup, Provider/user identity와 원본 filename은 사용하지 않는다.
5. random attempt partial을 같은 filesystem에 exclusive 생성하고, file `fsync`와 actual-byte 검증 뒤 existing publisher convention과 같은 exclusive hard-link로 final을 publish한다. overwrite 가능한 `os.replace()` fallback은 금지한다.
6. ordering은 bytes publish 후 latest claim·cancel·rights·revocation·revision 재검증과 짧은 `verified_staged` CAS다. filesystem I/O 동안 DB transaction은 없다.
7. publish와 DB 사이 crash는 deterministic orphan을 만든다. restart는 full verification 후 같은 locator에 adopt하고 CAS를 재시도한다. 별도 intent state나 manifest/table을 만들지 않는다.
8. local object는 매 open containment·regular identity·full SHA-256·size·media를 DB actual facts와 비교한다. mtime·extension·Content-Type만 신뢰하지 않는다.
9. DB `verified_staged`인데 object가 missing/tampered면 backward transition과 같은 locator reacquisition 없이 fail closed한다. integrity revocation과 cleanup을 수행하고 새 execution은 명시적 RetryJob/new binding을 요구한다.
10. cleanup은 `cleanup_pending → physical idempotent delete → cleaned` 순서다. policy는 Reconciliation Service, physical operation은 adapter, stale/orphan 실행은 janitor가 소유한다.
11. healthy staging에 임의 TTL을 두지 않는다. source expiry는 기존 verified bytes를 무효화하지 않고 locator policy와 rights가 reuse를 결정한다.
12. narrow `VerifiedPayloadStagingPort`를 두되 첫 구현은 local filesystem이다. object storage는 conditional create·version·consistency·retention authority를 별도 ADR에서 검토한다.

schema 판정은 다음과 같다.

```text
NO_NEW_SCHEMA_REQUIRED
NO_NEW_ALEMBIC_REQUIRED
```

## 선택 이유

- locator-derived key가 orphan과 DB row를 연결하므로 random storage ID용 metadata가 필요 없다.
- DB보다 bytes를 먼저 publish하면 object 없는 `verified_staged` row를 만들지 않는다.
- orphan file은 안전하게 scan/adopt/delete할 수 있지만 DB의 잘못된 success authority는 복구하기 어렵다.
- existing storage primitives와 staging root를 재사용해 Artifact storage와 보안 관례를 일치시킨다.
- local filesystem의 mutable 성격은 매 open full verification으로 닫고 확인되지 않은 immutability guarantee를 두지 않는다.

## 대안

| 대안 | 판정 | 이유 |
|---|---|---|
| 별도 staging metadata table | 거부 | current locator actual fields와 deterministic key를 중복하고 새 two-record transaction을 만듦 |
| DB intent → file → DB finalize | 거부 | 새 lifecycle/state가 필요하며 이번 authority에서 이득 없이 복잡도 증가 |
| content-hash final key | 거부 | dedup·공유 retention·payload 상관관계가 불필요하고 locator ownership이 흐려짐 |
| random final object ID | 거부 | publish-before-DB orphan을 locator에 연결할 별도 metadata 필요 |
| `os.replace()` publish | 거부 | 기존 final을 silent overwrite할 수 있고 cross-platform no-clobber semantics가 다름 |
| object storage abstraction 선행 | 거부 | local 요구는 기존 port/primitives로 충족하며 object version authority가 아직 없음 |
| process-local registry를 production 사용 | 거부 | restart·multi-process handoff를 보장하지 못함 |

## 장단점과 영향

장점은 schema 변경 없이 restart adoption, idempotent same-locator publish와 existing Artifact ingestion handoff를 제공하는 것이다. 단점은 local resolve마다 full checksum/media 검증 비용이 들고 orphan janitor가 필요하다는 점이다. Windows directory `fsync`와 갑작스러운 전원 손실 전체에 대한 완전한 durability는 보장하지 않는다.

staging success는 Workspace success나 Artifact ingestion이 아니다. downloader, Completion, Worker와 Product API는 계속 미구현이다. 개인 음성 payload root는 process-private 권한이 필요하며 filename·DB·로그에 voice/user/source identity를 넣지 않는다.

## 마이그레이션과 구현 순서

DB migration은 없다. 첫 구현 PR은 port, local adapter, partial/publish/recover/open/delete, crash·security tests와 `PayloadLocator verified_staged` integration까지만 포함한다. 그 뒤 downloader, Artifact ingestion adapter, Completion adapter, Worker wiring 순서로 진행한다.

## 재검토 조건

- object storage 또는 network filesystem을 운영 backend로 채택할 때
- immutable object version·conditional create·retention lock을 DB에 기록해야 할 때
- Windows/Linux supported filesystem에서 exclusive hard-link publish를 제공할 수 없을 때
- 매 open full verification 비용이 실제 측정으로 병목임이 확인될 때
- multi-host shared staging과 stronger power-loss durability가 제품 요구가 될 때

## 관련 PR

- Authority 문서 PR: Draft 생성 후 번호 기록

