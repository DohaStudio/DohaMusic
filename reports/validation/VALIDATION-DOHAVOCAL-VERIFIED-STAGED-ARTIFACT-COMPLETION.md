# DohaVocal Verified Staged Artifact Completion Foundation 검증

> 기준: PR #156 contract head `60c95f066c77418518d45082b42629fdafee6254`
> 결정: ADR-069
> 검증일: 2026-09-17

## 구현 범위

- `VerifiedPayloadStagingPort.open_verified()` → `ArtifactIngestionService.prepare_verified_stream()` path-free handoff
- generation의 새 Vocal Asset·ProjectAsset·version 1
- conversion/correction의 source Vocal Asset 다음 immutable Version
- analysis의 exact source AssetVersion JSON Artifact
- Asset/Version, Artifact/StorageLocation, JobOutput, ModelUsage, locator `ingested`, Job `succeeded` 단일 transaction
- session-aware current rights·claim·cancel·revocation final gate
- cleanup 이후 staging I/O 없는 exact replay와 conflict fail-closed

## 경계 확인

- schema/Alembic: 변경 없음
- Alembic source head: `20260908_0032`
- Public API/Frontend: 변경 없음
- Worker/dispatcher/daemon: 변경 없음
- production rights/authentication adapter: 미구현
- PR #130 acquisition orchestration: 변경 없음
- `TrustedArtifactRegistrationService`와 `ExportPublicationLedger`: 사용하지 않음
- 실제 사용자 DB, production Artifact, Provider network, 실제 payload: 접근 없음

## 검증 항목

직접 테스트 26개는 네 Job type의 target/lineage, selection 불변, stream checksum·size·media mismatch,
Owner·Workspace·Project·Result·source binding, I/O 이후 rights loss, claim·cancel·locator·revocation gate,
여섯 transaction failure 지점의 rollback/compensation, replay, cleanup 후 replay, conflict와 concurrency를
검증한다.

## 로컬 검증 결과

- completion foundation 직접 테스트: `26 passed`
- cleanup 뒤 source Asset soft-delete replay 회귀 수정 확인: `1 passed`
- 전체 backend 수집: `1538` tests
- 24-way 격리 shard 실행: `1498 passed`, `6 skipped`, `34 failed`
  - completion replay 실패 1건은 target과 source가 같은 conversion/correction Asset tombstone 조회 누락으로
    확인했고 수정 후 직접 테스트에서 통과했다.
  - 기존 pipeline API의 5초 terminal-state timeout 20건은 직렬 재실행에서 모두 통과했다.
  - 기존 ffmpeg Export 경로 13건은 직렬 재실행에서도 실패했다. 이번 diff는
    `backend/audio`, Export worker/runner를 변경하지 않으며, 설치된 ffmpeg의 직접 MP3 인코딩은 성공했다.
    따라서 로컬 fixture/ffmpeg 호환 환경 문제로 분리하고 GitHub Actions 결과를 최종 gate로 사용한다.
- 병렬 실패 파일 직렬 재실행: `76 passed`, `1 skipped`, `13 failed`(위 ffmpeg 경로만 해당)
- `ruff check --no-cache backend ai_worker`: 통과
- `ruff format --check --no-cache backend ai_worker`: `437 files already formatted`
- `python -m compileall -q backend ai_worker`: 통과
- `git diff --check`: 통과
- 변경 파일 strict UTF-8 decode: 통과
- Alembic source head: `20260908_0032`

GitHub Actions 결과는 최종 commit 및 PR 본문에 추가 기록한다.
