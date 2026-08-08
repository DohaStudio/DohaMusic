# AssetVersion Resource API 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-08
> 기준 develop: `bf9bcda410f8145e75865ed7ed0845d304903a46`
> 작업 브랜치: `feature/assetversion-api`
> 관련 기능: AssetVersion 생성·목록·상세 REST API와 불변 Version 계약
> 관련 문서: [Workspace REST API 공통 계약](../../docs/06-api/workspace-rest-api-contract.md), [Endpoint 목록](../../docs/06-api/workspace-rest-api-endpoints.md), [데이터베이스 재설계 개요](../../docs/07-database/database-redesign-overview.md)

## 1. 범위

다음 세 Endpoint를 구현했다.

- `GET /api/v1/assets/{asset_id}/versions`
- `POST /api/v1/assets/{asset_id}/versions`
- `GET /api/v1/assets/{asset_id}/versions/{asset_version_id}`

Artifact·Composition·Job API, Selection API, Frontend, Bootstrap, backfill, dual write, Runtime 전환, Provider, Cursor·Index와 Alembic은 변경하지 않았다. 실제 사용자 DB에도 접근하지 않았다.

## 2. 불변 계약

| 항목 | 결과 |
|---|---|
| 생성 | 기존 최대 `version_number + 1`의 새 row 생성 |
| 기존 Version | 덮어쓰기·수정·삭제 없음 |
| PATCH·DELETE | Route 미등록, `405 Method Not Allowed` |
| 목록 순서 | `version_number DESC`, `asset_version_id DESC` |
| 상세 소속 | URL의 Asset과 Version의 `asset_id` 일치 확인 |
| 상위 Version | 같은 Asset에 속한 Version만 허용 |
| 자동 생성·변경 | Artifact·Composition·ProjectAsset·Selection 자동 변경 없음 |
| 공개 입력 | `version_number`·`created_by`·내부 식별자 거부 |
| 공개 응답 | Lineage·설정 Metadata만 반환하고 `created_by` 비노출 |

기존 Repository·Service의 기본 오름차순·100개 제한 계약은 보존했다. REST 목록에서만 완전한 Asset 계보를 최신순으로 요청한다. 기존 `(asset_id, version_number)` Unique Constraint를 재사용하므로 신규 Index나 Alembic revision은 필요하지 않다.

## 3. 테스트

| 검증 | 결과 |
|---|---|
| AssetVersion API 신규 테스트 | PASS — 8개 |
| Asset·Repository·Service·Entity·Migration 인접 선별 회귀 | PASS |
| Workspace v1 Router·OpenAPI 계약 | PASS — 11개 |
| 중복 없이 집계한 선별 테스트 | PASS — 58개 |
| Python compile | PASS |
| 변경 Python 파일 Ruff lint | PASS |
| 변경 Python 파일 Ruff format check | PASS |
| `git diff --check` | PASS |

신규 테스트는 Version 생성·번호 증가·최신순 목록·상세 소속·불변 Method·내부 필드 거부·상위 Version 소속·충돌 rollback을 확인한다. 인접 회귀 묶음은 최초 실행에서 Router 기대값 한 곳을 발견했고 19개 Operation 계약으로 수정한 뒤 해당 Router·OpenAPI 테스트 11개를 재실행해 통과했다.

기존 Pipeline API 선별 묶음은 5분 제한 내 결과를 회수하지 못해 통과로 기록하지 않는다. 이 항목은 GitHub Actions의 `backend-ubuntu`, `ffmpeg-windows` 결과로 추가 확인한다.

## 4. Route·OpenAPI

| 항목 | 결과 |
|---|---:|
| 전체 등록 Route | 64 |
| 전체 `APIRoute` | 60 |
| OpenAPI path | 44 |
| OpenAPI operation | 62 |
| Workspace v1 Resource operation | 19 |

기존 Pipeline file Route의 OpenAPI operation ID 중복 2건은 이번 변경 이전부터 존재한 WARNING이며 이 작업에서 수정하지 않았다.

## 5. 판정

**PASS** — AssetVersion Resource API 3개가 기존 Entity·Repository·Service와 불변 계약을 유지하며 구현됐다. Resource API 진행도는 19/64다. Artifact 이하 45개 Endpoint와 운영 전환은 별도 작업이다.

## 6. WARNING

- 동시 Version 생성 충돌은 DB Unique Constraint와 `409 ASSET_VERSION_CONFLICT`로 안전하게 종료하지만, 높은 동시성 운영 정책은 실제 Bootstrap 이후 별도 부하 검증이 필요하다.
- Version 목록은 불변 계보 전체를 반환한다. 단일 Asset의 Version 수가 커지는 운영 단계에서는 별도 계약 변경으로 Cursor·상한 도입을 검토해야 한다.
- 기존 Pipeline file Route의 OpenAPI operation ID 중복 2건이 남아 있다.
- 전체 Backend suite, Frontend, 실제 DB, 외부 Provider·GPU·모델 통합은 이번 범위에서 실행하지 않았다.
