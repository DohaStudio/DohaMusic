# Phase 4 Definition of Done — Voice Conversion

> 상태: [계획]
> 진행률: 0/16, 0%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-4-voice-conversion--계획), [Voice Conversion 조사](../01-research/voice-conversion.md)

## 목표

명시적으로 동의된 본인 음성을 이용해 분리 보컬의 음색을 변환하는 교체 가능한 경로를 구축한다.

## 구현 범위와 포함 기능

Seed-VC를 포함한 후보의 공식 조사, Adapter·Mock·Provider, Voice Profile·Backend·Worker 연결, Benchmark, EXP·EVAL·ADR과 안전 검증을 포함한다.

## 제외 기능

타인 음성 무단 복제, Dataset 학습, LoRA·Fine Tuning, Mixer와 Frontend는 제외한다.

## 선행 조건

EVAL-002 검토, 본인 음성 동의·삭제·접근 정책, RTX 3060 Ti 8GB 실행 조건을 확인해야 한다.

## 완료 체크리스트

- [ ] Seed-VC와 대안 공식 문서 조사
- [ ] 코드·가중치·데이터 라이선스 검토
- [ ] 동의·삭제·보안 영향 검토
- [ ] 단독 Voice Conversion 추론
- [ ] `VoiceConverter` Interface·Adapter
- [ ] Mock·Provider Factory
- [ ] Voice Profile·Backend Service 연결
- [ ] 비동기 Worker·상태·안정적 오류
- [ ] API·DB·Storage 변경과 migration
- [ ] 실행 시간·VRAM·출력 Benchmark
- [ ] 음질·화자 유사성·발음 보존 자동 검사
- [ ] EXP-004와 사용자 EVAL-003
- [ ] ADR 작성·관련 문서·CHANGELOG
- [ ] 성공·실패·예외·GPU E2E 테스트
- [ ] 한국어 커밋·Push·`develop` PR·병합
- [ ] 병합 후 검증과 `main` 무변경

## 완료 조건

위 항목 전체와 사용자 품질·동의 검토가 완료되어야 한다. 모델 실행만으로 완료 처리하지 않는다.

## 산출물

Voice Converter Adapter·API·DB·Worker·Benchmark·EXP-004·EVAL-003·ADR.

## 관련 문서·ADR·실험

- 문서: [Voice Adapter](../04-models/voice-conversion-adapter.md), [Voice Consent](../09-security/voice-consent-policy.md)
- ADR·실험: 새로 작성 필요

## 예상 다음 단계

Phase 5 Pipeline Integration.
