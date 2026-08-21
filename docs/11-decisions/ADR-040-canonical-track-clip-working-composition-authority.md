# ADR-040 — Canonical Track·Clip과 Working Composition 권위

> 상태: 승인
> 작성일: 2026-08-21
> 최종 수정일: 2026-08-21
> 관련 기능: AI-native DAW D3 Non-destructive Clip Editing
> 관련 문서: [ADR-035](ADR-035-d1-composition-read-authority.md), [CompositionSnapshot 기반](../06-api/composition-snapshot-foundation.md), [목표 아키텍처](../03-architecture/ai-native-daw-target-architecture.md), [Clip Domain DoD](../DoD/Clip-Domain-Persistence.md)

## 1. Context

현재 `CompositionSnapshot`은 Project의 exact `AssetVersion` 조합과 Mix·Provider·Model 계보를 고정하는 불변 aggregate다. `SnapshotItem`도 불변 membership/projection이며, `snapshot_item_id`는 한 Snapshot 안에서만 유효한 D1 Track read projection이다. 따라서 다음 편집을 기존 row의 in-place mutation으로 표현할 수 없다.

- Clip move·trim·split·delete
- Track reorder
- refresh 뒤 편집 상태 복원
- 명시적 저장·rollback·동시 수정 충돌
- 편집 결과를 새 불변 Snapshot으로 commit

현행 Backend·Frontend에는 canonical `track_id`, canonical `clip_id`, working edit persistence가 없다. Frontend의 `selectedTrackId`는 `projection_id == snapshot_item_id`를 사용하는 local UI state이고, 현재 Timeline duration과 Waveform은 단일 committed Master/Mix media에 종속된다.

## 2. Decision summary

DohaMusic product domain에 `WorkingComposition`, `CompositionTrack`, `CompositionClip` 세 aggregate 구성 요소를 도입한다. V1에서는 Project마다 현재 WorkingComposition을 하나만 허용한다.

```text
Project
  └─ current WorkingComposition (mutable, 1:1)
       ├─ CompositionTrack (mutable, 1:N)
       │    └─ CompositionClip (mutable, 1:N)
       │         └─ exact AssetVersion
       └─ base CompositionSnapshot (immutable, nullable)

WorkingComposition
  └─ explicit commit
       └─ new CompositionSnapshot + immutable SnapshotTrack/SnapshotClip
```

`WorkingCompositionRevision`, `EditOperation`, `EditHistory`를 별도 aggregate/table로 만들지 않는다. WorkingComposition의 정수 `revision`과 기존 `idempotency_records`로 V1 동시성·재시도 요구를 충족한다. Undo/Redo 명령 이력은 Frontend가 소유하고, 서버는 각 역연산이 반영된 최종 working state만 영속화한다.

이 ADR은 product-only Domain과 향후 API·logical schema를 승인한다. ORM, Alembic, Router, UI, 테스트 또는 Common Contract schema를 구현하지 않는다.

## 3. Domain model

### 3.1 WorkingComposition

- `working_composition_id`: 서버가 발급한 opaque UUID PK
- `project_id`: Project당 하나인 unique FK
- `base_composition_snapshot_id`: 편집을 시작했거나 마지막으로 commit한 같은 Project의 Snapshot, 빈 Project에서는 `null`
- `mix_settings`: mutable product mix 설정 JSON. D4 구현 전에는 빈 object
- `revision`: 0 이상 정수. 성공한 상태 mutation transaction마다 정확히 1 증가
- `created_at`, `updated_at`

WorkingComposition은 Project의 현재 mutable draft authority다. 여러 named draft나 branch는 V1에서 허용하지 않는다. 특정 Snapshot을 여는 명시적 checkout/revert는 기존 working rows를 한 transaction에서 교체하고 `base_composition_snapshot_id`를 갱신한다. GET, Snapshot 선택, 페이지 진입만으로 WorkingComposition을 생성하거나 바꾸지 않는다.

### 3.2 CompositionTrack

