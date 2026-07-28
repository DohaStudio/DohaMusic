# Phase 6 Definition of Done — Lyrics AI

> 상태: [계획]
> 진행률: 0/14, 0%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-6-lyrics-ai--계획), [Generated Content Policy](../09-security/generated-content-policy.md)

## 목표

사용자 의도에서 한국어 가사와 음악 생성용 prompt를 안전하고 재현 가능하게 생성한다.

## 구현 범위와 포함 기능

Lyrics Generator 후보 조사, Interface·Adapter·Mock·Provider, prompt 계약, API·Backend·Benchmark, 안전·품질 평가를 포함한다.

## 제외 기능

기존 곡 가사의 장문 복제, 권리 미확인 Dataset 학습, Doha Voice와 Frontend는 제외한다.

## 선행 조건

음악 생성 입력 계약, 콘텐츠 안전 정책과 라이선스 기준을 확정해야 한다.

## 완료 체크리스트

- [ ] Lyrics 모델·공식 API 조사
- [ ] 라이선스·데이터·상업 이용 검토
- [ ] `LyricsGenerator` Interface·Adapter
- [ ] Mock·Provider Factory
- [ ] Prompt·가사 schema와 입력 검증
- [ ] API·Service·Worker 연결
- [ ] 안전 필터·오류·로그 정책
- [ ] 한국어 품질·속도 Benchmark
- [ ] 성공·실패·예외·회귀 테스트
- [ ] EXP·EVAL과 모델 선정 ADR
- [ ] API·Architecture·Security 문서
- [ ] CHANGELOG·README·ROADMAP·Master·DoD 갱신
- [ ] 한국어 커밋·Push·`develop` PR·병합
- [ ] 병합 후 검증과 `main` 무변경

## 완료 조건

모델 실행, 한국어 품질, 안전·권리 기준과 Backend 통합을 모두 검증해야 한다.

## 산출물

Lyrics Adapter·API·Benchmark·안전 평가·ADR·EXP·EVAL.

## 관련 문서·ADR·실험

- 문서: [Music Generation Models](../01-research/music-generation-models.md), [Security Policy](../09-security/security-policy.md)
- ADR·실험: 새로 작성 필요

## 예상 다음 단계

Phase 7 Doha Voice와 Phase 8 Studio 우선순위를 재검토한다.
