# Workspace Job Foundation 계약 검증

> 검증 상태: PASS — 문서 계약 기준
> 검증일: 2026-08-10
> 기준 commit: `5ed3c67452f7c62dab5bbdf344446bccee5aa165`
> 실제 구현 상태: Job Migration·Cursor·Worker·API 미구현

## 검증 범위

- DohaStudio Common Specification `0.1.0` / `draft-baseline`
- Workspace Job Entity·Repository·Service와 Legacy Runtime Worker·Pipeline
- Workspace REST·Provider·Artifact·CompositionSnapshot 계약
- Job state, input/output lineage, cancellation, retry, idempotency와 completion 경계
- HMAC Cursor와 SQLite keyset Index 선행 조건

## 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| Legacy와 Workspace Job 분리 | PASS | Legacy Table·Worker 완료 상태를 Workspace API 완료로 사용하지 않음 |
| 공개 상태 | PASS | 공통 5-state 유지, cancel 요청은 내부 marker로 분리 |
| Job type Matrix | PASS | 현재 제품 근거가 있는 7개 type만 채택 |
| exact input | PASS | role + Artifact ID, 자동 Artifact 선택 금지 |
| output lineage | PASS | role + canonical Artifact, AssetVersion 역참조 |
| retry·idempotency | PASS | 새 Job lineage, 기존 idempotency record 재사용 |
| Provider 경계 | PASS | Provider success와 Workspace success 분리 |
| completion UoW | PASS | publish 후 단일 DB transaction과 보상·quarantine 계약 |
| Worker 안전성 | PASS | atomic claim·lease·heartbeat·crash failure 계약 |
| Owner·Collection | PASS | direct Workspace scope와 제한된 filter·HMAC Cursor 요구 |
| Common Specification | PASS | 공통 명세보다 엄격하며 근본 충돌 없음 |

## Query Plan 근거

현재 Index를 모사한 임시 SQLite 6,000 Job fixture에서 Workspace·Project·status·job type 목록이 `TEMP B-TREE`를 사용했다. 따라서 공식 API 구현 전에 tie-breaker `job_id`를 포함한 Workspace-scoped keyset Index Migration과 fixture `EXPLAIN QUERY PLAN` 비교가 필요하다. 실제 사용자 DB에는 접근하지 않았다.

## 현재 상태

- Job Contract: [완료]
- Job Entity Migration: [미구현]
- Job Cursor·Index: [미구현]
- Job Service Foundation: [미구현]
- Worker claim·lease: [미구현]
- Job API: 0/5
- Resource API: 25/64
- Backend Foundation: [진행 중]
- Generative AI Track: OPEN 아님

## 수행하지 않은 작업

Python·Entity·Repository·Service·Cursor·Alembic·실제 DB·Artifact·Provider·Worker·Router·Frontend·Bootstrap·backfill·dual write·Runtime 전환은 수행하지 않았다.
