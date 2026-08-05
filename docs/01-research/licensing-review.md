# 라이선스 검토

> 문서 목적: 코드·가중치·의존성·출력 사용 조건을 모델별로 추적한다.
> 현재 상태: **기존 Provider 기술 검토 / DohaLM 상업 사용 미승인 / 법률 결론 아님**
> 최종 수정일: 2026-08-05

## 공통 모델 검토 항목

모델 또는 Adapter를 DohaMusic Provider로 등록하기 전에 다음 항목을 버전별로 확인하고 근거 URL·확인일·검토자를 기록한다.

- 기반 모델 라이선스
- 모델 가중치 라이선스
- 학습 데이터 라이선스와 데이터 계보
- 파인튜닝 데이터 라이선스
- Adapter 라이선스
- 추론 라이브러리와 transitive dependency 라이선스
- 상업적 서비스 제공 가능 여부
- 생성 결과의 상업 이용 조건
- 모델 또는 데이터 출처 표시 의무
- 파생 모델 공개 의무
- 재배포 제한
- 지역 또는 사용 목적 제한

## 상업 이용 판정 상태

| 상태 | 의미 | 상업 기능 선택 |
|---|---|---|
| `research_only` | 연구·비상업 범위로만 허용 | 금지 |
| `commercial_review_pending` | 하나 이상의 근거·법률·배포 조건 검토가 미완료 | 금지 |
| `commercial_approved` | 대상 버전·데이터 계보·배포 방식의 상업 이용 검토 승인 | 허용 |
| `commercial_rejected` | 상업 이용 금지 또는 충족할 수 없는 조건 확인 | 금지 |

상업용 작업에서는 `commercial_approved`인 정확한 모델·가중치·Adapter·데이터 계보 조합만 선택한다. 사람의 출력 수정 여부는 이 판정을 변경하지 않는다. 모델이나 데이터 버전, 서비스 방식, 재배포 범위가 달라지면 기존 승인을 자동 승계하지 않고 재검토한다.

## DohaLM — [연동 계획 / 상업 사용 미승인]

2026-08-05 `DohaStudio/DohaLM`의 `develop` 문서를 확인했다. DohaLM은 별도 LLM 모델·추론 Provider이고 DohaMusic은 외부 Reference Application이다. REST/SSE MVP는 구현됐지만 Python SDK와 versioned release는 아직 계획 상태다.

| 대상 | 확인된 상태 | DohaMusic 판정 |
|---|---|---|
| `AIHUB-71748` 계열 데이터·파생 모델 | 학생·비상업 연구 범위, 상업 이용·원본 및 파생 데이터 재배포 미승인 | `research_only` |
| DohaLM Candidate B Foundation Base | 현재 연구 baseline, publication·상업 승인 근거 없음 | `research_only` |
| Qwen 계열 Base/Adapter Runtime 후보 | 승인된 Adapter artifact 없음, 개별 기반 모델·가중치·데이터 계보 검토 미완료 | `commercial_review_pending` |
| 향후 상업용 DohaLM release | 기반 모델·가중치·학습 및 파인튜닝 데이터·Adapter·Runtime을 버전 manifest로 고정해야 함 | `commercial_review_pending` |

따라서 현재 DohaLM 모델은 상업용 DohaMusic 작업에서 선택할 수 없다. 별도 상업용 release가 모든 검토 항목을 충족하고 `commercial_approved`로 승인될 때에만 production 후보로 평가한다. 이 판정은 현재 문서 근거에 대한 기술 검토이며 법률 자문이 아니다.

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

## Seed-VC

확인일은 2026-07-29이다.

