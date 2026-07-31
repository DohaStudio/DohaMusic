# Local Lyrics LLM Roadmap

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 Phase: 6.6~6.9
> 관련 문서: [ADR-016](../docs/11-decisions/ADR-016-local-lyrics-llm-finetuning.md), [Lyrics Architecture](../docs/03-architecture/lyrics-ai.md), [Dataset Policy](../docs/05-data/lyrics-dataset-policy.md), [Model Card](../docs/04-models/local-lyrics-llm-model-card-template.md)

## 현재 상태

Base Model 미선정, Dataset 미구축, Training Script 미구현, QLoRA SFT 미착수, checkpoint 없음, `LocalLyricsLLMAdapter` 미구현, 품질 평가 미실시, 운영 미승인이다. Qwen 계열 1.7B~4B Instruct는 우선 검토 후보이며 확정 모델이 아니다.

## Phase 6.6 — Local Lyrics Dataset

### 목적

한국어 중심 학습·평가에 사용할 권리 추적 가능하고 삭제·재현 가능한 text Dataset을 구축한다.

### 선행 조건

- Dataset schema·허용 출처·권리 검토 절차 승인
- 사용자 입력 opt-in과 삭제 요청 정책 확정
- Lyrics 입력·section·Validator 계약 고정

### 주요 작업

- 직접 작성·허가·허용 라이선스·추적 가능한 합성 가사 수집
- 출처·권리·동의·삭제 상태와 Dataset manifest/version 기록
- 원본·가공본 분리, 정제·중복 제거·section 구조화
- 언어·장르·분위기·구조 분포 측정
- 작품 group 단위 Train·Validation·Test 분리와 leakage 검사
- 개인 정보·사용자 입력·Phase 7 음성 Dataset 격리

### 완료 기준

- 모든 record의 출처·권리 상태 기록과 미확인 상업 가사 제거
- split·중복·leakage·schema 검증 완료
- Dataset Card와 삭제·version 절차 승인

### 산출물

Dataset Card, record·rights manifest, 원본/가공 version, split·duplicate·leakage 보고서.

### 위험 요소

권리 확보량 부족, 합성 편향, 작품 파생본 leakage, 철회 시 checkpoint 영향 추적 실패.

### 보류 조건

권리 미확정, 약관 위반 수집, 삭제 불가, leakage 또는 안전한 규모 미달.

## Phase 6.7 — Local Lyrics LLM Fine-tuning

### 목적

승인 Dataset과 공개 Instruct Base 후보로 RTX 3060 Ti 8GB에서 재현 가능한 QLoRA SFT baseline을 만든다.

### 선행 조건

- Phase 6.6 완료와 Dataset version 동결
- Base code·weight·Tokenizer license 승인
- 학습 환경·checkpoint·실험 기록·삭제 정책 승인

### 주요 작업

- Base 후보의 한국어·8GB·QLoRA·VRAM·license·배포·Tokenizer 호환 비교
- QLoRA SFT 설정: seed, batch, sequence length, learning rate, epoch, LoRA rank·alpha·dropout, quantization 기록
- checkpoint·hash, 실패·OOM·재시작, Validation loss와 재현 명령 기록
- Dataset version 연결과 Model Card 초안 작성

### 완료 기준

- 학습 명령·환경·설정 재현 가능
- checkpoint 또는 LoRA Adapter와 Validation loss 산출
- Dataset version·hash 연결과 Model Card 초안 완료

### 산출물

후보 비교표, 고정 학습 설정·명령·실험 보고서, checkpoint/LoRA hash, Validation 결과와 Model Card 초안.

### 위험 요소

OOM·긴 학습 시간, quantization 품질 저하, 과적합·암기·표현 단조화, 파생 모델 license 충돌.

### 보류 조건

license 미승인, 반복 OOM, 재현 실패, 암기·leakage 또는 baseline 악화.

## Phase 6.8 — Local Lyrics Provider Integration

### 목적

검증 학습 산출물을 API 변화 없이 `LyricsGenerator` 경계의 명시적 `local_llm` Provider 후보로 연결한다.

### 선행 조건

- Phase 6.7 checkpoint·license·Model Card 초안 승인
- runtime 격리·model/adapter path·load/unload·timeout 정책 결정
- 기존 API·Validator 회귀 기준 고정

### 주요 작업

- `LocalLyricsLLMAdapter`와 local inference runtime 경계
- Base model·Tokenizer·Adapter/model path 설정 계획
- 기존 `LyricsGenerator` 결과, Provider Factory와 공통 Validator 재사용
- timeout, OOM, invalid output와 안전한 오류·metadata
- Template·Mock 회귀 유지와 API 계약 무변경 확인

### 완료 기준

- 명시적 Local Provider 선택 시 격리 추론 가능
- 공통 Validator 통과와 안전 오류·metadata 기록
- Template·Mock 테스트와 API 계약 유지
- 승인 전 기본값 `template`, Pipeline 비연결 확인

### 산출물

Local Adapter·runtime, Provider Factory 연결, 안전 오류·metadata 계약, 자동·통합·회귀 검증 결과와 운영 설정 문서.

### 위험 요소

runtime 의존성 충돌, memory leak·OOM, 구조화 출력 실패, 동기 API 지연, 모델 형식의 Service 누출.

### 보류 조건

Service·Repository 대규모 변경, Validator 우회, API 파괴, runtime 격리·timeout·해제 실패.

## Phase 6.9 — Local Lyrics Quality Gate

### 목적

Local 후보의 계약·한국어 창작 품질·성능·안정성을 비교하고 운영 승격 또는 보류를 결정한다.

### 선행 조건

- Phase 6.8 Adapter와 동결 Test Dataset
- 평가 rubric·임계값·실행 환경·blind 평가자 확정
- OpenAI 비교 호출 시 비용·데이터 정책 승인

### 평가 항목

- JSON 구조 준수율, LyricsValidator 통과율, 빈 출력 비율
- section 구조 정확도, 문장 길이, 과도 반복
- 한국어 자연스러움, 주제·장르·분위기·키워드 반영, 후렴 기억성, 수정 지시 반영률
- 응답 시간, VRAM·peak VRAM, 추론 실패율, 재현성
- Template·OpenAI Experimental 비교와 사용자 blind 평가

### 운영 승인 조건

- Dataset·모델 license와 데이터 권리 승인
- 품질 임계값과 RTX 3060 Ti 또는 승인 환경 안정성 통과
- 오류 처리, Model Card, rollback·Template fallback 검증
- 사용자 평가·보안 검토·운영 책임자 승인

### 산출물

자동 평가·성능 benchmark, Template/OpenAI/Local 비교표, 사용자 blind 평가, 최종 Model Card와 승격·보류 결정.

### 위험 요소

평가 표본 부족·주관성, 외부 비교 모델 변경, 품질 대비 지연·VRAM 증가, 자동 지표가 권리·안전 문제를 놓치는 위험.

### 보류 조건

필수 평가 누락, 품질·자원 기준 미달, 권리·보안 미승인, rollback 불가.

## K-POP Creation Track과의 경계

K-POP Lyrics Template·Hook·언어 비율은 초기에는 Prompt Compiler 계약이며 Local Lyrics LLM 학습 완료를 전제로 하지 않는다. Local Lyrics LLM Dataset은 Music Style LoRA와 개인 Voice Dataset과 분리하고, K-POP 제어 계층이 생겨도 Phase 6.6~6.9의 권리·품질 Gate를 생략하지 않는다.
