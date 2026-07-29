# Lyrics AI 아키텍처

> 문서 상태: [완료]
> 최종 수정일: 2026-07-29
> 관련 기능: Phase 6 Lyrics AI
> 관련 문서: [Lyrics API](../06-api/lyrics-api.md), [ADR-014](../11-decisions/ADR-014-lyrics-generator-architecture.md)

## 구조

```text
Lyrics API
  → LyricsService
  → LyricsGenerator Interface
      ├─ TemplateLyricsGenerator (기본)
      └─ MockLyricsGenerator
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
