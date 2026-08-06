# QG-001 — Voice Conversion 운영 준비도

> 평가일: 2026-07-29
> 결정: **운영 보류**
> Provider 상태: **Experimental**

## 결정 요약

Seed-VC는 RTX 3060 Ti에서 3/3 추론에 성공해 기술 검증과 로컬 개발에는 사용할 수 있다. 그러나 사용자 청취 평가가 없고, full-scale 초과 출력과 현재 PCM16 export의 결합 위험이 검증되지 않았으며, GPL-3.0 배포 경계와 archive upstream 위험이 남아 운영 Provider로 채택하지 않는다.

## 증거

| 영역 | 증거 | 판정 |
|---|---|---|
| 실행 | 30-step 3/3 성공, 평균 27.224초 | 기술 실행 가능 |
| 자원 | peak VRAM 5,067~5,069MB | RTX 3060 Ti에서 가능 |
| 파일 | 48kHz stereo, 길이 보존, 비무음 | 자동 형식 기준 통과 |
| Peak | 반복 3/3 full-scale 부근/초과 경고 | 운영 차단 |
| 청감 | EVAL-003 미작성 | 운영 차단 |
| 라이선스 | 코드·모델 GPL-3.0, 외부 배포 영향 검토 필요 | 배포 차단 |
| 유지보수 | 공식 저장소 archive | 승격 차단 |

## 운영 정책

| 사용 시나리오 | 판정 | 조건 |
|---|---|---|
| 기술 검증 | 허용 | 격리 환경·비민감 샘플 |
| 로컬 개발 | 조건부 허용 | 동의된 음성, Provider 명시 선택, 외부 배포 금지 |
| Preview/운영 | 보류 | 품질·청감·실패 대응 기준 필요 |
| 상용 SaaS | 보류 | 품질 게이트와 법률 검토 필요 |
| Docker/온프레미스 배포 | 보류 | GPL 준수 배포물·대응 소스·고지 범위 검토 필요 |

## 해제 조건

1. EVAL-003 사용자 평가 및 채택 결정
2. pre-resample/post-resample/PCM16 export peak와 true-peak 재현
3. headroom 또는 limiter 정책 구현 후 회귀 검증
4. 배포 단위별 코드·가중치·의존성 라이선스 목록과 법률 승인
5. archive upstream 유지보수 또는 대체 Provider 계획

## Phase 5 Gate

현재는 **진행 불가**다. Voice 모듈이 운영 가능 수준으로 승인되지 않았고, Phase 5 선행 품질 게이트도 닫히지 않았다. 이 문서의 해제 조건과 음악·Stem Provider의 사용자 평가를 모두 충족한 뒤 Pipeline Integration을 다시 검토한다.

## 근거 문서

- [EXP-004](../experiments/EXP-004-seed-vc.md)
- [EVAL-003](../evaluations/EVAL-003-seed-vc-listening-evaluation.md)
- [ADR-009](../../docs/11-decisions/ADR-009-seed-vc-voice-provider.md)
- [ADR-010](../../docs/11-decisions/ADR-010-voice-provider-selection-policy.md)
