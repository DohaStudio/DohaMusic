# Original Confirmation Canonical Payload 검증

> 상태: [검증 완료 — Foundation Draft 전용; 운영 미활성]
> 최종 수정일: 2026-09-19
> 구현 계약: [ADR-090](../11-decisions/ADR-090-original-confirmation-canonical-payload-foundation.md)

## Authority와 범위

#176은 START develop `3ae77bda08c3661a72d2f3c2052f027fc54b7db1`, H `f2293c9ed41903f256192e0667650c4a3629fbed`, T `ddaf74ae1a5a30bec2f224dde46279e8d3cbfe05`, exact-head run `35407667179` required 3 SUCCESS/reviews·threads 0/MERGEABLE·CLEAN에서 Ready 후 same Gate와 develop race 0을 확인해 expected-head squash merge했다. Merge/new BASE `034ca95a9173bf3a6f2950df93351c001214373c`이며 PR/merge/develop tree가 T와 같다. Source branch와 main/보호 PR을 보존했다.

선택 후보 C는 raw snapshot과 future authenticity verifier 사이 exact canonical payload boundary다. JCS exact bytes, strict field set/type/identifier, independently supplied expectation 및 existing held action/policy/designation binding만 제공한다. 서명 검증, verifier currentness, authentic human/source, admission은 미구현이다.

## 발견·수정과 검증

Oversize negative case의 원문 전체가 pytest parameter ID가 되어 Windows 임시 경로 한도를 넘었다. 짧은 명시 ID로 fixture path만 수정했다. 또한 expectation validator의 `isinstance(str)`가 hostile `str` subclass equality를 허용할 수 있는 점과 payload identifier 형식 검사가 valid expectation 불일치에만 의존한 점을 정적 재감사에서 발견했다. Exact built-in string Gate/callback 0 회귀와 payload 자체 UUID/digest/reference validation을 추가했다. 변경 전 direct/full 실행은 evidence에서 제외하고 최종 소스로 다시 시작했다. 입력/Gate/테스트를 삭제하거나 skip하지 않았다.

최종 source/test 고정 후 새 negative `40 passed`, focused 9 files `445 passed`, direct 19 files `871 passed`, full backend `2349 passed / 12 skipped / 0 failed`다. Ruff/format/compileall/diff/UTF-8/relative link/ADR·보호 범위/security scan은 PASS, Alembic은 `20260918_0037` single head다. Repository `commit()`/`rollback()`과 schema/migration/production port 변경은 0이다. 기존 Starlette/httpx deprecation warning 1개 외 새 warning은 없다.
