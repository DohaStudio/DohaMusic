# Original Confirmation Raw Snapshot 검증

> 상태: [검증 완료 — Foundation Draft 전용; 운영 미활성]
> 최종 수정일: 2026-09-19
> 구현 계약: [ADR-089](../11-decisions/ADR-089-original-confirmation-raw-snapshot-foundation.md)

## #175 Final Validation·새 authority

START develop `655985b3432d4949ecae6d27e33ef8afb699c227`, H `03117f14e27654b9203ebb1520ef62aded9eee91`, T `b60c60286f94e62f9f26809e7ff0d2914da9c41b`. Remote/local/PR H/T 일치, clean worktree, OPEN/Draft/base develop, blocking reviews·REQUEST_CHANGES·unresolved threads 0/MERGEABLE·CLEAN을 재확인했다. Exact-head run `35403752359` required backend-ubuntu/ffmpeg-windows/frontend-playwright 모두 COMPLETED/SUCCESS였다. 구현 재감사에서 comparison != authentication/currentness/admission 및 strict type/history/terminal/replay/manifest/stale predecessor 경계를 유지했다.

Draft → Ready 후 same D/H/T/CI/reviews/threads/mergeability를 재확인하고 merge 직전 develop race 0에서 expected-head guarded squash merge했다. #175 MERGED, merge SHA/fixed BASE `3ae77bda08c3661a72d2f3c2052f027fc54b7db1`, PR tree = merge/develop tree = T. Source branch H/main/보호 PR을 보존했고 Final Validation 파일 수정 0이다.

## 선택·실행 범위와 한계

사용자 후보 C의 raw original-confirmation snapshot prerequisite를 구현했다. 실제 authentication verifier/signed wire/authoritative current-lineage reader/persistence/runtime/admission은 미구현이다. Original unsigned fixture를 raw bytes로 취급하고 authentication 성공으로 표시하지 않는다. Constructor policy/digest/public ACTIVE history로 provenance/currentness를 추정하거나 witness를 mint하지 않는다. Existing lease/pin/designation/custody/native snapshot 및 strict comparison에 necessary live binding을 더할 뿐 다른 Gate를 대체하지 않는다.

## 발견·직접 재현·최소 수정

1. 새 composition이 action exact-type validation 전에 equality를 호출하여 hostile `__eq__`가 1회 실행됨: minimal regression FAIL 후 action digest/strict validation을 비교 전에 실행, custom callback 0을 검증했다.
2. 기존 transport CloseHandle이 OSError를 던지면 `_snapshot`이 quarantine을 보존하지 못함: minimal regression FAIL(`quarantine == []`) 후 `_close`가 native exception을 safe denial로 정규화하고 list ownership을 유지하도록 수정했다.
3. Quarantine가 남아도 native transport가 새 snapshot을 yield함: minimal regression 2 FAIL 후 verified cleanup까지 새 `_snapshot` 초기 deny를 추가했다. Retry failure에서 retained list 유지, actual close 성공 뒤 quarantine 비움을 검증했다.
4. Public frozen lineage 객체를 `object.__setattr__`로 제자리 변경하면 original registry의 같은 객체도 바뀌어 anchor 재연결을 허용함: regression FAIL(DID NOT RAISE) 후 anchor/installation/source/statuses/전체 action digest의 immutable primitive tuple을 최초 open 시 별도로 저장했다. Fresh tuple을 그 원래 값과 대조하며 anchor와 old value를 복원해도 original handle을 재사용하지 못한다. 변경 전 full 실행은 중단하고 최종 소스로 전체 검증을 다시 시작했다.

Windows writable mapping 테스트의 초기 after-read 기대는 실제로 sharing-denied open에서 실패했다. Root cause에 따라 기존 sharing Gate를 보존한 before-handoff denial + mapping 제거/bytes 복원 후 old lease reuse denial 테스트로 정정했다. Same-size byte 변조를 실제 관측하는 injected ReadFile response는 별도 테스트하며 API 복원 후 handle reuse denial을 확인했다. 테스트 삭제/skip/Gate 완화는 0이다.

## 검증 결과

Final source/test 고정 후 focused 8 files `405 passed`, direct 18 files `831 passed`, full backend `2309 passed / 12 skipped / 0 failed`다. Ruff/format/compileall/diff/UTF-8/문서 링크/보호 범위 검사는 PASS, Alembic은 `20260918_0037` single head다. Repository `commit()`/`rollback()` 호출과 schema/migration/production port 변경은 0이다. 기존 Starlette/httpx deprecation warning 1개 외 새 warning은 없다.

Native tests는 disposable files/ACLs/OS lease/mapping/API injection만 사용한다. 실제 key/credential/governance/ceremony/user DB/Provider는 없다. Source authentication proof/actual policy CAS winner 1/crash recovery/operational 권한을 검증했다고 주장하지 않는다.