- `track_id`: 서버가 발급하고 Project의 Composition lineage 안에서 유지되는 canonical UUID
- `working_composition_id`: 소유 WorkingComposition
- `track_type`: V1 allowlist `audio`
- `name`: 사용자 표시 이름
- `track_order`: 0 이상의 정수. Track 세로 순서의 canonical authority
- `created_at`, `updated_at`, `deleted_at`

`track_id`는 move·trim·Track reorder와 Snapshot commit 뒤에도 유지한다. Project 전역의 다른 Composition branch를 포괄하는 identity는 아니다. V1은 Project당 WorkingComposition 하나이므로 scope는 해당 Project의 Composition lineage다. D1 `projection_id`나 `snapshot_item_id`를 `track_id`로 승격하지 않는다.

### 3.3 CompositionClip

- `clip_id`: 서버가 발급한 stable canonical UUID
- `working_composition_id`: same-composition 복합 FK를 위한 소유 ID
- `track_id`: 같은 WorkingComposition의 canonical Track
- `source_asset_version_id`: exact AssetVersion FK
- `timeline_start`: Timeline 배치 시작
- `source_in`, `source_out`: source 안의 반개구간 `[source_in, source_out)`
- `source_duration`: 생성 시 검증한 exact source media duration
- `split_from_clip_id`: split 직전 원본 Clip ID, 일반 생성은 `null`
- `created_at`, `updated_at`, `deleted_at`

Domain/API 이름은 초 단위 `timeline_start`, `source_in`, `source_out`, `source_duration`을 사용한다. DB 구현은 부동소수 누적 오차를 피하기 위해 동일 이름의 값을 정수 microseconds로 저장하거나 동등한 exact fixed-point 형식을 사용해야 한다. public DTO의 decimal seconds 변환은 경계에서 수행한다.

Clip은 generic timeline region으로 유지하되 V1 eligibility는 audio AssetVersion만 허용한다. `AudioClip`과 `MidiClip` subclass/table은 지금 만들지 않는다.

## 4. Mutable / immutable boundary

| 구분 | 객체 | 정책 |
|---|---|---|
| Mutable | WorkingComposition | 현재 draft, revision·base Snapshot 변경 가능 |
| Mutable | CompositionTrack | 이름·순서 변경, 명시적 삭제 가능 |
| Mutable | CompositionClip | 위치·source range 변경, split·삭제 가능 |
| Frontend ephemeral | 선택·hover·drag preview·Undo/Redo stack | canonical persistence가 아님 |
| Immutable | CompositionSnapshot | 새 identity로만 commit |
| Immutable | SnapshotItem | 기존 membership/projection, update/delete/reorder 금지 |
| Immutable | SnapshotTrack·SnapshotClip | commit 시 frozen arrangement representation |
| Immutable identity | AssetVersion·Artifact | 기존 정책 유지; 편집으로 payload를 변경하지 않음 |

Working edit는 `CompositionSnapshot`이나 `SnapshotItem`을 수정하지 않는다. Snapshot N을 열어 편집하고 commit하면 Snapshot N은 0건 변경되고 Snapshot N+1과 그 불변 arrangement rows가 새로 생긴다.

## 5. Identity and lineage

### 5.1 Track identity

`track_id`는 WorkingComposition과 그 Snapshot commit lineage에서 안정적이다. Snapshot copy는 `canonical_track_id` 값을 보존하지만 mutable Track row를 FK로 참조하지 않는다. 이렇게 해야 이후 Track 삭제·복원과 무관하게 과거 Snapshot이 독립적으로 재현된다.

### 5.2 Clip identity

move와 trim은 기존 `clip_id`를 유지한다. delete는 active working set에서 Clip reference만 제거하고 tombstone을 남긴다.

Split은 다음 정책을 사용한다.

```text
original clip: inactive tombstone
left clip:     new clip_id, split_from_clip_id = original clip_id
right clip:    new clip_id, split_from_clip_id = original clip_id
```

