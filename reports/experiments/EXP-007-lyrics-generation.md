# EXP-007 — Lyrics Generation

> 실험일: 2026-07-29
> 작업 브랜치: `feat/lyrics-ai`
> 관련 구현: Phase 6 Template Lyrics Provider
> 외부 LLM·GPU·VRAM: 사용하지 않음

## 목적

Template Provider가 한국어·영문 입력을 구조화하고 Validator·SQLite 저장·HTTP API를 통과하는지 측정한다. 실제 LLM 품질이나 음악적 운율을 평가하지 않는다.

## 환경과 실행

- Windows 로컬 Backend, Python 3.12
- Provider: `template`, model `dohamusic-template-lyrics` 1.0
- 입력: ballad, warm and melancholic, 180초, keyword 3개
- 기본 구조 8개 section
- 명령: `python -m backend.scripts.benchmark_lyrics`
- 결과 파일: 없음. 임시 SQLite 문서는 benchmark 종료 시 삭제

## 결과

| 지표 | 한국어 | 영문 |
|---|---:|---:|
| 생성 시간 | 0.000037초 | 0.000213초 |
| 검증 시간 | 0.000256초 | 0.000165초 |
| 저장 시간 | 0.018901초 | 0.005556초 |
| 전체 생성 API | 0.027959초 | 0.011878초 |
| 검증 API | 0.002470초 | 0.002320초 |
| 글자 수 | 570 | 969 |
| 가사 줄 수 | 15 | 15 |
| section 수 | 8 | 8 |
| 자동 검증 | 통과, 경고 0 | 통과, 경고 0 |

## 대표 출력 구조

전문은 보고서에 복제하지 않는다. 두 언어 모두 `Verse → Pre-Chorus → Chorus → Verse → Chorus → Bridge → Final Chorus → Outro`를 생성했다. 한국어 대표 Verse는 topic과 첫 keyword를 사용한 두 줄짜리 규칙 기반 초안이었다.

## 제약과 결론

Template은 입력·Provider Factory·Schema·Validator·Repository·API 연결을 검증하는 scaffolding이다. 표본 1개씩의 warm/cold 편차가 섞인 단일 PC 결과이며 SLO가 아니다. 한국어 운율, 장르 적합성, 후렴 기억성과 독창성은 [EVAL-005](../evaluations/EVAL-005-lyrics-quality.md)의 사용자 평가 전까지 미확정이다.

향후 외부 LLM 연결은 공식 API, 라이선스, 입력 보존, 안전 정책, Token·비용 metadata와 한국어 품질 benchmark를 별도 검증한 후 Adapter로 추가한다.
