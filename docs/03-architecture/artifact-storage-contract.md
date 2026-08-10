# Artifact Storage Resolver와 무결성 계약

> 문서 상태: [승인]
> 최종 수정일: 2026-08-10
> 관련 기능: Artifact Catalog, Storage Resolver, 안전한 ingestion과 content·download
> 관련 문서: [Workspace Artifact 모델](workspace-artifact-model.md), [Workspace Job Foundation](workspace-job-foundation.md), [Storage Architecture](storage-architecture.md), [Workspace REST API 계약](../06-api/workspace-rest-api-contract.md), [ADR-032](../11-decisions/ADR-032-artifact-storage-resolver-integrity.md), [Common Artifact Specification](https://github.com/DohaStudio/.github/blob/main/docs/specifications/03-artifact-specification.md), [Common Provider Contract](https://github.com/DohaStudio/.github/blob/main/docs/specifications/04-provider-contract.md), [Common Job Contract](https://github.com/DohaStudio/.github/blob/main/docs/specifications/05-job-contract.md)

## 1. 목적과 현재 경계

이 문서는 `Artifact`의 논리 식별자와 물리 Payload를 연결하는 내부 Storage 계약을 확정한다. `ArtifactStorageLocation` Catalog와 revision `20260809_0016`은 실제 사용자 DB 적용을 완료했으며 row는 0개다. Catalog 조회·local Resolver와 trusted ingestion을 구현해 임시 root에서 authoritative SHA-256·size·MIME, immutable publish, Artifact·Catalog transaction과 실패 보상을 검증했다. Owner 계보·retention·integrity read Gate, batch dry-run reconciliation, Artifact Router와 single-byte HTTP Range도 구현했다. destructive reconciliation과 실제 운영 폴더·파일 전환은 구현하지 않았다.

현재 `AUDIO_STORAGE_ROOT`와 기존 Runtime Table 14개는 계속 운영 source of truth다. Workspace Resource API는 Job 5개를 포함해 30/64, Artifact API는 3/3이며 다음 세 공개 Endpoint를 구현했다.

```text
GET /api/v1/artifacts/{artifact_id}
GET /api/v1/artifacts/{artifact_id}/content
GET /api/v1/artifacts/{artifact_id}/download
```

Artifact POST·PATCH·DELETE·목록과 Version 하위 Artifact 목록은 공개 계약에 추가하지 않는다.

Metadata 응답은 논리 식별자·kind·MIME·크기·checksum·producer·retention·생성 시각과 활성 Artifact의 content·download link만 제공한다. Catalog, backend, domain, storage key, URI와 로컬 Path는 공개하지 않는다. content·download는 같은 검증된 descriptor를 1MiB chunk로 전달하며 전체 응답은 `200`, 유효한 단일 byte range는 `206`, multiple·invalid·unsatisfiable range는 `416 INVALID_RANGE`로 응답한다.

## 2. 도메인 의미와 불변성

```text
Asset
  → 불변 AssetVersion
    → 불변 Artifact Metadata
      → 내부 Artifact Storage Catalog
        → 승인된 Storage root의 불변 Payload
```

- `Asset`은 논리 자산이다.
- `AssetVersion`은 특정 시점의 불변 논리 버전이다.
- `Artifact`는 정확한 `asset_version_id`에 귀속된 물리 Payload의 불변 기록이다.
- Artifact는 최신 AssetVersion이나 Asset 자체를 자동 참조하지 않는다.
- Payload, checksum, size, media type 또는 locator의 의미가 달라지면 기존 Artifact를 덮어쓰지 않고 새 Artifact를 발급한다. 논리 내용이나 계보까지 달라지면 새 AssetVersion도 생성한다.
- `retention_status` 전이는 Payload 변경이 아니라 lifecycle event다.

## 3. Storage root와 도메인

신규 Artifact Storage는 Legacy `AUDIO_STORAGE_ROOT`와 분리하고 환경별 설정으로 주입하는 논리 root를 사용한다. 개발자 로컬 예시는 다음과 같지만 코드·DB·API에는 이 절대 경로를 저장하지 않는다.

```text
D:/DohaArtifacts/
├── lm/
├── audio/
├── vocal/
└── music/
    ├── mixes/
    ├── exports/
    ├── previews/
    ├── snapshots/
    └── runs/
```

초기 local backend는 `DOHA_ARTIFACT_ROOT` 환경 설정으로 base root를 주입한다. trusted ingestion의 서비스 소유 임시 Payload는 별도 `DOHA_ARTIFACT_STAGING_ROOT`로 주입하며 두 변수는 기본 미설정이고 서로 겹치면 fail-closed한다. 네 domain directory와 staging root는 실제 안전한 directory여야 한다. `lm`, `audio`, `vocal`은 Provider 결과를, `music`은 DohaMusic의 Mix·Export·Preview·Snapshot·Workspace run을 소유한다. 코드와 공개 DTO에는 운영 절대 경로를 저장하지 않는다.

## 4. authoritative Catalog 결정

Artifact Entity에는 path와 storage key를 추가하지 않는다. 내부 전용 별도 DB Table인 `artifact_storage_locations`를 authoritative Catalog로 추가하는 방향을 채택한다.

최소 목표 필드는 다음과 같다.

| 필드 | 계약 |
|---|---|
| `artifact_id` | `artifacts.artifact_id`를 참조하는 1:1 식별자 |
| `storage_backend` | 초기값 `local`; 향후 object storage 확장 식별자 |
| `storage_domain` | `lm`, `audio`, `vocal`, `music` 중 하나 |
| `storage_key` | 해당 domain root 기준 canonical 상대 key |
| `locator_version` | locator 해석 계약 version, 초기값 `1` |
| `published_at` | 불변 위치 publish 완료 시각 |
| `created_at` | Catalog row 생성 시각 |

`(storage_backend, storage_domain, storage_key)`는 유일해야 하고 하나의 Artifact는 하나의 authoritative locator만 가진다. 위치 변경은 기존 row의 의미를 조용히 바꾸지 않고 별도 승인된 relocation 절차와 감사 이력을 요구한다.

### 4.1 대안 평가

| 대안 | 판정 | 이유 |
|---|---|---|
| 별도 DB Catalog Table | 채택 | Artifact row와 같은 transaction으로 참조를 고정하고 backup·조회·권한·다중 backend 확장이 용이함 |
| Manifest·Catalog 파일 | 제외 | DB와 파일 사이 crash drift, 동시 갱신과 backup 일관성 관리가 어려움 |
| `artifact_id`의 deterministic path 변환 | 제외 | domain·backend·파일 형식·Provider별 보존 경계를 표현하기 어렵고 relocation 유연성이 낮음 |
| 기존 Runtime 상대 경로 재사용 | 제외 | Legacy source of truth와 목표 Artifact 경계를 다시 결합함 |

이 결정에 따라 별도 `ArtifactStorageLocation` Entity와 `artifact_storage_locations` Table, additive revision `20260809_0016`을 구현하고 실제 사용자 DB에 적용했다. 목표 21개 Workspace Entity와 기존 35개 Table은 변경하지 않았으며 source metadata와 실제 사용자 DB는 Catalog를 포함한 36개 Application Table이다. Catalog row는 0개이고 기존 79개 row와 canonical digest는 보존됐다.

## 5. Storage key 계약

`storage_key`는 domain root 기준 UTF-8 canonical POSIX 상대 표현이다.

- `/`만 구분자로 사용한다.
- 빈 segment, `.`, `..`, 역슬래시, NUL, drive letter, UNC, 절대 POSIX path를 거부한다.
- percent-encoded separator·dot segment와 이중 인코딩을 허용하지 않는다.
- URL·HTTP 입력으로 직접 받지 않는다. Adapter가 encoded 값을 다뤄야 하면 정확히 한 번 decode한 뒤 canonical validator에 전달한다.
- 최종 파일명에는 `artifact_id`를 포함해 충돌과 덮어쓰기를 방지한다.
- `music` domain의 첫 segment는 `mixes`, `exports`, `previews`, `snapshots`, `runs` 중 계약상 허용된 값이어야 한다.

예시는 설명용이며 공개 계약이나 하드코딩된 경로가 아니다.

```text
domain: music
storage_key: runs/<run-id>/<artifact-id>.wav
```

## 6. URI와 공개 식별 계약

내부 논리 URI가 필요할 때 canonical 형식은 다음으로 고정한다.

```text
artifact://<artifact_id>
```

- URI에는 domain, storage key, drive, mount와 실제 파일명을 넣지 않는다.
- Resolver는 URI의 Artifact ID를 검증한 뒤 Catalog를 조회한다.
- 공개 HTTP 응답은 내부 URI보다 `/api/v1/artifacts/{artifact_id}/content`와 `/download` API link를 우선한다.
- 공개 API는 `file://`, 절대·상대 path, storage key와 object storage credential을 반환하지 않는다.
- Provider 경계에서는 등록 완료된 Artifact만 ID 또는 `artifact://`로 참조한다. 등록 전 출력은 신뢰된 임시 handoff이며 Artifact가 아니다.

## 7. Resolver 계약

공개 요청의 owner scope와 retention은 상위 Artifact Application Service가 먼저 확인한다. 승인된 `artifact_id`를 받은 Resolver는 다음 순서로만 물리 Payload를 해석한다.

```text
승인된 artifact_id
→ Artifact Storage Catalog 조회
→ 승인된 backend·domain root 선택
→ canonical storage_key 검증
→ root와 결합 후 resolve
→ root containment·symlink/reparse point·regular file 검증
→ 열린 file descriptor의 identity·size·mtime 재검증
```

현재 Resolver는 `local` backend와 locator version `1`만 지원하고 그 밖의 값은 fallback 없이 거부한다. Resolver는 내부 dataclass에만 검증된 Path를 보존하며 Router, 공개 Pydantic DTO, 오류 메시지 또는 로그에 반환하지 않는다. 내부 로그도 사용자 절대 경로 대신 `artifact_id`, domain과 안전한 오류 식별자만 기록한다. Resolver는 Catalog·Artifact 생성, 파일 publish·copy·move·delete, transaction 종료, retention 전이와 HTTP 응답을 담당하지 않는다.

Windows에서는 모든 component의 symlink와 사용 가능한 `Path.is_junction()` 및 `FILE_ATTRIBUTE_REPARSE_POINT` 검사를 조합한다. 경로 검사 뒤 `os.open()`한 descriptor와 `lstat` identity를 비교하고 content 계층이 같은 handle을 사용하도록 `open_payload()`를 제공한다. 다만 신뢰 root에 대한 동시 쓰기를 완전히 통제하는 것은 운영 권한 정책의 책임이며, delivery 전 전체 checksum 검증은 후속 단계다.

## 8. 신뢰된 ingestion

공개 Artifact POST는 제공하지 않는다. Provider·Worker·Import workflow는 DohaMusic의 신뢰된 Application Service를 통해 다음 절차를 수행한다.

```text
승인된 임시 Payload
→ 허용 root·regular file·symlink 검사
→ 실제 bytes 읽기
→ size 계산
→ SHA-256 계산
→ artifact kind별 media type 검증
→ 새 artifact_id와 충돌 없는 storage key 결정
→ 최종 불변 위치에 exclusive atomic publish
→ 하나의 DB transaction에서 Artifact·Catalog·필요한 계보 참조 등록
→ 성공 후 임시 Payload 정리
```

- DB row를 먼저 만들고 검증되지 않은 파일을 나중에 맞추지 않는다.
- 호출자·Provider의 checksum, size와 media type은 비교용 hint일 뿐 authoritative 값이 아니다.
- 최종 대상이 이미 있으면 overwrite하지 않고 실패한다.
- publish 뒤 DB transaction이 실패하면 해당 실행이 새로 만든 Payload만 조건부 정리한다. 즉시 정리에 실패하거나 publish와 commit 사이에 process가 종료되면 deterministic Artifact ID와 grace period를 사용하는 orphan reconciliation 대상으로 남기며 다른 파일을 자동 삭제하지 않는다.
- Artifact와 Catalog row는 같은 DB transaction에서 생성해 row만 존재하고 locator가 없는 상태를 만들지 않는다.

Job은 Artifact의 필수 부모가 아니다. `import`, 사용자·Workspace 내부 생성과 Provider 결과가 모두 가능하고 `run_id`는 선택적이다. Provider 결과일 때만 성공한 Job의 `JobOutput`과 새 AssetVersion 계보를 함께 연결한다.

Workspace Job 결과는 단일 Artifact ingestion 성공만으로 Job을 성공 처리하지 않는다. 필수 output 전체를 검증한 뒤 Artifact·Catalog·필요한 AssetVersion·JobOutput·ModelUsage와 상태를 completion Unit of Work에 등록한다. 일부 output만 생성되면 Job은 `failed`이며 partial Payload는 staging 제거 또는 quarantine하고 정상 사용자 Artifact로 공개하지 않는다. 구체적인 cancel race와 보상 순서는 [Workspace Job Foundation](workspace-job-foundation.md)을 따른다.

Completion Unit of Work는 기존 ingestion을 우회하지 않고 prepare·register·verify·compensate primitive를 재사용한다. 독립 ingestion은 기존 자체 transaction을 유지하고 Completion Service는 같은 primitive를 상위 transaction에 주입해 AssetVersion부터 Job 성공까지 원자적으로 묶는다. 성공·replay 뒤 staging payload를 identity 확인 후 정리하며 rollback 시 이번 invocation이 publish한 payload만 보상한다.

현재 구현은 Common Specification의 kind 중 `lyrics_text`, `audio`, `stem`, `manifest`, `evaluation`, `snapshot`만 허용한다. Audio는 WAV·FLAC·MP3 header와 WAV parser, text는 streaming UTF-8 decoder, 구조화 kind는 16MiB 상한의 UTF-8 JSON parser로 검증한다. format validator와 권리 정책이 확정되지 않은 `model`·`checkpoint`는 fail-closed한다. producer는 `user`, `provider`, `workspace`, `import`만 허용하고 새 Artifact의 retention은 caller 입력 없이 `active`로 고정한다.

storage key는 caller가 지정하지 않는다. non-`music`은 `payloads/<kind>/<uuid-shard>/<artifact-id>.<validated-extension>`, `music`은 `snapshots` 또는 `runs` namespace를 사용한다. source가 다른 filesystem에 있어도 final root 내부 exclusive 임시 inode로 streaming copy·file `fsync`한 뒤 hard-link로 publish하므로 기존 target을 덮어쓰지 않는다. POSIX에서는 directory `fsync`도 시도하며 Windows directory durability는 제한된 WARNING이다.

DB 실패 시 이번 실행이 publish한 inode만 identity 확인 후 보상 삭제한다. 삭제 실패 또는 성공 후 staging 정리 실패는 absolute path 없는 `OrphanCandidate`와 내부 reporter hook으로 남긴다. 자동 삭제 worker, grace period scan과 영속 reconciliation 상태는 후속 범위다.

## 9. 무결성 Metadata 책임

### 9.1 Checksum

- 초기 authoritative algorithm은 `sha256`이다.
- 서버 ingestion 계층이 실제 Payload bytes 전체에서 lowercase 64자리 checksum을 계산한다.
- 호출자 제공 checksum은 비교용 hint이며 불일치하면 publish하지 않는다.
- 같은 checksum의 Payload가 있어도 별도 Artifact ID를 허용할지는 dedup 정책의 후속 결정이며 현재 자동 병합하지 않는다.

### 9.2 Size

`size_bytes`는 서버가 같은 Payload handle의 실제 byte 길이에서 계산한다. 음수, bool, float와 호출자 선언값을 authoritative 값으로 저장하지 않는다.

### 9.3 Media type

확장자와 producer hint만으로 확정하지 않는다.

| Artifact 종류 | 최소 검증 |
|---|---|
| WAV·FLAC·MP3 등 Audio | 허용 MIME·magic/header와 필요 시 제한된 `ffprobe` 결과 일치 |
| Lyrics·text | UTF-8 decode와 허용 text media type |
| JSON Manifest·Evaluation·Snapshot | UTF-8 JSON parse, 대상이 정한 Schema가 있으면 Schema 검증 |
| Model·Checkpoint·Adapter | 전용 kind·크기 상한·권리 정책 확인, 공개 inline 금지 |

완전한 sniffing이 불가능하면 kind별 allowlist와 validator 결과를 사용하고 검증할 수 없는 조합은 fail-closed한다.

## 10. Owner와 공개 접근

Artifact에는 `owner_id`를 추가하지 않는다. 모든 공개 요청은 다음 관계로 effective Owner를 파생한다.

```text
Artifact → AssetVersion → Asset → owner_id
```

- 공개 입력으로 `owner_id`, storage key와 local path를 받지 않는다.
- 권한이 없거나 다른 Owner의 Artifact는 존재 여부를 숨기기 위해 `404 ARTIFACT_NOT_FOUND`로 처리한다.
- `active`여도 kind·권리·Consent 정책이 허용하지 않으면 content·download를 제공하지 않는다.
- Model, Checkpoint, Adapter, Dataset, Consent 증적과 개인 음성 원본은 별도 명시적 정책 없이는 공개 delivery 대상이 아니다.

## 11. Retention과 GC

Entity는 이번 PR에서 변경하지 않지만 `retention_status`에 저장할 값은 다음으로 제한한다.

| 상태 | Metadata | Content | Download | GC |
|---|---:|---:|---:|---:|
| `active` | 허용 | kind·권한 허용 시 허용 | kind·권한 허용 시 허용 | 금지 |
| `quarantined` | 허용 | `409` 거부 | `409` 거부 | 검토 전 금지 |
| `expired` | 허용 | `410` 거부 | `410` 거부 | 정책·계보 확인 후 가능 |
| `pending_delete` | 허용 | `410` 거부 | `410` 거부 | 가능 |
| `deleted` | 허용 | `410` 거부 | `410` 거부 | Payload 없음 |

공개 DELETE API는 제공하지 않는다. 물리 삭제는 retention policy와 별도 GC·maintenance 승인 흐름에서만 수행한다. GC는 AssetVersion·JobInput·JobOutput·Snapshot·Consent·법적 보존과 계보 참조를 먼저 검사하고, DB row와 감사 이력을 즉시 제거하지 않는다. 실패 시 상태와 안전한 오류 식별자를 남기며 자동 restore나 무관한 Payload 삭제를 수행하지 않는다.

## 12. Metadata GET 계약

`GET /api/v1/artifacts/{artifact_id}`는 권한 확인 후 다음 공개 필드를 반환한다.

- `artifact_id`
- `asset_version_id`
- `artifact_kind`
- `media_type`
- `size_bytes`
- `checksum_algorithm`
- `artifact_checksum`
- `producer_type`
- 공개 가능한 경우에만 `producer_id`, `run_id`
- `retention_status`
- `created_at`
- 정책상 허용되는 경우의 `content_url`, `download_url`

`storage_backend`, `storage_domain`, `storage_key`, 내부 URI, 절대·상대 Path와 임시 파일 정보는 반환하지 않는다. `producer_id`와 `run_id`가 내부 Provider·사용자·운영 식별자를 노출하면 생략하거나 공개용 식별자로 투영한다.

## 13. Content와 Download

### 13.1 공통 검증

두 Endpoint는 매 요청 owner, retention, delivery allowlist, Catalog, regular file, size와 checksum을 확인한다. 초기 local backend는 전체 SHA-256 검증을 통과하기 전 Payload bytes를 보내지 않는다. 향후 검증 cache는 immutable file identity·size·mtime과 checksum에 결합하고 어떤 값이 달라져도 폐기해야 한다.

### 13.2 Content

`GET /api/v1/artifacts/{artifact_id}/content`는 허용된 Payload를 `Content-Type`, `Content-Length`와 `Content-Disposition: inline`으로 제공한다. 공식 Endpoint 수에 HEAD를 추가하지 않는다.

### 13.3 Download

`GET /api/v1/artifacts/{artifact_id}/download`는 동일 검증 후 `Content-Disposition: attachment`를 사용한다. 초기 안전한 파일명은 검증된 media type의 allowlist extension을 사용한 다음 형식이다.

```text
<artifact-kind>-<artifact-id>.<extension>
```

파일명은 CR·LF, 따옴표, path separator, control character와 예약 이름을 제거하고 길이를 제한한다. 유효한 이름을 만들 수 없으면 `artifact-<artifact-id>.bin`을 사용한다. storage key와 서버 파일명은 공개 파일명으로 사용하지 않는다.

## 14. Range 계약

Audio 재생을 위해 두 delivery Endpoint는 단일 byte range를 지원한다.

- 지원: `bytes=start-end`, `bytes=start-`, `bytes=-suffix`
- 제외: multiple range, 다른 unit, 겹치거나 정렬되지 않은 범위
- 전체 응답: `200`, `Accept-Ranges: bytes`, 정확한 `Content-Length`
- 부분 응답: `206`, 정확한 `Content-Range`와 부분 `Content-Length`
- 문법 오류·범위 밖·multiple range: `416 INVALID_RANGE`, `Content-Range: bytes */<size>`

Range 검증 전에 owner·retention·integrity 검증을 우회하지 않는다.

## 15. Path·symlink·TOCTOU 방어

- 승인된 root는 application 설정에서만 주입하며 사용자 입력으로 선택하지 않는다.
- canonical key를 root와 결합한 후 `resolve()`하고 root containment를 다시 검사한다.
- 모든 path component의 symlink, Windows junction과 reparse point를 거부한다.
- regular file만 열고 directory, device, pipe와 socket을 거부한다.
- POSIX에서는 가능한 경우 `O_NOFOLLOW`, Windows에서는 reparse point 검사를 사용한다.
- 검증과 open 사이 경로 교체를 막기 위해 open한 handle의 file identity·stat을 확인하고 checksum 계산과 전송도 같은 handle을 사용한다. 다시 열어야 하면 identity·size·mtime 일치를 재검증한다.
- Artifact root의 일반 write 권한은 ingestion component로 제한하고 delivery process는 read-only를 원칙으로 한다.

## 16. 손상·누락과 오류 계약

| HTTP | 오류 코드 | 조건 |
|---:|---|---|
| 404 | `ARTIFACT_NOT_FOUND` | Artifact 없음, owner 불일치 또는 존재 비공개 |
| 409 | `ARTIFACT_CONTENT_UNAVAILABLE` | Catalog locator·Payload 누락, delivery 비허용 또는 안전하게 제공할 수 없음 |
| 409 | `ARTIFACT_QUARANTINED` | `quarantined` 상태 |
| 410 | `ARTIFACT_GONE` | `expired`, `pending_delete`, `deleted` 상태 |
| 416 | `INVALID_RANGE` | 지원하지 않거나 만족할 수 없는 byte range |
| 500 | `ARTIFACT_INTEGRITY_ERROR` | 실제 size·checksum이 DB Metadata와 불일치 |

Checksum·size mismatch가 발생하면 전송을 시작하지 않고 내부 손상으로 기록한다. 외부 응답에는 path, 기대·실제 checksum, stack trace와 Catalog 내용을 포함하지 않는다. 자동 quarantine 전이는 별도 maintenance transaction과 감사 정책으로 구현하며 read 요청이 DB 상태를 암묵적으로 변경하지 않는다.

DB row는 있지만 Catalog나 Payload가 없는 경우 `ARTIFACT_CONTENT_UNAVAILABLE`을 반환한다. 이는 Artifact 자체가 없다는 뜻이 아니므로 owner가 확인된 요청에 한해 409를 사용하고 내부 path는 숨긴다.

## 17. 구현 선행 조건

1. `[완료]` `artifact_storage_locations` Entity·additive source revision `20260809_0016`과 임시 DB upgrade·downgrade 검증
2. `[완료]` 실제 사용자 DB read-only Inventory·backup·restore·migration rehearsal과 별도 승인에 따른 `20260809_0016` 적용
3. `[완료]` Storage root 설정, canonical key validator, Catalog 조회 Repository와 local Resolver 구현
4. `[완료]` trusted ingestion Service와 local Publisher 구현
5. `[완료]` symlink·reparse simulation·traversal·checksum·MIME·크기·collision·orphan signal 테스트
6. `[완료]` Owner·retention·full SHA-256 read Gate와 dry-run reconciliation 구현
7. Artifact Metadata·content·download API 3개 구현

Catalog와 Resolver가 검증되기 전 Artifact API를 구현하지 않는다. Artifact Collection·Cursor·keyset Index와 Job API는 이 Foundation의 선행 조건이 아니다.
