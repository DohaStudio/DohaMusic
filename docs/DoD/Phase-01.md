# Phase 1 Definition of Done — Legacy Backend Foundation

> 상태: [완료]
> 진행률: 15/15, 100%
> 최종 수정일: 2026-08-10
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-1-legacy-backend-foundation--완료), [Backend Architecture](../03-architecture/backend-architecture.md), [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md)

## 목표

실제 AI 모델 없이도 API·DB·비동기 Job·Storage 경계를 검증할 수 있는 Backend Foundation을 구축한다.

이 완료 판정은 `generation_jobs`와 기존 Mock Worker를 사용하는 Legacy Runtime 범위다. Workspace `jobs` Aggregate의 Migration·Cursor·claim/lease·completion Unit of Work와 공식 API 5개는 별도 Foundation Gate이며 아직 미완료다.

## 구현 범위와 포함 기능

FastAPI Router·Dependency·Config·Logging·Exception Handler, SQLite·SQLAlchemy·Alembic, Repository Pattern, generation Job·generated file·voice profile, Mock `MusicGenerator`, ThreadPool Worker와 테스트를 포함한다.

## 제외 기능

실제 AI, 인증, Frontend, Redis·Celery·RabbitMQ, Docker 최적화는 제외한다.

## 선행 조건

Phase 0의 요구사항·아키텍처·문서 정책이 확정되어야 한다.

## 완료 체크리스트

- [x] FastAPI 앱과 Router·Dependency 구성
- [x] Config·Logging·공통 Exception Handler
- [x] SQLite·SQLAlchemy 설정
- [x] Alembic 초기 migration
- [x] `generation_jobs`, `generated_files`, `voice_profiles`
- [x] Repository·Service·Worker 계층
- [x] Mock `MusicGenerator`와 샘플 WAV
- [x] 생성·조회·파일·음성 프로필 API
- [x] 성공·실패·입력 예외·회귀 테스트
- [x] Storage 안전 경로와 초기 디렉터리 검증
- [x] README·ROADMAP·API·ERD·Architecture 최신화
- [x] CHANGELOG 기록과 ADR 검토
- [x] 한국어 커밋과 원격 Push
- [x] `develop` 대상 PR과 병합
- [x] 병합 후 검증 및 `main` 무변경 확인

## 완료 조건

위 15개 항목이 모두 확인되고 Mock 생성 요청이 파일 조회까지 종단 간 완료되어야 한다.

## 산출물

`backend/`, 초기 Alembic schema, Mock Worker, 로컬 Storage, Backend 테스트와 관련 문서.

## 관련 문서·ADR·실험

- 문서: [API 개요](../06-api/api-overview.md), [ERD](../07-database/erd.md), [Worker Architecture](../03-architecture/worker-architecture.md)
- ADR: [ADR-002](../11-decisions/ADR-002-modular-ai-pipeline.md), [ADR-003](../11-decisions/ADR-003-async-job-processing.md)
- 실험 보고서: 실제 AI 실험 없음

## 예상 다음 단계

Phase 2 `MusicGenerator` 실제 Provider와 로컬 추론 검증.
