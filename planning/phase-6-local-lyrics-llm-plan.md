# Phase 6.6~6.9 Local Lyrics LLM 실행 계획

> 문서 상태: [계획]
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 6 후속 Local Lyrics LLM Dataset·Fine-tuning·Provider·Quality Gate
> 관련 문서: [Master Roadmap](../MASTER_ROADMAP.md), [Lyrics AI](../docs/03-architecture/lyrics-ai.md), [모델 선정 정책](../docs/04-models/model-selection-policy.md), [ADR-016](../docs/11-decisions/ADR-016-local-lyrics-llm-finetuning.md)

## 공통 방향과 범위

완료된 Phase 6의 Template·Mock 기반 Lyrics AI를 유지하면서 로컬 LLM을 선택적 후속 Provider로 검증한다. 공개 사전학습 Instruct LLM을 사용하고 Qwen 계열 1.7B~4B Instruct를 우선 후보로 검토한다. 1차 학습 방식은 QLoRA 기반 Supervised Fine-tuning이며 Full Fine-tuning은 RTX 3060 Ti 8GB에서 기본 전략으로 사용하지 않는다.

학습 입력은 `topic`, `genre`, `mood`, `keywords`, `language`, `structure`, `duration`, `additional_instructions`를 사용한다. 출력은 기존 `LyricsGenerator` 공통 결과 계약과 JSON Schema, `LyricsValidator` 규칙을 준수해야 한다. 결과 모델은 향후 `local_llm` Provider Adapter로 격리하며 모든 품질·권리·성능 게이트 전까지 기본 Provider는 `template`, OpenAI Adapter는 `Experimental`을 유지한다.

## 데이터 정책

- 직접 작성하거나 사용 권한을 확보한 가사를 우선한다.
- 상업 가사를 무단 수집하거나 학습에 사용하지 않는다.
- 각 record에 출처, 라이선스, 권리 상태, 수집·작성일, 가공 이력과 삭제 식별자를 기록한다.
- exact·near duplicate와 동일 곡 파생본을 제거하거나 연결한다.
- Train·Validation·Test를 분리하고 동일 작품군이 split 사이에 섞이지 않게 한다.
- 원본 데이터와 정제·구조화·증강한 가공 데이터를 별도 위치와 manifest로 구분한다.
- 합성 데이터는 생성 모델·버전·입력·sampling·후처리 등 생성 조건을 기록하고 사람 작성 데이터로 표시하지 않는다.
- 개인 음성 데이터와 가사 학습 데이터는 저장 위치·접근 권한·계보·삭제 절차를 분리한다.

## 공통 품질 평가 기준

| 분류 | 평가 항목 | 판정 방법 |
|---|---|---|
| 계약 | JSON Schema 준수율 | 전체 생성 중 schema parsing과 필수 필드 검증 성공 비율 |
| 계약 | `LyricsValidator` 통과율 | 오류 없이 공통 Validator를 통과한 비율과 warning 분포 |
| 언어 | 한국어 문장 자연스러움 | 블라인드 사용자 평가와 대표 실패 사례 기록 |
| 의도 | 주제 적합성 | topic·keywords가 중심 내용에 반영된 정도 |
| 의도 | 장르 및 분위기 반영 | genre·mood 요구와 어휘·서사·리듬의 일치도 |
| 창작성 | 후렴 기억성 | chorus의 기억성·구별성 사용자 평가 |
| 안전성 | 반복 과다 여부 | 반복 비율·Validator warning·수동 판정 |
| 구조 | 섹션 구조 정확성 | 요청 structure의 순서·필수 섹션·태그 일치율 |
| 수정 | 수정 지시 반영률 | `additional_instructions`와 revision 요구 반영 성공률 |
| 비교 | Provider 상대 평가 | 동일 입력·평가표로 Template, OpenAI Experimental, Local LLM 블라인드 비교 |
| 성능 | 응답 시간 | cold·warm p50/p95와 출력 길이 조건 기록 |
| 자원 | VRAM 사용량 | 학습·추론 최대 allocated/reserved VRAM과 OOM 경계 |
| 안정성 | 추론 안정성 | 반복 성공률, invalid output, timeout, OOM, 복구와 메모리 해제 기록 |

수치 합격선은 Dataset과 baseline 측정 후 Phase 6.9 시작 전에 확정한다. 측정하지 않은 값은 `[검증 필요]`로 남기며 문서 계획만으로 완료 처리하지 않는다.

