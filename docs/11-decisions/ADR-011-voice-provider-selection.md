# ADR-011: Voice Provider Selection

> 상태: 승인 — Primary 미선정, Phase 5 보류
> 작성일: 2026-07-29
> 최종 수정일: 2026-07-29

## 배경과 문제

Seed-VC는 기술 추론에 성공했지만 Phase 4.5에서 운영 보류됐다. DohaMusic 표준 Voice Provider를 정하려면 단순 인기도가 아니라 직접 SVC, 한국어, 라이선스, 유지보수, RTX 3060 Ti, Backend 계약과 사용자 품질을 함께 평가해야 한다.

## 결정

| 역할 | 결정 |
|---|---|
| Primary | 미선정 |
| Secondary 평가 후보 | RVC |
| Experimental | Seed-VC, Amphion Vevo2 |
| Rejected | OpenVoice V2, CosyVoice, Fish Speech |
| 개발 기본값 | `mock` 유지 |

Primary를 억지로 지정하지 않는다. 여섯 후보 중 공식 SVC, 현재 zero-shot reference 계약, 상업 라이선스, 8GB 실측, 사용자 품질과 유지보수 게이트를 모두 통과한 Provider가 없기 때문이다.

RVC는 직접 Voice Conversion과 AI singer workflow, MIT core, 활성 Community를 근거로 다음 **평가 후보**로 둔다. 그러나 사용자별 checkpoint와 feature index 학습이 필요해 현재 runtime fallback이나 구현 대상으로 승인하지 않는다.

Seed-VC는 유일한 로컬 반복 검증 결과 때문에 Experimental로 유지한다. Amphion Vevo2는 zero-shot SVC와 Korean metadata가 있지만 가중치가 CC BY-NC-ND 4.0이므로 비상업 연구 후보로만 유지한다.

OpenVoice V2, CosyVoice와 Fish Speech는 현재 공식 자료에서 DohaMusic의 직접 Singing VC 역할을 입증하지 못했다. Fish Speech는 별도 상업 계약도 필요하다. 이 분류는 각 모델의 TTS 용도 채택 가능성과 무관하다.

## Provider Matrix

```text
Primary       미선정
  ↓ 실패 시
Fallback      미선정
  ↓ 명시적 연구 선택
Experimental  seed_vc / 향후 검증 Provider
  ↓ 개발·테스트
Mock          현재 기본값
```

Primary와 Fallback은 `Preview` 이상의 동일 출력 계약 Provider가 생긴 뒤에만 설정한다. Experimental Provider는 자동 fallback에 참여하지 않는다.

## 대안

- Seed-VC를 Primary로 승격: archive, clipping, EVAL, GPL 배포 위험 때문에 기각
- Vevo2를 Primary로 지정: 비상업·변경금지 가중치 때문에 기각
- CosyVoice/OpenVoice/Fish Speech를 singing으로 간주: 공식 SVC 근거가 없어 기각
- RVC를 즉시 구현: 학습·Dataset·Fine Tuning이 이번 범위 밖이고 현재 계약과 달라 기각

## 영향

- 코드, API, 환경 변수와 기본 `mock`은 변경하지 않는다.
- Phase 4는 94% `[검증 필요]`를 유지한다.
- 표준 Primary가 없으므로 Phase 5 Pipeline Integration을 시작하지 않는다.
- 다음 작업은 새 구현이 아니라 후보별 차단 조건을 해소하는 검증이어야 한다.

## 재검토 조건

- zero-shot SVC 후보의 상업 사용 가능한 코드·가중치 공개
- RVC 학습형 Provider를 Phase 7 Doha Voice 범위와 함께 검토하기로 결정
- Seed-VC clipping·EVAL-003·배포 라이선스 게이트 해제
- 후보의 공식 Singing/Korean 지원, 라이선스 또는 유지보수 상태 변경
- RTX 3060 Ti 반복 benchmark와 사용자 청취 평가 확보

## 관련 문서

- [Voice Provider 비교](../01-research/voice-provider-comparison.md)
- [Voice Provider Score](../04-models/voice-provider-score.md)
- [ADR-009](ADR-009-seed-vc-voice-provider.md)
- [ADR-010](ADR-010-voice-provider-selection-policy.md)
