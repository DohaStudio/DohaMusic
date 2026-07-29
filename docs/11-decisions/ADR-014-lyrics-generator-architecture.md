# ADR-014 — Lyrics Generator Architecture

> 상태: 승인
> 작성일: 2026-07-29
> 최종 수정일: 2026-07-29
> 관련 PR: `feat/lyrics-ai` 작업 PR

## 배경

가사 생성과 직접 작성 가사 검증을 특정 LLM SDK나 Music Pipeline에 결합하지 않고 추가해야 한다. 현재는 승인된 외부 LLM, API Key, 라이선스·비용·개인정보 정책이 없다.

## 문제

외부 Provider를 추측 구현하면 지원 범위와 비용·Token·품질을 사실처럼 만들 위험이 있다. 반대로 고정 Mock만으로는 입력 Schema, 구조화, Validator와 저장 흐름을 현실적으로 검증하기 어렵다.

## 결정

1. Service가 의존하는 `LyricsGenerator` Interface와 공통 request/result/section 계약을 둔다.
2. `template`을 기본 Provider, `mock`을 테스트 Provider로 둔다.
3. Template은 외부 호출 없는 결정적 초안으로 명시하며 실제 LLM이나 음악적 품질을 주장하지 않는다.
4. Provider 결과는 독립 `LyricsValidator`로 다시 검사한 후 `lyrics_documents`에 저장한다.
5. 현재 Provider는 빠른 로컬 처리이므로 동기 API로 구현하고 `lyrics_generation_jobs`는 만들지 않는다.
6. Phase 5 Pipeline 입력은 변경하지 않고 Lyrics ID 연결은 후속 계약으로 남긴다.

## 선택 이유

Interface·Factory·Validator·Repository 경계를 먼저 검증하면서 외부 API와 비밀·비용·네트워크 실패를 도입하지 않는다. 직접 작성 가사와 Provider 출력에 같은 Validator를 적용해 Music Generation으로 전달할 형식을 일관되게 만든다.

## 대안

- 외부 LLM 즉시 연결: 공식 Provider 선정과 데이터·라이선스·비용·안전 검토가 없어 보류했다.
- Mock만 사용: topic·keyword·language별 구조 검증에 부족해 제외했다.
- 처음부터 비동기 Job: 현재 실행 시간에 비해 복잡도가 커 보류했다.
- Pipeline에 직접 삽입: Phase 5 안정성과 독립 모듈 원칙을 훼손하므로 제외했다.

## 장단점

장점은 오프라인 재현성, 빠른 테스트, Provider 교체성, 안전한 입력 경계다. 단점은 Template 결과가 의미 이해·운율·독창성을 보장하지 않고 자유 형식 수정 지시를 정교하게 반영하지 못한다는 점이다.

## 영향

Lyrics API와 `lyrics_documents` migration이 추가된다. Music·Stem·Voice·Mixer·Pipeline API와 DB 관계는 변경하지 않는다. 로그에는 전체 topic·가사·instructions를 남기지 않는다.

## 마이그레이션

Alembic `20260729_0005`가 독립 `lyrics_documents` 테이블을 생성한다. downgrade는 해당 인덱스와 테이블만 제거한다.

## 재검토 조건

외부 LLM 후보가 공식 API·라이선스·데이터 처리·비용·안전·한국어 품질 게이트를 통과하거나, 응답이 5초 이상 걸려 비동기 처리와 취소·재시도가 필요해질 때 재검토한다. Pipeline이 `lyrics_id`를 받게 될 때도 호환성 ADR을 검토한다.
