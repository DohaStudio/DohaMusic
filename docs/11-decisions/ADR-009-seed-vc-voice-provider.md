# ADR-009: Seed-VC 격리형 Voice Provider

> 상태: 기술 검증용 채택, 운영 보류
> 결정일: 2026-07-29
> Phase 4.5 재검토: 2026-07-29

## 배경

분리 보컬과 명시적으로 동의한 참조 음성을 입력으로 받는 singing voice conversion 경계가 필요하다. 장비는 RTX 3060 Ti 8GB이며 FastAPI 프로세스의 의존성과 안정성을 보호해야 한다.

## 결정

1. Provider 계약은 `VoiceConverter`로 고정한다.
2. 기본 Provider는 `mock`이며, `seed_vc`는 명시적으로 선택하는 실험용 Provider로만 유지한다.
3. Seed-VC는 고정 커밋과 별도 Python 환경의 subprocess로만 실행한다.
4. 참조 음성은 동의된 Voice Profile과 `voices/references` 경계로 제한한다.
5. 음악 생성·Stem·Voice 작업은 기존 GPU 동시성 1 shared executor를 사용한다.
6. Seed-VC의 운영 상태는 ADR-010의 수명주기 기준에 따라 `Experimental`로 분류한다.

## Phase 4.5 품질 게이트 결과

판정은 **운영 보류**다.

- 30-step 3회는 모두 성공했고 평균 27.224초, peak VRAM 5,067~5,069MB로 RTX 3060 Ti에서 기술 실행 가능성을 확인했다.
- 세 출력 모두 full-scale 부근 또는 초과 샘플이 탐지됐다. 공식 실행 로그의 저장 전 텐서 최대값 `1.0214`는 Seed-VC/vocoder 출력이 export 전에 이미 범위를 초과할 수 있음을 확인한다.
- 실험 파일은 float WAV라 초과값을 보존했으므로 당시 경고만으로 정수 PCM의 비가역 clipping을 단정하지 않는다. 다만 현재 PCM16 export 경로는 같은 입력에서 재검증되지 않아 hard clipping 위험을 배제할 수 없다.
- EVAL-003 사용자 청취 평가가 비어 있어 음색 유사도와 노래 자연스러움을 승인할 근거가 없다.
- 공식 저장소가 archive 상태이고 코드·모델이 GPL-3.0으로 표시돼 유지보수 및 외부 배포 검토가 필요하다.

## 라이선스 판단 경계

GPL-3.0은 상업적 이용 자체를 금지하지 않는다. GPL 프로그램을 수정해 서버에서만 실행하고 사본을 배포하지 않는 경우에는 GPL만으로 소스 제공 의무가 발생하지 않는다는 GNU FAQ 설명이 있다. 그러나 Docker, 온프레미스 패키지, 설치 번들처럼 Seed-VC 또는 가중치 사본을 외부에 제공하면 해당 배포물의 라이선스 고지와 대응 소스 제공 등 GPL 의무를 검토해야 한다.

DohaMusic과 subprocess 프로그램이 법적으로 별도 저작물인지, 결합 저작물인지에 대한 최종 판단은 기술 문서의 범위를 벗어난다. 따라서 SaaS 상용화와 모든 외부 배포는 코드·가중치·의존성 목록을 확정한 뒤 법률 검토를 통과해야 한다. 이 문서는 법률 자문이 아니다.

## 허용 범위

| 용도 | 현재 정책 |
|---|---|
| 기술 검증 | 허용 |
| 로컬 개발 | 동의된 음성과 격리 런타임에 한해 허용 |
| Preview/운영 | 보류 |
| 상용 SaaS | 법률·품질 게이트 전 보류 |
| Docker/온프레미스/외부 배포 | GPL 준수 패키지와 법률 검토 전 보류 |

## 재검토 조건

- EVAL-003 사용자 청취 평가 완료 및 채택 판단
- 저장 전·resample 후·PCM16 export 후 peak/true-peak 비교 재현
- 검증된 headroom normalization 또는 limiter 정책과 회귀 검증
- 코드·가중치·의존성의 배포 단위별 라이선스 목록과 법률 검토
- archive된 upstream을 대체할 유지보수 계획 또는 대체 Provider 평가

위 조건을 충족하기 전에는 `seed_vc`를 기본값이나 운영 Provider로 승격하지 않고 Phase 5 Pipeline Integration에 연결하지 않는다.

## 관련 문서

- [ADR-010 Voice Provider Selection Policy](ADR-010-voice-provider-selection-policy.md)
- [EXP-004](../../reports/experiments/EXP-004-seed-vc.md)
- [EVAL-003](../../reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md)
- [Voice Provider 정책](../04-models/voice-provider-selection-policy.md)
