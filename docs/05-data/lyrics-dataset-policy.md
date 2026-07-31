# Local Lyrics Dataset Policy

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 6.6 Local Lyrics Dataset
> 관련 문서: [ADR-016](../11-decisions/ADR-016-local-lyrics-llm-finetuning.md), [Local Lyrics LLM Roadmap](../../planning/local-lyrics-llm-roadmap.md)

## 목적

Local Lyrics LLM에 사용할 텍스트 Dataset의 출처·권리·계보·품질·삭제 가능성을 보장한다. 사용자 입력 가사는 별도 동의 없이 학습 데이터로 재사용하지 않는다.

## 허용

- 사용자가 직접 작성하고 학습 이용에 명시적으로 동의한 가사
- DohaMusic이 직접 제작하고 권리를 보유한 가사
- 권리자로부터 명시적 학습·파생 모델 이용 허가를 받은 데이터
- 라이선스상 학습, 상업 이용과 파생 모델 이용이 허용된 데이터
- 생성 조건과 권리 상태를 기록한 합성 데이터

## 금지 또는 보류

- 상업 음악 가사의 무단 대량 수집
- robots·서비스 약관·접근 통제를 무시한 crawling
- 출처 불명 또는 학습 허용 여부가 불명확한 가사
- 삭제 요청과 파생 산출물 추적을 처리할 수 없는 데이터
- 개인 음성 파일·voice embedding·참조 audio를 Lyrics Dataset에 포함하는 행위
- 사용자의 API 입력 가사를 별도 opt-in 없이 재사용하는 행위

## Record와 Manifest

각 record는 고유 ID, 원본/가공 구분, 언어, 장르, 분위기, section 구조, 출처, 작성·수집일, 권리자, 라이선스, 허용 범위, 동의 증적, 가공 이력, split, 삭제 상태를 가진다. Dataset manifest는 schema version, Dataset version, record hash, 중복 group, 생성·검수자를 기록한다.

합성 데이터는 생성 모델, 모델 버전, prompt template, 생성 시각, sampling 조건, 후처리, 검수 상태, 상업 이용 가능성, 전체 Dataset 내 비율을 추가 기록한다.

## 처리와 분할

1. 원본은 immutable 영역에 두고 가공본과 분리한다.
2. normalize·section 구조화·언어 판정 뒤 exact/near duplicate와 같은 작품 파생본을 group화한다.
3. 언어·장르·분위기·구조 분포를 기록한다.
4. 작품·중복 group 단위로 Train·Validation·Test를 분리한다.
5. Test는 학습·checkpoint 선택에 사용하지 않고 leakage를 검사한다.
6. 삭제 요청 시 원본·가공본·manifest·학습 Dataset version·파생 checkpoint 영향을 추적한다.

## Voice Dataset과 격리

Lyrics Dataset은 가사 text 전용이다. Phase 7 Doha Voice의 audio, speaker ID, consent record, voice checkpoint와 저장 경로·권한·Dataset Card·Model Card를 공유하지 않는다. 두 Dataset의 결합은 별도 보안·동의 결정 없이는 금지한다.

## 완료 기준

- 모든 record의 출처·권리·라이선스 상태 기록
- 미확인 상업 가사 0건
- Train·Validation·Test 분리와 leakage 검사 완료
- exact/near duplicate 검사 완료
- schema 검증 통과와 Dataset Card 작성
- 삭제·철회 절차와 Dataset version 재현 가능
