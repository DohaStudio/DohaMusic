# 음원 분리 모델 조사

> 문서 목적: 보컬과 반주 분리 후보의 품질·자원·권리 기준을 정의한다.
> 현재 상태: **공식 조사·HTDemucs 선정·RTX 3060 Ti 검증 완료 / 수동 품질 평가 필요**

| 후보 | 공식 근거·라이선스 | 품질·지원 | RTX 3060 Ti·적용성 | 판정 |
|---|---|---|---|---|
| HTDemucs | [유지보수 저장소](https://github.com/adefossez/demucs), [모델 카드](https://huggingface.co/adefossez/HTDemucs), 코드·가중치 MIT | 공식 기본 모델, 2-stem vocals·CUDA·segment 지원 | 20초 3/3, 분리 평균 3.915초, GPU 전체 peak 평균 2,555.67MiB | **선정** |
| HTDemucs FT | 같은 공식 Demucs 배포 | 공식 설명상 더 나을 수 있으나 약 4배 느림 | 같은 Adapter로 교체 가능, 이번 실측 안 함 | 후속 품질 비교 |
| Hybrid Demucs v3 | [Meta 보관 저장소](https://github.com/facebookresearch/demucs), MIT | 공식 표의 SDR 7.7 | 구세대, 현재 기본 아님 | 제외 |
| MDX-Net | [공식 저장소](https://github.com/kuielab/mdx-net) | MDX challenge 계열, 공식 표 SDR 7.5 | 유지보수·패키징 추가 검증 필요 | 대안 |
| Open-Unmix | [공식 저장소](https://github.com/sigsep/open-unmix-pytorch), MIT | 안정적인 공개 기준선, 공식 비교 SDR 5.3 | 쉬운 구조지만 HTDemucs 대비 성능 우위 근거 없음 | 기준선 |

한국어는 모델의 언어 조건이 아니라 실제 가창·믹스 특성으로 평가한다. 이번 입력은 한국어 가창이지만 발음이나 가사 정확도를 Stem 모델이 생성하는 것은 아니다. 자동 검증은 존재·48kHz·Stereo·길이·비무음·clipping만 판정하며 보컬 누출, 반주 손상, 잔향과 노이즈는 [EVAL-002](../../reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md)에 사용자가 기록한다.

변환 단계에는 보컬 Stem만 전달하고, 원본과 중간 Stem은 작업 권한과 보존 정책을 적용한다. 세부 실측은 [EXP-003](../../reports/experiments/EXP-003-stem-separation.md), 구조 결정은 [ADR-008](../11-decisions/ADR-008-stem-separation-provider.md)을 따른다. Seed-VC는 이번 Phase에서 구현하지 않았다.
