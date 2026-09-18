# Designation Private Source Custody Policy Foundation 검증

> 상태: [로컬 Gate PASS; 별도 Draft 대상·운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 관련: [ADR-086](../11-decisions/ADR-086-designation-source-custody-policy-foundation.md)

## #172 Final Validation / merge

- START develop `bebf693fb41358abdddaf5d4110686323222cf2b`.
- H `26ed74b74fbec766a39c6d55c92db38f4e5d064d`, T `13bea1a7880fba555ee158aefccd3fbf28b26244`.
- exact-head run `35385985545`: backend-ubuntu/ffmpeg-windows/frontend-playwright COMPLETED/SUCCESS.
- OPEN/Draft/develop base/local=remote=PR H/T/clean/reviews·REQUEST_CHANGES·threads 0/MERGEABLE·CLEAN 확인. raw transport profile과 complete public binding을 full provenance authority codec로 오인하지 않는지 source/ADR-084/085를 직접 대조했다.
- sandbox의 default temp/Win32 IPC 거부로 첫 재실행 200 passed/6 failed/54 setup errors였다. test를 변경/skip하지 않고 isolated temp·approved Windows execution으로 focused 260 passed/0 skipped/0 failed, 5.84s를 재확인했다. 기존 direct 652/full 2164·12 skipped evidence는 #172 H/T에만 유지했다.
- Ready 후 same H/T/D/base/CI/reviews·threads 0/CLEAN을 재확인해 expected-head SQUASH MERGE했다. merge/new BASE `702eab36ecd56eac8f47e6664d06e94dde64d6a5`, merge tree = T, source H/main 보존.

## 새 implementation / 재현

C의 작은 직접 prerequisite인 independent expected root/record identity·explicit owner/SID/binary protected DACL의 same-handle policy comparison과 existing snapshot handoff revalidation이다. 전체 human provenance/current designation authority가 아니다. 독립 policy provisioning·initializer human 연결·designation eligibility source 및 full admission은 여전히 unavailable다.

- 새 cleanup exception regression: 1 passed/1 failed. LocalFree OSError 때 retained pointer를 잃는 결함을 재현했다. ownership pre-registration·confirmed success에만 제거하는 최소 수정으로 failure return/exception/retry 모두 retain했다.
- 최초 invalid-mask fixture는 기존 mask와 같은 byte를 쓴 테스트 작성 오류였다. 실제 unsupported generic mask bit로 교정했으며 assertion/Gate를 완화하지 않았다.
- 최종 focused native Windows: 301 passed / 0 skipped / 0 failed, 6.94s.
- Direct: 693 passed / 0 skipped / 0 failed, 66.78s.
- 새 full backend: 2205 passed / 12 skipped / 0 failed, 954.33s (15:54), native Windows. 기존 2164 결과를 새 source evidence로 재사용하지 않았다.
- Ruff check/format(backend 487 files, ai_worker 포함 498 files), compileall/diff/strict UTF-8/fences/relative links(464)/86 unique indexed ADRs/secret·local-path/protected authority audit PASS. 기존 Starlette TestClient deprecation warning 1개는 유지된다.
- Alembic `20260918_0037` single head, Repository commit()/rollback() 0, source/snapshot/pin/lifetime/OS helper SQL/flush/commit/rollback 0. 기존 authority/production ports/migrations/DoD 변경 0.

새 tests는 strict native primitives/ACL sizes/types/unknown ACE/flags/masks/broad SID, exact descriptor/file identity, source replacement/missing/hardlink/junction, source ACL 변경·복원/concurrent writer, unchanged native handle/currentness comparison, transaction 교체·permanent stale denial/native API failure/retained cleanup retry를 검증한다. shared process/crash/serialization/pin/snapshot regressions를 함께 실행한다. 두 관측 사이 privileged transient ACL restore의 완전 탐지/anti-rollback/provenance 자체를 검증했다고 주장하지 않는다.

SetFileSecurity는 disposable test root/record에만 사용하며 parents/real trust store/user file ACL은 수정하지 않는다. actual key/credential/designation/approval/ceremony/user DB/Provider 접근·발급 0. production ports unconditional unavailable·app migration 0/Alembic 0037/external journal v1·Phase/DoD 보존이다.

## #173 exact-head CI repair

- 최초 H `62a2d080793ab75cfa861b0c98b229f048d04160`, T `ab547b24d8db26b64f191ca9e7f4c16fce1c714f`, run `35391350201`: backend-ubuntu/frontend-playwright SUCCESS, ffmpeg-windows FAILURE. Ready/merge하지 않았다.
- Windows elevated runner의 default owner `S-1-5-32-544`를 fixture가 승인 계정 SID로 추론했다. production의 Administrators 거부는 올바르며 그대로 유지한다. fixture만 current process TokenUser를 선택하고 owner가 다를 때 임시 root/record owner를 설정한 뒤 owner/DACL을 확인한다. 실제 governance/provisioning ceremony가 아니다.
- 원래 H의 test source를 읽기 전용 historical mock replay로 재실행해 Administrators default owner → SourceCustodyPolicy 거부를 로컬 재현했다. replay의 실제 file/owner/DACL 변경은 0이다.
- 무조건 owner를 재설정하는 첫 수정은 로컬 WRITE_OWNER 부재로 focused 20 failed/281 passed 및 direct 20 failed/673 passed였다. 같은 owner에는 owner 변경 요청을 하지 않고 실제 owner 재조회로 확인하도록 최소 수정했다. assertion/negative case 삭제 또는 skip은 없다.
- default account/Administrators 두 경우의 selected-account provisioning 회귀를 추가했다. 수정 focused 303 passed/0 skipped/0 failed (7.04s), direct 695 passed/0 skipped/0 failed (67.54s), full backend 2207 passed/12 skipped/0 failed (909.88s, 15:09). 새 exact-head CI는 PR에서 별도로 확인하며 최초 H의 성공 job을 수정 H의 evidence로 사용하지 않는다.
- compileall/Ruff check/format(498 files)/diff PASS, Alembic `20260918_0037` single head. production source·SID policy·ports·migration 변경 0. temp owner/DACL 외 부모/실제 private store/user DB 접근 0.
