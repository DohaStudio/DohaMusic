# ADR-034 — DohaVocal Consumer Contract Foundation

> 상태: [승인]
> 작성일: 2026-08-19
> 최종 수정일: 2026-08-19
> 관련 기능: DohaMusic에서 DohaVocal Runtime 계약 소비
> 관련 문서: [Consumer Contract](../03-architecture/dohavocal-consumer-contract.md), [ADR-028](ADR-028-provider-runtime-artifact-contract.md), [ADR-033](ADR-033-workspace-job-execution-boundary.md)
> 관련 PR: 이 결정을 구현하는 `develop` 대상 Draft PR

## 배경

DohaVocal `develop`에는 4개 Vocal capability와 9개 Provider operation을 제공하는 single-process in-memory Fake Runtime Foundation이 있다. DohaMusic에는 Workspace Job·Artifact·Owner authority와 fake `ProviderDispatcher` port가 있지만 DohaVocal JSON 계약을 독립적으로 decode하고 검증하는 consumer는 없었다.

## 문제

DohaVocal package, DB 또는 in-memory store를 직접 import하면 저장소·Runtime 경계가 무너진다. 반대로 실제 HTTP transport·Worker polling·Artifact persistence를 한 번에 도입하면 authorization, idempotency, 상태, 계보와 transaction 변경이 결합된다. Fake metadata checksum을 payload checksum으로 해석하거나 Provider output ID를 곧바로 Workspace AssetVersion으로 저장하는 것도 권위 경계를 위반한다.

## 결정

1. `VocalProviderClient`와 `VocalProviderTransport` port를 내부 consumer 경계로 둔다.
2. DohaVocal `0.1.0` JSON surface를 strict DTO로 decode하고 extra·unknown capability·contract drift를 fail-closed 한다.
3. Owner·Workspace·Project 권한은 DohaMusic Service가 먼저 해소하고 mapping은 effective owner만 `requested_by`로 전달한다.
4. capability별 `job_input`은 DohaVocal extension으로 유지하고 조직 전체 capability registry를 만들지 않는다.
5. Provider의 5-state, 새 Job retry, idempotency scope, root/parent/processing chain을 의미 변경 없이 보존한다.
6. Provider 결과는 `VocalProviderResultCandidate`로만 표현하며 AssetVersion·Artifact persistence나 선택을 수행하지 않는다.
7. Fake checksum은 metadata descriptor, Fake Manifest checksum은 fake manifest descriptor로 보존하고 payload/model 무결성으로 승격하지 않는다.
8. `REVIEW_REQUIRED`, `null VRAM`과 Consent caller-verified 요구를 그대로 보존한다.
9. Provider application error와 transport·timeout·invalid response·version mismatch를 구분하되 raw body와 내부 예외는 노출하지 않는다.
10. 첫 검증은 stable JSON fixture와 fake transport만 사용하고 실제 network·localhost·audio·AI·GPU를 사용하지 않는다.
11. 기존 Workspace Job Worker, 공개 API, DB Entity·Alembic과 기존 Seed-VC 호환 경로는 변경하지 않는다.

## Idempotency 위치 결정

DohaVocal `0.1.0` request schema는 body `idempotency_key`가 필수다. `.github` 공통 명세는 이를 공통 요청 metadata로 정의하지만 HTTP header/body 위치를 고정하지 않는다. 따라서 이 adapter는 실제 Provider schema를 따라 body에 전달한다. DohaMusic의 과거 header-only 목표는 범용 장기 목표로 남기지 않고, Provider별 versioned schema와 일치하는 transport mapping을 사용한다.

## 선택 이유

- 실제 Provider와 consumer를 독립 배포하면서도 JSON drift를 조기에 검출한다.
- Workspace 권한·Artifact commit·Worker 실행 변경을 첫 계약 PR에서 분리한다.
- production transport 없이 request/response 의미와 보안 경계를 반복 검증할 수 있다.
- 실제 payload가 없는 Foundation을 운영 Vocal integration 완료로 오인하지 않는다.

## 대안

1. DohaVocal Python package 직접 import: 저장소 release와 process 경계를 결합하므로 선택하지 않는다.
2. 실제 localhost server를 contract test 필수 조건으로 사용: network·process 상태에 테스트가 종속되므로 선택하지 않는다.
3. Provider result를 즉시 Workspace AssetVersion으로 commit: payload·Catalog·권한 transaction이 준비되지 않아 선택하지 않는다.
4. 기존 Seed-VC `VoiceConverter`를 DohaVocal Runtime으로 교체: 운영 승격·rollback 근거가 없어 선택하지 않는다.
5. 전체 organization Provider registry 설계: 첫 Vocal consumer 범위를 넘으므로 선택하지 않는다.

## 영향

내부 Python package와 contract test, 문서만 추가한다. 공개 Route·OpenAPI operation, DB schema, Alembic revision, 실제 사용자 DB, Artifact Catalog와 Frontend는 변하지 않는다. DohaVocal Runtime Foundation과 Consumer Contract Foundation은 구현되지만 Production Vocal Integration, 실제 Voice Conversion·Singing Voice와 audio payload 처리는 완료가 아니다.

## 후속 작업

1. 인증·deadline·connection policy를 승인한 실제 transport adapter
2. Workspace Job `ProviderDispatcher` 조립과 bounded polling/cancel/heartbeat
3. Provider candidate를 검증·ingestion·AssetVersion commit하는 Completion UoW 확장
4. production multi-process persistence와 idempotency
5. 실제 Vocal model adapter의 별도 품질·권리·GPU Gate

## 재검토 조건

- DohaVocal contract version 또는 endpoint가 변경될 때
- 실제 HTTP/subprocess transport를 선택할 때
- payload Artifact와 Workspace AssetVersion을 commit할 때
- Workspace Worker에 Vocal dispatcher를 등록할 때
- Model Manifest 공통 schema가 새 version으로 확정될 때
