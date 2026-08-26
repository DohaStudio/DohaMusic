# Artifact Trusted Ingestion 운영 계약

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-10
> 관련 기능: 내부 Artifact publish, authoritative SHA-256·size·MIME, 실패 보상
> 관련 문서: [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Verified Durable Staging Authority](../03-architecture/verified-durable-staging-authority.md), [ADR-032](../11-decisions/ADR-032-artifact-storage-resolver-integrity.md), [ADR-051](../11-decisions/ADR-051-verified-durable-staging-authority.md), [환경 변수](environment-variables.md)

## 1. 현재 경계

Trusted Ingestion은 Provider·Worker·Import·DohaMusic 내부 workflow가 넘긴 서비스 소유 임시 Payload를 불변 Artifact로 등록하는 내부 Application 경계다. 공개 REST POST가 아니며 Router·Frontend·Provider Runtime에 아직 연결하지 않았다.

```text
승인 staging Payload
→ AssetVersion 존재 확인
→ bytes·MIME 검증
→ final filesystem 내부 exclusive publish
→ Artifact + Catalog 단일 transaction
→ Resolver round-trip
→ staging 정리
```

## 2. 필수 설정

```env
DOHA_ARTIFACT_ROOT=
DOHA_ARTIFACT_STAGING_ROOT=
```

두 값에는 기본 경로가 없다. Artifact root의 `lm`, `audio`, `vocal`, `music` directory와 staging root가 모두 실제 안전한 directory여야 하고 서로 상위·하위 관계로 겹치면 구성을 거부한다. 코드·DB·로그·공개 DTO에 실제 절대 경로를 저장하지 않는다.

Staging root에 handoff한 파일은 DohaMusic이 소유하는 pre-Artifact Payload여야 한다. 사용자 원본, Provider 원본 저장소와 Dataset 파일을 staging으로 가장해 전달하지 않는다. verified local staging adapter는 같은 root의 전용 `payload-staging/v1` namespace에 verified object를 보존하고 context-managed safe handle을 제공한다. 검증 또는 DB 등록 실패 시 source는 재시도·진단을 위해 보존하고, 성공 후 locator cleanup policy와 identity/facts 검증을 통과한 staging Payload만 제거한다. Artifact ingestion 연결은 아직 미구현이다.

## 3. 허용 계약

| kind | domain | 검증 형식 |
|---|---|---|
| `lyrics_text` | `lm`, `music` | streaming UTF-8, `text/plain`, `.txt` |
| `audio` | `audio`, `vocal`, `music` | WAV·FLAC·MP3, 검증된 확장자 |
| `stem` | `audio`, `vocal`, `music` | WAV·FLAC·MP3, 검증된 확장자 |
| `manifest` | 모든 domain | 16MiB 이하 UTF-8 JSON |
| `evaluation` | 모든 domain | 16MiB 이하 UTF-8 JSON |
| `snapshot` | `music` | 16MiB 이하 UTF-8 JSON |

`model`·`checkpoint`는 공통 Artifact kind지만 format·크기·권리 validator가 확정되지 않아 현재 fail-closed한다. producer는 `user`, `provider`, `workspace`, `import`만 허용하고 새 Artifact의 retention은 `active`다. caller는 Artifact ID, storage key, final path, authoritative size·checksum·MIME를 지정할 수 없다.

## 4. Publish와 durability

Publisher는 source를 메모리에 전부 올리지 않고 1MiB chunk로 final filesystem 내부 exclusive 임시 inode에 복사하면서 SHA-256과 크기를 계산한다. 파일 `fsync` 후 검증된 MIME로 확장자를 정하고 hard-link를 사용해 final target을 무덮어쓰기 publish한다. 기존 target 또는 같은 pending target이 있으면 실패하며 `os.replace()`를 사용하지 않는다.

Staging이 다른 volume이어도 copy 경계를 사용하므로 cross-volume rename에 의존하지 않는다. POSIX에서는 parent directory `fsync`도 시도한다. Windows의 directory durability와 전원 장애 전체 원자성은 완전 보장하지 못하며 운영 WARNING이다.

## 5. DB와 filesystem 실패 보상

Artifact와 `ArtifactStorageLocation`은 같은 SQLAlchemy transaction에 add·flush되고 Service만 transaction을 종료한다. Repository는 commit·rollback·filesystem을 수행하지 않는다. commit 전 Resolver round-trip으로 Catalog·containment·regular file·identity·size를 재검증한다.

DB 또는 검증 실패 시 이번 실행이 만든 final inode만 identity 비교 후 삭제한다. 삭제 실패는 `artifact_id`, domain, canonical storage key와 안전한 reason code만 포함하는 `OrphanCandidate`로 reporter hook에 전달한다. staging 정리 실패도 성공 결과의 `staging_cleanup_pending`과 별도 candidate로 보고한다. 실제 절대 경로와 Payload 내용은 기록하지 않는다.

Reporter hook과 별도로 [Artifact Storage Reconciliation](artifact-storage-reconciliation.md)의 batch dry-run scanner를 구현했다. 승인 namespace에서 cleanup failure·Catalog·filesystem drift를 탐지하지만 영속 queue, 자동 재시도와 운영 삭제 승인은 후속 구현이다.

## 6. 현재 구현과 후속 범위

- Artifact Metadata·content·download, 공개 owner·retention HTTP 연결과 single-byte Range는 구현했다.
- 공개 Artifact POST·PATCH·DELETE·Collection은 계약에 없으며 추가하지 않았다.
- destructive reconciliation·영속 worker
- model·checkpoint authoritative validator
- local 이외 Storage backend
- 실제 Provider·Runtime 연결과 기존 파일 backfill

실제 사용자 DB와 실제 `DohaArtifacts`에 적용하려면 별도 Inventory·backup·rehearsal·사용자 승인이 필요하다.
