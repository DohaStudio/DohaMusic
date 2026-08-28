# Workspace DB Migration Preflight 체크리스트

> 문서 상태: [역사 기준 + 재사용 체크리스트]
> 최종 수정일: 2026-08-25
> 관련 기능: additive SQLite Migration 적용 전 Gate
> 구현 상태: `20260806_0012` 최초 적용용 원형이며 source는 `20260825_0022`, 실제 사용자 DB는 `20260810_0017`; 다음 Migration은 새 실행 기록에서 재검증 필요
> 관련 문서: [적용 Runbook](workspace-db-migration-runbook.md), [Backup·Rollback 정책](workspace-db-backup-rollback-policy.md)

아래 빈 체크 표시는 현재 DB 상태가 아니라 최초 `20260806_0012` 실행 전 재사용 Template입니다. 실제 증거는 revision별 Validation Report에서 보존하며, 다음 Migration도 새 실행 기록에서만 체크합니다. 문서 생성이나 fixture 테스트만으로 사용자 DB 항목을 완료 처리하지 않습니다.

코드 기준선에서는 Runtime·Alembic online SQLite 연결의 FK 활성화와 startup 자동 Migration 기본 비활성화를 구현했습니다. source head는 `20260828_0024`, 실제 사용자 DB는 `20260810_0017`이며 대상 DB의 actual revision과 backup·rehearsal Gate를 새로 확인해야 합니다. 아래 Template의 체크 표시는 특정 실행 결과를 대신하지 않으므로 비워 둡니다.

## Gate A — 대상과 승인

- [ ] 사용자 DB read-only 접근 승인을 받았다.
- [ ] `DATABASE_URL`, 기본 경로, 실행 작업 디렉터리를 비교했다.
- [ ] 테스트·benchmark DB가 아닌 사용자 DB임을 확인했다.
- [ ] 경로를 `D:/.../dohamusic.db` 형태로 마스킹했다.
- [ ] 앱·Worker와 예약 작업을 완전히 중지했다.

## Gate B — Read-only Inventory

- [ ] 파일 존재·크기·SHA-256을 기록했다.
- [ ] SQLite version, `application_id`, `user_version`을 기록했다.
- [ ] Alembic current가 `20260801_0011`이다.
- [ ] Runtime Table 14개가 모두 존재한다.
- [ ] Workspace Table 21개가 모두 존재하지 않는다.
- [ ] Table별 row count를 기록했다.
- [ ] `integrity_check = ok`이다.
- [ ] `quick_check = ok`이다.
- [ ] `foreign_key_check` 위반이 0건이다.
- [ ] WAL·SHM 존재 여부와 `journal_mode`를 기록했다.
- [ ] `foreign_keys`, `synchronous`, `busy_timeout`을 기록했다.

## Gate C — Schema Drift

- [ ] 누락·추가 Table과 Column을 비교했다.
- [ ] FK와 명시적 Index를 비교했다.
- [ ] `pipeline_jobs.input_snapshot` nullable drift를 WARNING으로 기록했다.
- [ ] 수동 변경 흔적을 검토했다.
- [ ] 자동 수정하지 않았다.
- [ ] BLOCKER가 0건이다.

## Gate D — Backup

- [ ] backup 생성 승인을 받았다.
- [ ] SQLite backup API를 사용했다.
- [ ] timestamp 이름으로 새 파일을 만들었다.
- [ ] 기존 backup을 overwrite하지 않았다.
- [ ] backup 파일 크기와 SHA-256을 기록했다.
- [ ] backup의 revision과 Table 수를 확인했다.
- [ ] backup `integrity_check = ok`이다.
- [ ] backup 복사본 restore rehearsal을 통과했다.

## Gate E — 적용 가능성

- [ ] DB 파일 쓰기 가능성을 확인했다.
- [ ] DB 크기의 3배와 100 MiB 중 큰 값 이상의 여유 공간을 확인했다.
- [ ] 원본 DB에 열린 writer가 없다.
- [ ] WAL·SHM 상태를 SQLite backup API 기준으로 안전하게 처리했다.
- [ ] Runtime과 Alembic 연결 모두 `PRAGMA foreign_keys=ON`을 보장한다.
- [ ] 앱 시작 시 자동 `upgrade head`가 통제된 절차를 우회하지 않는다.
- [ ] 사용자의 최종 Migration 적용 승인을 받았다.

## Gate F — 적용 후

- [ ] Alembic current가 `20260806_0012`이다.
- [ ] 적용 전 application Table 35개, 적용 후 Catalog를 포함한 36개인지 확인한다.
- [ ] Workspace Table 21개와 Runtime Table 14개가 모두 존재한다.
- [ ] 기존 Runtime row count가 보존되었다.
- [ ] `foreign_key_check` 위반이 0건이다.
- [ ] `integrity_check`와 `quick_check`가 `ok`이다.
- [ ] 최소 smoke와 앱 health가 정상이다.
- [ ] checksum·revision·검증·승인 결과를 기록했다.

## 즉시 중단 기준

어느 Gate에서든 실패하면 앱을 재시작하거나 다음 단계로 넘어가지 않습니다. 실패 DB와 검증된 backup을 모두 보존하고 [Rollback 정책](workspace-db-backup-rollback-policy.md)에 따라 복구 방향을 다시 승인받습니다.
