# Workspace Job Completion Unit of Work 검증

> 문서 상태: [완료]
> 검증일: 2026-08-11
> 기준 브랜치: `feature/job-completion-uow`
> 기준 revision: `20260810_0017`

## 검증 범위

- bounded `ProviderResult`·`ProviderOutput` DTO와 secret·raw response 배제
- 공식 7개 Job type별 output role·Artifact kind·storage domain Matrix
- running·Owner·Workspace·claim token 위치와 cancel marker 우선
- trusted ingestion prepare·register·full SHA-256 verify·compensate 재사용
- 새 AssetVersion과 Artifact·Catalog·JobOutput·ModelUsage 단일 transaction
- 동일 결과 replay, 다른 결과 conflict와 terminal 불변성
- 다중 output, MIME·publish·DB·lineage·최종 integrity failure rollback
- publish 뒤 DB commit 실패의 identity 기반 filesystem 보상
- retry Job 자체 lineage와 원본 Job 불변, ProjectAsset 자동 변경 금지

## 결과

| 항목 | 결과 |
|---|---|
| 신규 Completion UoW 테스트 | 14 passed |
| Job Service·Cursor·Schema 회귀 | 20 passed |
| Artifact trusted ingestion 회귀 | 37 passed, Windows symlink 1 skipped |
| Artifact 접근·AssetVersion·CompositionSnapshot·API Foundation 회귀 | 106 passed |
| Python compile | PASS |
| Ruff lint·format | PASS |
| Metadata | 36개 Table 유지 |
| Alembic | `20260810_0017`, 신규 revision 없음 |
| API surface | 변경 없음, Job API 0/5·Resource API 25/64 |
| 실제 사용자 DB·DohaArtifacts·Provider 접근 | 미수행 |

OpenAPI 생성 과정에서는 기존 Pipeline file route의 중복 operation ID 경고 2종이 유지됐다. 이번 Completion UoW와 무관한 기존 경고이며 새 API route는 추가하지 않았다. Windows symlink 회귀 1개는 현재 실행 환경에서 권한이 없어 skip됐고 나머지 containment·identity 검증은 통과했다.

## Transaction과 filesystem

기존 `ArtifactIngestionService.ingest()`는 독립 transaction을 유지한다. 새 Completion Service는 같은 ingestion의 prepare·register·verify·compensate primitive를 상위 Service transaction에서 사용하므로 nested commit이 없다. AssetVersion은 commitless Repository로 생성한다. DB rollback 또는 commit 실패 시 이번 completion이 publish한 inode만 identity를 확인해 제거하고 staging payload도 같은 root containment·identity 경계로 정리한다. 정리에 실패하면 절대 경로 없는 reconciliation warning을 남긴다.

## 남은 범위

- Worker atomic claim·lease·heartbeat와 crash recovery
- 실제 Provider dispatch와 실행 loop
- 공개 Job Router/API 5개
- durable History event 강화와 nullable role backfill

따라서 Completion UoW 기반은 완료했지만 Backend Foundation과 Generative AI Track은 아직 완료 또는 OPEN 상태가 아니다.