left가 기존 ID를 유지하지 않는다. 두 결과가 모두 원본을 대체한다는 대칭성과 lineage·undo 해석을 우선한다. `split_from_clip_id`는 immediate parent만 가리키며 root lineage는 필요할 때 반복 조회한다. 원본 payload를 실제로 둘로 자르지 않는다.

## 6. Editing semantics and invariants

모든 시간 범위는 반개구간이다.

```text
timeline_start >= 0
source_in >= 0
source_out > source_in
source_out <= source_duration
clip_duration = source_out - source_in
timeline_end = timeline_start + clip_duration
```

- **Move**: `timeline_start`만 변경한다. source range·AssetVersion·Artifact는 변경하지 않는다.
- **Trim start**: `source_in`과 `timeline_start`를 함께 변경해 선택한 source 구간의 Timeline 위치를 표현한다.
- **Trim end**: `source_out`만 변경한다.
- **Delete**: Clip reference만 inactive로 만든다. AssetVersion·Artifact·storage payload는 삭제하지 않는다.
- **Track reorder**: `track_order`를 충돌 없는 연속 값으로 한 transaction에서 재배치한다.

V1은 같은 Track의 active Clip overlap을 **DENY**한다. `[start, end)`에서 한 Clip의 `timeline_end ==` 다른 Clip의 `timeline_start`인 인접 배치는 허용한다. 다른 Track끼리의 시간 중첩은 허용한다. crossfade·layering이 구현되면 명시적 Mix policy와 함께 재검토한다.

Clip의 canonical 정렬은 `(timeline_start ASC, clip_id ASC)`다. 별도 `clip_order`나 `ordinal`은 만들지 않는다. Track 정렬에는 시간축으로 대체할 수 없는 `track_order`가 필요하다.

Working timeline duration은 active Clip의 `max(timeline_end)`로 계산하며 Clip이 없으면 0이다. 저장된 Master/Mix media duration이나 base Snapshot playback duration을 working duration authority로 사용하지 않는다.

## 7. Exact AssetVersion and Artifact boundary

Clip은 `source_asset_version_id`로 exact AssetVersion을 참조한다. latest/newest/selected Version fallback과 implicit replacement를 금지한다.

```text
CompositionClip
  └─ exact AssetVersion
       └─ eligible Artifact resolution
            └─ storage location (내부 경계)
```

Clip은 `artifact_id`, absolute path, storage key, locator, signed URL 또는 credential을 저장하지 않는다. 재생·Waveform·render용 payload 선택은 기존 AssetVersion→Artifact eligibility와 secure Resolver 경계를 거친다.

Clip 생성 전 Service는 exact AssetVersion의 활성 Asset, effective Owner, 대상 Workspace 또는 global Asset 허용, 대상 Project의 활성 `ProjectAsset`, audio eligibility와 immutable payload에서 검증된 duration을 확인한다. source media로 eligible한 Artifact가 정확히 하나로 해석되지 않으면 생성하지 않는다. 현재 AssetVersion이 Project에 직접 종속되지 않는 N:M 구조이므로 이 scope는 FK만으로 충분하지 않으며 Service 검증을 필수로 병행한다. 검증된 `source_duration`을 Clip에 고정해 DB 시간 CHECK와 이후 재현성을 유지한다.

Clip 편집은 source의 권리·승인·Training eligibility를 새로 부여하지 않는다. Snapshot commit은 exact source lineage를 보존한다.

## 8. Logical persistence schema

실제 SQLAlchemy·Alembic 이름은 구현 PR에서 repository naming convention과 SQLite migration 검증을 거쳐 확정하되 논리 구조는 다음과 같다.

### 8.1 Mutable tables

