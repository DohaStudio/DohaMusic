# ADR-010: Voice Provider Selection Policy

> 상태: 승인
> 결정일: 2026-07-29

## 배경

기술적으로 실행되는 Voice Provider와 운영에 채택할 수 있는 Provider를 구분할 공통 기준이 필요하다. 단일 benchmark 성공만으로 기본값이나 상용 배포 여부를 결정하면 품질, 라이선스, 유지보수 위험이 누락된다.

## 결정

Voice Provider의 수명주기를 `Experimental → Preview → Stable → Deprecated → Removed`로 관리한다.

- 각 승격은 자동 신호 검사, 사용자 평가, 안정성, 보안, 라이선스, 운영 준비를 모두 검토한다.
- `Stable`만 운영 기본값 후보가 될 수 있다.
- 기본값 변경은 별도 ADR과 회귀 검증이 필요하다.
- 품질·보안·라이선스·유지보수 위험이 새로 확인되면 상태를 강등하거나 비활성화한다.
- 상태와 세부 승격 조건은 [Voice Provider Selection Policy](../04-models/voice-provider-selection-policy.md)를 단일 기준으로 사용한다.

## 현재 적용

| Provider | 상태 | 기본값 | 근거 |
|---|---|---|---|
| `mock` | 개발 기준 | 예 | 외부 AI 런타임 없이 계약·Worker·API 검증 |
| `seed_vc` | Experimental | 아니요 | 추론 성공, clipping·청취 평가·라이선스·archive 위험 미해결 |

Seed-VC는 `Preview` 승격 전까지 운영 트래픽과 Phase 5 통합 대상이 아니다.

## 결과

장점은 기술 PoC와 운영 승인을 명확히 분리하고 대체 Provider 추가 시 같은 기준을 재사용할 수 있다는 점이다. 단점은 승격에 추가 검증과 문서 승인이 필요하다는 점이며, 이는 운영 위험을 통제하기 위한 의도된 비용이다.

## 재검토 조건

- Provider 유형 또는 배포 모델 변경
- 품질/SLO 기준 변경
- 라이선스나 upstream 유지보수 상태 변경
- 첫 Preview 또는 Stable 승격 요청
