# Asset Cursor Pagination과 keyset Index 검증

> 상태: [완료]
> 검증일: 2026-08-08
> 기준 브랜치: `feature/asset-cursor-indexes`
> 기준 develop: `d06827c06a9c3f7f2af4eba2a80faf0fef1ba7e9`
> 실제 사용자 DB 접근: 미수행

## 1. 범위

Asset Resource API 구현 전에 공개 Owner scope, filter allowlist, HMAC Cursor, Repository·Service keyset page, Index 후보와 Alembic source revision을 검증했다. Asset Router 5개, 실제 Bootstrap·backfill·dual write·Frontend·Runtime과 실제 사용자 DB migration은 포함하지 않았다.

## 2. 확정 계약

- 공개 목록은 신뢰된 현재 Owner의 `deleted_at IS NULL` Asset만 조회한다.
- `workspace_id=<uuid>`와 `asset_type=<enum>`만 선택적 공개 filter로 허용한다.
- `owner_id`, `include_deleted`, `lifecycle_status`, 자유 검색과 임의 sort는 공개하지 않는다.
- 정렬은 `(created_at DESC, asset_id DESC)`다.
- Cursor version 1의 created-at payload를 `resource=asset`으로 확장하고 기존 Resource token 의미를 변경하지 않는다.
- fingerprint는 effective Owner, 선택적 Workspace·Asset type, `include_deleted=false`와 sort를 고정한다. 원문 filter는 token에 포함하지 않는다.

## 3. Query Plan

Alembic `20260807_0014` 임시 SQLite에 6,000개 Asset을 구성하고 공식 filter 조합의 첫·다음 page 8개 Query를 비교했다.

| 상태 | 결과 |
|---|---|
| Migration 전 | `ix_assets_deleted_at` 선택, 8개 모두 `USE TEMP B-TREE FOR ORDER BY` |
| full 후보 | Owner 또는 Owner+Workspace 후보 선택, 임시 B-Tree 0건, full scan 0건 |
| partial 후보 | 기존 `ix_assets_deleted_at` 선택, 임시 B-Tree 8건 |
| `20260808_0015` | 최종 full Index 선택, 임시 B-Tree 0건, 결과 row와 정렬 동일 |

최종 Index는 `ix_assets_owner_active_keyset`, `ix_assets_owner_workspace_active_keyset` 두 개다. `asset_type`은 residual filter로 처리해 추가 Index를 만들지 않았다.

## 4. Migration

- Chain: `20260807_0014 → 20260808_0015`
- Upgrade: Asset full keyset Index 2개 추가
- Downgrade: 신규 Index 2개만 역순 제거
- Application Table 35개, Runtime 14개, Workspace 21개 유지
- Asset row count와 deterministic digest 유지
- `quick_check=ok`, `integrity_check=ok`, `foreign_key_check=0`
- Entity metadata와 SQLite reflection의 Index 이름·Column 순서 일치

## 5. 테스트 결과

| 검증 | 결과 |
|---|---|
| Asset Cursor·Service 전용 테스트 | PASS |
| Asset keyset Query Plan·Migration round-trip 전용 테스트 | PASS |
| 신규 전용 테스트 합계 | 9 passed |
| Cursor·Repository·Service·Entity 회귀 | PASS — 88 passed |
| Workspace·Project·ProjectAsset API 회귀 | PASS — 50 passed |
| Alembic·keyset·Preflight·SQLite 안전성 회귀 | PASS — 21 passed |
| 중복 없이 합산한 선별 검증 | PASS — 159 passed |
| Python compile | PASS |
| Ruff lint | PASS |
| Ruff format check | PASS — Backend 267개 파일 |
| Alembic head | PASS — 단일 head `20260808_0015` |
| Route·OpenAPI | PASS — Route 56, APIRoute 52, path 40, operation 54, `/api/v1` Resource operation 11 |
| `git diff --check` | PASS |
| 변경 문서 상대 링크·Markdown fence | PASS |

신규 전용 테스트는 Cursor 서명·변조·Resource·filter mismatch, 엄격한 limit 검증, Owner·Workspace·Asset type scope, 동률 정렬, Soft Delete, page 사이 삽입·삭제, 6,000행 Query Plan, `0014 → 0015 → 0014` 임시 SQLite round-trip과 schema·data 무변경을 검증했다.

초기 병렬 회귀 실행은 시간 제한으로 결과를 회수하지 못했으나 잔여 임시 프로세스가 종료된 뒤 세 묶음으로 분리해 모두 재검증했다. Migration 기준선 테스트는 신규 source head와 Asset Index 두 개를 인식하도록 기대값만 갱신했다. 실제 사용자 DB나 외부 Provider는 사용하지 않았다.

## 6. 경계와 Warning

- 실제 사용자 DB revision은 계속 `20260807_0014`이며 source head `0015`는 미적용이다.
- Asset Resource API는 0/5, 전체 Resource API는 11/64다.
- 기존 단일 Index와 신규 복합 Index의 prefix 중복은 운영 통계를 확보한 뒤 별도 PR에서 검토한다.
- Python 3.12 SQLite 기본 datetime adapter 폐기 예정 경고를 유지한다.
- 인증이 아직 없으므로 향후 Router는 Bootstrap된 Workspace의 Owner context에서 effective Owner를 파생해야 한다.
- 전체 Backend suite는 실행하지 않았으며 선별 159개 회귀와 후속 GitHub Actions를 최종 Gate로 사용한다.
