# Windows Ceremony Serialization Foundation 검증

> 문서 상태: [로컬 Gate PASS — 운영 비활성, 별도 Draft]
> 작성일·최종 수정일: 2026-09-18
> 관련 문서: [ADR-082](../11-decisions/ADR-082-windows-ceremony-serialization-foundation.md), [ADR-081](../11-decisions/ADR-081-provider-witness-lifetime-foundation.md)

## #167 Final Validation / merge

- START develop `e45525e0c87656c8b5b6efc8986e5d2c925b48c6`.
- H `7cac6cfb8e72c6b1bf771038a77e4d3d644115a4`; T `7425d21eccbc9b401960c5450f149f9d46eb829a`.
- run `35353625051`, exact H required backend-ubuntu/ffmpeg-windows/frontend-playwright 모두 COMPLETED/SUCCESS, steps > 0.
- OPEN/Draft/develop base/local=remote=PR H/T/clean, reviews/REQUEST_CHANGES/threads 0, MERGEABLE/CLEAN, Alembic single head 0037를 확인했다. source/test와 ADR-075/076/077/078/080/081을 대조했다.
- Ready 직후 H/develop/base/CI/reviews/CLEAN 재확인 후 expected-head SQUASH MERGE. source 삭제 0.
- MERGED SHA/new BASE `2af6f7e8de7f42ea7f1758924bafcdcb25ddf56f`, merge tree = T. source H/main 보존.
- 기존 #167 focused 82/direct 474/full 1986 passed/12 skipped/0 failed evidence는 변경 없는 H/T에만 적용했다. 새 unit evidence와 혼합하지 않는다.

## 구현·재현·자체 수정

- Windows Global kernel mutex, complete sorted scope mechanics, original provider/thread/process/SessionTransaction identity, non-recursive acquire, partial cleanup, fail-closed unsupported/busy/namespace collision/abandonment.
- scope/savepoint/조기 release 거절 후 lease 재활성화: **3 failed** 재현 → permanent invalid + witness abandon. transaction active 시 lock은 계속 유지한다.
- partial cleanup failure 후 reservation 소실 및 CloseHandle failure 후 이중 ReleaseMutex: **2 failed** 재현 → handle ownership 상태/cleanup quarantine/reservation 보존, close-only retry.
- 최초 sandbox process pipe 3개 PermissionError는 platform 테스트의 sandbox 제약이었다. isolated test-only process/resources를 승인된 실행 환경에서 재실행했다. test 삭제/skip/assert 완화/production fallback 없음.
- 최종 source 변경 전 direct/full 실행은 새 Gate 증거로 사용하지 않는다. full은 작업이 만든 exact PID/commandline을 확인하여 중단 후 최종 source로 새 temp에서 재시작했다.

## 실제 검증 결과

- Focused: **112 passed / 0 skipped / 0 failed** (Windows serialization 30 + witness 82).
- Direct: **504 passed / 0 skipped / 0 failed**, 71.56초. witness/journal/crypto/Auth/Rights/Completion/Workspace migration/UoW를 포함한다.
- Full backend: **2016 passed / 12 skipped / 0 failed**, 970.43초. **2028 collected**와 수치 일치. source/test blob을 실행 전후 대조하여 변경 없음을 확인했다.
- 실제 process/process 경쟁 3회 각각 winner 1/denied 1, partial acquire cleanup, native object-type collision, process crash/WAIT_ABANDONED deny 및 fresh mechanical restart PASS.
- commit/rollback/close 뒤 old lease/witness deny, live transaction 조기 release 시 다른 process acquire deny, scope/custom equality/type confusion/forged provider/thread/duplicate acquire deny PASS.
- Repository/helper commit()/rollback()/flush()/SQL 0. caller-owned transaction 보존; 실제 app/user DB/migration 실행 0.
- frontend 변화 0, 새 로컬 E2E 불필요. 필수 frontend CI는 유지한다.
- compileall/Ruff check/Ruff format(489 files)/diff check/strict UTF-8/fences/conflict/439 relative links/82 unique indexed ADR/secret-local-path/authority consistency PASS. 기존 authority/ports/lifetime source/migrations/Phase DoD 변경 0.

## 경계·미수행·WARNING

실제 private readers/installation possession/provisioned pin/current HEAD history verification/durable admission/pin install은 구현·검증하지 않았다. OS acquisition/scope DTO/helper witness는 그 evidence가 아니다. production ports는 unconditional unavailable, production wiring/Fake fallback 0. 실제 OS ACL/custody/security descriptor deployment review는 후속이다. complete trusted manifest/current evidence verification 및 durable journal→pin crash는 PASS로 주장하지 않는다.

기존 frontend dependency advisory 6개(2 moderate/3 high/1 critical) 및 Python deprecation warning은 별도 maintenance 범위다. secret/source boundary 검증을 dependency audit 전체 PASS로 확대하지 않는다. hardware/privileged anti-clone/rollback 보장도 없다.
