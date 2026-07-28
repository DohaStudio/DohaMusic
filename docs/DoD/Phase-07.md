# Phase 7 Definition of Done — Doha Voice

> 상태: [계획]
> 진행률: 0/16, 0%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-7-doha-voice--계획), [Audio Data Policy](../05-data/audio-data-policy.md)

## 목표

동의·삭제·계보 관리가 가능한 본인 가창 Dataset으로 개인화 음성 품질 향상을 검증한다.

## 구현 범위와 포함 기능

Dataset, recording·metadata, preprocessing, LoRA·Fine Tuning 후보, 학습·Benchmark·Evaluation과 Model Card를 포함한다.

## 제외 기능

타인 음성, 무동의 수집, 권리 미확인 Dataset, 대규모 기반 모델 사전학습은 제외한다.

## 선행 조건

Phase 4 baseline, 음성 동의·철회·삭제, 접근 제어·보존 기간, 학습 라이선스 ADR이 승인되어야 한다.

## 완료 체크리스트

- [ ] 본인 음성 동의·철회·삭제 절차
- [ ] Dataset schema와 계보
- [ ] 녹음·품질 기준
- [ ] Preprocessing Pipeline
- [ ] Train·validation·test 분리
- [ ] LoRA 후보 조사
- [ ] Fine Tuning 후보 조사
- [ ] 라이선스·보안·개인정보 ADR
- [ ] 재현 가능한 학습 설정
- [ ] Baseline 대비 Benchmark
- [ ] 화자 유사성·발음·음질 Evaluation
- [ ] Overfit·오용·삭제 검증
- [ ] Model Card·EXP·EVAL
- [ ] 관련 데이터·보안·운영 문서·CHANGELOG
- [ ] 한국어 커밋·Push·`develop` PR·병합
- [ ] 병합 후 검증과 `main` 무변경

## 완료 조건

품질 향상뿐 아니라 동의 철회와 원본·파생·모델 artifact 삭제 가능성을 검증해야 한다.

## 산출물

Dataset·전처리 도구·학습 설정·Model Card·Benchmark·EXP·EVAL·ADR. 개인 음성과 가중치는 Git에 포함하지 않는다.

## 관련 문서·ADR·실험

- 문서: [Dataset Structure](../05-data/dataset-structure.md), [Voice Consent](../09-security/voice-consent-policy.md)
- ADR·실험: 개인화 학습 승인 문서와 실험 필요

## 예상 다음 단계

Phase 8 Doha Studio에서 승인된 Voice 모델을 선택적으로 제공한다.
