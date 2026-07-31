# Lyrics AI 아키텍처

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 6 Lyrics AI
> 관련 문서: [Lyrics API](../06-api/lyrics-api.md), [ADR-014](../11-decisions/ADR-014-lyrics-generator-architecture.md), [ADR-016](../11-decisions/ADR-016-local-lyrics-llm-finetuning.md), [Local Lyrics LLM Roadmap](../../planning/local-lyrics-llm-roadmap.md)

## 구조

```text
Lyrics API
  → LyricsService
  → LyricsGenerator Interface
      ├─ TemplateLyricsGenerator (기본)
      ├─ MockLyricsGenerator
      ├─ OpenAILyricsGenerator [Experimental]
      └─ LocalLyricsLLMAdapter [Planned]
             → Local Inference Runtime
             → Fine-tuned Lyrics LLM
                = Base Instruct Model
                + DohaMusic LoRA Adapter
                + Tokenizer
  → Lyrics Validator
  → LyricsRepository
  → lyrics_documents
```

Provider는 DB와 FastAPI를 알지 않고 구조화된 초안만 반환한다. Service가 생성 결과를 다시 Validator로 검사한 뒤 Repository를 통해 저장한다. 외부 LLM SDK·API Key·Token·비용은 이번 구조에 없다.

## Provider

- `template`: topic·genre·mood·keywords·structure로 한국어 또는 영문 규칙 기반 초안을 만든다. 결정적 로컬 scaffolding이며 실제 LLM 품질을 의미하지 않는다.
- `mock`: 고정 출력으로 Interface·API·오류 경계를 검증한다.

환경 변수 `DOHAMUSIC_LYRICS_PROVIDER`의 기본값은 `template`이다. Provider를 추가할 때 Service나 Repository가 해당 SDK 응답을 직접 참조하지 않도록 Adapter 안에서 공통 결과로 변환한다.

## 검증 경계

Schema는 topic·keywords·structure·duration·instructions 길이와 지원 언어 `ko`, `en`을 제한한다. Validator는 제어 문자와 script/style·HTML을 제거하고 섹션을 파싱한다. 지원하지 않는 태그, 줄 길이, 빈 결과는 오류이며 후렴 누락·과도 반복·섹션 태그 누락은 경고다.

지원 섹션은 `intro`, `verse`, `pre_chorus`, `chorus`, `post_chorus`, `bridge`, `outro`, `final_chorus`다. 같은 섹션의 반복은 허용한다.

## 동기 처리 결정

Template·Mock은 로컬에서 수 ms 이내에 끝나므로 Job·Worker를 추가하지 않는다. 외부 LLM이 도입되어 5초 이상 걸리거나 재시도·rate limit·비용 추적이 필요해지면 비동기 `lyrics_generation_jobs`와 Queue 경계를 별도 ADR로 검토한다.

## Pipeline 경계

Phase 6 API는 Pipeline을 호출하지 않으며 Pipeline도 LyricsService를 호출하지 않는다. 향후 승인된 변경에서 `lyrics_id`, `raw_lyrics`, `generate_lyrics`, `lyrics_options` 중 필요한 계약을 선택한다. 현재 MusicGenerator와 Phase 5 Orchestrator 입력은 변경하지 않았다.

`additional_instructions`는 Provider 계약까지 전달하고 metadata에는 존재 여부만 남긴다. Template Provider는 자유 형식 지시의 의미를 이해하는 LLM이 아니므로 의미 기반 가사 재작성 품질을 주장하지 않는다.
# Phase 6.5 External Provider 확장

`openai` Experimental Adapter는 기존 `LyricsGenerator` 계약 아래 `adapter → prompts → client → mapper`로 격리된다. Responses API strict JSON Schema 결과도 공통 Validator를 다시 통과해야 저장된다. Service·Router는 Provider SDK 형식을 알지 않는다. 기본 Provider는 `template`다.

의미 기반 수정은 `RevisionCapableLyricsGenerator`의 선택 기능이다. 원본을 보존하고 parent/version과 전후 hash를 가진 새 문서를 만든다. 외부 Prompt에는 허용된 가사 필드만 넣고 내부 ID·파일·음성 데이터를 제외한다. 실패 fallback은 요청별 명시 허용 때만 Template로 전환한다.

## Phase 6.6~6.9 Local Lyrics LLM 목표 구조