| Table | PK | 주요 FK·제약 | Index |
|---|---|---|---|
| `working_compositions` | `working_composition_id` | `project_id` UNIQUE → `music_projects`; `(project_id, base_composition_snapshot_id)` → 같은 Project Snapshot; bounded `mix_settings`; `revision >= 0` | unique `project_id`, `base_composition_snapshot_id` |
| `composition_tracks` | `track_id` | `working_composition_id` → WorkingComposition; UNIQUE `(working_composition_id, track_id)`; UNIQUE active `(working_composition_id, track_order)`; `track_order >= 0` | active order `(working_composition_id, deleted_at, track_order, track_id)` |
| `composition_clips` | `clip_id` | UNIQUE `(working_composition_id, clip_id)`; `(working_composition_id, track_id)` → same WorkingComposition Track; `source_asset_version_id` → AssetVersion; `(working_composition_id, split_from_clip_id)` → same WorkingComposition Clip RESTRICT; 시간 CHECK | active Timeline `(track_id, deleted_at, timeline_start, clip_id)`, source Version, split parent |

`composition_clips.working_composition_id`는 중복 정보가 아니라 cross-composition Track 연결을 DB에서 거부하기 위한 composite FK 구성 요소다. Track/Clip 삭제는 과거 Snapshot과 split lineage를 보존하도록 tombstone 처리한다. Project나 WorkingComposition의 파괴적 cascade는 V1 API에서 제공하지 않고 FK는 `RESTRICT`를 기본으로 한다.

### 8.2 Immutable snapshot extension

| Table | PK | 주요 값·FK·제약 | Index |
|---|---|---|---|
| `composition_snapshot_tracks` | `snapshot_track_id` | `composition_snapshot_id` → Snapshot RESTRICT, `canonical_track_id` opaque lineage, type·name·order frozen, UNIQUE `(snapshot_id, snapshot_track_id)`, UNIQUE `(snapshot_id, canonical_track_id)`, UNIQUE `(snapshot_id, track_order)` | `(snapshot_id, track_order, snapshot_track_id)` |
| `composition_snapshot_clips` | `snapshot_clip_id` | `composition_snapshot_id`와 `snapshot_track_id`의 composite FK → 같은 Snapshot Track RESTRICT, `canonical_clip_id` opaque lineage, exact AssetVersion FK RESTRICT, source/timeline range·source duration·split parent identity frozen, UNIQUE `(snapshot_id, canonical_clip_id)` | `(snapshot_track_id, timeline_start, snapshot_clip_id)`, source Version |

Snapshot Track/Clip은 mutable tables를 FK로 참조하지 않는다. canonical ID는 lineage 값으로 복사한다. Snapshot 안의 same-Track과 deterministic order는 snapshot-local FK·unique로 강제한다. 두 table은 update/delete API가 없고 Snapshot과 동일하게 `RESTRICT` 보존한다.

현재 `SnapshotItem`은 다음 이유로 Clip arrangement를 표현할 수 없다.

- canonical Track/Clip identity와 timeline/source range가 없다.
- 같은 AssetVersion·role을 한 Snapshot에서 여러 Clip으로 배치할 수 없는 unique 제약이 있다.
- `sort_order`는 membership projection일 뿐 Track order나 Clip position이 아니다.

따라서 다음 구현 전제는 필수다.

```text
COMPOSITION_SNAPSHOT_SCHEMA_EXTENSION_REQUIRED
```

`SnapshotItem`에 가변 Clip 의미를 덧씌우지 않고 별도 불변 Snapshot Track/Clip tables를 추가한다. 기존 SnapshotItem·D1 API는 호환성을 유지하며, versioned Composition read 계약이 새 arrangement projection을 명시적으로 추가한다.

## 9. Open, save, reload, rollback and commit

### 9.1 Open / checkout

```text
Immutable CompositionSnapshot N
  → explicit open/checkout
WorkingComposition(base_snapshot_id=N)
  → mutable Track / Clip edits
```

checkout은 Snapshot Track/Clip copy를 working rows로 원자적으로 복원한다. Snapshot에 canonical IDs가 있으면 그대로 복원하고, 기존 tombstone과 일치하면 재활성화한다. schema extension 전의 legacy Snapshot은 canonical arrangement가 없으므로 임의 Track/Clip을 합성하지 않고 `SNAPSHOT_ARRANGEMENT_NOT_AVAILABLE`로 실패한다.

### 9.2 Save and autosave

V1의 모든 성공한 mutation은 Service transaction에서 즉시 DB에 지속 저장된다. 따라서 refresh/reload는 서버의 동일 WorkingComposition과 revision을 복원한다.

