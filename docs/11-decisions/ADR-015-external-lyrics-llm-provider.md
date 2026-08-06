# ADR-015 — External Lyrics LLM Provider

> 상태: 승인(Experimental Adapter에 한함)
> 작성일: 2026-07-29
> 관련 브랜치: `feat/external-lyrics-llm-provider`

## 배경

Template은 계약·저장 흐름은 검증하지만 의미 기반 생성과 수정을 검증할 수 없다. 외부 후보의 품질·비용·지연·데이터 정책을 비교하면서 기존 `LyricsGenerator` 경계를 유지해야 한다.

## 후보 Provider

OpenAI, Google Gemini, Anthropic Claude, Alibaba Qwen API와 Qwen 로컬을 공식 자료로 비교했다. 한국어 가사 품질·수정 이해·속도는 Key 부재로 실측하지 않아 점수와 우열을 확정하지 않았다.

## 결정

OpenAI Responses API의 `gpt-5-mini-2025-08-07`을 검증용 `openai` Experimental Provider 하나로 구현한다. 기본 Provider는 `template`, 테스트 Provider는 `mock`으로 유지한다. Stable 또는 Primary 채택 결정이 아니다.

## 선택 이유와 비선정 이유

OpenAI는 strict JSON Schema, refusal, snapshot·가격, 데이터 통제 문서가 있어 Adapter의 구조화 경계를 검증하기 좋다. Gemini·Claude는 구조화 출력과 공식 API가 있으나 한 Provider만 구현한다는 범위 때문에 후속 비교로 남겼다. Qwen API는 JSON mode와 지역·정책 상세 검토가, 로컬 Qwen은 RTX 3060 Ti 8GB 성능 검증이 더 필요하다.

## Adapter 구조와 구조화 출력

`adapter → prompts → client → mapper → LyricsGenerationResult`로 캡슐화한다. Service와 API는 Provider 응답을 모른다. official strict JSON Schema를 먼저 사용하고, 제한된 복구는 바깥쪽 `json` code fence 제거만 허용한다. 그 뒤 언어·section 순서·빈 줄과 공통 Validator를 검사하며 실패는 `LYRICS_OUTPUT_INVALID`다.

## Retry, Fallback, 비용

일시적 timeout/network/일부 5xx/rate limit만 최대 1회, 전체 5초 deadline 안에서 재시도한다. 인증·요청 거부·콘텐츠 차단·invalid output은 재시도하지 않는다. fallback은 요청별 명시 허용 때만 Template로 가고 실제 Provider·사유를 metadata에 쓴다. token·request count·중앙 가격 설정 기반 예상 비용을 기록하며 가격 미설정은 null이다.

## 데이터·보안 영향

허용된 가사 입력만 전송하고 DB ID·경로·음성·개인정보·Key는 제외한다. `store=false`를 사용하고 원문 Provider 오류를 노출하지 않는다. OpenAI의 기본 abuse monitoring 보존과 승인형 ZDR 때문에 개인정보 운영 승인은 보류한다. 상업 이용·생성물 권리·지역·DPA는 법률 검토가 필요하다.

## Revision과 마이그레이션

`POST /api/lyrics/{id}/revise`는 새 `lyrics_documents` 버전을 만든다. Alembic 0006은 parent, version, instruction, 전후 hash를 추가하고 원본 덮어쓰기를 금지한다.

## 장단점

장점은 강한 구조 계약, 명시적 실패·비용 경계, Provider-neutral Service, 이력 보존이다. 단점은 네트워크·비용·제3자 데이터 처리, 아직 없는 실제 품질·지연 근거, 동기 5초 제한이다.

## 운영 승격 및 재검토 조건

EVAL-006, 실제 네 시나리오 benchmark, 비용 승인, ZDR/DPA·약관 검토, 인증·소유권, 장애·비동기 정책을 통과해야 Preview를 검토한다. 모델/가격/정책 변경, 5초 초과, 다른 후보 실측 또는 구조화 출력 변경 시 재검토한다.
