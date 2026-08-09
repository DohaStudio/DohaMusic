# Artifact Resource API 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: Artifact Metadata·content·download, single-byte HTTP Range
> 관련 문서: [Artifact Storage 계약](../../docs/03-architecture/artifact-storage-contract.md), [Workspace REST API 계약](../../docs/06-api/workspace-rest-api-contract.md), [Endpoint 목록](../../docs/06-api/workspace-rest-api-endpoints.md), [ADR-032](../../docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)

## 1. 검증 범위

다음 세 공개 Endpoint와 기존 `ArtifactApplicationService` 연결을 격리된 임시 SQLite DB·임시 Storage root에서 검증했다.

```text
GET /api/v1/artifacts/{artifact_id}
GET /api/v1/artifacts/{artifact_id}/content
GET /api/v1/artifacts/{artifact_id}/download
```

공개 Artifact POST·PATCH·DELETE·Collection, Version 하위 Artifact 목록, destructive reconciliation, 비로컬 Storage backend와 실제 Provider·Runtime 연결은 범위에 포함하지 않았다.

## 2. 계약 검증

| 항목 | 결과 |
|---|---|
| effective Owner 계보와 cross-owner 존재 비공개 | 통과 |
| `active` Metadata와 content·download link | 통과 |
| `quarantined` 409, `expired|pending_delete|deleted` 410 | 통과 |
| Catalog·storage key·URI·Path 공개 금지 | 통과 |
| 실제 size·전체 SHA-256 검증 후 같은 descriptor 전달 | 통과 |
| 전체 응답 200과 정확한 delivery header | 통과 |
| `start-end`, `start-`, `-suffix` 단일 Range 206 | 통과 |
| multiple·invalid·unsatisfiable Range 416 | 통과 |
| 무결성 검증 전 Range 우회 금지 | 통과 |
| 1MiB chunk streaming과 descriptor 수명 관리 | 통과 |
| 안전한 download 파일명과 `.bin` fallback | 통과 |
| HTTP 요청에 따른 DB row 변경 없음 | 통과 |

## 3. 자동 검증 결과

| 검증 | 결과 |
|---|---|
| Artifact API 신규 테스트 | 46 passed |
| 최종 header·416 영향 선별 재검증 | 13 passed |
| 기존 Artifact·Workspace 회귀 묶음 | 207 passed, 3 skipped, 최초 count assertion 1 failed |
| 갱신한 API 기반 전체 테스트 | 11 passed |
| Python compile | 통과 |
| 변경 Python Ruff lint·format check | 통과 |
| `git diff --check` | 통과 |

회귀 묶음의 최초 실패 한 건은 기능 오류가 아니라 신규 Route 반영 전 고정 count assertion이었다. 기대값을 FastAPI Route 67개, `APIRoute` 63개, OpenAPI Path 47개, Operation 65개로 갱신한 뒤 API 기반 테스트 11개가 모두 통과했다. Windows symlink 관련 기존 테스트 3개는 환경 조건으로 skip됐으며 통과로 표현하지 않는다.

## 4. 현재 상태

- Artifact API: 3/3
- Workspace Resource API: 22/64
- FastAPI Route: 67개
- `APIRoute`: 63개
- OpenAPI Path: 47개
- OpenAPI Operation: 65개
- SQLAlchemy metadata: 36개 Application Table
- Alembic head: `20260809_0016`
- 실제 사용자 DB: 접근하지 않음
- 실제 `DohaArtifacts`: 접근하지 않음

## 5. 판정과 제한

**PASS** — 공개 Artifact Metadata·content·download와 single-byte Range가 기존 owner·retention·integrity 계약을 우회하지 않고 구현됐다.

남은 WARNING은 매 content 요청의 전체 SHA-256 비용, Windows symlink 테스트 3개 skip, 기존 Pipeline OpenAPI operation ID 중복 경고와 변경 범위 밖 전체 Backend Ruff 부채 71건이다. 변경 Python은 기존 dependency의 `TRY004` 2건과 같은 설정 검증 관례 1건을 제외한 lint와 전체 format check를 통과했다. 전체 Backend suite, 실제 대용량 Payload 성능, 비로컬 Storage, 실제 Provider·Runtime과 실제 사용자 DB·운영 Artifact는 실행하지 않았다.
