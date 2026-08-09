# CompositionSnapshot 계약·Cursor 기반 검증

> 상태: [완료]
> 검증일: 2026-08-10
> 기준 브랜치: `feature/composition-snapshot-foundation`
> 기준 develop: `4173ec469ff2300323a840618501f41f46081c76`
> 관련 문서: [CompositionSnapshot 기반 계약](../../docs/06-api/composition-snapshot-foundation.md)

## 검증 범위

- effective Owner·Bootstrap·Project·Workspace·ProjectAsset scope
- 닫힌 Item role, 정수 sort order와 중복 방지
- 정확한 AssetVersion 고정과 불변 aggregate
- Project별 자동 version·유한 retry·원자적 rollback
- `composition_snapshot` HMAC Cursor와 keyset page
- 기존 `idempotency_records` 기반 replay·conflict·transaction
- Processing Chain, Provider·Model Manifest와 bounded JSON
- 6,000개 임시 SQLite Snapshot Query Plan
- 기존 Workspace Service·Repository·Cursor 회귀

## 결과

| 항목 | 결과 |
|---|---|
| Snapshot 기반·Workspace 회귀 | 72 passed |
| Query Plan | 1 passed |
| API surface·기존 Resource API 회귀 | 103 passed |
| Python compile | PASS |
| Ruff lint | PASS |
| Ruff format check | PASS |
| `git diff --check` | PASS |

API 회귀에서 FastAPI Route 67개, `APIRoute` 63개, OpenAPI Path 47개, Operation 65개와 Workspace v1 Resource Route 22개가 유지됐습니다. source metadata는 36개 Table, Alembic 단일 head는 `20260809_0016`입니다.

`backend/tests` 전체 일괄 실행은 약 3분 동안 결과를 반환하지 않아 중단했으며 통과로 표시하지 않습니다. 신규 계약·직접 회귀 73개와 API surface·기존 Resource API 103개는 독립 실행해 모두 통과했습니다. 기존 Pipeline HEAD operation ID 중복 경고 2종은 이번 범위에서 변경하지 않았습니다.

## Query Plan

임시 SQLite에 Project 하나당 6,000개 Snapshot과 Item을 구성했습니다. Project별 첫 page와 다음 page는 기존 `(project_id, snapshot_version)` Unique Index를 사용했고 `SCAN composition_snapshots`와 `USE TEMP B-TREE`가 없었습니다. Item aggregate 정렬도 기존 Snapshot·role·sort Unique Index를 사용해 TEMP B-TREE가 없었습니다. 전체 keyset 순회에서 중복과 누락은 0건입니다.

## 보안·운영 경계

- 실제 사용자 DB 접근: 0회
- 실제 Artifact 접근: 0회
- Alembic·Entity·Index 변경: 0건
- Router·OpenAPI operation 변경: 0건
- Dataset·모델·Checkpoint·개인 음성·미디어 추가: 0건
- 비밀정보와 Cursor 서명 키 출력: 0건

## 판정

CompositionSnapshot Router 구현을 시작할 수 있는 Application 기반은 PASS입니다. 공식 Endpoint는 0/3으로 유지하며, Router 단계에서 공개 DTO·공통 오류 매핑·`Idempotency-Key` header·App Factory 주입을 별도로 검증해야 합니다.