| 대상 | 공식 근거 | 표시 | 기술 판정 |
|---|---|---|---|
| Seed-VC 코드 | [공식 GitHub](https://github.com/Plachtaa/seed-vc) | GPL-3.0, 2025-11-21 archive | 상업 이용 금지 라이선스는 아니나 복제·배포 시 GPL 의무 검토 필요 |
| 공식 가중치 | [Hugging Face 모델 카드](https://huggingface.co/Plachta/Seed-VC) | GPL-3.0 표시 | 배포 시 고지·대응 소스 범위와 transitive 구성 검토 필요 |
| 서버 전용 실행 | [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html.en) | GPL은 네트워크 사용만으로 배포 의무를 추가하지 않음 | SaaS 품질·법률 승인을 의미하지 않음 |

GPL-3.0은 상업적 이용을 금지하지 않는다. GNU FAQ에 따르면 수정한 GPL 프로그램을 웹 서버에서만 실행하고 사본을 배포하지 않으면 GPL만으로 소스 공개 의무가 발생하지 않는다. 반대로 바이너리·Docker·온프레미스 번들 등 사본을 조직 외부에 제공하면 해당 GPL 대상의 라이선스 고지와 대응 소스 제공을 포함한 의무를 검토해야 한다.

DohaMusic이 Seed-VC를 subprocess로 호출한다는 기술 사실만으로 두 프로그램의 법적 결합 여부를 확정하지 않는다. 상용 SaaS와 외부 배포는 코드·가중치·의존성 inventory, 제공 방식, 수정 내용과 사용자 권리를 확정한 뒤 법률 검토한다. 검토 전 상태는 `[배포 보류]`이며 이 문서는 법률 자문이 아니다.

## Phase 4.6 Voice 후보

| 후보 | 코드 | 평가 대상 가중치 | 상업 SaaS | 외부 배포 기술 판정 |
|---|---|---|---|---|
| Seed-VC | GPL-3.0 | GPL-3.0 표시 | 법률 검토 후 조건부 | GPL 대응 소스·고지 검토 |
| OpenVoice V1/V2 | MIT | 공식 README가 V1/V2 MIT 명시 | 가능 | MIT 고지와 transitive 구성 검토 |
| CosyVoice | Apache-2.0 | CosyVoice2-0.5B Apache-2.0 | 가능 | LICENSE·NOTICE·변경·특허 조항 검토 |
| Fish Speech | Fish Audio Research License | 동일 Research License | 별도 서면 계약 필요 | 별도 계약과 필수 표시 필요 |
| RVC | MIT | 공식 배포 모델 카드 MIT 표시 | 구성요소 검토 후 조건부 | encoder·vocoder·학습 데이터·사용자 checkpoint 권리 검토 |
| Amphion Vevo2 | MIT | CC BY-NC-ND 4.0 | 불가 | 상업 배포 불가, 별도 허가 필요 |

OpenVoice와 CosyVoice의 permissive 라이선스는 공식 Singing VC 지원을 의미하지 않는다. 반대로 Vevo2의 기술적 SVC 적합성은 비상업·변경금지 가중치 조건을 해제하지 않는다. 상세 시나리오와 공식 링크는 [Voice Provider 비교](voice-provider-comparison.md)를 따른다.

## Phase 5.1 Audio Mixer 의존성

확인일은 2026-07-29이다.

| 의존성 | 공식 근거 | 표시 | 기술 판정 |
|---|---|---|---|
| NumPy | [공식 License](https://numpy.org/doc/2.0/license.html) | BSD-3-Clause | 배포 고지 inventory에 포함 |
| SciPy | [공식 GitHub LICENSE](https://github.com/scipy/scipy/blob/main/LICENSE.txt) | BSD-3-Clause | bundled component 고지 포함 여부를 배포 artifact에서 재확인 |
| psutil | [공식 GitHub](https://github.com/giampaolo/psutil) | BSD-3-Clause | 배포 고지 inventory에 포함 |
| pyloudnorm 0.2.0 | [공식 GitHub](https://github.com/csteinmetz1/pyloudnorm) | MIT | K3.1 Integrated LUFS, 배포 고지 inventory에 포함 |

네 라이브러리는 모델·가중치 라이선스 문제를 추가하지 않지만, binary wheel과 transitive/bundled component의 고지는 실제 Docker·설치 번들 생성 시 다시 고정한다. 이 확인은 제품 전체의 법률 승인과 동일하지 않다.
