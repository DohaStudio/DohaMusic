# Clip Domain / Persistence Design Definition of Done

> 문서 상태: [완료]
> 최종 수정일: 2026-08-21
> 관련 기능: AI-native DAW D3 Clip Editing 선행 설계
> 관련 문서: [ADR-040](../11-decisions/ADR-040-canonical-track-clip-working-composition-authority.md), [AI-native DAW DoD](AI-Native-DAW.md), [Master Roadmap](../../MASTER_ROADMAP.md)

이 문서는 Clip Editing 구현 완료가 아니라 구현을 시작하기 위한 Domain/Persistence 결정 완료를 판정한다. ORM·Alembic·API·Frontend·테스트는 모두 후속 범위다.

## 설계 결정 — [완료]

- [x] Project당 하나의 mutable WorkingComposition authority 결정
- [x] Composition lineage 범위의 canonical `track_id` 결정
- [x] move·trim에서 유지되고 split 시 두 새 ID로 대체되는 canonical `clip_id` 결정
- [x] exact `source_asset_version_id`와 AssetVersion→Artifact resolution 경계 결정
- [x] `timeline_start`, `source_in`, `source_out`, duration invariant와 exact persistence 단위 결정
- [x] WorkingComposition·Track·Clip mutable, CompositionSnapshot·SnapshotItem immutable 경계 결정
- [x] `base_composition_snapshot_id`, save/reload/revert와 explicit commit 의미 결정
- [x] 별도 immutable SnapshotTrack/SnapshotClip schema extension 필요성 결정
- [x] Service-owned transaction, atomic split·commit과 rollback 0건 기준 결정
- [x] 필수 revision optimistic concurrency와 mutation idempotency 정책 결정
- [x] Frontend memory Undo/Redo와 server resulting-state persistence 소유권 결정
- [x] same-Track overlap DENY와 derived working timeline duration 결정
- [x] committed playback·working preview, Master/Mix·Clip Waveform 경계 결정
- [x] product-only edit operation과 신규 Common Contract schema 0건 결정
- [x] future MIDI/Instrument 확장과 V1 audio-only eligibility 분리
- [x] path·storage locator·credential 비저장과 기존 rights authority 유지

## 구현 Gate — [미구현]

- [ ] mutable·immutable 5개 logical table의 SQLAlchemy/Alembic 구현
- [ ] exact source duration의 서버 검증 authority 구현
- [ ] Repository·Service·revision·idempotency·rollback 테스트
- [ ] WorkingComposition product API와 OpenAPI/error contract
- [ ] Frontend Clip move·trim·split·delete·Track reorder
- [ ] memory Undo/Redo command stack과 refresh recovery 검증
- [ ] Track/Clip Waveform과 working preview/render
- [ ] Draft PR 검토·Ready 전환·`develop` 병합

## 판정

`Clip Domain/Persistence Design`은 COMPLETE다. `Clip Editing Implementation`은 NEXT이며 구현 완료로 표시하지 않는다.
