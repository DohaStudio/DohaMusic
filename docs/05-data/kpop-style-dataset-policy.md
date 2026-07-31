# K-POP Style Dataset 정책

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 기능: 향후 K-POP Style Fine-tuning
> 관련 문서: [Audio Data Policy](audio-data-policy.md), [Lyrics Dataset Policy](lyrics-dataset-policy.md), [K-POP Roadmap](../../planning/kpop-creation-roadmap.md)

이번 단계는 정책 정의만 수행하며 Dataset 구축·수집·전처리·LoRA 학습을 수행하지 않는다.

## 허용 원칙

- 직접 제작했거나 학습·상업 이용·변형·재배포 범위를 명시적으로 확보한 데이터만 사용한다.
- 출처, 라이선스, 권리자, 동의 증적, 허용 범위, 만료·철회 상태를 항목별 manifest에 기록한다.
- 원본과 가공 데이터를 분리하고 중복 제거 및 Train·Validation·Test 분리를 적용한다.
- 합성 데이터는 생성 모델·버전·Prompt·Seed·생성 조건과 사용 권리를 기록한다.

## 금지

- 유명 아티스트의 상업 음원·가사 무단 수집 또는 학습
- 특정 아티스트의 고유 음색·문체·곡을 모방하기 위한 Dataset 구성
- 크롤링 가능하다는 이유만으로 상업 음원·가사를 학습에 사용
- 권리 상태가 불명확한 데이터의 임시 포함

## 데이터 분리

Music Style LoRA, Voice Personalization, Lyrics LLM은 목적·권리·Adapter가 서로 다른 Dataset이다. 개인 음성은 Style·Lyrics Dataset과 물리적·논리적으로 분리하고 명시적 동의와 삭제 정책을 따른다.

## 향후 후보 범위

- Korean Dance Pop
- Synth Pop
- Electro Pop
- House 기반 Pop
- Performance Pop

후보 장르명은 수집 허가가 아니며, 실제 Dataset 편입 전 법률·라이선스 검토가 필요하다.
