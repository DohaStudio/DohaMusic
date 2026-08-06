# Phase 7 완료 기준 — Doha Voice

> 상태: [계획]
> 진행률: 0/16, 0%
> 최종 수정일: 2026-08-01
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-7-doha-voice--계획), [책임 경계](../03-architecture/repository-provider-boundaries.md), [Audio Data Policy](../05-data/audio-data-policy.md), [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md)

## 목표

동의·삭제·계보 관리가 가능한 본인 가창 Dataset으로 개인화 음성 품질 향상을 검증한다.

## 구현 범위와 포함 기능

DohaVocal `[계획]`이 Dataset의 기술 처리, preprocessing, LoRA·Fine Tuning 후보, 학습·Checkpoint·Benchmark·Evaluation과 Model Manifest를 소유한다. DohaMusic은 recording UX, 동의·소유권·접근 권한·삭제 결정과 Provider Orchestration을 소유한다.

## 제외 기능

타인 음성, 무동의 수집, 권리 미확인 Dataset, 대규모 기반 모델 사전학습은 제외한다. 기존 Voice Conversion용 단일 참조 음성을 안내·녹음·등록하는 F6 Voice Enrollment UX는 Phase 8 후속 범위이며, Phase 7 Dataset·학습 완료 항목으로 계산하지 않는다.

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

DohaMusic이 DohaVocal의 승인된 Voice Provider를 선택적으로 호출한다.

K-POP Style Fine-tuning, 개인 Voice 학습, Local Lyrics LLM은 서로 다른 Dataset·목표·Adapter 경계를 유지한다. K-POP 제어 계층 K0 문서는 Phase 7 학습 착수나 Voice Provider 승인을 의미하지 않는다.

F6 Enrollment sample을 Phase 7 Dataset으로 재사용하려면 별도 학습 opt-in, Dataset schema·lineage, 전사, split, 보존·철회와 원본·전처리·cache·모델 artifact 삭제 ADR이 선행되어야 한다. F6 제출만으로 개인화 Dataset 동의나 Phase 7 진행 증거를 만들지 않는다.
