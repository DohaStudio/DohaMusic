# Private Pin Facts Reader Foundation 검증

> 상태: [로컬 Gate PASS; 별도 Draft 대상, 운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 관련: [ADR-083](../11-decisions/ADR-083-private-pin-facts-reader-foundation.md)

## #168 Final Validation

- START develop `2af6f7e8de7f42ea7f1758924bafcdcb25ddf56f`.
- H `bd0012f5572f6f032ff8be13bc626fe8eb72f7d3`, T `b6adbb3093bdcb7c4a062c3a60b8ccf55d9c867f`.
- run `35358771087`: exact H backend-ubuntu/ffmpeg-windows/frontend-playwright COMPLETED/SUCCESS, steps > 0. Windows native mechanics step SUCCESS.
- OPEN/Draft/develop/local=remote=PR H/T/clean/reviews·REQUEST_CHANGES·threads 0/MERGEABLE·CLEAN/Alembic single-head 0037 확인 후 Ready 전환; 직후 동일 Gate 재확인 후 expected-head SQUASH MERGE.
- MERGED SHA/new BASE `fb10bc9367835b0d4a39837287a358fe6b46a1be`; merge tree = T. source H 보존, main 변경 0. 기존 H/T evidence focused 112/direct 504/full 2016 passed·12 skipped를 유지했다.

## 구현과 재현·수정

- minimum independent-file transport/complete pin comparison이다. independent private custody/provenance/journal history/authoritative manifest/possession/currentness authority는 미구현이며 production unavailable다.
- malformed expectation(None/True/dict/object)을 I/O 전 거절할 때 기존 witness가 live인 결함을 native regression 4개로 재현했다. original lease를 먼저 bind하고 이후 검증 전부를 witness-finally 폐기 범위 안으로 옮겼다. 파일 수정·생성·SQL·공식 witness 발급은 reader에 없다.
- negative test wire serializer가 float 1.0을 JCS 정수로 바꾸거나 unsafe integer를 parser 전에 거절하던 harness를 보정했다. hostile wire를 실제 decoder까지 보내며 큰 입력 parameter ID도 bounded하게 했다.
- native stable handle/write·rename denial, ancestor junction, leaf hardlink, replacement-before-open, missing/malformed/stale/oversize, concurrent readers, partial/native read failure, retained close-failure handles/explicit cleanup, I/O 도중 caller transaction 교체를 검증한다. test fixture는 격리 disposable public facts와 placeholder witness mechanics만 사용한다. 실제 key/credential/approval/ceremony는 없다.
- Linux는 unsupported-platform denial과 pure codec을 검증한다. native Windows 테스트를 Linux 성공으로 대체하지 않으며 기존 ffmpeg-windows job에 새 두 test file을 추가했다.

## Gate

- final focused: 225 passed / 0 skipped / 0 failed (native Windows).
- direct: 617 passed / 0 skipped / 0 failed.
- full backend: 2129 passed / 12 skipped / 0 failed, 1052.45s (native Windows).
- Ruff/compileall/diff/strict UTF-8/Markdown fence·relative links/secret·path/authority audit PASS. 기존 Starlette deprecation warning은 별도 미해결 사항이다.
- migration 0, app Alembic `20260918_0037` single head/external journal v1. canonical ADR-075/076/077/078/080/081, original OS/lifetime/ports 및 Phase/DoD unchanged. 새 세 module의 execute/flush/commit/rollback calls 0.
- 새로운 Draft PR head/tree/CI metadata는 PR 본문에서 관리한다. 이 PR의 Ready/merge는 이번 범위가 아니다.
