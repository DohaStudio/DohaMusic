# Voice Provider Selection Policy

> 현재 상태: **Primary·Fallback 미선정 / Seed-VC Experimental / 운영 보류**

## 상태 정의

| 상태 | 의미 | 운영 기본값 가능 여부 |
|---|---|---|
| Experimental | 기술 검증 단계. 품질·안정성·라이선스 중 미해결 항목이 있다. | 불가 |
| Preview | 제한된 사용자와 입력에서 품질·실패 대응을 검증한다. | 불가 |
| Stable | 승인된 품질·운영·보안·라이선스 기준을 모두 충족한다. | 가능 |
| Deprecated | 신규 사용을 중단하고 대체 Provider로 이전한다. | 불가 |
| Removed | 코드와 운영 경로에서 제거됐다. | 불가 |

## 승격 기준

Provider는 다음 상태의 모든 필수 조건을 통과한 경우에만 한 단계씩 승격한다.

### Experimental → Preview

- 사용자 청취 평가와 채택 판정 완료
- clipping·무음·길이·sample rate·channel 회귀 기준 통과
- 실패율·처리 시간·VRAM 기준과 재현 가능한 benchmark 확보
- 데이터 동의·보존·삭제 정책 검증
- 코드·가중치·의존성의 사용 및 배포 시나리오별 라이선스 승인

### Preview → Stable

- 대표 입력군의 장기 안정성 및 품질 기준 통과
- timeout·취소·재시도·모니터링·장애 격리 검증
- 보안 검토와 운영 runbook 승인
- 유지보수 책임자, upstream 대응 및 대체/rollback 계획 확정

치명적 품질 회귀, 라이선스 변경, upstream 중단, 보안 취약점 또는 운영 SLO 미달이 발생하면 즉시 강등하거나 비활성화한다.

## Seed-VC 적용

Seed-VC는 RTX 3060 Ti에서 기술 추론에 성공했으나 clipping 위험, 미완료 EVAL-003, GPL-3.0 배포 경계, archive된 upstream 위험이 남아 `Experimental`이다.

- 기본 Provider: `mock` 유지
- 명시적 로컬 기술 검증: 허용
- Preview·Stable·운영·Pipeline Integration: 보류
- 외부 배포와 상용 사용: ADR-009의 라이선스 및 품질 재검토 조건 통과 전 보류

상태 변경은 ADR을 갱신하고 README, MASTER_ROADMAP, ROADMAP, CHANGELOG, 운영·보안 문서를 같은 변경에서 최신화한다.

## Phase 4.6 Provider 분류

| 역할 | Provider | 런타임 참여 여부 |
|---|---|---|
| Primary | 미선정 | 없음 |
| Fallback | 미선정 | 없음 |
| Secondary 평가 후보 | RVC | 구현되지 않음 |
| Experimental | Seed-VC, Amphion Vevo2 | Seed-VC만 opt-in 구현, Vevo2 미구현 |
| Rejected | OpenVoice V2, CosyVoice, Fish Speech | 없음 |
| Mock | `mock` | 현재 기본값 |

향후 선택 순서는 `Primary → 호환 Fallback → 명시적 Experimental → Mock 개발 경로`다. Experimental은 운영 자동 fallback으로 사용하지 않는다. 점수와 상세 근거는 [Voice Provider Score](voice-provider-score.md)와 [Voice Provider 비교](../01-research/voice-provider-comparison.md)를 따른다.
