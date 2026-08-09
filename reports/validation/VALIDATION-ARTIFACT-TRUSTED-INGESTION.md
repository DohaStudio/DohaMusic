# Artifact Trusted Ingestion 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: Artifact Trusted Ingestion 기반
> 관련 문서: [Artifact Storage 계약](../../docs/03-architecture/artifact-storage-contract.md), [Artifact Ingestion 운영](../../docs/10-operations/artifact-storage-ingestion.md), [ADR-032](../../docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)

## 1. 검증 범위

이번 검증은 별도 staging root에서 신뢰 경계 안으로 파일을 반입하고, 서버가 계산한 SHA-256·크기·MIME을 기준으로 immutable publish한 뒤 `Artifact`와 `ArtifactStorageLocation`을 하나의 Service transaction으로 등록하는 기반을 대상으로 한다.

다음 항목은 범위에서 제외했다.

- Artifact Metadata·content·download API와 Range 전송
- 실제 사용자 DB, 실제 `DohaArtifacts`와 운영 staging root 접근
- Alembic revision, backfill, dual write, Runtime·Provider·Frontend 변경
- owner·retention 공개 Service, full orphan reconciliation worker
- 실제 GPU·모델·외부 Provider·유료 API 통합 검증

## 2. 계약 검증

| 항목 | 결과 | 확인 내용 |
|---|---|---|
| 신뢰 경계 | PASS | staging root를 최종 Artifact root와 분리하고 상대 경로·root 이탈·symlink·reparse point·비정규 파일을 거부한다. |
| 권위 있는 메타데이터 | PASS | SHA-256과 크기는 1 MiB chunk streaming copy 중 서버가 계산하고, MIME은 복사된 실제 바이트를 검증한다. |
| 지원 kind | PASS | `lyrics_text`, `audio`, `stem`, `manifest`, `evaluation`, `snapshot`만 allowlist로 허용한다. |
| fail closed | PASS | `model`, `checkpoint`와 알려지지 않은 kind·domain·producer는 명시적 validator가 없어 거부한다. |
| immutable publish | PASS | 최종 filesystem 안의 pending 파일을 exclusive hard-link publish해 기존 key를 덮어쓰지 않는다. |
| cross-volume 입력 | PASS | staging source를 최종 filesystem의 pending 파일로 먼저 복사하므로 source와 final root가 다른 volume이어도 rename에 의존하지 않는다. |
| key 정책 | PASS | 사용자 입력 경로를 key로 사용하지 않고 kind·Artifact ID·검증된 확장자로 collision-resistant key를 생성한다. |
| 단일 transaction | PASS | `Artifact`와 Catalog row를 같은 SQLAlchemy transaction에서 생성하며 Repository는 commit·rollback을 호출하지 않는다. |
| 사후 검증 | PASS | commit 전에 Resolver round-trip으로 Catalog, 파일 identity와 size를 다시 확인한다. |
| 보상·orphan 신호 | PASS | DB 등록 실패 시 방금 게시한 동일 파일만 보상 삭제하고, 실패하면 절대 경로 없는 orphan candidate를 보고한다. |
| lineage | PASS | 동일 checksum도 별도 Artifact ID와 storage key로 등록할 수 있어 자동 dedup으로 계보를 합치지 않는다. |
| 외부 계약 | PASS | 결과 객체와 오류에 staging·최종 절대 경로를 포함하지 않는다. |

Windows에서는 일반 파일과 디렉터리 handle의 durability 보장이 POSIX와 다르다. 파일 `fsync`는 수행하지만 directory `fsync`는 지원 가능한 환경에서만 수행하므로 운영 환경별 crash durability 검증은 WARNING으로 유지한다.

## 3. 테스트 결과

깨끗한 격리 worktree에서 다음 선별 회귀를 실행했다.

| 구분 | 결과 |
|---|---|
| Trusted Ingestion 신규 테스트 | 37 passed, 1 skipped |
| 기존 Resolver·Catalog·Workspace·Resource·Migration 회귀 | 135 passed, 2 skipped |
| 합계 | 172 passed, 3 skipped |

Windows에서 권한 없이 실제 symlink를 만들 수 없는 fixture 3건은 skip됐으며, reparse·link 거부 분기는 모의 검증과 가능한 실제 경로 검증으로 보완했다. 경고는 Starlette `httpx` shortcut 폐기 예정 1개와 기존 OpenAPI operation ID 중복 2종이 반복 보고된 4개로, 이번 구현의 BLOCKER가 아니다.

검증한 주요 시나리오는 다음과 같다.

- WAV·FLAC·MP3, UTF-8 text, UTF-8 JSON의 성공과 형식 불일치 실패
- checksum·size·media type caller hint 불일치 실패
- missing AssetVersion, 잘못된 domain·kind·producer 실패
- staging escape, directory, missing file, symlink·reparse point 실패
- 동일 최종 key의 순차·동시 collision과 기존 파일 무변경
- Artifact·Catalog·commit 실패 시 보상 삭제와 orphan signal
- staging cleanup 실패 신호와 성공 결과의 절대 경로 비노출
- chunk보다 큰 입력의 streaming 처리와 동일 checksum 별도 lineage

## 4. 정적·구조 검증

| 항목 | 결과 |
|---|---|
| Python 3.12.5 compile | PASS |
| Ruff lint | PASS |
| Ruff format check | PASS — Backend 280개 파일 |
| `git diff --check` | PASS |
| Alembic head | PASS — `20260809_0016` 단일 head, 신규 revision 없음 |
| 실제 DB·Artifact 접근 | PASS — 수행하지 않음 |
| API·Frontend 변경 | PASS — 없음 |
| Dataset·모델·Checkpoint·미디어·비밀정보 | PASS — 포함하지 않음 |

전체 Backend suite, GPU·모델·외부 Provider·유료 API·실제 DB·실제 Artifact root 검증은 범위와 안전 조건 때문에 실행하지 않았다. 실행하지 않은 검증을 통과로 표현하지 않는다.

## 5. 판정

- BLOCKER: 0건
- 최종 판정: PASS
- 실제 사용자 DB: `20260809_0016`, Application Table 36개 상태를 변경하지 않음
- Resource API: 19/64, Artifact API 0/3 상태를 변경하지 않음
- 다음 단계: owner·retention 정책, full orphan reconciliation, Artifact Resource API와 Range 전송을 각각 별도 작업으로 검토
