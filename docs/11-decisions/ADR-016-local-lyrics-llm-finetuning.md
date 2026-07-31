# ADR-016 — Local Lyrics LLM Fine-tuning

> 상태: 계획 승인, 구현 보류
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 6.6~6.9 Local Lyrics LLM
> 관련 문서: [Lyrics AI](../03-architecture/lyrics-ai.md), [모델 선정 정책](../04-models/model-selection-policy.md), [실행 계획](../../planning/phase-6-local-lyrics-llm-plan.md)

## 배경

Phase 6은 외부 통신 없는 `template`·`mock` Provider와 공통 `LyricsGenerator`·`LyricsValidator` 계약으로 완료됐다. Phase 6.5의 OpenAI Adapter는 의미 기반 생성 가능성을 검증하는 `Experimental` 경로지만 비용·제3자 데이터 처리·네트워크 의존성이 있다. 한국어 중심 가사 품질을 로컬에서 검증하면서 기존 경계를 유지할 후속 경로가 필요하다.

## 문제

RTX 3060 Ti 8GB 환경에서 어떤 기반 모델과 학습 방식을 우선할지, 학습 데이터 권리를 어떻게 통제할지, 결과를 기존 Lyrics API와 어떻게 호환할지 결정해야 한다. 모델 후보나 문서 계획만으로 운영 Provider 승격 또는 품질 완료를 주장해서는 안 된다.

## 결정

1. 직접 LLM 구조를 새로 설계하지 않는다.
2. 공개된 사전학습 Instruct 모델을 가져와 파인튜닝한다.
3. 우선 검토 후보는 Qwen 계열 1.7B~4B Instruct이며 최종 모델명은 확정하지 않는다.
4. 1차 학습 방식은 QLoRA 기반 Supervised Fine-tuning이다.
5. 결과 모델은 기존 `LyricsGenerator` Adapter 경계와 `LyricsValidator` 규칙을 유지하는 `local_llm` Provider 후보로 연결한다.
6. 검증 전에는 운영 Pipeline에 자동 연결하지 않고 기본 Provider `template`을 유지한다.
7. Full Fine-tuning은 RTX 3060 Ti 8GB 환경의 기본 전략으로 사용하지 않는다.

## 선택 이유

사전학습 Instruct 모델은 새 기반 모델 설계·사전학습보다 데이터·연산 요구량이 작고 지시 입력과 구조화 출력에 적합하다. QLoRA SFT는 전체 가중치 학습보다 VRAM 요구량을 낮추면서 학습 결과를 분리된 Adapter로 관리할 수 있다. 기존 `LyricsGenerator` 경계는 Service·API·DB가 모델 구현에 종속되는 것을 막고 Template·OpenAI Experimental과 동일한 Validator·평가 기준을 적용하게 한다.

## 대안

- Full Fine-tuning: 8GB VRAM, 학습 시간, checkpoint 크기와 안정성 근거가 없어 기본 전략에서 제외한다.
- 기반 LLM 직접 설계·사전학습: 데이터·연산·검증 비용이 현재 범위를 초과해 제외한다.
- Prompt-only 로컬 모델: baseline으로 비교할 수 있으나 한국어 가사 특화 학습 목표를 충족하는 최종 방식으로 확정하지 않는다.
- 외부 API만 사용: 빠른 품질 비교에는 유용하지만 비용·네트워크·데이터 처리 의존성을 해소하지 못해 OpenAI Adapter를 Experimental 비교군으로 유지한다.
- 다른 공개 Instruct 계열: 라이선스·한국어 품질·8GB 실행성이 더 우수하다는 근거가 생기면 후보군에 추가한다.

## 장점과 단점

장점:

- 로컬 추론으로 외부 전송과 호출 비용을 줄일 가능성이 있다.
- QLoRA Adapter를 기반 모델과 분리해 실험·교체·rollback을 추적할 수 있다.
- 공통 계약과 Validator로 기존 Template·OpenAI 결과와 직접 비교할 수 있다.

단점:

- 8GB VRAM에서 sequence length·batch·quantization 제약과 OOM 위험이 있다.
- Dataset 품질과 권리 상태가 결과 품질 및 배포 가능성을 제한한다.
- JSON Schema 준수, 한국어 자연스러움과 수정 지시 반영이 학습만으로 보장되지 않는다.
- 로컬 모델 배포 시 기반 모델·Adapter·학습 데이터의 고지와 라이선스 조합을 관리해야 한다.

## 데이터 및 라이선스 위험

- 직접 작성하거나 명시적 사용 권한을 확보한 가사를 우선하고 상업 가사를 무단 수집·학습하지 않는다.
- 데이터별 출처, 라이선스, 권리 상태, 가공 이력과 삭제 가능 식별자를 기록한다.
- 중복 제거 후 Train·Validation·Test를 분리하며 같은 곡·파생본이 split을 넘나들지 않게 한다.
- 원본과 가공 데이터를 구분하고 합성 데이터에는 생성 모델·버전·prompt·sampling 등 생성 조건을 기록한다.
- 개인 음성 데이터와 가사 학습 데이터를 저장·권한·삭제 정책에서 분리한다.
- 기반 모델 코드·가중치와 QLoRA Adapter의 상업 이용·재배포·파생물 조건은 학습 전에 별도 승인한다.

## 운영 Provider 승격 조건

`local_llm`은 다음 조건을 모두 충족한 뒤에만 Stable 또는 기본 Provider 승격을 검토한다.

1. Dataset 계보·권리·split·중복 제거 감사 완료
2. 기반 모델과 학습·추론 의존성 라이선스 및 상업 이용 검토 완료
3. JSON Schema 준수율과 `LyricsValidator` 통과율 목표 충족
4. 한국어 자연스러움·주제·장르·분위기·후렴·반복·섹션·수정 지시 사용자 평가 승인
5. Template·OpenAI Experimental·Local LLM의 동일 조건 비교 완료
6. RTX 3060 Ti 8GB 응답 시간·최대 VRAM·반복 추론·OOM·복구 측정 완료
7. Model Card·Dataset Card·실험 보고서·rollback·명시적 Provider 선택 정책 완료

승격 전에는 `template`을 기본값으로 유지하고 Pipeline 자동 연결과 암묵적 fallback을 금지한다.

## 재검토 조건

- Qwen 후보의 공식 버전·라이선스·가중치 또는 지원 상태가 변경될 때
- 다른 1.7B~4B급 Instruct 모델이 한국어 품질이나 8GB 실행성에서 더 나은 근거를 제공할 때
- QLoRA가 목표 품질·구조 준수율·안정성을 달성하지 못할 때
- GPU 환경, 데이터 권리 정책, 기존 `LyricsGenerator` 계약 또는 `LyricsValidator` 규칙이 변경될 때
- 운영 Pipeline이 비동기 Lyrics Job, 다중 사용자 격리 또는 새로운 보안 경계를 요구할 때

## 마이그레이션

현재 구현 변경은 없다. 향후 Phase 6.8에서 `local_llm` Adapter를 명시적 opt-in으로 추가하고 기존 `template` 설정과 저장된 Lyrics 문서를 마이그레이션 없이 유지한다. 기본값 변경은 Phase 6.9 품질 게이트와 별도 승인 이후의 새 결정으로 다룬다.

## 관련 PR

- 문서 계획 PR: 생성 후 연결 필요
