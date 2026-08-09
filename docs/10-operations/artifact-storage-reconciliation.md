# Artifact Storage Reconciliation 운영 계약

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-10
> 관련 기능: Owner·retention read Gate와 local Artifact dry-run reconciliation
> 관련 문서: [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Trusted Ingestion](artifact-storage-ingestion.md), [ADR-032](../11-decisions/ADR-032-artifact-storage-resolver-integrity.md)

## 1. Application read Gate

`ArtifactApplicationService`는 공개 Router 아래에 연결될 내부 경계다. 현재 Router는 구현하지 않았으며 Service 호출자는 기존 Workspace API와 같은 trusted effective Owner를 전달해야 한다.

```text
Artifact
→ AssetVersion
→ Soft Delete되지 않은 Asset
→ Asset.owner_id == effective_owner_id
→ retention Gate
→ Resolver
→ 같은 descriptor의 size·전체 SHA-256
```

다른 Owner, 누락된 Artifact·AssetVersion·Asset과 Soft Delete된 Asset 계보는 모두 `ARTIFACT_NOT_FOUND`로 처리한다. 권한 확인 전에 Resolver나 filesystem을 조회하지 않는다.

## 2. Retention matrix

| 상태 | Metadata | Content | 내부 오류 |
|---|---:|---:|---|
| `active` | 허용 | integrity 검증 후 허용 | 없음 |
| `quarantined` | 허용 | 거부 | `ARTIFACT_QUARANTINED` |
| `expired` | 허용 | 거부 | `ARTIFACT_GONE` |
| `pending_delete` | 허용 | 거부 | `ARTIFACT_GONE` |
| `deleted` | 허용 | 거부 | `ARTIFACT_GONE` |
| 그 외 | 거부 | 거부 | `ARTIFACT_CONTENT_UNAVAILABLE` |

Metadata 조회는 전체 Payload checksum을 계산하지 않는다. Content read는 초기 안전 정책으로 매 요청 같은 열린 descriptor에서 전체 SHA-256과 크기를 검증하고 stream 위치를 처음으로 되돌린 뒤 전달한다. MIME은 Trusted Ingestion에서 확정된 Metadata를 사용하며 Payload 변조는 checksum이 탐지한다. 대용량 Artifact의 매 요청 전체 해시는 성능 WARNING이며 immutable identity·size·mtime에 결합된 검증 cache는 후속 검토 대상이다.

## 3. Dry-run reconciliation

`ArtifactReconciliationService.scan()`의 유일한 현재 모드는 `dry_run=True`다. `False`는 거부하며 DB row, retention, Catalog와 파일을 생성·수정·삭제하지 않는다.

Catalog는 `storage_location_id` UUID keyset과 제한된 batch로 읽는다. Filesystem은 설정으로 주입된 `lm`, `audio`, `vocal`, `music` root 아래 다음 namespace만 탐색한다.

| Domain | 탐색 namespace |
|---|---|
| `lm`, `audio`, `vocal` | `payloads/` |
| `music` | `mixes/`, `exports/`, `previews/`, `snapshots/`, `runs/` |
| 모든 domain | `.ingestion/`의 grace period를 넘은 pending 후보 |

전체 disk, root 밖, 운영 경로 자동 탐색은 하지 않는다. Directory stack은 symlink·junction·reparse point를 따라가지 않고 regular file만 Catalog와 대조한다.

## 4. Issue 분류

| Issue | 의미 | 자동 조치 |
|---|---|---|
| `missing_payload` | Artifact·Catalog는 있으나 Payload 없음 | 없음 |
| `unreferenced_payload` | 승인 namespace의 파일에 Catalog locator 없음 | 없음 |
| `size_mismatch` | 실제 크기와 Artifact Metadata 불일치 | 없음 |
| `checksum_mismatch` | 실제 SHA-256과 Artifact Metadata 불일치 | 없음 |
| `invalid_locator` | backend·domain·key·version 또는 Resolver 계약 위반 | 없음 |
| `catalog_without_artifact` | FK drift로 Catalog의 Artifact가 없음 | 없음 |
| `pending_payload` | grace period를 넘긴 `.pending` 후보 | 없음 |
| `unsafe_filesystem_entry` | link·reparse·비정규 파일 또는 stat 실패 | 없음 |

Issue에는 선택적 Artifact ID, 승인 domain, 안전한 logical storage key와 reason code만 포함한다. 절대 경로·root·Payload 내용·checksum 실제값은 포함하지 않는다. 잘못된 Catalog key는 결과에 원문을 남기지 않는다.

## 5. Memory와 결과 상한

Catalog는 batch 처리하며 filesystem locator는 파일별로 조회해 전체 Catalog key를 메모리에 적재하지 않는다. Issue count는 전체를 집계하지만 상세 issue tuple은 설정된 `max_issues`까지만 보존하고 초과 시 `issues_truncated=true`로 표시한다.

## 6. 미구현과 운영 제한

- destructive repair, 파일 삭제, Catalog 재생성, retention 자동 전이
- 영속 reconciliation queue·scheduler·재시도
- Artifact Metadata·content·download Router와 HTTP Range
- content checksum 검증 cache
- local 이외 Storage backend
- 실제 사용자 DB와 실제 `DohaArtifacts` Inventory·scan

운영 자원에 scanner를 연결하거나 repair를 추가하려면 별도 read-only Inventory, backup, dry-run 결과 검토와 사용자 승인이 필요하다.
