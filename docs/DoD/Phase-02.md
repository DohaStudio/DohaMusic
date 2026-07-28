# Phase 2 Definition of Done — Music Generation

> 상태: [진행 중]
> 진행률: 14/15, 93%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-2-music-generation--진행-중), [Music Generation Adapter](../04-models/music-generation-adapter.md)

## 목표

공식 음악 생성 모델을 조사하고 `MusicGenerator` 계약을 유지한 실제 로컬 Provider와 Backend 경로를 검증한다.

## 구현 범위와 포함 기능

ACE-Step 공식 문서·라이선스 조사, 격리 runtime, Adapter·Provider Factory, 단독 추론, Backend Job 연결, WAV·성능 metadata, GPU 통합 테스트와 실험 보고서를 포함한다.

## 제외 기능

ACE-Step 제품 기본값 확정, Codex 청감 점수, Lyrics AI, Stem 이후 Pipeline, Frontend는 제외한다.

## 선행 조건

Phase 1 Backend Foundation과 RTX 3060 Ti 8GB 실행 환경이 필요하다.

## 완료 체크리스트

- [x] 후보 모델과 공식 문서 조사
- [x] 코드·가중치 라이선스 1차 확인
- [x] ACE-Step 버전·모델·설정 고정
- [x] 격리 runtime과 자동 다운로드 금지
- [x] `MusicGenerator` Adapter 구현
- [x] Provider Factory와 Mock 유지
- [x] 단독 instrumental·한국어 가창 추론
- [x] Backend 생성 Job E2E 연결
- [x] 시간·VRAM·WAV metadata 기록
- [x] 성공·오류·GPU opt-in 테스트
- [x] EXP-001과 관련 문서·CHANGELOG
- [x] ADR-005·ADR-006 검토·작성
- [x] 한국어 커밋·Push·PR
- [x] `develop` 병합과 `main` 무변경 확인
- [ ] EVAL-001 사용자 청취 평가 후 기본 Provider 채택 여부 확정

## 완료 조건

기술 구현뿐 아니라 EVAL-001의 한국어 발음·가사 정렬·음악성·잡음 판정과 ADR-006 상태 갱신이 필요하다. 현재 기본 Provider는 `mock`이다.

## 산출물

ACE-Step Adapter·runner·benchmark 입력·GPU 통합 테스트·EXP-001·EVAL-001.

## 관련 문서·ADR·실험

- 문서: [Model Comparison](../01-research/model-comparison.md), [GPU Strategy](../04-models/gpu-memory-strategy.md)
- ADR: [ADR-005](../11-decisions/ADR-005-ai-worker-dependency-isolation.md), [ADR-006](../11-decisions/ADR-006-ace-step-primary-provider.md)
- 실험: [EXP-001](../../reports/experiments/EXP-001-ace-step-local-inference.md), [EVAL-001](../../reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)

## 예상 다음 단계

EVAL-001 사용자 입력을 반영해 Phase 2 종료 여부와 ACE-Step Provider 상태를 결정한다.