- `Save`: 이미 승인된 mutation의 durable state를 확인하는 UX이며 새 Snapshot을 만들지 않는다.
- `Commit`: 새 불변 Snapshot을 만든다.
- `Ctrl+S`: 필요하면 pending UI command를 전송하고 server revision을 확인하지만 Snapshot commit으로 매핑하지 않는다.
- 별도 timer autosave나 Frontend/localStorage canonical draft는 V1에 없다. server write-through가 persistence authority다.

### 9.3 Rollback / revert

Revert는 `base_composition_snapshot_id`의 frozen arrangement로 working rows를 한 transaction에서 복원하고 revision을 1 증가시킨다. 부분 복원은 허용하지 않는다. base가 `null`이면 명시적 clear-to-empty만 가능하다.

### 9.4 Snapshot commit

```text
WorkingComposition at expected revision R
  → freeze active Tracks, Clips, exact AssetVersions, WorkingComposition mix settings
  → create CompositionSnapshot N+1 with new snapshot identity
  → create immutable SnapshotTrack / SnapshotClip rows
  → set Project explicit selection to N+1
  → set WorkingComposition base to N+1
  → revision R+1
```

이 전체는 하나의 Service-owned transaction이다. 기존 Snapshot N은 변경하지 않는다. commit mutation은 새 Snapshot 선택을 명시적으로 요청하는 동작이므로 ADR-035의 “Snapshot 생성이 selection을 암묵 변경하지 않는다”는 원칙과 충돌하지 않는다. 일반 Snapshot Resource POST는 계속 selection을 변경하지 않는다.

Commit은 audio render가 아니다. 편집에 맞는 새 Mix Artifact가 없으면 이전 Master/Mix를 새 Snapshot의 canonical playback source로 복사하지 않는다. 새 Snapshot의 committed playback은 `NO_CANONICAL_PLAYBACK_SOURCE`가 될 수 있으며 후속 render/export가 새 exact Mix AssetVersion을 만들 때 별도 Snapshot commit으로 연결한다.

## 10. Transactions and rollback

Router는 Session·ORM을 직접 변경하지 않는다. 기존 정책대로 Service가 transaction을 소유하고 Repository는 `flush()`만 수행하며 `commit()`/`rollback()`을 호출하지 않는다.

- split: 원본 inactive + left/right 생성 + overlap 검증 + revision 증가가 한 transaction
- trim/move/delete/reorder: validation + mutation + revision 증가가 한 transaction
- commit: Snapshot·SnapshotTrack·SnapshotClip·Idempotency 완료·selection·base·revision이 한 transaction
- checkout/revert: 전체 working state 교체와 revision 증가가 한 transaction

예외 또는 강제 실패 시 partial split, partial trim, partial commit, half-created Snapshot, selection만 변경된 상태를 0건으로 보장한다. Provider 호출·파일 I/O·audio render는 DB transaction 안에서 실행하지 않는다.

## 11. Idempotency and concurrency

모든 mutation은 `expected_revision`을 요구한다. 현재 revision과 다르면 어떤 row도 바꾸지 않고 `409 WORKING_COMPOSITION_REVISION_CONFLICT`로 실패한다. 성공한 mutation은 revision을 정확히 1 증가시키고 새 revision을 반환한다. 다중 사용자 collaboration/merge engine, lock server와 CRDT는 V1 범위가 아니다.

- move/trim/reorder PATCH는 최종 absolute 값을 보내며 의미상 idempotent다. 성공 응답을 잃고 이전 revision으로 재시도하면 409 후 GET/reconcile한다.
- split, delete, checkout/revert와 commit은 필수 `Idempotency-Key`를 사용한다.
- 기존 `idempotency_records`에 effective Owner·Project·WorkingComposition·operation·normalized body fingerprint를 scope로 포함한다.
- 같은 key·같은 요청은 최초 결과를 replay하고, 같은 key·다른 요청은 `IDEMPOTENCY_KEY_REUSED`로 거부한다.

