# Phase 5 Definition of Done — Pipeline Integration

> 상태: [완료]
> 진행률: 15/15, 100%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-5-pipeline-integration--계획), [AI Pipeline](../03-architecture/ai-pipeline.md)

## 목표

Music → Stem → Voice → Mixer를 하나의 추적 가능한 비동기 작업으로 연결한다.

## 구현 범위와 포함 기능

Pipeline 오케스트레이션, Mixer, 통합 API·Worker·상태·파일, 단계별 오류·재시도 경계, Benchmark와 통합 테스트를 포함한다.

## 제외 기능

Lyrics AI, Frontend, Production Queue·DB·Storage 전환은 제외한다.

## 선행 조건

Phase 2·3·4의 Provider 인터페이스를 재사용한다. Voice 운영 품질 게이트는 미충족이므로 사용자 지시에 따라 `MockVoiceConverter`만 사용한다.

## 완료 체크리스트

- [x] Music 단계 연결
- [x] Stem 단계 연결
- [x] Voice 단계 연결
- [x] Default/Mock Mixer와 실제 48kHz Stereo PCM16 출력 계약
- [x] gain·headroom·peak normalization·soft limiter·fade·품질 metadata
- [x] Pipeline API·Service
- [x] 비동기 Worker·단계 상태
- [x] 단계 실패·정리·재시도 정책
- [x] DB·ERD·Storage 변경
- [x] E2E Benchmark와 자원 기록
- [x] 성공·실패·회귀 통합 테스트
- [x] API·Architecture·Operations 문서
- [x] Pipeline ADR·실험 보고서
- [x] CHANGELOG·README·ROADMAP·Master·DoD 갱신
- [x] 한국어 커밋·Push·`develop` PR·병합
- [x] 병합 후 검증과 `main` 무변경

## 완료 조건

고정 Mock AI 입력 한 건이 모든 단계를 통과하고 각 단계 실패가 안전한 상태·파일 정리로 귀결돼 완료했다. Phase 5.1에서 실제 Mixer의 합성·format·headroom·clipping 자동 검증을 완료했다. 실제 AI와 Mixer 청감 품질은 EVAL 사용자 게이트다.

## 산출물

Pipeline Service·Worker·API·Mixer, schema·문서·ADR·통합 실험 보고서.

## 관련 문서·ADR·실험

- 문서: [Worker Architecture](../03-architecture/worker-architecture.md), [Job State](../07-database/job-state-model.md)
- ADR·실험: [ADR-012](../11-decisions/ADR-012-pipeline-orchestrator.md), [ADR-013](../11-decisions/ADR-013-audio-mixing-engine.md), [EXP-005](../../reports/experiments/EXP-005-pipeline-execution.md), [EXP-006](../../reports/experiments/EXP-006-audio-mixing.md), [EVAL-004](../../reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)

## 예상 다음 단계

Phase 6 Lyrics AI.
