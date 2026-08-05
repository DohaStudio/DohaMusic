# ADR-031 — Workspace 중심 REST API 계약

> 상태: [제안]
> 작성일: 2026-08-05
> 최종 수정일: 2026-08-05
> 관련 기능: DohaMusic Workspace REST API 재설계
> 관련 문서: [공통 계약](../06-api/workspace-rest-api-contract.md), [Endpoint 목록](../06-api/workspace-rest-api-endpoints.md), [Provider API](../06-api/provider-api-contract.md), [API 전환 전략](../06-api/api-contract-migration-strategy.md)
> 관련 PR: [추후 연결]

## 배경

현재 DohaMusic API는 Generation, Stem, Voice Conversion, Pipeline, Lyrics와 Voice Profile별 Endpoint를 제공합니다. 이 구조는 현재 구현을 정확히 반영하지만 결과 파일과 상태를 기능별 Job·File aggregate로 노출하고 Pipeline 실행을 제품의 중심으로 보이게 합니다.

DohaStudio Common Specification과 DohaMusic DB Redesign은 Workspace, Project, Asset, AssetVersion, Artifact, Composition Snapshot과 Job을 공통 경계로 정의합니다. Provider Runtime은 DohaMusic Orchestrator가 호출하고 Workspace client에 직접 노출하지 않습니다.

## 문제

기능별 Endpoint를 계속 확장하면 같은 작품의 Version·Selection·Snapshot·Artifact·Job을 일관된 계약으로 조회하기 어렵습니다. Asset와 실제 파일, Workspace Job과 Provider Job, Recording과 Enrollment가 섞일 수 있으며 새 Provider가 추가될 때 public API가 모델 내부 구조에 종속될 수 있습니다.

## 결정

DohaMusic의 목표 API를 `/api/v1` Workspace REST API로 설계합니다.

- 16개 API 그룹과 64개 Method·Path 조합을 계획합니다.
- Asset 생성은 Version을 자동 생성하지 않습니다.
- AssetVersion과 CompositionSnapshot은 POST로만 생성하고 PATCH·DELETE하지 않습니다.
- Selection은 Asset의 현재 Version 선택이며 Snapshot과 분리합니다.
- Job은 독립 비동기 실행 단위이며 다섯 공통 상태를 사용합니다.
- Retry는 새 Job을 생성합니다.
- Artifact API는 ID·checksum·권한 기반 Metadata와 content link를 제공하고 경로를 노출하지 않습니다.
- Recording은 작품 Asset, Take는 AssetVersion, Enrollment는 별도 Consent·Approval 과정으로 구분합니다.
- Workspace Job API와 Orchestrator 전용 Provider API를 분리합니다.
- cursor pagination, 공통 success/error response, Idempotency-Key와 path major versioning을 사용합니다.
- 현행 API는 단계적으로 전환하며 자동 redirect와 Big-bang 제거를 하지 않습니다.

## 선택 이유

- Workspace 작품 모델과 REST Resource 경계를 일치시킵니다.
- AI Provider를 교체해도 Workspace client 계약을 유지합니다.
- Version 불변성, Snapshot 재현성과 Artifact 경로 비노출을 API에서 강제할 수 있습니다.
- Job 취소·재시도·상태·오류를 기능별 중복 없이 통합합니다.
- Recording과 Enrollment의 권리·Consent 경계를 유지합니다.
- major version과 Idempotency 정책으로 client 호환성과 중복 mutation을 관리합니다.

## 대안

1. 현행 기능별 Endpoint를 계속 확장: 현재 구현과 가깝지만 공통 Workspace Resource와 Provider 독립성이 약해 선택하지 않습니다.
2. 하나의 Pipeline Endpoint와 큰 request/response JSON 유지: 부분 편집·재사용·Selection·Snapshot 표현이 어렵고 Pipeline이 결과를 소유하게 되어 선택하지 않습니다.
3. Provider Runtime Endpoint를 Frontend에 직접 노출: 권한·GPU admission·Selection·Artifact 등록을 우회하므로 금지합니다.
4. GraphQL로 전환: 유연한 조회 장점은 있으나 현재 FastAPI·OpenAPI 기반, 비동기 Job과 file transfer 계약을 먼저 안정화하는 범위에 비해 과도해 보류합니다.
5. 현행 API를 즉시 v1로 redirect: write 의미와 response가 달라 데이터 중복·호환성 위험이 있어 선택하지 않습니다.

## 장점과 단점

장점은 Resource·Version·Job·Provider 책임이 명확하고 새 모델·도메인 추가 시 public API 중복이 줄어드는 점입니다. 단점은 64개 Endpoint의 우선순위 조정, 목표 DB 선행, compatibility projection, Frontend 전환, OpenAPI와 권한·Idempotency 구현이 필요하다는 점입니다.

## 영향

이번 ADR은 문서만 추가합니다. 현재 FastAPI Router, Endpoint, DTO, OpenAPI JSON, SQLAlchemy, Alembic, Worker, Runtime, Provider와 테스트는 변경하지 않습니다. 현재 API 문서는 계속 실제 구현 기준이며 목표 v1 API는 모두 `[계획]`입니다.

Common Specification PR #2와 DB Redesign PR #52가 선행 의존성입니다. 두 계약이 변경되면 이 ADR을 구현 전에 갱신합니다.

## Migration

1. Common Specification과 DB Redesign을 확정합니다.
2. Endpoint·Schema·Error·Idempotency와 권한 계약을 승인합니다.
3. 현행 DB를 읽는 v1 projection으로 GET 동등성을 검증합니다.
4. 목표 DB 전환과 함께 v1 write를 Resource 순서대로 추가합니다.
5. Frontend를 전환하고 Legacy Endpoint에 Deprecation·Sunset을 알립니다.
6. 사용량·회귀·복구 검증 후 별도 PR에서 Legacy Router를 제거합니다.

세부 매핑과 Rollback은 [API 전환 전략](../06-api/api-contract-migration-strategy.md)을 따릅니다.

## 재검토 조건

- Common Specification 또는 DB Redesign Entity·관계가 변경될 때
- 인증·Owner·Workspace Role이 확정될 때
- Artifact Resolver와 object storage 접근 계약이 결정될 때
- Provider Runtime transport가 HTTP 외 방식으로 확정될 때
- Recording Take upload·Artifact 등록 계약이 확정될 때
- Approval·AssetRelation·ProcessingChain 공개 API 범위가 확정될 때
- 64개 Endpoint가 초기 구현 범위에 과도해 단계 분할이 필요할 때
- cursor pagination 또는 Idempotency 저장소가 운영 요구를 충족하지 못할 때
