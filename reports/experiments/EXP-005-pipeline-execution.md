# EXP-005 — Pipeline Execution

> 상태: [완료]
> 실험일: 2026-07-29
> 작업 브랜치: `feat/pipeline-orchestrator`
> 목적: Mock Provider 기반 5단계 Pipeline의 순서·출력·metadata·실행 시간을 검증한다.

## 조건

- 실행: `python -m backend.scripts.benchmark_pipeline`
- Music·Stem·Voice·Mixer: Mock
- Exporter: WAV
- 입력 길이 설정: 10초
- Seed: 20260729
- Mock delay: 각 AI 단계 0.01초
- DB·Storage: 임시 SQLite와 임시 로컬 Storage

## 결과

| 항목 | 결과 |
|---|---:|
| 성공률 | 1/1, 100% |
| 전체 실행 시간 | 0.099139초 |
| 단계 시간 합계 | 0.070167초 |
| Music | 0.012436초 |
| Stem | 0.018398초 |
| Voice | 0.030093초 |
| Mixer | 0.001258초 |
| Export | 0.007982초 |
| GPU·VRAM·CPU 사용률 | Mock이므로 측정하지 않음 |
| 최종 출력 | 48kHz Stereo WAV |

성공 경로에서 `music`, `vocals`, `instrumental`, `converted_voice`, `final`, `metadata` 파일이 등록됐다. 테스트에서는 Music·Stem·Voice 실패, Provider 1회 실패 후 재시도 성공, timeout, 부분 오디오 정리도 별도로 검증했다.

## 결론

Mock 기반 Orchestrator 기술 경계는 동작한다. 이 결과는 실제 음악 품질, 실제 Mixer 품질, GPU 성능 또는 Voice Provider 운영 준비도를 증명하지 않는다. 실제 Provider E2E benchmark는 각 품질·라이선스 게이트 승인 후 별도 실험으로 수행한다.
