# EXP-008 — External Lyrics LLM

> 실험일: 2026-07-29
> 상태: **[외부 실측 차단] / Adapter 자동 검증 완료**
> Provider: OpenAI `gpt-5-mini-2025-08-07` Experimental

## 목적과 환경

OpenAI Adapter의 strict 구조 매핑, 수정, retry, fallback, 오류, 비용 metadata를 검증하고 한국어 발라드·시티팝·수정·영문 팝의 실제 품질·지연·비용 측정을 준비한다. Windows, Python 3.12에서 수행했다. `DOHAMUSIC_LYRICS_API_KEY`가 없어 실제 API를 호출하지 않았다.

## 조사와 선정

OpenAI, Gemini, Claude, Qwen API·로컬을 공식 자료로 조사했다. OpenAI를 JSON Schema 경계 검증용으로 선택했으며 품질 우승이나 운영 채택을 뜻하지 않는다. 공식 자료와 정책은 Provider 비교 문서에 링크했다.

## 실행 결과

| 항목 | 결과 |
|---|---|
| 실제 외부 호출 | `[차단]` Key 없음, 0회, 청구 없음 |
| 실제 한국어 발라드·시티팝·수정·영문 출력 | `[검증 필요]` |
| 실제 응답·검증·전체 시간 | `[실측 필요]` |
| 실제 input/output/cached token | `[실측 필요]` |
| 실제 예상 비용 | `null` |
| Mock transport Adapter benchmark | 100/100 성공 |
| Adapter-only latency | min 0.0209ms, mean 0.0315ms, max 0.1324ms |
| synthetic usage | input 100, output 50 token |
| synthetic 공식표 추정 | $0.000125, 청구액 아님 |

Mock transport 수치는 네트워크·Provider 추론을 포함하지 않으며 외부 응답 속도로 해석하지 않는다.

## 자동 검증과 수정

정상 응답은 언어, exact section 순서, 빈 section, line 타입, strict schema payload와 Validator를 통과했다. malformed JSON, 언어·순서·line 오류는 실패했다. Revision Prompt는 원문·지시·구조만 전송하고 로컬 ID·음성 정보를 제외했다. DB/API 테스트는 원본을 유지하고 version 2, parent, 전후 SHA-256을 만들었다. 실제 의미 반영 품질은 `[검증 필요]`다.

## Fallback과 오류

timeout/rate/network/일부 5xx만 retry한다. 명시 허용 시에만 Template fallback하고 metadata에 실제 Provider와 사유를 기록했다. timeout, rate limit, 인증, invalid output, 콘텐츠 차단 등은 안전한 내부 오류로 변환하도록 단위 테스트했다.

## 데이터·약관

Prompt는 허용 필드만 포함하고 `store=false`다. 공식 정책상 기본 보존과 승인형 ZDR가 존재하므로 운영 데이터 전송은 보류한다. 상업 SaaS·지역·DPA·생성물 권리는 `[법률 검토 필요]`다.

## 결론과 다음 작업

Adapter는 Experimental 상태로 유지하고 기본값은 Template다. EVAL-006 사용자 블라인드 평가, Key를 사용한 opt-in 네 시나리오 실측, 비용·지연 기록, 법률·개인정보 승인 후 Preview 승격을 검토한다.
