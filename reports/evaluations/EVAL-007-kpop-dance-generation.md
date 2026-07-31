# EVAL-007: K-POP Dance Generation 평가 계획

> 상태: [계획]
> 작성일: 2026-07-31
> 최종 수정일: 2026-08-01
> 관련 문서: [Capability Matrix](../../docs/04-models/kpop-provider-capability-matrix.md), [K-POP Roadmap](../../planning/kpop-creation-roadmap.md), [EVAL-001](EVAL-001-ace-step-listening-evaluation.md), [EVAL-008](EVAL-008-audio-analysis-validation.md)

## 목적과 원칙

Korean Dance Pop을 DohaMusic의 대표 제품 평가 시나리오로 검증한다. Instrumental과 Korean Ballad는 보조 비교군으로 유지한다. 아직 실험·청취를 수행하지 않았으므로 결과와 점수를 기록하지 않는다.

## 공통 평가 항목

- 음질, 프롬프트 반영, 한국어 발음, 가사 일치
- 보컬 자연스러움, 실사용 가능성

## K-POP 전용 평가 항목

- 리듬 안정성, Kick·Bass, Dance Groove
- Energy 전개
- Verse·Pre-Chorus·Chorus 구분
- Hook 기억성, 첫 Chorus 도달 시간
- 한국어·영어 혼용의 자연스러움
- 춤 가능성
- Voice Conversion 입력 적합성

## 단계별 계획

| Stage | 조건 | 평가 | 상태 |
|---|---|---|---|
| 1 | 30초, 동일 Prompt, Seed 3개 이상, K-POP Dance, 0.6B LM 우선 후보 | 기본 리듬·음질·Prompt 반영 | [계획] |
| 2 | 60초, 동일 Prompt·Lyrics, Seed 3개 이상 | 구조·Hook·발음·가사 일치 | [계획] |
| 3 | 동의된 본인 Voice Conversion 적용 | 발음·음색·고음·빠른 가사·입력 적합성 | [계획] |
| 4 | BPM·Hook candidate·15초 Preview·True Peak | EVAL-008 후속 구현 후 자동·청취 평가 | [보류: K3.2~K3.4·True Peak 미구현, K3.1 LUFS 완료] |

K3.0에서 분석·평가 계약만 완료했다. `detected_bpm`, Hook/Chorus 시간과 confidence는 추정값이며 EVAL-008 검증 전 EVAL-007의 생성 품질 점수나 Provider 승격 근거로 사용하지 않는다.

## 점수 기준

1점은 사용 불가, 2점은 문제가 많음, 3점은 실험용 가능, 4점은 창작 활용 가능, 5점은 공개 검토 후보를 뜻한다. 5점을 Production 승인으로 해석하지 않는다.

운영 Provider 승격 제안 기준은 평균 4.0 이상, 치명 항목 2점 이하 없음, 한국어 발음 3.5 이상, Voice Conversion 적합성 3.5 이상, 파일 오류·데이터 유실 없음이다. 이는 제안 기준이며 인증·권리·운영 Gate를 대신하지 않는다.

## 기록 항목

Prompt·Lyrics hash, Provider·모델·버전, Seed, 요청·실제 길이, 실행 시간, VRAM, 출력 식별자, 평가자와 평가일을 기록한다. 음원 자체와 개인 음성 원본은 Git에 커밋하지 않는다.
