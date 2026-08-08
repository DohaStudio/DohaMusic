# Artifact Storage 계약 검증 보고서

> 상태: [완료]
> 검증일: 2026-08-08
> 기준 브랜치: `develop`
> 기준 commit: `391adbda461c4a6fa0dec6dc159c5ce1eb1849d6`
> 관련 문서: [Artifact Storage 계약](../../docs/03-architecture/artifact-storage-contract.md), [ADR-032](../../docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)

## 목적

Artifact Resource API 구현 전에 Entity·Repository·Service·Legacy Storage·REST 계약과 DohaStudio Common Specification을 대조하고 Resolver·URI·ingestion·무결성·접근·보존 계약을 문서로 고정한다.

## 확인한 현재 구현

- Artifact는 정확한 `asset_version_id`와 kind·MIME·size·checksum·producer·retention Metadata를 가지며 path·URI·storage key가 없다.
- Artifact Repository는 등록·단건 조회·Version별 offset 목록·checksum 조회를 제공한다.
- Artifact Service는 SHA-256 문자열 형식과 음수 size만 검사하며 실제 Payload를 읽지 않는다.
- Legacy `StorageService`는 `AUDIO_STORAGE_ROOT` 내부 상대 경로를 다루지만 Artifact ID Resolver가 아니다.
- 공개 Artifact 계약은 Metadata·content·download 3개이며 모두 미구현이다. POST·PATCH·DELETE·Collection은 공식 64개 Endpoint에 없다.

## 결정 검증

| 항목 | 결과 |
|---|---|
| Artifact 의미 | 정확한 AssetVersion에 귀속된 불변 물리 Payload 기록으로 고정 |
| Catalog | 별도 DB Table `artifact_storage_locations` 채택 |
| Entity 영향 | 기존 Artifact 변경 없음; 신규 내부 Catalog Entity·Table 필요 |
| Migration 영향 | 다음 구현 전에 additive Migration 필요 |
| URI | 내부 `artifact://<artifact_id>`, 공개 API link 우선 |
| storage key | domain root 기준 canonical POSIX 상대 key |
| checksum·size | 실제 bytes에서 ingestion Service가 계산 |
| media type | kind별 allowlist와 header·parser·선택적 ffprobe 검증 |
| owner | Artifact → AssetVersion → Asset → owner_id 파생 |
| retention | active·quarantined·expired·pending_delete·deleted |
| delivery | active 및 kind·권한 허용 시에만 content·download |
| Range | single byte range 지원, multiple range 제외 |
| 삭제 | 공개 DELETE 없이 GC·maintenance로 분리 |
| Job 의존 | 필수 부모가 아니며 Provider 결과일 때만 JobOutput 연결 |

## 안전성 검토

- absolute path, drive letter, UNC, dot segment, NUL과 encoded traversal을 금지했다.
- symlink, Windows junction·reparse point와 root 탈출을 금지했다.
- 같은 열린 file handle의 identity·stat·size·checksum을 검증하도록 TOCTOU 경계를 정했다.
- checksum mismatch는 전송 전 `ARTIFACT_INTEGRITY_ERROR`, Payload 누락은 owner 확인 후 `ARTIFACT_CONTENT_UNAVAILABLE`로 처리한다.
- 외부 응답과 로그에 path·storage key·내부 checksum 비교값을 노출하지 않는다.
- Model·Checkpoint·Dataset·Consent 증적과 개인 음성 원본은 명시적 정책 없이는 공개 delivery하지 않는다.

## 현재 상태

- Alembic source head: `20260808_0015`
- 실제 사용자 DB 기준: `20260808_0015`
- Application Table: 35개
- Runtime Table: 14개, source of truth 유지
- Workspace Resource API: 19/64
- Artifact API: 0/3
- Resolver·Catalog·신규 Artifact root·실제 파일 이동: 미구현

실제 사용자 DB와 실제 Artifact 파일에는 접근하지 않았다. 코드·Entity·Repository·Service·Alembic·DB·Runtime·Frontend를 변경하지 않았다.

## 문서 검증

| 검증 | 결과 |
|---|---|
| UTF-8 decode | PASS |
| 상대 링크 | PASS |
| Markdown fence | PASS |
| Mermaid block | PASS |
| `git diff --check` | PASS |
| 현재 상태 stale 표현 | 대상 문서 0건 |
| 비밀정보·사용자 절대 경로 | 0건 |
| 코드·Alembic·DB·Dataset·모델·미디어 변경 | 0건 |

## 판정

문서 계약은 **PASS**다. Artifact API 구현은 아직 **BLOCKED**이며 다음 Gate를 먼저 통과해야 한다.

1. Catalog Entity·additive Migration
2. Storage Resolver·trusted ingestion 구현
3. traversal·symlink·TOCTOU·checksum·MIME·orphan 회귀 테스트
4. owner·retention·delivery 정책 테스트

## WARNING

- Common Specification `0.1.0`은 `draft-baseline`·제안 상태다.
- local filesystem과 DB는 단일 원자 transaction이 아니므로 orphan reconciliation이 필요하다.
- 대용량 Payload의 매 요청 SHA-256 비용은 구현 benchmark 후 cache 정책을 재검토해야 한다.
- object storage, replica, signed URL과 다중 사용자 Role은 후속 범위다.
