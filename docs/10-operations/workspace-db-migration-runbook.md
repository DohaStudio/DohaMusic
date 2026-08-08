# Workspace DB Migration 적용 Runbook

> 문서 상태: [역사 기준 + 재사용 Runbook]
> 최종 수정일: 2026-08-08
> 관련 기능: SQLite 사용자 DB additive Migration 승인 절차
> 구현 상태: `20260801_0011 → 20260806_0012` 원형 절차와 후속 `20260808_0015`까지 실제 적용 완료; 다음 revision은 대상·checksum·Gate를 새 실행 기록으로 갱신해야 함
> 관련 문서: [Preflight 체크리스트](workspace-db-preflight-checklist.md), [Backup·Rollback 정책](workspace-db-backup-rollback-policy.md), [Migration 전략](../07-database/database-redesign-migration-strategy.md), [Preflight 검증](../../reports/validation/VALIDATION-WORKSPACE-DB-MIGRATION-PREFLIGHT.md), [SQLite 안전 제어 검증](../../reports/validation/VALIDATION-SQLITE-MIGRATION-SAFETY.md)

## 1. 목적과 강제 중단 조건

이 Runbook 본문은 `20260801_0011`에서 `20260806_0012`로 올린 최초 적용 절차의 역사 기준입니다. 현재 소스와 실제 사용자 DB는 `20260808_0015`이며, 아래 revision·checksum 예시는 새 Migration에 그대로 재사용하지 않습니다. 다음 적용은 별도 Inventory·backup·rehearsal·사용자 승인 기록에서 대상 revision과 모든 Gate를 다시 확정합니다.

다음 중 하나라도 충족하면 적용을 시작하거나 계속하지 않습니다.

- 원본 DB의 명시적 읽기 승인이 없음
- 앱·Worker가 실행 중이거나 쓰기를 완전히 차단하지 못함
- 검증된 backup과 checksum이 없음
- `integrity_check` 또는 `quick_check`가 `ok`가 아님
- `foreign_key_check` 위반이 1건 이상임
- 현재 revision이 `20260801_0011`이 아님
- Runtime Table 14개가 누락되었거나 Workspace Table이 이미 일부 존재함
- schema drift BLOCKER가 1건 이상임
- DB 파일 쓰기 권한 또는 필요한 여유 공간을 확인하지 못함
- 승인된 적용 실행에서 Alembic 연결의 `PRAGMA foreign_keys=ON` 증거를 확보하지 못함
- 사용자의 최종 적용 승인이 없음

## 2. DB 위치 결정 방식

Runtime은 `Settings.database_url`을 사용합니다. `DATABASE_URL` 환경 변수가 있으면 해당 값을 사용하고, 없으면 `sqlite:///./backend/storage/doha_music.db`를 사용합니다. 상대 경로는 프로세스의 현재 작업 디렉터리에 따라 달라지므로 기본 문자열만 보고 실제 파일을 단정하면 안 됩니다.

Alembic CLI의 기본 URL도 `backend/alembic.ini`의 같은 상대 문자열입니다. 앱은 `DOHAMUSIC_AUTO_MIGRATE=true`를 명시한 경우에만 `upgrade_database()`에 Runtime의 `DATABASE_URL`을 전달합니다. 기본값 `false`에서는 DB revision을 읽거나 schema를 변경하지 않고 수동 preflight가 필요하다는 경고만 남깁니다. 따라서 다음 순서로 하나의 대상 파일을 확정해야 합니다.

1. 앱 시작 명령과 작업 디렉터리를 기록합니다.
2. 비밀값을 출력하지 않는 방식으로 `DATABASE_URL` 설정 여부를 확인합니다.
3. SQLite URL을 정규화해 실제 파일 하나를 식별합니다.
4. 보고서에는 `D:/.../dohamusic.db`처럼 중간 경로를 마스킹합니다.
5. 테스트 DB, benchmark DB와 사용자 DB를 파일 식별자·크기·revision으로 구분합니다.

앱 startup의 자동 Migration은 기본 비활성화입니다. 임시·테스트 DB 외에는 `DOHAMUSIC_AUTO_MIGRATE=true`를 사용하지 않으며, 사용자 DB의 현재 revision은 명시적 읽기 승인 후 `inventory`로 확인합니다. 현재 revision이 기대값 `20260801_0011`과 다르면 자동 변경하지 않고 적용을 중단합니다. 자동 Migration 비활성화 로그에는 DB URL이나 절대 경로를 포함하지 않습니다.

## 3. 승인 전 계획 확인

다음 명령은 DB를 열거나 파일을 만들지 않고 backup 예상 위치만 마스킹해 출력합니다.

```powershell
python -m backend.scripts.workspace_db_preflight plan-backup `
  --database "<사용자 승인 후 확정할 DB 경로>" `
  --backup-root "<DOHA_ARTIFACT_ROOT>/music/database-backups"
```

실제 경로를 shell history, PR, Issue 또는 일반 로그에 붙여 넣지 않습니다.

## 4. 단계별 적용 절차

