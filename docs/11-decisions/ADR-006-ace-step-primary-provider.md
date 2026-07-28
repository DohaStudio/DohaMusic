# ADR-006: ACE-Step 1차 음악 생성 Provider 채택

> 상태: **보류됨**
> 작성일: 2026-07-29
> 최종 수정일: 2026-07-29
> 관련 작업: Phase 2.5 품질·반복 추론 평가

## 배경과 문제

ACE-Step 1.5는 RTX 3060 Ti 8GB에서 Backend Adapter와 반복 추론에 성공했다. 제품 기본값으로 바꾸려면 기술 실행뿐 아니라 한국어 발음·가사 일치·음악성·후속 활용 가능성을 확인해야 한다.

## 결정

ACE-Step을 선택적 `ace_step` Provider로 유지하되 기본 Provider 채택은 보류한다. 기본값은 `DOHAMUSIC_MUSIC_GENERATOR=mock`으로 유지한다.

## 선택 이유

- 두 상주 suite 총 12/12 실행과 0.6B LM 1회가 성공했다.
- 같은 Seed는 고정 환경에서 PCM 수준 재현됐고 다른 Seed는 서로 다른 파형이었다.
- 모든 WAV가 48kHz stereo·20초·비무음·비클리핑 기계 검증을 통과했다.
- 사용자 청취 평가가 없어 한국어 발음·가사·음악 품질을 승인할 근거가 없다.
- 기술적 1차 라이선스 확인과 제품 법률 승인은 구분해야 한다.

## 대안

- 즉시 기본값 채택: 품질 근거가 없어 제외한다.
- ACE-Step Adapter 제거: 기술 검증과 선택 실행 가치가 있어 제외한다.
- 조건부 자동 fallback: 운영 복잡도와 품질 기준이 미정이라 보류한다.

## 장단점과 영향

Mock 기본값은 모델이 없는 개발 환경과 테스트를 안정적으로 유지한다. 사용자는 환경 변수를 명시해야 실제 ACE-Step을 실행한다. 반면 실제 제품 경로의 기본 동작 확정은 늦어진다.

API·DB 계약은 바뀌지 않는다. 0.6B LM도 Backend 기본 설정에 추가하지 않는다.

## 마이그레이션

현재 변경은 필요 없다. 채택 시 별도 변경에서 기본 설정, 설치 요구사항, startup health, fallback, 배포·라이선스 고지를 함께 갱신한다.

## 재검토 조건

- [EVAL-001](../../reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)의 필수 항목 완료
- 한국어 발음·가사·음악성의 합격 기준 합의
- 후속 음색 변환에 사용할 수 있다는 사용자 판정
- 법률·배포 검토 및 운영 실패 기준 확정

근거는 [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md)와 develop 대상 Phase 2.5 PR에서 추적한다.