```text
사용자 또는 Frontend
        ↓
FastAPI Lyrics API
        ↓
LyricsService
        ↓
LyricsGenerator Interface
        ├─ TemplateLyricsGenerator [Stable 기본값]
        ├─ MockLyricsGenerator [Test]
        ├─ OpenAILyricsGenerator [Experimental]
        └─ LocalLyricsLLMAdapter [Planned]
                ↓
        Local Inference Runtime
                ↓
        Fine-tuned Lyrics LLM
                ↓
        Base Instruct Model + DohaMusic LoRA Adapter + Tokenizer
        ↓
LyricsValidator
        ↓
LyricsRepository
        ↓
lyrics_documents
```

Provider SDK, Tokenizer, quantization, 추론 엔진과 모델 고유 출력은 `LocalLyricsLLMAdapter` 내부에서 기존 `LyricsGenerationResult`로 변환한다. `LyricsService`, Repository, API와 Frontend는 모델 구현을 알지 않는다. 모든 출력은 저장 전에 공통 `LyricsValidator`를 다시 통과한다.

DohaMusic은 LLM 구조를 처음부터 설계하거나 사전학습하지 않는다. 라이선스·상업 이용·재배포·파생 모델 조건을 승인한 공개 사전학습 Instruct LLM을 Base로 사용하고, 직접 제작하거나 학습 권한을 확보한 가사 Dataset으로 QLoRA SFT를 우선 검토한다. 최종 산출물은 LoRA Adapter 또는 별도 승인을 받은 병합 모델 후보다.

## Provider 상태

| Provider | 상태 | 목적 |
|---|---|---|
| `template` | Stable 기본값 | 결정적 로컬 가사 초안 |
| `mock` | Test | API·계약·오류 테스트 |
| `openai` | Experimental | 외부 Provider 구조화 출력·수정·비용·지연 비교 |
| `local_llm` | Planned | 파인튜닝 자체 모델의 향후 연결 |

| Local Lyrics LLM 항목 | 현재 상태 |
|---|---|
| Base Model | 미선정 |
| Dataset | 미구축, 계획만 존재 |
| Training Script | 미구현 |
| QLoRA SFT | 미착수 |
| Checkpoint·LoRA Adapter | 없음 |
| Local Inference Adapter | 미구현 |
| 품질 평가 | 미실시 |
| 운영 승인 | 미완료 |

`openai`는 운영 기본 Provider나 Local Lyrics LLM의 Base Model이 아니며 DohaMusic 자체 모델을 의미하지 않는다. 비교 Benchmark 대상으로 유지한다. `local_llm`이 권리·품질·성능·보안 게이트를 통과하기 전에는 `template` 기본값을 변경하거나 Pipeline에 자동 연결하지 않는다.

## 학습 흐름

```text
공개 사전학습 Instruct LLM 후보 조사
→ 라이선스·상업 이용·재배포 조건 검토
→ Base Model 선정
→ 권리 확보 가사 수집·권리 상태 기록
→ 정제·중복 제거·구조화
→ Train / Validation / Test 분리
→ QLoRA 기반 SFT
→ Checkpoint·LoRA Adapter 저장
→ Offline Evaluation
→ Local Inference Benchmark
→ LyricsValidator 통과율 측정
→ 사용자 품질 평가
→ 운영 Provider 승인 또는 보류
```

우선 검토 후보는 Qwen 계열 1.7B~4B Instruct와 동급 한국어 지원 공개 Instruct 모델이다. 이는 최종 선정·설치·검증 완료를 뜻하지 않는다. 한국어 생성, RTX 3060 Ti 8GB 실행·QLoRA 가능성, 학습·추론 VRAM, 라이선스와 파생 모델 배포·상업 이용, Tokenizer·Transformers 호환성을 확인한 뒤 결정한다.

## Phase 7 Doha Voice와 분리

| 구분 | Local Lyrics LLM | Doha Voice |
|---|---|---|
| 대상 | 텍스트 가사 생성 | 사용자 가창 음색 개인화 |
| 데이터 | 권리 확보 가사 텍스트 | 동의된 사용자 음성 |
| Base | 공개 Instruct LLM | Voice Conversion·Singing Voice 모델 |
| 학습 | QLoRA SFT 후보 | 음성 모델 적응·Fine-tuning 후보 |
| 결과 | `LyricsGenerator` Provider | `VoiceConverter` Provider |

Dataset, checkpoint, Model Card, 저장 경로, 접근 권한과 동의·삭제 정책을 서로 분리한다.
