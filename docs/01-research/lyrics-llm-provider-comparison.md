# Lyrics LLM Provider 공식 자료 비교

> 조사일: 2026-07-29
> 상태: 외부 실측 전 조사 완료 / 가격 변동 가능 / 약관은 법률 검토 필요

## 평가 원칙

품질 20, 구조화 출력 15, 수정 이해 15, 비용 15, 속도 10, 데이터·개인정보 15, Backend 5, 공식 지원 5의 100점 체계를 사용한다. 한국어 가사 품질·수정 품질·응답 속도는 API Key가 없어 실측하지 못했으므로 점수를 부여하지 않는다. 따라서 현재 결과는 완전한 100점 순위가 아니라 공식 자료로 확인된 항목과 미측정 항목을 분리한 선정 근거다.

## 비교표

| Provider 후보 | 공식 구조화 출력 | 공개 가격 | 데이터 정책 | 한국어 가사·수정·속도 | 판단 |
|---|---|---|---|---|---|
| OpenAI `gpt-5-mini-2025-08-07` | Responses API strict JSON Schema, refusal | 입력 $0.25/M, cached $0.025/M, 출력 $2/M(조사일 공식 표) | API 데이터 기본 학습 제외, abuse monitoring log 최대 30일, 승인형 ZDR/MAM | `[실측 필요]` | Experimental 구현 |
| Google Gemini | JSON Schema 구조화 출력 | 무료·유료 tier별 동적 표 | 무료 tier는 제품 개선 사용, paid tier는 기본 미사용; logging 설정별 보존 | `[실측 필요]` | 비선정, 추후 비교 |
| Anthropic Claude | 공식 Structured Outputs | 모델별 동적 표 | API 기본 30일 이내 삭제, 계약형 ZDR | `[실측 필요]` | 비선정, 추후 비교 |
| Alibaba Qwen | JSON mode; strict Schema와 동일 보장은 아님 | 모델·지역별 동적 표 | FAQ는 학습 미사용을 명시하나 지역·보존·계약 상세 검토 필요 | `[실측 필요]` | 비선정, 정책 검토 필요 |
| Qwen 로컬 | 로컬 파서 구현 필요 | API token 비용 없음, GPU 운영비 별도 | 로컬 통제 가능 | RTX 3060 Ti 8GB 적합성 `[실측 필요]` | 이번 범위 제외 |

## 공식 출처

- OpenAI: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini), [Data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint)
- Google: [Structured output](https://ai.google.dev/gemini-api/docs/structured-output), [Pricing](https://ai.google.dev/gemini-api/docs/pricing), [Logs policy](https://ai.google.dev/gemini-api/docs/logs-policy)
- Anthropic: [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Data retention](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data)
- Alibaba: [Qwen structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output), [Model pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing), [Model Studio FAQ](https://www.alibabacloud.com/help/en/model-studio/faq-about-alibaba-cloud-model-studio)

## 선정 결론

OpenAI를 선택한 이유는 검증용 1개 Adapter에 필요한 strict JSON Schema와 명시적 refusal, 공개된 저비용 모델 snapshot, `store=false`와 데이터 통제 문서, 성숙한 HTTP/Python 적용 경계를 한 번에 검증할 수 있기 때문이다. 이는 품질 우승이나 운영 채택을 뜻하지 않는다. OpenAI의 확인 점수도 품질 20·수정 15·속도 10을 비워 둔 불완전 점수이며 EVAL-006과 실제 비용·지연 실측 전에는 Provider 간 최종 순위를 확정하지 않는다.

상업 SaaS·Docker·온프레미스·결과물 이용 조건은 각 서비스 약관과 지역·계약에 따라 달라질 수 있어 `[법률 검토 필요]`다. API를 쓴다는 사실만으로 생성물의 독창성이나 제3자 권리 비침해가 보장되지 않는다.
