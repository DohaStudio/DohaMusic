# ADR-052 — WorkingComposition Preview Render Ownership Authority

> 상태: 승인
> 작성일: 2026-08-28
> 최종 수정일: 2026-08-28
> 관련 기능: AI-native DAW D3 Working Preview Backend Foundation
> 관련 문서: [WorkingComposition Service](../03-architecture/working-composition-service.md), [Workspace Job](../03-architecture/workspace-job-foundation.md), [Artifact Storage](../03-architecture/artifact-storage-contract.md), [Product API](../06-api/working-composition-api.md)

## 배경과 문제

WorkingComposition은 mutable 편집 authority지만 Preview worker가 실행 시점의 현재 row를 다시 읽으면 요청 revision과 다른 결과가 생긴다. Preview output을 기존 Artifact content API로 안전하게 재생하려면 `artifacts.asset_version_id NOT NULL`도 유지해야 한다. 반면 Preview는 Composition commit, current selection, canonical history와 Export가 아니다.

## 결정

1. Preview는 명시적 `POST .../working-composition/preview`가 만드는 async `working_preview` Workspace Job이다. 일반 Job create로 이 type을 만들 수 없다.
2. 생성 transaction은 `expected_revision`을 CAS 전제처럼 검증하되 WorkingComposition revision을 변경하지 않고, ordered Track·Clip, integer microseconds geometry와 현재 eligible한 exact Artifact ID를 전용 durable manifest에 고정한다. Worker는 WorkingComposition을 다시 읽지 않는다.
3. Project마다 하나의 non-canonical Preview Asset을 `working_preview_assets`로 소유한다. Common `AssetType`은 변경하지 않고 물리 audio 분류로 기존 `MIX`를 사용한다. 전용 binding이 Preview 의미와 Project 범위를 소유하므로 일반 `ProjectAsset` 목록과 canonical selection에는 넣지 않는다.
4. 같은 revision의 새 explicit action은 새 Job을 허용한다. 같은 Idempotency-Key와 fingerprint는 최초 Job과 결과를 replay하고 다른 fingerprint는 conflict다. fingerprint는 Project, WorkingComposition ID와 expected revision을 포함한다.
5. 성공 render마다 같은 Preview Asset 아래 새 immutable AssetVersion을 만든다. `WorkingPreviewRender.preview_asset_version_id`가 Job, WorkingComposition ID와 rendered revision provenance를 연결한다. name·description·임의 JSON parsing으로 revision을 추정하지 않는다.
6. output은 PCM16 stereo 48 kHz WAV Artifact이며 `asset_version_id`는 항상 NOT NULL이다. `JobOutput.output_role=working_preview`와 exact Artifact ID를 기록하고 기존 `/api/v1/artifacts/{artifact_id}/content` owner·retention·integrity gate를 사용한다.
7. AssetVersion은 render 성공 뒤 생성한다. AssetVersion, trusted Artifact/Catalog, PreviewRender 연결, JobOutput과 `running → succeeded`는 claim-owned transaction 하나로 확정한다. publish 뒤 DB 실패는 ingestion compensation 대상이며 실패·cancel·timeout에는 빈 AssetVersion을 남기지 않는다.
8. Preview payload TTL은 24시간이다. due scan은 Artifact를 `active → expired`로 바꿔 content를 fail-closed하고, Preview Asset·AssetVersion·manifest provenance는 유지한다. 물리 삭제는 기존 Artifact retention/GC 운영 경계가 담당하며 public delete를 추가하지 않는다.
9. 현재 WorkingComposition revision이 `C`이고 manifest의 `rendered_revision=R`일 때 `R != C`는 stale다. 기존 Preview AssetVersion을 mutation하지 않는다.
10. renderer V1의 최대 64 Tracks, 512 Clips, 30분, input Artifact당 128 MiB, output 384 MiB, 300초 timeout은 유지한다. WAV·FLAC·trusted MP3 decode, trim, static Gain, [ADR-054](ADR-054-clip-fade-authority.md)의 linear Fade, timeline offset, silence, cross-Track overlap과 deterministic mix를 지원한다. Pan·Mute·Solo·automation·loop·mastering·Export codec은 지원하지 않는다.
11. FFmpeg는 runtime-owned random temp, argument list와 `shell=False`만 사용한다. caller path·URL은 받지 않고 owner·retention·checksum 검증을 통과한 exact Artifact stream만 random temp로 복사한다. 성공·실패·timeout·cancel 모두 temp와 subprocess를 정리한다.
12. cancel은 existing Job marker와 claim ownership을 사용한다. retry는 failed/cancelled 원본의 immutable manifest를 새 Job/PreviewRender로 복제하며 성공하면 새 AssetVersion을 만든다. 기존 결과를 덮어쓰지 않는다.
13. Preview 성공은 CompositionSnapshot, SnapshotTrack/Clip, WorkingComposition revision/base, Project current selection, canonical AssetVersion과 final Export lineage를 변경하지 않는다.

## 선택 이유와 대안

Project당 Preview Asset 하나는 render마다 Asset row를 만드는 방식보다 row 증가를 제한하면서 AssetVersion 불변 이력을 보존한다. Artifact FK를 nullable로 만들거나 별도 PreviewPayload storage를 도입하는 대안은 기존 lineage/content authority를 깨므로 거부한다. fake CompositionSnapshot과 16개로 자른 JobInput은 manifest 손실 또는 canonical history 오염 때문에 거부한다. 기존 `mix` Job과 `DefaultAudioMixer`는 Snapshot 필수·2-input 동기 WAV 계약이라 arbitrary Clip timeline을 표현하지 못해 재사용하지 않는다.

## 영향과 migration

additive Alembic `20260828_0024`가 `working_preview_assets`, `working_preview_renders`, `working_preview_render_tracks`, `working_preview_render_clips`를 추가한다. backfill, Artifact 변경, Common Contract·Provider 변경과 실제 사용자 DB 적용은 없다. 일반 Asset/ProjectAsset Product projection은 Preview Asset을 노출하지 않는다.

## 장단점

장점은 revision-pinned 재현성, exact Artifact revocation gate, NOT NULL lineage, 원자적 성공과 stale 판정이다. 단점은 manifest·Preview provenance row와 FFmpeg 운영 의존성, payload 만료 scan이 추가되는 것이다. background daemon/scheduler activation과 Frontend 소비는 별도 통합 작업이다.

## 재검토 조건

- object storage가 Artifact TTL과 physical GC를 authoritative하게 제공할 때
- Mixer/automation 계약이 Preview renderer V1 geometry를 대체할 때
- distributed worker concurrency와 lease activation을 운영 배포할 때
- Preview를 user deliverable 또는 Export lineage로 승격해야 할 때

## 관련 PR

Draft PR 생성 후 번호를 기록한다.
