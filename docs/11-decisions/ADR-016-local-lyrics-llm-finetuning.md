# ADR-016 — 로컬 가사 LLM Fine-tuning

> 상태: 계획 승인, 저장소 책임은 ADR-028로 갱신
> 작성일: 2026-07-31
> 최종 수정일: 2026-08-05
> 관련 기능: Phase 6.6~6.9 Local Lyrics LLM
> 관련 문서: [Lyrics AI](../03-architecture/lyrics-ai.md), [Dataset Policy](../05-data/lyrics-dataset-policy.md), [Roadmap](../../planning/local-lyrics-llm-roadmap.md), [ADR-028](ADR-028-provider-runtime-artifact-contract.md)

## 배경

Phase 6은 `TemplateLyricsGenerator`·`MockLyricsGenerator`, API, Repository와 Validator를 완료했다. Phase 6.5 OpenAI Adapter는 외부 구조화 출력·수정·비용·지연 비교를 위한 Experimental이다. 장기 목표는 외부 API를 운영 기본값으로 고정하는 것이 아니라 권리 확보 가사로 적응한 Local Lyrics LLM 후보다. 전체 LLM 사전학습은 현재 범위 밖이다.

## 문제

외부 API 종속·비용·데이터 처리, 한국어 가사 품질, Base Model과 파생 모델 권리, RTX 3060 Ti 8GB 제약, Dataset 저작권, 추론 안정성과 유지보수 위험을 해결하면서 기존 Lyrics API를 보존해야 한다.

## 결정

1. LLM을 처음부터 설계·사전학습하지 않고 공개 사전학습 Instruct Base Model을 사용한다.
2. Base는 라이선스·상업 이용·재배포·파생 모델 조건을 승인한 뒤 선정한다.
3. 직접 제작하거나 명시적 학습 권리를 확보한 Dataset만 사용한다.
4. 1차 방식은 QLoRA SFT이며 Full Fine-tuning은 기본 전략에서 제외한다.
5. 산출물은 추적 가능한 LoRA Adapter 또는 별도 검증된 병합 모델이다.
6. DohaLM이 Dataset·Fine-tuning·Evaluation·Runtime을 소유하고, DohaMusic의 Provider Client가 결과를 기존 `LyricsGenerator` 계약으로 변환해 `LyricsValidator`를 재사용한다.
7. 승인 전 기본 Provider는 `template`, OpenAI는 비교용 Experimental을 유지한다.
8. 승인 전 Local Provider를 Pipeline에 자동 연결하지 않는다.

## 대안

- 처음부터 LLM 사전학습: Dataset·연산·검증 비용이 범위를 초과해 제외한다.
- 외부 OpenAI API만 사용: 빠른 baseline이나 비용·데이터·network 종속이 남아 비교용으로 제한한다.
- Prompt engineering만 사용: 학습 없는 baseline으로 유지 가능하지만 자체 domain adaptation 목표를 충족하지 않는다.
- Full Fine-tuning: 8GB 환경에서 기본 전략으로 부적합해 근거가 생길 때 재검토한다.
- Template만 유지: 안정적 fallback이지만 의미 기반 한국어 품질 확장을 제공하지 못한다.

## 장점

- 모델·데이터·추론을 로컬에서 통제할 가능성
- 외부 Provider 호출 비용 감소 가능성
- 한국어 가사 domain 적응
- 기존 API와 Validator 유지
- Base와 LoRA Adapter 교체·rollback 가능

## 단점과 위험

- Dataset 권리·삭제·계보 관리 비용
- 학습 품질 편차, hallucination, 과도 반복과 암기 위험
- 8GB GPU OOM·지연·quantization 품질 위험
- Base·Tokenizer·파생 모델 라이선스 조합
- runtime·checkpoint·평가·보안 유지보수
- 사용자 blind 평가와 법률 검토 비용

## 운영 승격 조건

- Dataset manifest·Card와 모든 권리 승인
- Base·Tokenizer·LoRA·병합 모델 license 승인
- JSON·Validator·한국어·구조·반복·수정 지시 Benchmark 통과
- RTX 3060 Ti 또는 승인 운영 환경의 응답 시간·peak VRAM·실패·복구 안정성 확인
- Model Card·오류 처리·보안 검토 완료
- 사용자 blind 평가와 운영 책임자 승인
- 기존 `template` rollback과 명시적 fallback 검증

## 재검토 조건

더 적합한 Base 등장, GPU 환경·라이선스 변경, 품질 미달, 추론 지연 과다, Dataset 권리 문제, 모델 배포 방식·`LyricsGenerator` 계약 변경 시 재검토한다.

## 마이그레이션

현재 구현·API·DB·Provider 기본값 변경은 없다. Phase 6.8에서만 DohaLM 외부 Provider를 명시적 Planned/Experimental 경로로 추가하며 Phase 6.9 승인 전 Stable·Pipeline 자동 연결을 금지한다. 기존 Fine-tuning 전략은 유지하지만 DohaMusic 내부 Runtime·checkpoint 경로를 추가하지 않는다.

## 관련 PR

- 문서 계획 PR: 생성 후 연결 필요
