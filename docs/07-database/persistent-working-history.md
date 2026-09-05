# Persistent WorkingComposition History Tables

> 문서 상태: [완료]
> 최종 수정일: 2026-09-05
> Migration: `20260905_0028`

`working_composition_history_states`는 WorkingComposition당 한 cursor를 저장한다. row가 없는 기존
WorkingComposition은 cursor 0인 빈 history와 같다.

`working_composition_history_entries`는 `(working_composition_id, sequence)` unique 순서를 가지며
`CLIP_GAIN`, `CLIP_FADE`, `CLIP_LOOP`의 Backend-captured canonical before/after JSON을 저장한다.
두 테이블은 WorkingComposition 삭제 시 cascade된다. 새 forward command는 redo suffix를 삭제하고
append한다. Commit, Checkout, 지원 범위 밖 mutation은 journal barrier다.

Migration은 additive이며 기존 composition, snapshot, preview, media row를 읽거나 변경하지 않는다.