## Phase 6.6 — Local Lyrics LLM Dataset

### 목적

한국어 중심 Lyrics SFT와 독립 평가에 사용할 권리 추적 가능하고 재현 가능한 Dataset을 정의·구축한다.

### 선행 조건

- 데이터 schema와 허용 출처 승인
- 생성 콘텐츠·저작권·삭제 정책 검토
- 기존 Lyrics 입력 8종과 출력 section 계약 확정

### 주요 작업

- 원본·가공·합성 record schema와 provenance manifest 정의
- 직접 작성·권리 확보 데이터 수집 및 권리 증적 연결
- 정제·section 구조화·언어 판정·중복 제거 규칙 수립
- 작품군 기준 Train·Validation·Test 분리와 leakage 검사
- 금지 데이터·삭제 요청·권리 미확정 격리 절차 정의

### 산출물

- Dataset Card와 권리·출처 manifest
- 원본/가공 데이터 디렉터리·버전 정책
- split manifest와 중복·leakage 검사 보고서
- 학습 입력·출력 JSON Schema 예시

### 완료 기준

- 모든 record의 출처·라이선스·권리 상태와 가공 계보 확인
- 상업 가사 무단 수집 데이터 0건 확인
- 작품군 단위 Train·Validation·Test 분리 및 중복 검사 통과
- 합성 데이터 생성 조건과 원본/가공 구분 검토 완료
- 개인 음성 데이터와 물리적·논리적 분리 확인

### 위험 요소

- 한국어 가사 권리 확보 데이터 부족
- 합성 데이터 편향과 표현 다양성 저하
- near duplicate 또는 파생본의 평가 split 유출
- 권리 철회 시 파생 Dataset·Adapter 추적 어려움

### 보류 조건

- 출처나 상업 이용 권리가 불명확한 record가 학습 후보에 포함됨
- split leakage·중복 제거 기준이 재현되지 않음
- 삭제·계보 추적이 불가능함
- 목표 학습·평가 규모를 안전한 데이터로 확보하지 못함

## Phase 6.7 — Local Lyrics LLM Fine-tuning

### 목적

승인된 Dataset과 공개 Instruct 기반 모델로 RTX 3060 Ti 8GB에서 재현 가능한 QLoRA SFT baseline을 검증한다.

### 선행 조건

- Phase 6.6 완료
- 후보 모델 코드·가중치·Tokenizer 라이선스와 상업 이용 검토
- GPU·학습 환경, seed, checkpoint·log 보관 정책 승인

### 주요 작업

- Qwen 계열 1.7B~4B Instruct 후보의 버전·context·한국어·8GB 실행성 비교
- 4-bit quantization, LoRA target, rank, batch, accumulation, sequence length 후보 설계
- 고정 seed baseline·학습·Validation과 checkpoint 선택 절차 실행
- 시간·VRAM·loss·오류·재시작·산출물 hash 기록
- 과적합·암기·평가 Dataset 오염과 금지 구문 점검

### 산출물

- 고정된 기반 모델 후보와 라이선스 검토 기록
- 재현 가능한 학습 설정과 실험 보고서
- QLoRA Adapter checkpoint와 hash
- Model Card 초안과 제한 사항

### 완료 기준

- RTX 3060 Ti 8GB에서 승인된 설정의 학습 완료와 OOM 경계 기록
- Validation 지표·학습 시간·최대 VRAM·환경·seed·hash 기록
- Test split 미사용과 학습 데이터 계보 확인
- baseline 대비 구조·Validator 지표 악화 여부 판정
- checkpoint·log에 비밀·개인 음성·금지 데이터가 없음을 확인

### 위험 요소

- 8GB VRAM OOM, 지나친 학습 시간과 불안정한 quantization
- 소규모 Dataset 과적합·가사 암기·표현 단조화
- 기반 모델 또는 파생 Adapter 배포 라이선스 충돌
- 한국어 tokenizer 효율과 긴 구조 출력 한계

### 보류 조건

- 모델·가중치·데이터 라이선스 승인 실패
- 안전한 batch·sequence 조건에서도 반복 OOM 또는 재현 실패
- baseline보다 Validator·구조 성능이 악화됨
- 암기·권리 침해 또는 Test leakage 징후 발견

## Phase 6.8 — Local Lyrics Provider Integration

### 목적

검증용 QLoRA 모델을 기존 API 동작을 바꾸지 않고 `LyricsGenerator` 경계의 명시적 `local_llm` Provider로 연결한다.

