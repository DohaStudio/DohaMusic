# ADR-071: Music Director Candidate materialization과 proposal publication

- 상태: 승인
- 작성일: 2026-09-12
- 최종 수정일: 2026-09-12

## 결정

- Candidate는 schema v1 JSON proposal만으로 유효하며 preview는 필수가 아니다.
- operation은 `set_clip_gain`, `set_track_gain`, `set_track_pan`, `set_master_gain`으로
  제한하고 immutable Snapshot target만 허용한다.
- canonical UTF-8 JSON의 SHA-256을 proposal digest와 Artifact checksum으로 사용한다.
- `20260911_0035` ledger가 Run, Candidate, Asset, AssetVersion, Artifact 계획 ID와
  deterministic storage identity를 physical write 전에 보존한다.
- publication은 `runs/music-director/...` identity와 publish-or-adopt를 사용한다.
- 모든 proposal이 `PUBLISHED`일 때 caller-owned transaction 하나로 전체 Candidate set을
  완료한다. Physical publication과 DB는 literal ACID가 아니라 recoverable authority다.
- exact replay는 같은 authority를 반환하고 mismatch는 overwrite 없이 fail closed한다.
- materialization row가 존재하는 downgrade는 recovery authority 보존을 위해 차단한다.

## 영향

WorkingComposition, Snapshot, history와 selected/applied pointer는 변경하지 않는다.
Provider Port, Mock Worker와 Project-scoped read·SELECT Public API는 구현됐다. Frontend, atomic APPLY와 실제 외부 Provider 연결은 후속 작업이다.
