# 벤치마크 시나리오

> 문서 목적: 모델 후보와 파이프라인을 동일 조건에서 비교할 최소 시나리오를 정의한다.
> 현재 상태: **B-01·B-05·B-07·B-08·B-09·B-10·B-11 실행 / 나머지 계획**

| ID | 시나리오 | 주요 관찰 |
|---|---|---|
| B-01 | 짧은 한국어 발라드, 직접 가사 | 기술 출력 완료, 발음·가사는 사용자 평가 필요 |
| B-02 | 빠른 템포 한국어 곡 | 음절 누락·리듬 안정성 |
| B-03 | 고음 구간 포함 곡 | 가창·변환 아티팩트 |
| B-04 | 8GB 한계 길이 탐색 | OOM, offload, 최대 길이 |
| B-05 | 동일 Seed 3회·다른 Seed 3개 | PCM 재현성과 파형 다양성 완료 |
| B-06 | 취소·단계 실패 주입 | 정리, 오류, 재시도 |
| B-07 | 같은 프로세스 6회 연속 | 2 suite 12/12 성공, CPU RSS 증가 관찰 |
| B-08 | no LM 대 0.6B LM | 양쪽 실행 성공, 품질 비교는 사용자 평가 필요 |
| B-09 | 같은 20초 입력 HTDemucs 3회 | 3/3 성공, 분리 평균 3.915초, GPU 전체 peak 평균 2,555.67MiB |
| B-10 | Mock 5단계 Pipeline 1회 | 성공, 전체 0.099139초, 실패·재시도·timeout 자동 테스트 |
| B-11 | 합성 10초 vocals+instrumental Default Mixer | 성공, 0.069688초, -1dBFS, 48kHz Stereo, clipping 0 |

실행 환경과 결과는 [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md), 청취 결과는 [EVAL-001](../../reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)에 기록한다.

Stem 분리 환경·결과는 [EXP-003](../../reports/experiments/EXP-003-stem-separation.md), 청취 결과는 [EVAL-002](../../reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md)에 기록한다.

Pipeline 결과는 [EXP-005](../../reports/experiments/EXP-005-pipeline-execution.md)에 기록한다. Mock 결과를 실제 AI 성능으로 해석하지 않는다.

Audio Mixer 결과는 [EXP-006](../../reports/experiments/EXP-006-audio-mixing.md)에 기록한다. 단일 합성 신호 결과를 실제 곡 청감이나 운영 SLO로 일반화하지 않는다.
