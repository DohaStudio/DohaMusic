# Phase 6 Definition of Done — Lyrics AI

> 상태: [완료]
> 진행률: 14/14, 100%
> 최종 수정일: 2026-08-05
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-6-lyrics-ai--완료), [Generated Content Policy](../09-security/generated-content-policy.md)

## 목표

사용자 의도에서 한국어·영어 구조화 가사 초안을 안전하고 재현 가능하게 생성한다.

## 구현 범위와 포함 기능

`LyricsGenerator` Interface, Template·Mock Provider, 입력·출력 계약, 동기식 API·DB·Benchmark, 안전·자동 품질 검증을 포함한다. 외부 Lyrics 모델이나 API는 공식 근거·라이선스·데이터 처리·비용 검토 전까지 도입하지 않는다.

## 제외 기능

기존 곡 가사의 장문 복제, 외부 LLM, 권리 미확인 Dataset 학습, Pipeline 자동 연결, Doha Voice와 Frontend는 제외한다.

## 선행 조건

음악 생성 입력 계약과 콘텐츠 안전 정책을 확인했다. 외부 Provider를 추가할 때에는 별도의 공식 API·라이선스·데이터 처리 검토가 다시 필요하다.

## 완료 체크리스트

- [x] 외부 모델을 추측 도입하지 않고 향후 공식 API·라이선스·데이터 처리 검토 게이트 기록
- [x] 새 AI 모델·가중치·외부 서비스 의존성 미도입
- [x] `LyricsGenerator` Interface와 로컬 `TemplateLyricsGenerator`
- [x] `MockLyricsGenerator`와 `template`·`mock` Provider Factory
- [x] 주제·장르·분위기·키워드·언어·섹션·길이 schema와 입력 검증
- [x] 동기식 API·Service·Repository·`lyrics_documents` 연결
- [x] HTML·script·control 문자 제거, 입력 상한, 구조화 오류, 원문 미기록 로그 정책
- [x] 한국어·영어 생성·검증·저장·API Benchmark
- [x] 성공·실패·예외·영어·회귀 테스트
- [x] EXP-007·EVAL-005·ADR-014
- [x] API·Architecture·Database·Security·Operations 문서
- [x] CHANGELOG·README·ROADMAP·Master·DoD 갱신
- [x] 한국어 커밋·Push·`develop` PR·병합
- [x] 병합 후 회귀 검증과 `main` 무변경 확인

## 완료 조건

로컬 Template·Mock Provider, 한국어·영어 구조, 안전 검증과 Backend 저장·API 통합을 자동 검증했다. 실제 창작 품질과 의미 기반 자유 형식 수정은 EVAL-005 사용자 평가와 향후 외부 Provider 검토로 분리한다.

## 산출물

Lyrics Adapter·API·`lyrics_documents`·Benchmark·안전 평가·ADR-014·EXP-007·EVAL-005.

## 관련 문서·ADR·실험

- 문서: [Lyrics AI Architecture](../03-architecture/lyrics-ai.md), [Lyrics API](../06-api/lyrics-api.md), [Security Policy](../09-security/security-policy.md)
- ADR·실험: [ADR-014](../11-decisions/ADR-014-lyrics-generator-architecture.md), [EXP-007](../../reports/experiments/EXP-007-lyrics-generation.md), [EVAL-005](../../reports/evaluations/EVAL-005-lyrics-quality.md)

## 예상 다음 단계

Phase 7 Doha Voice와 Phase 8 Studio 우선순위를 재검토한다.
# Phase 6.5 확장 상태 (2026-08-05)

- Phase 6 로컬 Lyrics AI의 완료 상태는 유지한다.
- OpenAI 외부 Adapter·Factory·strict Schema·오류·retry·명시적 fallback·비용 metadata: `[Experimental 구현 완료]`
- DohaLM REST/Streaming Provider·가사 생성·분석·수정 제안·사용자 승인 연동: `[계획] 0%`
- DohaLM 일반 Chat REST/SSE MVP는 확인했지만 Python SDK·전용 Lyrics API·versioned manifest·DohaMusic Adapter·가사 승인 DB·Pipeline 연결은 미구현이다.
- `AIHUB-71748` 계열은 `research_only`이며 상업 작업에서 사용할 수 없다. 상업용 release는 전체 모델·데이터 계보가 `commercial_approved`일 때만 후보가 된다.
- 이 계획 문서화는 기존 Phase 6의 `14/14, 100%` 완료 판정과 OpenAI Experimental 구현 상태를 변경하지 않는다.

# Phase 6.6~6.9 Local Lyrics LLM 확장 상태 (2026-07-31)

- Phase 6의 Template·Mock API·Validator 완료 상태는 유지한다.
- Phase 6.6 Dataset, 6.7 Fine-tuning, 6.8 Provider Integration, 6.9 Quality Gate는 모두 `[계획] 0%`다.
- Base Model 미선정, Dataset 미구축, Training Script 미구현, QLoRA SFT 미착수, checkpoint 없음, Adapter 미구현, 품질 평가 미실시, 운영 미승인이다.
- Local Lyrics LLM 확장은 Phase 7 Doha Voice의 음성 개인화와 별개이며 Phase 8 Frontend 요청 계약을 변경하지 않는다.
- 세부 완료 기준은 [Local Lyrics LLM Roadmap](../../planning/local-lyrics-llm-roadmap.md)을 따른다. 문서 작성만으로 기존 14/14 Phase 6 DoD에 새 완료 증거를 추가하지 않는다.
- Revision API·원본 보존 버전 이력·Alembic 0006: `[구현 완료]`
- 실제 외부 네 시나리오·한국어 품질·지연·token·비용: `[사용자 승인 필요] [API Key 필요] [유료 실측 미수행]`
- 비용 상태: 실제 유료 API 호출 없음, 발생 비용 0원, API Key 사용 없음
- 기본 Provider: `template` 유지
- Stable 승격 및 Pipeline 연결: 미승인

K-POP Lyrics Template과 언어 비율·Hook 계약은 [KPopPromptCompiler 설계](../03-architecture/kpop-prompt-compiler.md)에 정의하지만 현재 `LyricsGenerator` 구현과 `template` 기본 Provider는 변경하지 않는다. Local Lyrics LLM은 별도 Phase 6.6~6.9 Track이다.
