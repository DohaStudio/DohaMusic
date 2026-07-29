# 모델 비교

> 문서 목적: 후보 모델을 같은 근거와 상태로 비교하고 도입 결정을 추적한다.
> 현재 상태: **ACE-Step·HTDemucs·Seed-VC 기술 검증 / Voice Primary 미선정 / 사용자 품질 판정 대기**

| 모델명 | 기능 | 한국어·가사 | RTX 3060 Ti 8GB | 라이선스 | 도입 상태 | 검증 결과 |
|---|---|---|---|---|---|---|
| ACE-Step 1.5 v0.1.8, 2B Turbo | 음악·가창 생성 | 한국어 20초 생성·동일 Seed PCM 재현 성공. 발음·정렬은 사용자 평가 필요 | INT8·CPU/DiT offload로 상주 suite 12/12 성공. 상주 CPU RSS 증가로 Job별 subprocess 유지 | 코드·주 모델 카드 MIT. 상세 권리 검토는 별도 문서 참조 | 선택적 Provider, 기본값 보류 | EXP-001·002 기술 검증 완료 |
| ACE-Step 1.5 0.6B LM | 프롬프트·가사 계획 보조 | 한국어 20초 생성 성공, no-LM 대비 청감 이점은 사용자 평가 필요 | PyTorch backend에서 성공, 추론 56.856초, Torch peak 3,455.66MiB | 모델 카드 MIT | 선택 사용 보류 | 단일 비교 성공 |
| Seed-VC 44k F0 | 음색 변환 | 공식 SVC, 한국어·청감은 사용자 평가 필요 | 3/3 성공, peak 약 5.07GB | GPL-3.0, 배포 검토 필요 | Experimental, 기본값 `mock` | EXP-004 기술 검증·운영 보류 |
| HTDemucs 4.1.0 | 보컬·반주 분리 | 한국어 가창 20초 파일 기술 처리 성공, 언어별 청감은 사용자 평가 필요 | 3/3 성공, 분리 평균 3.915초, GPU 전체 peak 평균 2,555.67MiB | 코드·HTDemucs 가중치 MIT 표시 | 선택적 `demucs`, 기본값 `mock` | EXP-003·Backend E2E 완료 |

ACE-Step 검증은 [공식 v0.1.8 릴리스](https://github.com/ace-step/ACE-Step-1.5/releases/tag/v0.1.8), [설치 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INSTALL.md), [GPU 호환성 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/GPU_COMPATIBILITY.md), [추론 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INFERENCE.md)를 기준으로 고정했다. 실측값과 한계는 [EXP-001](../../reports/experiments/EXP-001-ace-step-local-inference.md)과 [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md)에 있다.

Stem 후보와 실측은 [음원 분리 조사](source-separation.md)와 [EXP-003](../../reports/experiments/EXP-003-stem-separation.md)을 따른다. Codex는 Stem 청감 점수를 작성하지 않았다.

Voice 후보 6개의 현재성·라이선스·한국어·SVC·Backend 적합성과 점수는 [Voice Provider 비교](voice-provider-comparison.md)와 [Voice Provider Score](../04-models/voice-provider-score.md)를 따른다. 점수와 별도의 필수 게이트를 모두 통과한 후보가 없어 Primary는 미선정이다.
