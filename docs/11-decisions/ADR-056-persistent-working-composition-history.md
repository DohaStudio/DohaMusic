# ADR-056: Persistent WorkingComposition History Authority

> 상태: 승인
> 작성일: 2026-09-05
> 최종 수정일: 2026-09-05

## 배경

ADR-050의 Frontend 메모리 command stack은 새로고침과 재접속을 견디지 못한다. Gain, Fade,
Loop는 이미 Backend canonical state와 revision CAS를 갖고 있으므로 history payload 또한
Backend가 실제 mutation 전후에 캡처해야 한다.

## 선택지

- A. mutation log: redo cursor와 product history 경계가 불명확하다.
- B. mutable undo/redo stack: 동일 command를 중복 저장하고 두 stack 원자성이 필요하다.
- C. immutable journal + persisted cursor: 단일 순서, CAS, idempotency와 직접 결합된다.
- D. 전체 event sourcing: 현재 mutable composition을 대체하는 과도한 변경이다.

## 결정

선택지 C를 채택한다. `working_composition_history_entries`는 Backend가 캡처한 immutable
canonical before/after payload를 보존하고 `working_composition_history_states.cursor`가 적용된
prefix를 가리킨다. 새 forward command는 cursor 뒤 redo entries를 삭제한 뒤 append한다. 이는
감사 로그가 아니라 bounded product undo history이므로 redo 삭제는 허용한다.

초기 지원 command는 `CLIP_GAIN`, `CLIP_FADE`, `CLIP_LOOP`이다. 클라이언트는 history payload나
phase를 제출하지 않는다. undo/redo intent는 `expected_revision`과 `Idempotency-Key`를 요구하며,
state 적용, cursor 이동, revision 증가, completion 기록은 하나의 transaction이다.

Commit과 Checkout은 명시적 history barrier이다. 초기 지원 범위 밖 Track/Clip 구조 mutation도
barrier로 journal을 비운다. 이를 통해 부분 command 집합이 기존 strict LIFO 순서를 건너뛰는 것을
막는다. 지원 command target의 구조가 호환되지 않으면 mutation, cursor 이동, revision 증가,
completion 없이 fail closed 한다.

## 호환성

기존 WorkingComposition은 빈 history로 시작한다. ADR-053 Gain, ADR-054 Fade, ADR-055 Loop의
canonical state와 DSP 순서는 변경하지 않는다. Frontend production integration은 후속 작업이며
현재 메모리 history는 그대로 유지한다.

## 관련 작업

- Migration `20260905_0028`
- Authoritative NEXT: Persistent History Frontend Integration
