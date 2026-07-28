# 개발 로드맵

> 문서 목적: 단계별 산출물, 완료 조건, 다음 단계 진입 조건을 정의한다.
> 현재 상태: **Phase 2.5 진행 중 — 반복 기술 검증 완료, 사용자 품질 평가 대기**

각 Phase는 앞 단계의 산출물과 검증 결과를 입력으로 삼는다. 일정은 모델 라이선스와 RTX 3060 Ti 8GB 실측 결과에 따라 조정한다.

## Phase 0. 프로젝트 설계 — [완료]

- 문서 구조와 요구사항 정의
- 모델 후보와 라이선스 조사 기준 수립
- 개발 환경, 데이터 및 동의 정책 정의
- 완료 조건: 문서 링크·범위·정책·ADR 검토 완료

## Phase 1. Backend Foundation — [완료]

- FastAPI Router·Service·Repository 계층
- SQLAlchemy·Alembic·SQLite 초기 schema
- Mock `MusicGenerator`와 비동기 ThreadPool Worker
- 생성 Job·결과 파일·음성 프로필 API
- 로컬 Storage, 환경 변수, 예외·로그, 자동 테스트
- 완료 조건: Mock Job 종단 간 실행, migration, API와 실패 경로 검증

## Phase 2. AI Adapter와 로컬 추론 검증 — [진행 중]

- [완료] `MusicGenerator` 계약을 유지한 ACE-Step Adapter·Provider Factory 구현
- [완료] ACE-Step 1.5 v0.1.8 2B Turbo 단독 추론과 Backend 종단 간 연결
- [완료] RTX 3060 Ti 8GB에서 시간·VRAM·WAV 신호 지표 측정
- [완료] 고정 instrumental·한국어 가사 입력과 재현용 실행기 추가
- [완료] 동일 Seed PCM 재현성·다른 Seed 파형 다양성 확인
- [완료] 상주 프로세스 6회 suite 2회, 총 12/12 기술 실행
- [완료] 0.6B LM의 8GB 실행 가능성과 성능 비교
- [완료] 현재 운영 수명을 Job별 격리 subprocess로 결정
- [진행 중] EVAL-001 사용자 청취 평가: 한국어 발음·가사 정렬·음악성·청감 잡음
- [검토 필요] 사용자 평가 후 ACE-Step 기본 Provider 채택 여부 재검토
- 완료 조건: 최소 한 후보의 재현 가능한 실험 보고서와 도입 판정

ACE-Step은 선택적 실험 Provider이며 제품 기본 모델로 채택하지 않았다. 기술 반복 게이트는 통과했지만 품질 게이트가 남아 있으므로 Phase 2 전체를 완료 처리하지 않는다. 근거는 [EXP-001](reports/experiments/EXP-001-ace-step-local-inference.md), [EXP-002](reports/experiments/EXP-002-ace-step-quality-and-stability.md), [EVAL-001](reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)을 따른다.

## Phase 3. 음색 변환 및 AI 파이프라인 — [계획]

- 본인 참조 음성 준비와 동의 기록
- 말하기/노래 음성 차이, 음질·음색 유사도·발음 보존 평가
- 완료 조건: 안전 정책을 충족하는 변환 후보와 실패 기준 확정

- 음악 생성 → 분리 → 변환 → 믹싱 → 인코딩 연결
- 단계별 오류 처리, 모델 순차 로드/해제
- 완료 조건: 단일 로컬 작업의 종단 간 재현과 산출물 기록

## Phase 4. API 확장 — [계획]

- 실제 모델 Adapter와 생성 API 연결
- 모델 상태, 재시도, 취소, 인증·접근 제어
- 외부 Queue와 객체 Storage 도입 여부 결정
- 완료 조건: [API 인수 기준](docs/02-requirements/acceptance-criteria.md) 충족

## Phase 5. 웹 MVP — [계획]

- 프롬프트·가사·참조 음성 입력
- 진행률, 재생, WAV 다운로드, 이력
- 완료 조건: 동의된 개인 음성으로 MVP 사용자 시나리오 통과

## Phase 6. 품질 개선 — [계획]

- 한국어 발음, 음색 유사도, 고음 안정성, 보컬/반주 균형, 속도 개선
- 완료 조건: 고정 벤치마크의 목표값 합의 및 회귀 기준 수립

## Phase 7. 개인화 학습 — [검증 필요]

- 개인 가창 데이터셋과 전처리 검토
- LoRA 또는 파인튜닝 실험, 전후 비교
- 전용 가창 모델 검토
- 진입 조건: 동의·삭제·라이선스·보안 영향 검토와 별도 ADR 승인

세부 계획은 [planning](planning/phase-01-research.md), 미확정 작업은 [백로그](planning/backlog.md)를 참고한다.
