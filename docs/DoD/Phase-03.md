# Phase 3 Definition of Done — Stem Separation

> 상태: [완료]
> 진행률: 16/16, 100%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-3-stem-separation--완료), [Stem Adapter](../04-models/source-separation-adapter.md)

## 목표

생성 음악에서 보컬과 반주를 분리하고 다음 Phase의 Voice Conversion이 사용할 안정적인 `vocals.wav` 계약을 만든다.

## 구현 범위와 포함 기능

후보 조사·HTDemucs 선정, `StemSeparator`, Mock·Demucs Provider, Backend API·DB·Worker, 48kHz Stereo 출력, Benchmark, 자동 품질 검사, EXP·EVAL·ADR을 포함한다.

## 제외 기능

Seed-VC, Voice Clone, Fine Tuning, Mixer, Frontend, 외부 Queue는 제외한다.

## 선행 조건

Phase 1 Backend와 유효한 generated file metadata가 필요하다.

## 완료 체크리스트

- [x] Demucs·HTDemucs·MDX-Net·Open-Unmix 조사
- [x] 공식 문서와 코드·가중치 라이선스 확인
- [x] RTX 3060 Ti 기준 HTDemucs 선정
- [x] 오프라인 단독 추론
- [x] `StemSeparator` Interface
- [x] `DemucsAdapter`와 Provider Factory
- [x] `MockStemSeparator` 유지
- [x] Stem API·Service·Repository·Worker
- [x] `stem_jobs`·`stem_files` migration
- [x] `STEM_SEPARATING` 상태와 오류 코드
- [x] 48kHz Stereo vocals·instrumental·metadata
- [x] 3회 Benchmark와 GPU Backend E2E
- [x] 자동 존재·길이·무음·clipping 검사
- [x] EXP-003·EVAL-002 평가 양식·ADR-008
- [x] README·ROADMAP·CHANGELOG와 전문 문서 최신화
- [x] 한국어 커밋·Push·PR·`develop` 병합·`main` 무변경

## 완료 조건

기술 범위와 사용자 평가 양식 구축을 완료 조건으로 한다. EVAL-002 사용자 점수는 Phase 4 진입 판단 입력이며 Codex가 대신 작성하지 않는다.

## 산출물

Stem Adapter·runner·API·migration·테스트, EXP-003, EVAL-002, ADR-008.

## 관련 문서·ADR·실험

- 문서: [Source Separation 조사](../01-research/source-separation.md), [Stem API](../06-api/stem-api.md)
- ADR: [ADR-008](../11-decisions/ADR-008-stem-separation-provider.md)
- 실험: [EXP-003](../../reports/experiments/EXP-003-stem-separation.md), [EVAL-002](../../reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md)

## 예상 다음 단계

EVAL-002를 사용자가 검토하고 Phase 4 Seed-VC 공식 조사·라이선스·단독 추론을 시작한다.
