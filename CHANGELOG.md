# 변경 이력

> 문서 목적: 사용자와 개발자에게 의미 있는 저장소 변경을 기록한다.
> 현재 상태: **운영 중**
> 최종 수정일: 2026-07-29

DohaMusic 프로젝트의 주요 변경 사항을 기록한다. 일반 작업은 `[Unreleased]`에 기록하고 프로젝트 버전 정책은 구현 단계에서 결정한다.

## [Unreleased]

### 추가

- FastAPI Router·Service·Repository 계층과 교체 가능한 의존성으로 Backend Foundation을 구축했다.
- SQLite·SQLAlchemy·Alembic 기반 `generation_jobs`, `generated_files`, `voice_profiles` schema를 추가했다.
- Mock `MusicGenerator`, ThreadPool Worker, 로컬 Storage와 생성·조회·음성 프로필 API를 추가했다.
- 생성 성공·조회·Mock Worker 실패·입력 예외·음성 동의·migration·Storage를 검증하는 테스트를 추가했다.

### 변경

- 개발 단계를 Phase 1 Backend Foundation 완료, Phase 2 AI Adapter·로컬 추론 계획으로 갱신했다.

### 수정

### 제거

### 보안

### 문서

- DohaMusic 초기 설계, 요구사항, 아키텍처, 데이터, API, 평가, 보안, 운영 문서 체계
- 단계별 계획과 실험 보고서 템플릿
- 저장소 전체에 적용되는 Codex Git 작업 지침과 문서 최신화·변경 이력 관리 규칙
- 장기 유지보수를 위한 구현 전 분석, 재사용, Adapter, 비동기 작업, 테스트·로그·성능 기록과 코드 품질 원칙
- README, Backend·Worker·Storage Architecture, API, ERD, 상태 모델과 로컬 운영 문서를 실제 Mock 구현에 맞게 갱신했다.
- ADR-002의 Adapter 경계와 ADR-003의 Phase 1 비동기 처리 결정을 구현 기준으로 검토·승인했다.
