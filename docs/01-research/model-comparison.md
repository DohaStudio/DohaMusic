# 모델 비교

> 문서 목적: 후보 모델을 같은 근거와 상태로 비교하고 도입 결정을 추적한다.
> 현재 상태: **ACE-Step 1.5 반복 기술 검증 완료 / 사용자 품질 판정 대기**

| 모델명 | 기능 | 한국어·가사 | RTX 3060 Ti 8GB | 라이선스 | 도입 상태 | 검증 결과 |
|---|---|---|---|---|---|---|
| ACE-Step 1.5 v0.1.8, 2B Turbo | 음악·가창 생성 | 한국어 20초 생성·동일 Seed PCM 재현 성공. 발음·정렬은 사용자 평가 필요 | INT8·CPU/DiT offload로 상주 suite 12/12 성공. 상주 CPU RSS 증가로 Job별 subprocess 유지 | 코드·주 모델 카드 MIT. 상세 권리 검토는 별도 문서 참조 | 선택적 Provider, 기본값 보류 | EXP-001·002 기술 검증 완료 |
| ACE-Step 1.5 0.6B LM | 프롬프트·가사 계획 보조 | 한국어 20초 생성 성공, no-LM 대비 청감 이점은 사용자 평가 필요 | PyTorch backend에서 성공, 추론 56.856초, Torch peak 3,455.66MiB | 모델 카드 MIT | 선택 사용 보류 | 단일 비교 성공 |
| Seed-VC 계열 후보 | 음색 변환 | 가창·한국어 테스트 필요 | 로컬 테스트 필요 | 검토 필요 | 후속 검토 | 미실행 |
| Demucs 계열 후보 | 음원 분리 | 해당 없음 | 로컬 테스트 필요 | 코드·가중치 별도 검토 | 후속 검토 | 미실행 |

ACE-Step 검증은 [공식 v0.1.8 릴리스](https://github.com/ace-step/ACE-Step-1.5/releases/tag/v0.1.8), [설치 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INSTALL.md), [GPU 호환성 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/GPU_COMPATIBILITY.md), [추론 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INFERENCE.md)를 기준으로 고정했다. 실측값과 한계는 [EXP-001](../../reports/experiments/EXP-001-ace-step-local-inference.md)과 [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md)에 있다.