| 단계 | 작업 | 통과 기준 | 중단 조건 |
|---:|---|---|---|
| 1 | 앱·Worker 종료 및 쓰기 차단 | DB를 사용하는 프로세스 0개 | 종료 여부 불명확 |
| 2 | 대상 DB 식별 | Runtime과 Alembic 대상이 같은 파일 | 경로 불일치 |
| 3 | 사용자에게 read-only Inventory 승인 요청 | 명시적 승인 기록 | 승인 없음 |
| 4 | read-only Inventory 실행 | 원본 checksum과 상태 기록 | 도구 오류 또는 경로 노출 |
| 5 | `integrity_check`·`quick_check` 확인 | 모두 `ok` | 다른 결과 |
| 6 | `foreign_key_check` 확인 | 위반 0건 | 위반 존재 |
| 7 | revision·Table 확인 | `0011`, Runtime 14개, Workspace 0개 | 다른 상태 |
| 8 | schema drift 분류 | BLOCKER 0건 | 누락 Column·FK·Index 등 BLOCKER |
| 9 | WAL·SHM·PRAGMA·공간 확인 | 정책과 공간 기준 충족 | 미확인 또는 공간 부족 |
| 10 | SQLite backup API 실행 승인 | 별도 사용자 승인 | 승인 없음 |
| 11 | timestamp backup 생성 | 기존 파일 overwrite 없음 | 생성 실패 |
| 12 | backup 검증 | checksum·revision·Table·integrity 일치 | 하나라도 불일치 |
| 13 | backup 복사본 dry-run | 복사본만 `0012`, 35개 Table | 원본 사용 또는 실패 |
| 14 | 최종 적용 승인 요청 | 사용자 명시적 승인 | 승인 없음 |
| 15 | Alembic 연결의 FK 활성화 확인 | `PRAGMA foreign_keys=1` | 0 또는 미확인 |
| 16 | `upgrade 20260806_0012` 실행 | 단일 transaction 범위 정상 종료 | 예외·부분 실패 |
| 17 | 적용 후 schema 검증 | revision `0012`, 전체 35개 Table | 누락·초과 |
| 18 | 무결성 재검증 | FK 위반 0, integrity `ok` | 위반 또는 오류 |
| 19 | 최소 read-only smoke | 기존 14개 Table row 수 보존 | 수량 감소·조회 실패 |
| 20 | `DOHAMUSIC_AUTO_MIGRATE=false`로 앱 재시작 | 자동 schema 변경 없음, 시작 로그와 health 정상 | 자동 추가 변경·오류 |
| 21 | 결과 기록 | checksum·revision·시각·검증 저장 | 기록 누락 |

## 5. Inventory 명령

다음 명령은 별도 승인 뒤 앱이 완전히 중지된 상태에서만 사용합니다. SQLite `mode=ro`와 `query_only`를 사용하며 schema·data 변경 기능은 없습니다.

```powershell
python -m backend.scripts.workspace_db_preflight inventory `
  --database "<승인된 DB 경로>" `
  --confirm-read-approved
```

출력은 경로를 마스킹하고 row 내용 대신 Table별 개수만 기록합니다. 개인 음성, 가사, Prompt 또는 동의 증적 원문을 출력하지 않습니다.

## 6. Backup 명령

다음 명령은 별도 backup 생성 승인과 `--confirm-create-backup`이 모두 있을 때만 사용합니다.

```powershell
python -m backend.scripts.workspace_db_preflight backup `
  --database "<승인된 DB 경로>" `
  --backup-root "<DOHA_ARTIFACT_ROOT>/music/database-backups" `
  --confirm-read-approved `
  --confirm-writers-stopped `
  --confirm-create-backup
```

이 도구는 SQLite backup API로 새 파일만 만들며 원본을 갱신하지 않습니다. backup 위치와 권한 정책은 [Backup·Rollback 정책](workspace-db-backup-rollback-policy.md)을 따릅니다.

## 7. 실제 적용 명령의 보관 원칙

실제 Alembic 명령은 1~15단계를 통과하고 사용자가 승인한 실행 기록에서만 구성합니다. 문서의 기본 `alembic.ini` 경로에 의존하지 않고, 승인된 DB URL을 해당 실행의 Alembic 설정에 명시해야 합니다. `head` 대신 목표 `20260806_0012`를 고정합니다.

Alembic online 연결은 공통 SQLite helper로 연결마다 `PRAGMA foreign_keys=ON`을 설정하고 값이 `1`인지 확인합니다. offline SQL 모드는 실제 연결이 없으므로 PRAGMA를 실행하지 않습니다. 실제 목표 구간 `0011 → 0012`는 FK를 끄지 않습니다. 과거 `0009 → 0010` batch backfill 회귀 테스트에는 별도의 내부 호환 플래그가 필요하지만 이 Runbook의 실제 적용 설정에는 사용하지 않습니다. 구현 검증은 임시 DB에서만 완료했으며, 15단계는 승인된 실제 적용 실행에서 증거를 다시 확보해야 합니다.

## 8. 적용 후 기록

`DohaArtifacts/music/runs/database-migration/` 또는 승인된 운영 기록 위치에 다음 값을 저장합니다.

- 실행 ID와 UTC 시각
- 마스킹된 DB 식별자
- 적용 전·backup·적용 후 SHA-256
- 적용 전후 Alembic revision과 Table 수
- integrity·quick·foreign key 검사 결과
- WAL·SHM와 PRAGMA 상태
- 실행자 승인과 사용자 승인 식별자
- 성공·중단 단계와 안전한 오류 코드

원본 절대 경로, DB 파일, row 내용과 개인정보는 Git에 기록하지 않습니다.