`updated_at`만을 concurrency token으로 사용하거나 silent last-write-wins를 허용하지 않는다. ETag는 향후 revision의 HTTP 표현으로 추가할 수 있지만 별도 authority가 아니다.

## 12. Undo / redo ownership

V1은 hybrid가 아닌 **Frontend command/history stack + server resulting-state persistence**를 선택한다.

- Frontend는 성공한 product-only edit command와 inverse command를 memory에 보관한다.
- Undo/Redo도 새 `expected_revision`을 사용하는 정상 mutation으로 서버에 적용한다.
- refresh/reload 후 working state는 보존되지만 Undo/Redo history는 사라진다. V1에서 허용한다.
- 서버 `EditHistory` table, event sourcing, cross-device history 복구는 구현하지 않는다.
- split undo는 두 child를 inactive로 만들고 tombstone original을 복원하는 atomic product operation으로 구현한다.

`move_clip`, `trim_clip_start`, `trim_clip_end`, `split_clip`, `delete_clip`은 DohaMusic product-domain operation이다. Common Contract에 신규 `EditIntent`나 operation schema를 만들지 않는다. AI 편집은 기존 `MusicIntent`를 재사용하며 Common 확장은 실제 부족함이 입증된 뒤 별도 검토한다.

## 13. API boundary candidate

기존 Project namespace와 Service injection convention을 따르는 versioned product API 후보는 다음과 같다.

```text
GET    /api/v1/projects/{project_id}/working-composition
POST   /api/v1/projects/{project_id}/working-composition/checkout
PATCH  /api/v1/projects/{project_id}/working-composition/tracks/{track_id}
PATCH  /api/v1/projects/{project_id}/working-composition/clips/{clip_id}
POST   /api/v1/projects/{project_id}/working-composition/clips/{clip_id}/split
DELETE /api/v1/projects/{project_id}/working-composition/clips/{clip_id}
POST   /api/v1/projects/{project_id}/working-composition/revert
POST   /api/v1/projects/{project_id}/working-composition/commit
```

URL과 DTO의 최종 형태는 구현 PR의 OpenAPI 검토에서 확정한다. 공개 입력은 owner, path, storage locator, canonical ID override를 받지 않는다.

## 14. Playback and Waveform boundary

- **Committed playback**: 현재 GlobalPlayer가 명시적으로 선택된 Snapshot의 canonical Master/Mix Artifact를 재생한다.
- **Working composition preview**: Track/Clip 배치를 합성해야 하며 후속 multi-track preview/render engine의 책임이다. working edit persistence만으로 audio가 바뀌었다고 표시하지 않는다.
- **현재 Waveform**: committed Master/Mix Artifact의 overview다.
- **향후 Clip Waveform**: Clip의 exact source AssetVersion에서 eligible Artifact를 resolve하고 `[source_in, source_out)` 구간을 표시한다.

Master Waveform을 Track Clip Waveform으로 재사용하거나 working duration을 Master media duration으로 고정하지 않는다.

## 15. Future MIDI and Track types

canonical Track identity와 Clip의 generic timeline region 구조는 향후 `instrument`/`midi`, `vocal`, `bus` Track type을 추가할 수 있게 한다. V1 DB/API allowlist는 `audio`만 승인하며 MIDI note/event, Piano Roll, SoundFont, Instrument rendering과 Bus routing은 NOT IMPLEMENTED다.

MIDI source가 도입되면 exact AssetVersion이 versioned MIDI payload 또는 구조화 data를 가리키고 Clip range 단위가 음악 시간과 어떻게 매핑되는지 별도 ADR에서 결정한다. 현재 audio seconds 계약을 MIDI tick/beat에 추측 확장하지 않는다.

## 16. Security and rights

