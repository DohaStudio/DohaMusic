# 라이선스 검토

> 문서 목적: 코드·가중치·의존성·출력 사용 조건을 모델별로 추적한다.
> 현재 상태: **ACE-Step 1.5·Demucs 4.1.0 1차 기술 검토 완료 / 법률 결론 아님**

## ACE-Step 1.5 v0.1.8

확인일은 2026-07-29이다.

| 대상 | 공식 근거 | 표시 | 기술 판정 |
|---|---|---|---|
| 소스 코드 v0.1.8 | [GitHub LICENSE](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/LICENSE) | MIT | 사용·수정·배포 시 고지 조건 준수 필요 |
| `ACE-Step/Ace-Step1.5` 가중치 | [Hugging Face 모델 카드](https://huggingface.co/ACE-Step/Ace-Step1.5) | MIT, 출력의 상업 사용 가능 취지 명시 | 공식 표시는 확인했으나 제품 법률 승인과 동일하지 않음 |
| 선택적 0.6B LM | [ACE-Step 모델 카드](https://huggingface.co/ACE-Step/acestep-5Hz-lm-0.6B) | MIT | 이번 실험 미사용 |
| Qwen3 Embedding 0.6B | [공식 모델 카드](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Apache-2.0 | 고지·NOTICE 요구를 배포 시 재검토 |

공식 표시는 코드와 배포 가중치의 라이선스 근거다. 학습 데이터 전체의 권리, 입력 가사·참조 음원 권리, 생성물이 제3자 권리를 침해하지 않는다는 보증, 관할별 상업 서비스 적합성은 이 확인만으로 결론낼 수 없다. 제품 공개 또는 재배포 전 `[법률 검토 필요]`이며, 모델 카드·LICENSE 원문과 배포물의 고지 파일을 다시 고정한다.

## Demucs 4.1.0 / HTDemucs

확인일은 2026-07-29이다.

| 대상 | 공식 근거 | 표시 | 기술 판정 |
|---|---|---|---|
| Demucs 4.1.0 코드 | [공식 유지보수 저장소](https://github.com/adefossez/demucs), [릴리스](https://github.com/adefossez/demucs/releases/tag/v4.1.0) | MIT | 고지 조건 준수 필요 |
| HTDemucs 가중치 | [공식 모델 카드](https://huggingface.co/adefossez/HTDemucs) | MIT | 사용 checkpoint의 공식 표시 확인 |

코드·가중치 표시 확인은 입력 음악, 원곡, 학습 데이터와 분리 출력에 대한 권리 결론이 아니다. 제품 배포·상업 사용 전 `[법률 검토 필요]`다.
