# Voice Provider Score

> 기준일: 2026-07-29
> 점수 목적: 확인 가능한 증거의 범위와 DohaMusic 적합성을 같은 규칙으로 비교

## 평가 기준

총점은 100점이지만 Primary 선정에는 별도의 필수 게이트를 적용한다. 확인되지 않은 항목은 0점이며 추정 점수를 부여하지 않는다.

| 항목 | 배점 | 객관적 부여 기준 |
|---|---:|---|
| 품질 | 20 | 로컬 반복+자동+사용자 평가 20, 로컬 반복 자동 평가 14, 공식 task-specific 평가·checkpoint 10, 인접 TTS/VC 근거 6, 없음 0 |
| 한국어 | 15 | 선택 모델의 공식 Korean 지원 명시 15, 공식 명시 없음 0 |
| 노래 지원 | 20 | pretrained zero-shot SVC 20, 사용자별 학습형 singing workflow 10, 공식 근거 없음 0 |
| 라이선스 | 20 | 코드·가중치 permissive 20, core permissive이나 구성요소 미확정 15, GPL 10, 비상업/별도 상업 계약 0 |
| 유지보수 | 10 | 비archive+180일 내 push 10, 1년 초과 저활동 3, archive 0 |
| Community | 5 | Stars 20k 이상 5, 5k 이상 4, 1k 이상 3, 그 미만 1 |
| Backend 적용성 | 10 | zero-shot source+reference SVC 10, zero-shot speech VC 7, 학습형/구버전 VC 4, text→speech 중심 2, 경로 없음 0 |

## 점수

| Provider | 품질 20 | 한국어 15 | 노래 20 | 라이선스 20 | 유지보수 10 | Community 5 | Backend 10 | 총점 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Amphion Vevo2 | 10 | 15 | 20 | 0 | 10 | 4 | 10 | **69** |
| CosyVoice | 6 | 15 | 0 | 20 | 10 | 5 | 4 | **60** |
| Seed-VC | 14 | 0 | 20 | 10 | 0 | 3 | 10 | **57** |
| OpenVoice V2 | 6 | 15 | 0 | 20 | 3 | 5 | 7 | **56** |
| RVC | 10 | 0 | 10 | 15 | 10 | 5 | 4 | **54** |
| Fish Speech | 6 | 15 | 0 | 0 | 10 | 5 | 2 | **38** |

## 점수 해석 제한

- Vevo2의 69점은 기술 적합도이며 `CC BY-NC-ND 4.0` 가중치 때문에 상업 Primary가 될 수 없다.
- CosyVoice의 60점은 한국어·라이선스·유지보수 점수 영향이며 직접 Singing VC가 확인됐다는 뜻이 아니다.
- Seed-VC의 품질 14점은 자동 benchmark 근거다. EVAL-003가 비어 있어 20점이 아니다.
- RVC의 한국어 UI는 모델의 한국어 품질 근거가 아니므로 한국어 점수를 부여하지 않았다.
- 서로 다른 모델의 공식 평가 수치는 데이터와 조건이 달라 음질 우열로 직접 비교하지 않는다.

## Primary 필수 게이트

1. 공식 pretrained Singing Voice Conversion 지원
2. 현재 `source vocals + reference voice` 계약 또는 승인된 계약 변경
3. 상업 SaaS와 계획된 배포 방식에 사용 가능한 라이선스
4. RTX 3060 Ti 8GB 반복 추론·실패·신호 검증
5. 사용자 청취 평가 승인
6. 유지보수·보안·rollback 계획

모든 항목을 통과한 후보가 없어 Primary는 미선정이다. 총점은 필수 게이트를 대체하지 않는다.

## 재평가 우선순위

1. RVC의 학습형 구조가 Doha Voice 장기 계획과 호환되는지 별도 Phase에서 검토
2. Vevo2 상업 사용 가능한 가중치 또는 별도 허가 여부 확인
3. Seed-VC EVAL-003 및 clipping 해제 조건 처리
4. OpenVoice가 공식 SVC 지원을 제공하는 경우 재평가

세부 근거는 [Voice Provider 비교](../01-research/voice-provider-comparison.md)를 따른다.