### 선행 조건

- Phase 6.7 기술·권리 검증 완료
- 모델 runtime 격리·로드/해제·오류·timeout 설계 승인
- 기존 결과 계약과 `LyricsValidator` 회귀 기준 확정

### 주요 작업

- 입력 8종의 prompt mapper와 구조화 출력 mapper 설계
- `local_llm` Adapter·Provider Factory의 명시적 opt-in 연결
- JSON Schema·Validator·오류 코드·metadata·모델 버전 계약 검증
- cold/warm load, GPU 해제, timeout, OOM과 invalid output 처리
- Template 기본값·OpenAI Experimental·Pipeline 비연결 회귀 확인

### 산출물

- `local_llm` Adapter와 격리 runtime
- 단위·통합·오류·회귀 테스트 결과
- 설정·운영 문서와 Model Card
- 추론 benchmark 초안

### 완료 기준

- 기존 API·DB·`LyricsGenerator` 결과 계약 호환
- 모든 출력의 공통 Validator 재검증과 안전한 오류 변환
- Provider를 명시하지 않으면 `template`이 선택됨
- `local_llm`이 Pipeline 자동 연결·암묵적 fallback에 참여하지 않음
- GPU load·release, timeout, OOM, 반복 추론 결과 기록

### 위험 요소

- 모델 runtime 의존성 충돌과 프로세스 메모리 누수
- 구조화 출력 실패·긴 응답·동기 API 5초 초과
- 모델 고유 형식이 Service/API로 누출되는 결합
- Adapter 선택 오류로 기본 Provider가 바뀌는 회귀

### 보류 조건

- 공통 결과 계약 또는 Validator를 우회해야 함
- 기본 `template` 동작이나 기존 API 호환성이 깨짐
- 5초 초과 호출에 대한 비동기 경계가 결정되지 않음
- 반복 OOM·메모리 해제 실패·안전하지 않은 오류 노출

## Phase 6.9 — Local Lyrics Quality Gate

### 목적

Local LLM의 계약·한국어 창작 품질·성능·안정성을 동일 조건에서 비교하고 운영 Provider 승격 여부를 판정한다.

### 선행 조건

- Phase 6.8 Adapter와 재현 가능한 Test Dataset 완료
- 평가 prompt·blind rubric·성능 측정 환경 고정
- OpenAI 유료 호출이 포함되면 API Key·비용·데이터 정책 승인

### 주요 작업

- 공통 품질 평가표의 자동 지표와 사용자 블라인드 평가 실행
- Template·OpenAI Experimental·Local LLM 동일 입력 비교
- 수정 지시·구조·장르·분위기·한국어 자연스러움 실패 분석
- cold/warm 응답 시간·VRAM·반복 성공·OOM·복구 측정
- Stable·기본 Provider·운영 Pipeline 승격 또는 보류 결정

### 산출물

- 품질 평가 보고서와 실패 사례
- Provider 비교표와 성능·자원 benchmark
- 최종 Model Card·운영 제한·rollback 기준
- Provider 승격 또는 보류 ADR 후속 결정

### 완료 기준

- JSON Schema·Validator·구조·수정 반영률 측정 완료
- 한국어 자연스러움·주제·장르·분위기·후렴·반복 사용자 평가 완료
- 세 Provider 비교 또는 OpenAI 제외 사유 기록
- 응답 시간·VRAM·반복 안정성·OOM·복구 측정 완료
- 데이터·모델 라이선스와 운영 보안 검토 완료
- 승격 여부를 근거와 함께 명시하고 미승격 시 `template` 기본값 유지

### 위험 요소

- 평가자 수·Dataset 규모 부족과 주관성
- benchmark 조건 불일치 또는 외부 API 모델 변경
- 품질 향상 대비 지연·VRAM·운영 복잡도 증가
- 안전·권리 문제를 자동 지표가 탐지하지 못함

### 보류 조건

- 필수 지표나 사용자 평가가 누락됨
- Template 대비 명확한 효익이 없거나 안정성·자원 기준 미달
- 라이선스·데이터 권리·보안 검토 미완료
- rollback·명시적 선택·장애 처리 정책 미확정

## 현재 금지 사항

이 계획 문서 단계에서는 코드·학습 스크립트·의존성·환경 변수·모델 파일을 추가하지 않고 모델을 다운로드하거나 학습·추론을 실행하지 않는다. 기존 API, Provider Factory, Pipeline 동작도 변경하지 않는다.
