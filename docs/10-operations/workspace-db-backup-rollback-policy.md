# Workspace DB Backup·Rollback 정책

> 문서 상태: [운영 기준]
> 최종 수정일: 2026-08-10
> 관련 기능: Workspace additive Migration의 원본 보존과 실패 복구
> 구현 상태: 실제 사용자 DB `20260806_0012`~`20260810_0017` 적용에서 backup·restore rehearsal 검증 완료; 자동 restore·downgrade 금지 유지
> 관련 문서: [적용 Runbook](workspace-db-migration-runbook.md), [Preflight 체크리스트](workspace-db-preflight-checklist.md)

## 1. 기본 원칙

- 원본 DB를 backup 대상으로 직접 overwrite하지 않습니다.
- Migration 직전에 timestamp가 포함된 새 backup을 만듭니다.
- 앱·Worker를 중지하고 SQLite backup API를 우선 사용합니다.
- 단순 파일 복사는 DB가 닫혀 있고 WAL·SHM 처리가 확인된 경우에만 사용합니다.
- backup 검증 완료 전 Migration을 실행하지 않습니다.
- 실패 DB와 backup DB를 모두 보존하며 자동 삭제하지 않습니다.
- DB·backup·검증 로그에는 개인 음성·가사·Prompt·동의 증적 원문을 남기지 않습니다.

## 2. 권장 위치와 이름

권장 root는 설정된 `DOHA_ARTIFACT_ROOT` 아래의 다음 위치입니다.

```text
DohaArtifacts/music/
├── database-backups/
└── runs/
    └── database-migration/
```

절대 경로를 코드에 하드코딩하지 않습니다. backup 파일명은 다음 규칙을 사용합니다.

```text
dohamusic-before-20260806-0012-YYYYMMDD-HHMMSS.sqlite3
```

DB 파일, WAL·SHM, backup과 Migration 실행 기록 원문은 Git에 포함하지 않습니다.

## 3. WAL 정책

WAL mode에서는 원본 DB 파일만 복사하면 최신 commit이 누락될 수 있습니다. 앱과 Worker를 먼저 중지하고 SQLite backup API가 일관된 snapshot을 생성하도록 합니다. 원본의 WAL·SHM 파일을 임의로 삭제하거나 `wal_checkpoint`를 강제 실행하지 않습니다.

단순 파일 복사가 필요한 예외 상황에서는 다음 조건을 모두 만족해야 합니다.

1. 모든 writer와 reader가 종료되었습니다.
2. SQLite가 DB를 정상적으로 닫았습니다.
3. WAL·SHM 상태와 journal mode를 기록했습니다.
4. 복사본의 `integrity_check`, revision과 Table 수를 검증했습니다.

## 4. Backup 검증

backup마다 다음 증거를 기록합니다.

- 파일 존재와 0보다 큰 크기
- SHA-256 checksum
- `integrity_check = ok`
- Alembic revision `20260801_0011`
- application Table 14개
- 원본과 동일한 Runtime Table별 row count
- 생성 UTC 시각과 승인 식별자

checksum은 무결성 식별자이며 암호화나 접근 통제를 대체하지 않습니다. backup root에는 사용자 계정 최소 권한과 별도 보존 기간을 적용합니다.

## 5. Rollback 우선순위

### 1순위 — 검증된 backup 복원

부분 실패, Alembic revision 불명확, schema drift 또는 적용 후 무결성 오류가 있으면 검증된 backup을 새 복구 파일로 복원하는 방식을 우선합니다. 실패 DB를 덮어쓰지 않고 별도 이름으로 보존합니다.

### 2순위 — `downgrade 20260801_0011`

다음 조건을 모두 만족할 때만 별도 승인으로 검토합니다.

- upgrade가 완전히 성공해 revision이 정확히 `20260806_0012`임
- 신규 Workspace Table에 보존해야 할 row가 없음
- downgrade SQL과 FK 순서를 검증한 임시 rehearsal이 있음
- backup 복원이 불가능하거나 downgrade가 더 안전하다는 근거가 있음
- 사용자가 데이터 손실 가능성을 승인함

자동 downgrade는 유일한 복구 수단이 아닙니다. 이번 작업에서는 실제 downgrade를 실행하지 않았습니다.

## 6. 부분 실패 처리

1. 앱·Worker를 계속 중지합니다.
2. 실패 DB, WAL·SHM과 로그를 보존합니다.
3. 추가 upgrade·downgrade·수동 SQL을 실행하지 않습니다.
4. revision, Table, integrity와 FK 상태를 read-only로 수집합니다.
5. backup checksum과 integrity를 다시 확인합니다.
6. backup 복원 또는 downgrade 중 하나를 별도 승인받습니다.
7. 복구본에서 smoke를 통과하기 전 앱을 재시작하지 않습니다.

## 7. 보존과 삭제

실패 DB와 Migration 전 backup의 삭제는 별도 보존 정책과 사용자 승인이 필요합니다. 개인 데이터 삭제 요청이 있는 경우에도 감사용 checksum과 실제 DB 내용의 보존을 동일시하지 않으며, 접근 권한·동의·삭제 정책을 우선 검토합니다.
