# Artifact 접근 제어와 Reconciliation 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: Owner scope, retention·integrity read Gate, local dry-run reconciliation
> 관련 문서: [Artifact Storage 계약](../../docs/03-architecture/artifact-storage-contract.md), [Reconciliation 운영 계약](../../docs/10-operations/artifact-storage-reconciliation.md), [ADR-032](../../docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)

## 1. 검증 범위

이번 검증은 `ArtifactApplicationService`와 `ArtifactReconciliationService`의 내부 경계를 대상으로 한다. 공개 Router·HTTP Range·destructive repair, 실제 사용자 DB와 실제 `DohaArtifacts`는 범위에서 제외했다.

## 2. Owner·retention·integrity

| 항목 | 결과 | 확인 내용 |
|---|---|---|
| Owner lineage | PASS | `Artifact → AssetVersion → Soft Delete되지 않은 Asset → owner_id` inner join |
| Cross-owner | PASS | 다른 Owner와 누락·손상 계보는 `ARTIFACT_NOT_FOUND`로 통합 |
| Metadata matrix | PASS | 공식 retention 5개 상태의 Metadata 허용 |
| Content matrix | PASS | `active`만 허용, `quarantined`·gone·unknown 상태 fail-closed |
| Resolver 순서 | PASS | Owner와 retention 확인 뒤에만 Catalog·filesystem 조회 |
| Integrity | PASS | 같은 열린 descriptor의 실제 크기와 전체 SHA-256 검증 |
| MIME read | PASS | Ingestion authoritative Metadata 사용, 재-sniff하지 않음 |
| 결과·오류 | PASS | 절대 경로·root·Payload·실제 checksum 비노출 |

초기 안전 정책은 content read마다 전체 SHA-256을 계산한다. 대용량 Artifact 비용은 WARNING이며 검증 cache는 이번 범위에서 구현하지 않았다.

## 3. Dry-run reconciliation

| 항목 | 결과 | 확인 내용 |
|---|---|---|
| 기본 모드 | PASS | `dry_run=True`만 허용, destructive mode 거부 |
| Catalog batch | PASS | UUID keyset과 제한된 batch 사용 |
| Filesystem scope | PASS | 승인된 네 domain과 namespace만 탐색 |
| Link 방어 | PASS | symlink·reparse 판정 재사용, unsafe directory 미추적 |
| DB-only | PASS | `missing_payload` 분류 |
| FS-only | PASS | `unreferenced_payload` 분류 |
| Integrity drift | PASS | size·checksum mismatch 분리 |
| Catalog drift | PASS | unsupported locator와 FK drift 분류 |
| Pending | PASS | 주입된 grace period를 넘긴 후보만 보고 |
| Path 비노출 | PASS | 잘못된 key는 보고서에서 제거 |
| Mutation | PASS | commit·rollback·파일 삭제·retention 변경 0건 |
| Memory | PASS | Catalog batch, 파일별 locator 조회, 상세 issue 상한 |

## 4. 테스트 결과

| 범위 | 결과 |
|---|---|
| 신규 Owner·retention·integrity·reconciliation | 36 passed |
| Trusted Ingestion·Resolver·Catalog·Workspace·Migration 선별 회귀 | 172 passed, 3 skipped |
| 중복 없는 선별 합계 | 208 passed, 3 skipped |

Skip 3건은 Windows에서 실제 symlink fixture 생성 권한이 없는 경로다. 이는 PASS로 집계하지 않았고 reparse fail-closed simulation을 별도로 검증했다. 기존 Pipeline HEAD route의 OpenAPI operation ID 중복 경고 2종이 두 테스트에서 반복돼 4 warnings가 발생했다.

전체 Backend suite, GPU·모델·외부 Provider·유료 API·실제 DB·실제 Artifact root 검증은 실행하지 않았다.

## 5. 정적·구조 Gate

| 항목 | 결과 |
|---|---|
| Python compile | PASS |
| Ruff lint·format | PASS |
| `git diff --check` | PASS |
| Metadata | 36 Tables 유지 |
| Alembic | `20260809_0016`, 신규 revision 없음 |
| API surface | Route 64, APIRoute 60, Path 44, Operation 62 유지 |
| Resource API | 19/64, Artifact API 0/3 유지 |
| 실제 사용자 자원 | 접근·변경 없음 |

## 6. 판정

- BLOCKER: 0건
- 최종 판정: PASS
- 후속 작업: Artifact API 3개와 Range 전에 effective Owner 주입·HTTP 오류 매핑·delivery allowlist를 연결하고, destructive reconciliation은 별도 승인형 maintenance로 분리
