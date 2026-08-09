# ADR-032 — Artifact Storage Resolver와 무결성 경계

> 상태: 승인
> 작성일: 2026-08-08
> 최종 수정일: 2026-08-09
> 관련 기능: Artifact Catalog, Storage Resolver, ingestion과 안전한 content·download
> 관련 문서: [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Workspace Artifact 모델](../03-architecture/workspace-artifact-model.md), [Workspace REST API 계약](../06-api/workspace-rest-api-contract.md), [ADR-029](ADR-029-dohamusic-workspace-artifact-domain.md), [ADR-031](ADR-031-workspace-rest-api-contract.md)

## 배경

Workspace `Artifact` Entity는 `asset_version_id`, kind, MIME, size, checksum과 retention Metadata를 저장하지만 물리 경로와 storage key는 저장하지 않는다. 이 경계는 환경 독립성과 경로 비노출에는 적합하지만 현재 Legacy `StorageService`는 Artifact ID를 Payload로 해석하지 못하고 `AssetService.register_artifact()`도 호출자가 제출한 Metadata 형식만 확인한다.

공식 Artifact API는 Metadata뿐 아니라 inline content와 download를 포함한다. Resolver와 실제 bytes 검증 없이 API부터 구현하면 임의 파일 읽기, checksum spoofing, owner 우회와 손상 Payload 제공 위험이 생긴다.

## 결정

1. Artifact Entity는 경로 없는 논리·무결성 Metadata로 유지한다.
2. 내부 전용 `artifact_storage_locations` DB Table을 Artifact ID와 물리 locator 사이의 authoritative Catalog로 채택한다.
3. Catalog는 Artifact와 1:1이며 backend, domain, canonical root-relative storage key와 locator version을 저장한다.
4. 내부 URI는 `artifact://<artifact_id>`로 고정하고 공개 응답은 Artifact API link를 사용한다.
5. 공개 Artifact POST·PATCH·DELETE·Collection을 제공하지 않는다.
6. Provider·Worker·Import 결과는 trusted ingestion을 통해 실제 bytes의 SHA-256, size와 kind별 media type을 검증한 뒤 불변 위치에 publish한다.
7. Artifact와 Catalog row는 같은 DB transaction에 등록하되 Payload를 먼저 exclusive publish한다. transaction 실패 또는 crash orphan은 grace period 후 reconciliation하며 자동 overwrite하지 않는다.
8. 공개 권한은 `Artifact → AssetVersion → Asset → owner_id`로 파생하고 공개 owner 입력을 금지한다.
9. content·download는 owner, retention, delivery allowlist, root containment, symlink·reparse point, regular file, size와 checksum을 검증한다.
10. single byte range만 지원하고 multiple range는 초기 범위에서 제외한다.
11. Payload overwrite와 locator의 무감사 교체를 금지한다. 변경된 Payload는 새 Artifact이며 논리 계보가 달라지면 새 AssetVersion도 생성한다.
12. 물리 삭제는 공개 DELETE가 아니라 retention과 GC·maintenance로 분리한다.

## 선택 이유

별도 DB Catalog는 Workspace DB의 논리 Artifact가 경로를 소유하지 않는 원칙을 지키면서도 root·domain·backend 이동을 표현할 수 있다. Artifact와 locator를 같은 transaction으로 관리할 수 있어 Manifest 파일이나 암묵적 deterministic path보다 backup, 권한, drift 탐지와 테스트가 명확하다.

## 대안

1. Artifact Table에 `storage_key` 추가: 논리·물리 책임이 다시 결합되고 다중 backend와 relocation 이력이 약해 제외한다.
2. Catalog JSON·Manifest 파일: DB와 파일의 crash consistency와 동시성 관리가 어려워 제외한다.
3. Artifact ID만으로 path를 계산: 단순하지만 domain·backend·Provider 수명주기와 relocation을 표현하지 못해 제외한다.
4. Legacy Runtime 상대 경로 재사용: 단계적 전환과 경로 비노출 목표에 맞지 않아 제외한다.

## 장점과 단점

장점은 경로 비노출, owner·retention 중앙화, 실제 bytes 무결성, local·object storage 확장과 독립적인 relocation이다. 단점은 신규 Catalog Table·Migration, filesystem과 DB 사이 orphan reconciliation, 대용량 Payload의 checksum 비용과 OS별 symlink 방어가 추가되는 점이다.

## 영향

- `ArtifactStorageLocation` Entity와 additive revision `20260809_0016`을 구현하고 별도 Gate를 거쳐 실제 사용자 DB에 적용했다. Catalog row는 0개이며 Resolver 구현은 별도 Gate가 필요하다.
- Artifact Repository·Service·Router와 현재 Alembic head는 이번 ADR에서 변경하지 않는다.
- Legacy `AUDIO_STORAGE_ROOT`, Runtime Table 14개와 기존 Pipeline은 source of truth를 유지한다.
- Resource API는 19/64, Artifact API는 0/3을 유지한다.
- Provider는 Workspace DB나 final Artifact root에 직접 쓰지 않고 임시 결과를 DohaMusic ingestion 경계에 전달한다.

## 마이그레이션

1. `[완료]` Catalog Entity·source Migration을 추가하고 기존 35개 Table을 변경하지 않는 additive upgrade·downgrade를 임시 SQLite에서 검증한다.
2. `[완료]` 실제 사용자 DB에 대해 read-only Inventory, backup·restore와 migration rehearsal을 수행하고 별도 승인 후 적용한다.
3. canonical storage key validator, Resolver와 trusted ingestion을 임시 root에서 검증한다.
4. Metadata·content·download API를 연결한다.
5. 신규 결과부터 Catalog를 사용하고 Legacy 결과는 checksum·backup·rollback Gate 후 선택적으로 backfill한다.
6. 모든 소비자가 전환되기 전 Legacy 경로나 파일을 삭제하지 않는다.

## 재검토 조건

- object storage와 서명 URL을 도입할 때
- 하나의 Artifact에 replica·tiered storage가 필요할 때
- relocation과 key rotation 감사 모델이 필요할 때
- 대용량 checksum 검증 cache가 운영 요구를 충족하지 못할 때
- 다중 사용자 Role·공유 Workspace 권한을 도입할 때

## 관련 PR

- 이 ADR을 추가하는 `develop` 대상 문서 PR
