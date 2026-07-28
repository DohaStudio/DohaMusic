# Phase 2.5 Definition of Done — Quality Benchmark

> 상태: [진행 중]
> 진행률: 13/14, 93%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-25-quality-benchmark--진행-중), [평가 전략](../08-evaluation/evaluation-strategy.md)

## 목표

ACE-Step의 재현성·다양성·반복 안정성·자원 사용과 적절한 runtime 수명을 증거 기반으로 판단한다.

## 구현 범위와 포함 기능

동일 Seed, 다른 Seed, 상주 반복, VRAM·RSS·시간, 0.6B LM 비교, WAV sample 비교, Benchmark 자동화, ADR·EXP·EVAL 양식을 포함한다.

## 제외 기능

Codex의 청감 품질 점수, 사용자 평가 없는 모델 우열 판정, 제품 기본 Provider 변경은 제외한다.

## 선행 조건

Phase 2 ACE-Step 단독 추론과 고정 입력이 성공해야 한다.

## 완료 체크리스트

- [x] 동일 Seed 3회 PCM 재현성 검증
- [x] 다른 Seed 3개 파형 다양성 검증
- [x] 상주 6회 suite 2개 반복 실행
- [x] 실행 시간과 VRAM 기록
- [x] Process RSS 증가 관찰·기록
- [x] 0.6B LM 단일 비교 실행
- [x] Benchmark suite·집계·WAV 비교 도구
- [x] 성공률과 작은 표본 한계 기록
- [x] EXP-002 작성
- [x] EVAL-001 사용자 평가 양식 작성
- [x] ADR-006·ADR-007 작성
- [x] 관련 문서·CHANGELOG 최신화
- [x] 한국어 커밋·Push·PR·`develop` 병합·`main` 무변경
- [ ] EVAL-001 사용자 점수·근거·종합 판정 입력

## 완료 조건

기술 Benchmark는 완료됐지만 사용자 청취 판정이 반영되어야 Phase 2.5를 `[완료]`로 변경한다.

## 산출물

Benchmark suite, 집계·오디오 비교 도구, EXP-002, EVAL-001, ADR-006·007.

## 관련 문서·ADR·실험

- 문서: [Benchmark Scenarios](../08-evaluation/benchmark-scenarios.md), [Model Loading](../04-models/model-loading-strategy.md)
- ADR: [ADR-006](../11-decisions/ADR-006-ace-step-primary-provider.md), [ADR-007](../11-decisions/ADR-007-ace-step-runtime-lifecycle.md)
- 실험: [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md), [EVAL-001](../../reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)

## 예상 다음 단계

EVAL-001 완료 후 Provider 선택을 확정하고 필요하면 추가 블라인드 비교를 수행한다.
