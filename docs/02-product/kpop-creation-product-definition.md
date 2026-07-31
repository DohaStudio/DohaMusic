# K-POP 제작 제품 정의

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 기능: K-POP Creation Control Layer
> 관련 문서: [Generation Options](../03-architecture/kpop-generation-options.md), [Prompt Compiler](../03-architecture/kpop-prompt-compiler.md), [구현 Roadmap](../../planning/kpop-creation-roadmap.md)

## 제품 정의

DohaMusic은 사용자가 프롬프트·가사·K-POP 스타일을 설정하면 음악을 생성하고, 동의된 사용자 자신의 목소리로 보컬을 변환하여 완성 음원과 향후 숏폼 Hook을 제공하는 개인용 AI 음악 스튜디오다.

핵심 사용자는 직접 노래를 만들고 싶은 비전문 사용자, 자신의 목소리를 AI 음악에 적용하려는 사용자, K-POP Dance·Easy Listening·Performance 스타일을 빠르게 실험하려는 사용자다.

## 현재 제공 범위

- 30초 또는 60초 생성, 장르·분위기·Seed 선택
- 생성 가사 또는 직접 작성 가사
- 동의된 본인 목소리 등록·선택과 Pipeline 실행
- Cancel·Retry, History·Project, WAV 재생·다운로드
- Provider-neutral `MusicGenerator`와 Lyrics·Stem·Voice·Mixer 경계

기본 Music Provider는 `mock`, ACE-Step은 조건부 채택이며 운영 Provider는 미확정이다. Lyrics 기본 Provider는 `template`이다.

## 계획 범위와 비범위

K-POP 제어 계층은 Preset, 구조화된 Generation Options, Prompt Compiler, Capability, 평가 계약을 먼저 정의한다. 다음 항목은 아직 제공 기능이 아니다.

- 긴 곡과 세밀한 BPM 제어, 실제 BPM 분석
- Hook timestamp·15초 Preview, LUFS·True Peak 측정
- Post-Chorus·Dance Break의 모델 수준 보장
- 정확한 한국어·영어 비율 보장
- Style Fine-tuning·LoRA·Local Lyrics LLM 실행

문서상 `[계획]`인 항목을 Frontend에서 작동하는 제어처럼 노출하지 않는다.

## 제품 원칙

1. 특정 아티스트·곡·고유 문체를 모방하지 않는다.
2. 직접 창작하거나 권리를 확보한 가사·음원·스타일 데이터만 사용한다.
3. Voice 데이터는 명시적 동의를 받은 본인 데이터로 제한하고 Style·Lyrics 데이터와 분리한다.
4. Preset은 결과를 보장하는 모델 파라미터가 아니라 Provider-neutral 제작 의도다.
5. Provider Capability와 평가 근거 없이 운영 기본값으로 승격하지 않는다.
