# 변경 이력

> 문서 목적: 사용자와 개발자에게 의미 있는 저장소 변경을 기록한다.
> 현재 상태: **운영 중**
> 최종 수정일: 2026-07-29

DohaMusic 프로젝트의 주요 변경 사항을 기록한다. 일반 작업은 `[Unreleased]`에 기록하고 프로젝트 버전 정책은 구현 단계에서 결정한다.

## [Unreleased]

### 추가

- ACE-Step 동일·다른 Seed, 상주 반복, 0.6B LM을 명시 실행하는 benchmark suite와 결과 집계·WAV sample 비교 도구를 추가했다.
- 실제 음원을 사용자가 직접 평가하는 EVAL-001과 재현성·안정성·운영 결정을 기록한 EXP-002를 추가했다.
- ACE-Step 기본 Provider 채택 보류 ADR-006과 Job별 subprocess 유지 ADR-007을 추가했다.
- ACE-Step 1.5 v0.1.8을 격리된 런타임에서 실행하는 선택적 Adapter, Provider Factory, 오류 체계를 추가했다.
- 단독 instrumental·한국어 가사 smoke 실행기, 고정 benchmark 입력, WAV 신호 분석기와 opt-in GPU 통합 테스트를 추가했다.
- RTX 3060 Ti 8GB 실측과 Backend 종단 간 연결 결과를 기록한 `EXP-001` 보고서를 추가했다.
- FastAPI Router·Service·Repository 계층과 교체 가능한 의존성으로 Backend Foundation을 구축했다.
- SQLite·SQLAlchemy·Alembic 기반 `generation_jobs`, `generated_files`, `voice_profiles` schema를 추가했다.
- Mock `MusicGenerator`, ThreadPool Worker, 로컬 Storage와 생성·조회·음성 프로필 API를 추가했다.
- 생성 성공·조회·Mock Worker 실패·입력 예외·음성 동의·migration·Storage를 검증하는 테스트를 추가했다.

### 변경

- 반복 실험 결과에 따라 현재 ACE-Step 운영 방식을 Job별 격리 subprocess로 확정하고 Mock 기본 Provider를 유지했다.
- 개발 단계를 Phase 2.5 기술 검증 완료·사용자 청취 평가 진행 중으로 갱신했다.
- `MusicGenerator` 결과 계약에 Provider·모델 버전·실제 Seed·추론 시간·최대 VRAM·메타데이터를 포함했다.
- Mock 전용 Worker를 Provider-neutral Worker로 확장하고 설정으로 `mock` 또는 `ace_step`을 선택하도록 변경했다.
- 개발 단계를 Phase 2 진행 중으로 갱신하고 기술 검증과 수동 청취 평가 상태를 분리했다.

### 수정

### 제거

### 보안

### 문서

- 동일 Seed PCM 재현성, 다른 Seed 파형 차이, 상주 CPU 메모리 증가, 0.6B LM 성능과 사용자 평가 상태를 관련 모델·아키텍처·운영 문서에 반영했다.
- ACE-Step 공식 출처·라이선스·격리 설치·저 VRAM 설정·성능·평가·오류·운영 문서와 ADR-005를 최신화했다.
- DohaMusic 초기 설계, 요구사항, 아키텍처, 데이터, API, 평가, 보안, 운영 문서 체계
- 단계별 계획과 실험 보고서 템플릿
- 저장소 전체에 적용되는 Codex Git 작업 지침과 문서 최신화·변경 이력 관리 규칙
- 장기 유지보수를 위한 구현 전 분석, 재사용, Adapter, 비동기 작업, 테스트·로그·성능 기록과 코드 품질 원칙
- README, Backend·Worker·Storage Architecture, API, ERD, 상태 모델과 로컬 운영 문서를 실제 Mock 구현에 맞게 갱신했다.
- ADR-002의 Adapter 경계와 ADR-003의 Phase 1 비동기 처리 결정을 구현 기준으로 검토·승인했다.