- Project·Workspace·effective Owner scope를 모든 mutation에서 검증하고 cross-Project Track·Clip·AssetVersion 연결을 fail-closed한다.
- Clip과 공개 DTO·로그에는 absolute path, storage key, signed URL, credential, token을 보관하지 않는다.
- AssetVersion·Artifact retention, consent, rights와 eligibility authority를 재사용한다.
- Clip edit와 Snapshot commit은 source 사용 권리나 Training 승인을 생성하지 않는다.
- Snapshot arrangement는 exact source AssetVersion과 canonical Clip lineage를 잃지 않는다.

## 17. Consequences

### 장점

- 불변 Snapshot을 훼손하지 않고 refresh 가능한 실제 편집 state를 제공한다.
- Track/Clip identity가 UI UUID나 snapshot-local projection에 종속되지 않는다.
- exact AssetVersion, split lineage, atomic commit과 optimistic concurrency로 재현성과 실패 안전성을 확보한다.
- V1 object 수를 세 개로 제한하고 event sourcing·collaboration engine을 연기한다.

### 비용과 후속 Gate

- mutable 3개와 immutable snapshot 2개 table, Alembic, Repository·Service·API 구현이 필요하다.
- exact source duration을 서버에서 검증하는 Artifact media metadata/probe 경계가 구현되어야 한다.
- 기존 Snapshot에는 arrangement가 없으므로 자동 합성 없이 명시적 unavailable/migration 정책이 필요하다.
- committed playback과 working preview가 분리되므로 multi-track preview/render 전에는 편집 결과를 즉시 들을 수 없다.
- refresh 뒤 Undo/Redo history는 복원되지 않는다.

## 18. Rejected alternatives

1. **SnapshotItem을 Clip으로 재사용**: identity·range가 없고 같은 source 반복 배치를 막는 unique 제약 때문에 제외한다.
2. **immutable Snapshot/SnapshotItem in-place mutation**: 과거 재현성과 D1 계약을 파괴하므로 금지한다.
3. **Frontend-only UUID를 canonical Clip으로 사용**: reload·권한·동시성·DB lineage authority가 없어 제외한다.
4. **localStorage를 WorkingComposition authority로 사용**: 서버 scope·rollback·다중 tab 충돌을 보장하지 못해 제외한다.
5. **latest AssetVersion fallback**: 재현성과 권리·Manifest 계보를 바꾸므로 금지한다.
6. **Artifact를 destructive trim**: 원본 불변성과 다른 Clip/Snapshot 참조를 파괴하므로 금지한다.
7. **split 시 binary payload 분할**: 편집 metadata만으로 가능한 작업에 파생 파일·권리·저장 비용을 만들므로 제외한다.
8. **Master Waveform을 Track/Clip Waveform으로 취급**: committed mix와 source region 의미가 달라 제외한다.
9. **left child가 원본 clip_id 유지**: split 결과 사이의 비대칭과 lineage 해석이 생겨 두 child 모두 새 identity 정책을 선택한다.
10. **같은 Track overlap 허용**: V1 render/mix policy가 없어 결과가 정의되지 않으므로 제외한다.
11. **server-persisted EditHistory/event sourcing**: V1 요구에 비해 schema·복구·동시성 비용이 커 제외한다.
12. **WorkingComposition 여러 개**: branch·merge·active draft 선택 authority가 추가되므로 V1에서는 Project당 하나로 제한한다.

## 19. Implementation order

1. Snapshot Track/Clip extension과 exact source duration 검증 경계
2. mutable WorkingComposition·Track·Clip schema와 isolated migration
3. Repository·Service transaction, revision·idempotency·rollback 테스트
4. product API와 OpenAPI/error contract
5. Frontend Clip Editing Foundation과 memory Undo/Redo
6. Track/Clip Waveform, working preview/render, Mixer
7. MIDI/Instrument editing은 별도 Track

## 20. Revisit conditions

- 여러 WorkingComposition branch나 collaborative editing이 제품 요구가 될 때
- 같은 Track overlap·crossfade·layering을 지원할 때
- refresh 뒤 Undo/Redo history 복원이 필요할 때
- MIDI tick/beat와 audio seconds의 공통 timebase가 필요할 때
- canonical Track/Clip identity를 Common Contract에 노출해야 하는 실제 Provider use case가 입증될 때
