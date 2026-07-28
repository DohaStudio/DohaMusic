# Phase 5 Definition of Done — Pipeline Integration

> 상태: [계획]
> 진행률: 0/15, 0%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-5-pipeline-integration--계획), [AI Pipeline](../03-architecture/ai-pipeline.md)

## 목표

Music → Stem → Voice → Mixer를 하나의 추적 가능한 비동기 작업으로 연결한다.

## 구현 범위와 포함 기능

Pipeline 오케스트레이션, Mixer, 통합 API·Worker·상태·파일, 단계별 오류·재시도 경계, Benchmark와 통합 테스트를 포함한다.

## 제외 기능

Lyrics AI, Frontend, Production Queue·DB·Storage 전환은 제외한다.

## 선행 조건

Phase 2·3·4의 Provider 계약과 품질·안전 게이트가 충족되어야 한다.

## 완료 체크리스트

- [ ] Music 단계 연결
- [ ] Stem 단계 연결
- [ ] Voice 단계 연결
- [ ] Mixer와 48kHz 출력 계약
- [ ] Pipeline API·Service
- [ ] 비동기 Worker·단계 상태
- [ ] 단계 실패·정리·재시도 정책
- [ ] DB·ERD·Storage 변경
- [ ] E2E Benchmark와 자원 기록
- [ ] 성공·실패·회귀 통합 테스트
- [ ] API·Architecture·Operations 문서
- [ ] Pipeline ADR·실험 보고서
- [ ] CHANGELOG·README·ROADMAP·Master·DoD 갱신
- [ ] 한국어 커밋·Push·`develop` PR·병합
- [ ] 병합 후 검증과 `main` 무변경

## 완료 조건

고정 입력 한 건이 모든 단계를 통과하고 각 단계 실패가 안전한 상태·파일 정리로 귀결되어야 한다.

## 산출물

Pipeline Service·Worker·API·Mixer, schema·문서·ADR·통합 실험 보고서.

## 관련 문서·ADR·실험

- 문서: [Worker Architecture](../03-architecture/worker-architecture.md), [Job State](../07-database/job-state-model.md)
- ADR·실험: Pipeline 상태·Storage·Mixer 결정 문서 필요

## 예상 다음 단계

Phase 6 Lyrics AI.
